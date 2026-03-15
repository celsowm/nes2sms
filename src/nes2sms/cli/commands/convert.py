"""Convert command: one-step NES -> SMS orchestration."""

from pathlib import Path

from ...core.assembly.flow_aware_translator import FlowAwareTranslator
from ...infrastructure.asset_writer import AssetWriter
from ...infrastructure.disassembler import Da65Disassembler
from ...infrastructure.disassembler.native_disassembler import Native6502Disassembler
from ...infrastructure.rom_loader import RomLoader
from ...infrastructure.symbol_extractor import StaticSymbolExtractor
from ...infrastructure.wla_dx.stub_generator import StubGenerator
from ...shared.models import Symbol
from ._convert_graphics import (
    _apply_profiled_sprite_variants,
    _build_default_sprite_variant_map,
    capture_runtime_snapshot,
    prepare_graphics_assets,
    write_graphics_assets,
)
from ._convert_project import build_rom, generate_wla_project, launch_emulator


def cmd_convert(args):
    """Run the full conversion pipeline for a NES ROM."""
    nes_path = Path(args.nes)
    if not nes_path.exists():
        raise FileNotFoundError(f"ROM not found: {nes_path}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[convert] Starting conversion: {nes_path.name}")
    print(f"[convert] Output directory: {out_dir}/")
    print()

    print("[1/6] Ingesting ROM...")
    loader = RomLoader().load(nes_path)
    writer = AssetWriter(out_dir)
    _write_ingested_rom_artifacts(writer, loader)
    print(
        f"      PRG: {len(loader.prg_data) // 1024}KB | CHR: {len(loader.chr_data) // 1024 if loader.chr_data else 0}KB"
    )
    print(f"      Mapper: {loader.header.mapper} | Mirroring: {loader.header.mirroring}")
    print()

    print("[2/6] Extracting symbols and disassembling code...")
    symbol_dict = _extract_symbol_dict(loader, writer)
    print()

    print("[3/6] Analyzing mapper...")
    bank_map = _analyze_mapper(loader)
    writer.write_json("banks.json", bank_map, "work")
    print(f"      PRG banks: {loader.header.prg_banks}")
    print("      Fixed bank: last")
    print()

    runtime_capture = capture_runtime_snapshot(args, loader, nes_path, out_dir)

    print("[4/6] Converting graphics...")
    graphics = prepare_graphics_assets(args, loader, bank_map, runtime_capture)
    write_graphics_assets(writer, graphics)
    print()

    print("[5/6] Generating Z80 stubs with translation...")
    translator = _generate_stubs(out_dir, loader, symbol_dict)
    print()

    print("[5b/6] Generating WLA-DX project...")
    from ...core.nes.mapper import get_mapper_strategy

    mapper_strategy = get_mapper_strategy(loader.header.mapper)
    generate_wla_project(
        out_dir,
        bank_map,
        loader,
        mapper_strategy,
        translator.instruction_translator,
        split_y=int(getattr(args, "split_y", 48)),
    )
    print()

    should_build = (hasattr(args, "build") and args.build) or (hasattr(args, "run") and args.run)
    build_success = True
    if should_build:
        print("[6/6] Building SMS ROM...")
        build_success = build_rom(out_dir)
    else:
        print("[6/6] Skipping build (use --build to compile)")

    print()
    print("=" * 60)
    print("[convert] Conversion complete!")
    print(f"[convert] Output: {out_dir}/")
    if not should_build:
        print(f"[convert] To build manually: cd {out_dir}/build && make")
    print("=" * 60)

    if hasattr(args, "run") and args.run:
        if not build_success:
            print()
            print("[convert] Skipping emulator: build failed")
            return
        print()
        print("[convert] Launching emulator...")
        emulator_path = args.emulator if hasattr(args, "emulator") else None
        launch_emulator(out_dir, emulator_path or None)


def _write_ingested_rom_artifacts(writer: AssetWriter, loader) -> None:
    writer.write_binary("prg.bin", loader.prg_data, "work")
    if loader.chr_data:
        writer.write_binary("chr.bin", loader.chr_data, "work")
    if loader.trainer_data:
        writer.write_binary("trainer.bin", loader.trainer_data, "work")


def _extract_symbol_dict(loader, writer: AssetWriter) -> dict:
    symbol_dict = {}
    if not loader.prg_data:
        return symbol_dict

    disassembler = Da65Disassembler()
    if disassembler.is_available():
        print("      Using da65 disassembler (external)...")
        extractor = StaticSymbolExtractor(loader.prg_data, disassembler=disassembler)
    else:
        print("      da65 not found, using native Python disassembler...")
        extractor = StaticSymbolExtractor(
            loader.prg_data,
            disassembler=Native6502Disassembler(),
        )

    symbols = extractor.extract()
    symbol_dict = extractor.to_dict()
    writer.write_json("symbols.json", symbol_dict, "work")
    print(f"      Found {len(symbols)} symbols")
    print(f"      Code ranges: {len(extractor.get_code_ranges())}")
    if extractor.disassembly_db:
        print(f"      Disassembly: {len(extractor.disassembly_db.instructions)} instructions")
    return symbol_dict


def _generate_stubs(out_dir: Path, loader, symbol_dict: dict) -> FlowAwareTranslator:
    translator = FlowAwareTranslator(symbol_map={})
    try:
        symbol_objects = _build_symbol_objects(symbol_dict)
        symbol_address_map = {symbol.address: symbol.name for symbol in symbol_objects}
        translator = FlowAwareTranslator(symbol_map=symbol_address_map)
        stub_gen = StubGenerator(
            symbols=symbol_objects,
            translator=translator,
            enable_translation=True,
            use_flow_aware=True,
            prg_data=loader.prg_data,
            data_ranges=_extract_data_ranges(symbol_dict),
        )
        stub_gen.write_stubs(out_dir)
        translated_count = sum(1 for symbol in symbol_objects if symbol.disassembly_snippet)
        stub_count = len(symbol_objects) - translated_count
        print(f"      Generated {len(symbol_objects)} routines")
        if translated_count > 0:
            print(f"      Translated: {translated_count} (with 6502 code)")
        if stub_count > 0:
            print(f"      Stubs only: {stub_count} (manual port needed)")
    except Exception as exc:
        print(f"      ERROR generating stubs: {exc}")
        import traceback

        traceback.print_exc()
    return translator


def _build_symbol_objects(symbol_dict: dict) -> list[Symbol]:
    symbol_objects: list[Symbol] = []
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
    return symbol_objects


def _extract_data_ranges(symbol_dict: dict) -> list[tuple[int, int]]:
    data_ranges: list[tuple[int, int]] = []
    for dr_str in symbol_dict.get("data_ranges", []):
        parts = dr_str.replace("$", "").split("-")
        if len(parts) == 2:
            data_ranges.append((int(parts[0], 16), int(parts[1], 16)))
    return data_ranges


def _analyze_mapper(loader) -> dict:
    """Generate bank mapping from ROM analysis."""
    prg_banks = loader.header.prg_banks
    bank_map = {
        "prg_banks": prg_banks,
        "prg_bank_size": 16384,
        "chr_banks": loader.header.chr_banks if loader.header.chr_size > 0 else 0,
        "chr_bank_size": 8192,
        "mapper": loader.header.mapper,
        "mirroring": loader.header.mirroring,
        "mappings": [],
    }
    for index in range(prg_banks):
        bank_map["mappings"].append(
            {
                "sms_slot": 1 if index < prg_banks - 1 else 2,
                "nes_bank": index,
                "fixed": index == prg_banks - 1,
            }
        )
    return bank_map
