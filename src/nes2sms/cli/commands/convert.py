"""Convert command: One-step full conversion pipeline."""

import json
from pathlib import Path
from typing import Optional

from ...infrastructure.rom_loader import RomLoader
from ...infrastructure.asset_writer import AssetWriter
from ...infrastructure.symbol_extractor import StaticSymbolExtractor
from ...infrastructure.wla_dx.stub_generator import StubGenerator
from ...infrastructure.disassembler import Da65Disassembler
from ...infrastructure.disassembler.native_disassembler import Native6502Disassembler
from ...core.graphics import TileConverter, PaletteMapper
from ...core.graphics.oam_extractor import OamExtractor
from ...core.graphics.palette_extractor import PaletteExtractor
from ...core.assembly.flow_aware_translator import FlowAwareTranslator
from ...shared.models import Symbol


def cmd_convert(args):
    """
    One-step NES to SMS conversion.

    Executes the full pipeline:
    1. Ingest ROM
    2. Analyze mapper
    3. Extract symbols
    4. Convert graphics
    5. Generate Z80 project
    6. Build SMS ROM (optional)
    """
    nes_path = Path(args.nes)
    if not nes_path.exists():
        raise FileNotFoundError(f"ROM not found: {nes_path}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[convert] Starting conversion: {nes_path.name}")
    print(f"[convert] Output directory: {out_dir}/")
    print()

    # Step 1: Ingest
    print("[1/6] Ingesting ROM...")
    loader = RomLoader()
    loader.load(nes_path)

    writer = AssetWriter(out_dir)
    writer.write_binary("prg.bin", loader.prg_data, "work")

    if loader.chr_data:
        writer.write_binary("chr.bin", loader.chr_data, "work")

    if loader.trainer_data:
        writer.write_binary("trainer.bin", loader.trainer_data, "work")

    print(
        f"      PRG: {len(loader.prg_data) // 1024}KB | CHR: {len(loader.chr_data) // 1024 if loader.chr_data else 0}KB"
    )
    print(f"      Mapper: {loader.header.mapper} | Mirroring: {loader.header.mirroring}")
    print()

    # Step 2: Extract symbols with disassembly
    print("[2/6] Extracting symbols and disassembling code...")
    symbols = []
    symbol_dict = {}

    if loader.prg_data:
        # Try da65 first, then fall back to native disassembler
        disassembler = Da65Disassembler()

        if disassembler.is_available():
            print("      Using da65 disassembler (external)...")
            extractor = StaticSymbolExtractor(
                loader.prg_data,
                disassembler=disassembler,
            )
        else:
            print("      da65 not found, using native Python disassembler...")
            native_disasm = Native6502Disassembler()
            extractor = StaticSymbolExtractor(
                loader.prg_data,
                disassembler=native_disasm,
            )

        symbols = extractor.extract()
        symbol_dict = extractor.to_dict()
        writer.write_json("symbols.json", symbol_dict, "work")
        print(f"      Found {len(symbols)} symbols")
        print(f"      Code ranges: {len(extractor.get_code_ranges())}")

        # Report if disassembly was successful
        if extractor.disassembly_db:
            print(f"      Disassembly: {len(extractor.disassembly_db.instructions)} instructions")
    print()

    # Step 3: Analyze mapper and generate bank map
    print("[3/6] Analyzing mapper...")
    bank_map = _analyze_mapper(loader)
    writer.write_json("banks.json", bank_map, "work")
    print(f"      PRG banks: {loader.header.prg_banks}")
    print(f"      Fixed bank: last")
    print()

    # Step 4: Convert graphics
    print("[4/6] Converting graphics...")
    if loader.chr_data:
        # Try to extract actual palette from PRG code
        nes_palette_ram = None
        if loader.prg_data:
            pal_extractor = PaletteExtractor(loader.prg_data)
            nes_palette_ram = pal_extractor.extract_palette()
            if nes_palette_ram:
                print("      Extracted palette from ROM PRG code")

        palette_mapper = PaletteMapper(nes_palette_ram=nes_palette_ram)
        bg_pal, spr_pal, color_maps = palette_mapper.build_all_palettes()

        tile_converter = TileConverter(
            color_maps=color_maps[:4],
            flip_strategy=args.flip_strategy if hasattr(args, "flip_strategy") else "cache",
        )

        # Check for multi-bank
        if bank_map.get("chr_banks", 1) > 1:
            chr_banks = _extract_chr_banks(loader.chr_data, bank_map)
            result = tile_converter.convert_multi_bank(chr_banks)
            print(f"      Multi-bank mode: {len(chr_banks)} banks")
        else:
            result = tile_converter.convert(loader.chr_data, bank_id=0)

        writer.write_palette(bg_pal, "bg")
        writer.write_palette(spr_pal, "spr")
        writer.write_tiles(result.sms_tiles)
        writer.write_flip_index(result.flip_index)
        writer.write_tile_symbols(result.tile_metadata, "assets")

        total_size = sum(len(t) for t in result.sms_tiles)
        print(f"      {len(result.sms_tiles)} tiles | {total_size // 1024}KB")
        print(f"      Palettes: palette_bg.bin + palette_spr.bin")
    print()

    # Step 4b: Extract OAM/sprite data
    oam_sprites = None
    if loader.prg_data and loader.chr_data:
        chr_tile_count = len(loader.chr_data) // 16
        oam_extractor = OamExtractor(loader.prg_data, chr_tile_count)
        oam_sprites = oam_extractor.extract_oam_table()
        if oam_sprites:
            print(f"[4b] Extracted {len(oam_sprites)} sprites from OAM data")
            y_table, xt_table = oam_extractor.to_sms_sat(oam_sprites)
            writer.write_binary("sat_y.bin", y_table, "assets")
            writer.write_binary("sat_xt.bin", xt_table, "assets")
            print()

    # Step 5: Generate Z80 stubs with translation
    print("[5/6] Generating Z80 stubs with translation...")

    try:
        # Convert symbols to proper format
        symbol_objects = []
        if loader.prg_data:
            for sym_data in symbol_dict.get("symbols", []):
                symbol_objects.append(
                    Symbol(
                        name=sym_data["name"],
                        address=int(sym_data["address"].replace("$", ""), 16),
                        bank=sym_data.get("bank", 0),
                        type=sym_data.get("type", "code"),
                        comment=sym_data.get("comment", ""),
                        disassembly_snippet=sym_data.get("disassembly_snippet"),
                        is_embedded=sym_data.get("is_embedded", False),
                    )
                )

        # Build symbol address map for label resolution
        symbol_address_map = {}
        for s in symbol_objects:
            symbol_address_map[s.address] = s.name

        # Use flow-aware translator with symbol map
        translator = FlowAwareTranslator(symbol_map=symbol_address_map)

        # Parse data ranges from symbol dict
        data_ranges = []
        for dr_str in symbol_dict.get("data_ranges", []):
            parts = dr_str.replace("$", "").split("-")
            if len(parts) == 2:
                data_ranges.append((int(parts[0], 16), int(parts[1], 16)))

        stub_gen = StubGenerator(
            symbols=symbol_objects,
            translator=translator,
            enable_translation=True,
            use_flow_aware=True,
            prg_data=loader.prg_data,
            data_ranges=data_ranges,
        )
        stub_gen.write_stubs(out_dir)

        # Count translated vs stub-only
        translated_count = sum(1 for s in symbol_objects if s.disassembly_snippet)
        stub_count = len(symbol_objects) - translated_count

        print(f"      Generated {len(symbol_objects)} routines")
        if translated_count > 0:
            print(f"      Translated: {translated_count} (with 6502 code)")
        if stub_count > 0:
            print(f"      Stubs only: {stub_count} (manual port needed)")
    except Exception as e:
        print(f"      ERROR generating stubs: {e}")
        import traceback

        traceback.print_exc()
    print()

    # Generate WLA-DX project structure
    print("[5b/6] Generating WLA-DX project...")
    from ...core.nes.mapper import get_mapper_strategy
    mapper_strategy = get_mapper_strategy(loader.header.mapper)
    _generate_wla_project(out_dir, bank_map, loader, mapper_strategy, translator.instruction_translator, oam_sprites=oam_sprites)
    print()

    # Step 6: Build (optional or required for --run)
    should_build = (hasattr(args, "build") and args.build) or (hasattr(args, "run") and args.run)
    build_success = True
    if should_build:
        print("[6/6] Building SMS ROM...")
        build_success = _build_rom(out_dir)
    else:
        print("[6/6] Skipping build (use --build to compile)")

    print()
    print("=" * 60)
    print(f"[convert] Conversion complete!")
    print(f"[convert] Output: {out_dir}/")

    if not (hasattr(args, "build") and args.build) and not (hasattr(args, "run") and args.run):
        print(f"[convert] To build manually: cd {out_dir}/build && make")

    print("=" * 60)

    # Run in emulator if requested
    if hasattr(args, "run") and args.run:
        if not build_success:
            print()
            print("[convert] Skipping emulator: build failed")
            return
        print()
        print("[convert] Launching emulator...")
        emulator_path = args.emulator if hasattr(args, "emulator") else None
        _launch_emulator(out_dir, emulator_path or None)


def _analyze_mapper(loader) -> dict:
    """Generate bank mapping from ROM analysis."""
    prg_banks = loader.header.prg_banks

    bank_map = {
        "prg_banks": prg_banks,
        "prg_bank_size": 16384,  # 16KB
        "chr_banks": loader.header.chr_banks if loader.header.chr_size > 0 else 0,
        "chr_bank_size": 8192,  # 8KB
        "mapper": loader.header.mapper,
        "mirroring": loader.header.mirroring,
        "mappings": [],
    }

    # Simple mapping strategy
    for i in range(prg_banks):
        bank_map["mappings"].append(
            {
                "sms_slot": 1 if i < prg_banks - 1 else 2,
                "nes_bank": i,
                "fixed": i == prg_banks - 1,
            }
        )

    return bank_map


def _extract_chr_banks(chr_data: bytes, banks_config: dict):
    """Extract CHR banks from data."""
    chr_banks = []
    chr_bank_size = banks_config.get("chr_bank_size", 8192)
    num_chr_banks = banks_config.get("chr_banks", 1)

    for i in range(num_chr_banks):
        offset = i * chr_bank_size
        bank_data = chr_data[offset : offset + chr_bank_size]
        if bank_data:
            chr_banks.append((i, bank_data))

    return chr_banks


def _build_rom(out_dir: Path) -> bool:
    """
    Build SMS ROM using wla-dx.

    Returns:
        True if build succeeded, False otherwise
    """
    import subprocess
    import shutil
    import sys
    import os

    build_dir = out_dir / "build"
    if not build_dir.exists():
        print(f"      ERROR: Build directory not found")
        return False

    # Search in PATH first
    wla_path = shutil.which("wla-z80") or shutil.which("wla-z80.exe")

    # Also search in common local directories
    if not wla_path:
        script_dir = Path(__file__).parent.parent.parent.parent.parent
        local_paths = [
            script_dir / "tools" / "wla-dx",
            Path.cwd() / "tools" / "wla-dx",
            Path.home() / "tools" / "wla-dx",
        ]
        for local_path in local_paths:
            if (local_path / "wla-z80.exe").exists():
                wla_path = str(local_path / "wla-z80.exe")
                break
            elif (local_path / "wla-z80").exists():
                wla_path = str(local_path / "wla-z80")
                break

    if not wla_path:
        print(f"      wla-dx not found. Install with: pip install wla-dx")
        print(f"      Or run: .{chr(92)}setup.bat (Windows) or .{chr(47)}setup.sh (Linux/macOS)")
        return False

    wla_dir = Path(wla_path).parent
    env = dict(os.environ)
    env["PATH"] = str(wla_dir) + os.pathsep + env.get("PATH", "")

    try:
        result = subprocess.run(
            [wla_path, "-o", "main.o", "main.asm"],
            cwd=str(build_dir),
            capture_output=True,
            text=True,
            env=env,
        )

        if result.returncode != 0:
            print(f"      Assemble failed: {result.stderr}")
            return False

        linker_path = (
            wla_dir / "wlalink.exe"
            if (wla_dir / "wlalink.exe").exists()
            else shutil.which("wlalink") or shutil.which("wlalink.exe")
        )
        if not linker_path or not Path(linker_path).exists():
            print(f"      wlalink not found. Install with: pip install wla-dx")
            return False

        result = subprocess.run(
            [str(linker_path), "-v", "link.sms", "game.sms"],
            cwd=str(build_dir),
            capture_output=True,
            text=True,
            env=env,
        )

        # wlalink may return warnings but still succeed - check if output file exists
        if not (build_dir / "game.sms").exists():
            print(f"      Link failed: {result.stderr}")
            return False

        print(f"      Build successful! ({(build_dir / 'game.sms').stat().st_size} bytes)")
        return True

    except Exception as e:
        print(f"      Build error: {e}")
        return False


def _generate_assets_with_oam(oam_sprites: list) -> str:
    """
    Generate assets.asm with proper SAT loading from extracted NES OAM data.

    Args:
        oam_sprites: List of dicts with y, tile, attr, x keys
    """
    # Build Y table bytes
    y_bytes = ", ".join(f"${s['y']:02X}" for s in oam_sprites)
    # Build X/tile pairs
    xt_bytes = ", ".join(f"${s['x']:02X},${s['tile']:02X}" for s in oam_sprites)
    num_sprites = len(oam_sprites)
    # First blank tile index (one past the highest used sprite tile)
    num_sprites_tiles = max(s['tile'] for s in oam_sprites) + 1

    return f"""
.export LoadPalettes
LoadPalettes:
    ; Load BG palette
    ld   hl, $C000
    call VDP_SetWriteAddress
    ld   hl, PaletteBG
    ld   bc, 16
    call VDP_CopyBytes

    ; Load Sprite palette
    ld   hl, $C010
    call VDP_SetWriteAddress
    ld   hl, PaletteSPR
    ld   bc, 16
    call VDP_CopyBytes
    ret

.export LoadTiles
LoadTiles:
    ld   hl, $0000
    call VDP_SetWriteAddress
    ld   hl, Tiles
    ld   bc, $2000
    call VDP_CopyBytes
    ret

.export LoadTilemap
LoadTilemap:
    ; Clear name table with a blank tile (first empty tile after sprite tiles)
    ld   hl, $3800
    call VDP_SetWriteAddress
    ld   bc, $0380 ; 32x28 entries
.tilemap_loop:
    ld   a, {num_sprites_tiles}
    out  ($BE), a
    xor  a
    out  ($BE), a
    dec  bc
    ld   a, b
    or   c
    jr   nz, .tilemap_loop
    ret

.export LoadSAT
LoadSAT:
    ; Load sprite Y positions
    ld   hl, $3F00
    call VDP_SetWriteAddress
    ld   hl, _SpriteY
    ld   bc, {num_sprites + 1}
    call VDP_CopyBytes

    ; Load sprite X/tile pairs
    ld   hl, $3F80
    call VDP_SetWriteAddress
    ld   hl, _SpriteXT
    ld   bc, {num_sprites * 2}
    call VDP_CopyBytes
    ret

_SpriteY:
    .db {y_bytes}, $D0

_SpriteXT:
    .db {xt_bytes}

; Helper to copy BC bytes from HL to VDP
VDP_CopyBytes:
    ld   a, (hl)
    out  ($BE), a
    inc  hl
    dec  bc
    ld   a, b
    or   c
    jr   nz, VDP_CopyBytes
    ret
"""


def _generate_wla_project(out_dir: Path, bank_map: dict, loader, mapper_strategy=None, translator=None, oam_sprites=None):
    """
    Generate WLA-DX project structure.

    Args:
        out_dir: Output directory
        bank_map: Bank mapping configuration
        loader: RomLoader instance with header info
        mapper_strategy: NES mapper strategy
        translator: InstructionTranslator instance
        oam_sprites: Extracted NES OAM sprite data (list of dicts with y, tile, attr, x)
    """
    from ...infrastructure.wla_dx.templates import (
        MAIN_ASM,
        MEMORY_INC,
        INIT_ASM,
        INTERRUPTS_ASM,
        ASSETS_ASM,
        HAL_VDP_ASM,
        HAL_PSG_ASM,
        HAL_INPUT_ASM,
        HAL_MAPPER_ASM,
        LINKER_SCRIPT,
        MAKEFILE_CONTENT,
    )

    # Create build directory structure
    build_dir = out_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "hal").mkdir(exist_ok=True)
    (build_dir / "assets").mkdir(exist_ok=True)
    (build_dir / "stubs").mkdir(exist_ok=True)

    # Calculate ROM banks
    prg_banks = bank_map.get("prg_banks", 2)
    rom_banks = prg_banks + 1  # Add one for init bank

    # Write main.asm with dynamic bank count
    main_content = MAIN_ASM.replace("NUM_BANKS", str(rom_banks))
    (build_dir / "main.asm").write_text(main_content, encoding="utf-8")

    # Write memory.inc
    memory_content = MEMORY_INC.replace("NUM_ROM_BANKS", str(rom_banks))
    (build_dir / "memory.inc").write_text(memory_content, encoding="utf-8")

    # Write other files
    (build_dir / "init.asm").write_text(INIT_ASM, encoding="utf-8")
    (build_dir / "interrupts.asm").write_text(INTERRUPTS_ASM, encoding="utf-8")

    # Generate assets.asm - use dynamic SAT if OAM sprites were extracted
    if oam_sprites:
        assets_content = _generate_assets_with_oam(oam_sprites)
    else:
        assets_content = ASSETS_ASM
    (build_dir / "assets.asm").write_text(assets_content, encoding="utf-8")

    # HAL files
    (build_dir / "hal" / "vdp.asm").write_text(HAL_VDP_ASM, encoding="utf-8")
    (build_dir / "hal" / "psg.asm").write_text(HAL_PSG_ASM, encoding="utf-8")
    (build_dir / "hal" / "input.asm").write_text(HAL_INPUT_ASM, encoding="utf-8")
    (build_dir / "hal" / "mapper.asm").write_text(HAL_MAPPER_ASM, encoding="utf-8")

    # Write dynamic support code if available
    if translator and mapper_strategy:
        support_code = translator.get_support_code(mapper_strategy)
        (build_dir / "hal" / "support.asm").write_text(support_code, encoding="utf-8")
        

    # Copy stubs
    import shutil

    stubs_src = out_dir / "stubs"
    stubs_dst = build_dir / "stubs"
    if stubs_src.exists():
        for stub_file in stubs_src.glob("*.asm"):
            shutil.copy2(stub_file, stubs_dst)

    # Copy assets
    assets_src = out_dir / "assets"
    assets_dst = build_dir / "assets"
    if assets_src.exists():
        for asset_file in assets_src.glob("*"):
            if asset_file.is_file():
                shutil.copy2(asset_file, assets_dst)

    # Write linker script
    linker_content = LINKER_SCRIPT.replace("NUM_BANKS", str(rom_banks))
    (build_dir / "link.sms").write_text(linker_content, encoding="utf-8")

    # Write Makefile
    (build_dir / "Makefile").write_text(MAKEFILE_CONTENT, encoding="utf-8")

    print(f"      WLA-DX project generated")
    print(f"      ROM banks: {rom_banks}")


def _launch_emulator(out_dir: Path, emulator_path: Optional[str] = None):
    """
    Launch SMS ROM in emulator.

    Args:
        out_dir: Output directory with built ROM
        emulator_path: Optional path to emulator executable
    """
    import subprocess
    import shutil

    MIN_ROM_SIZE = 1024  # Minimum 1KB for valid SMS ROM

    # Find SMS ROM file - check build directory first
    sms_rom = None

    # Try common locations
    search_paths = [
        out_dir / "build",
        out_dir,
    ]

    for search_path in search_paths:
        if not search_path.exists():
            continue

        # Look for .sms files (exclude linker scripts)
        for rom in search_path.glob("*.sms"):
            if rom.name == "link.sms":
                continue
            if rom.stat().st_size < MIN_ROM_SIZE:
                continue
            sms_rom = rom
            break

        if not sms_rom:
            # Look for .bin files that might be SMS ROMs
            for rom in search_path.glob("*.bin"):
                if rom.name == "link.bin":
                    continue
                if rom.stat().st_size < MIN_ROM_SIZE:
                    continue
                if "sms" in rom.name.lower() or rom.parent.name == "build":
                    sms_rom = rom
                    break

        if sms_rom:
            break

    if not sms_rom:
        print(f"      ERROR: No valid SMS ROM found")
        print(f"      Build may have failed or produced no output")
        print(f"      Check build logs above for errors")
        print(f"      Note: --run requires successful --build")
        print(f"      Install wla-dx: pip install wla-dx")
        return

    # Auto-detect emulator
    if not emulator_path:
        emulator_path = _detect_emulator()

    if not emulator_path or not Path(emulator_path).exists():
        print(f"      ERROR: Emulator not found")
        print(f"      Specify with: --emulator /path/to/emulator.exe")
        return

    print(f"      Emulator: {emulator_path}")
    print(f"      ROM: {sms_rom} ({sms_rom.stat().st_size} bytes)")

    try:
        subprocess.Popen([emulator_path, str(sms_rom)])
        print(f"      Launched!")
    except Exception as e:
        print(f"      ERROR: Failed to launch emulator: {e}")


def _detect_emulator() -> Optional[str]:
    """
    Auto-detect common SMS emulators.

    Returns:
        Path to emulator executable or None
    """
    # Common emulator names
    emulator_names = {
        "Windows": [
            "blastem.exe",
            "mesen.exe",
            "fceux.exe",
            "genesis-plus-gx.exe",
            "retroarch.exe",
        ],
        "Linux": [
            "blastem",
            "mesen",
            "fceux",
            "retroarch",
        ],
        "Darwin": [
            "blastem",
            "mesen",
            "retroarch",
        ],
    }

    import platform
    import shutil

    system = platform.system()
    emulators = emulator_names.get(system, emulator_names["Linux"])

    # Check in PATH
    for exe in emulators:
        path = shutil.which(exe)
        if path:
            return path

    # Check project-local emulators directory
    project_emulator_dir = Path(__file__).resolve().parents[4] / "emulators"
    if project_emulator_dir.exists():
        for exe in emulators:
            # Search recursively
            for match in project_emulator_dir.rglob(exe):
                if match.is_file():
                    return str(match)

    # Check common installation directories
    common_paths = [
        Path.home() / "Games" / "Emulators",
        Path.home() / "emulators",
        Path("C:\\Games\\Emulators"),
        Path("C:\\Program Files\\Emulators"),
    ]

    for base_dir in common_paths:
        if base_dir.exists():
            for exe in emulators:
                exe_path = base_dir / exe
                if exe_path.exists():
                    return str(exe_path)

    return None
