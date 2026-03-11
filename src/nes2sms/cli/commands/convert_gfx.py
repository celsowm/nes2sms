"""Convert graphics command."""

import json
from pathlib import Path
from typing import List, Tuple

from ...core.graphics import TileConverter, PaletteMapper
from ...infrastructure.asset_writer import AssetWriter


def cmd_convert_gfx(args):
    """Convert NES CHR to SMS VDP tiles."""
    chr_path = Path(args.chr)
    prg_path = Path(args.prg)

    if not chr_path.exists():
        raise FileNotFoundError(f"CHR file not found: {chr_path}")

    if not prg_path.exists():
        raise FileNotFoundError(f"PRG file not found: {prg_path}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load CHR data (single file or multi-bank)
    chr_data = chr_path.read_bytes()

    # Check for multi-bank configuration
    banks_json_path = out_dir / "work" / "banks.json"
    if banks_json_path.exists():
        banks_config = json.loads(banks_json_path.read_text())
        chr_banks = _extract_chr_banks(chr_data, banks_config)
        use_multi_bank = len(chr_banks) > 1
    else:
        chr_banks = [(0, chr_data)]
        use_multi_bank = False

    # Build palettes
    palette_mapper = PaletteMapper()
    bg_pal, spr_pal, color_maps = palette_mapper.build_all_palettes()

    # Convert tiles
    tile_converter = TileConverter(
        color_maps=color_maps[:4],
        flip_strategy=args.sprite_flip_strategy,
    )

    if use_multi_bank:
        result = tile_converter.convert_multi_bank(chr_banks)
    else:
        result = tile_converter.convert(chr_data, bank_id=0)

    # Write outputs
    writer = AssetWriter(out_dir)
    writer.write_palette(bg_pal, "bg")
    writer.write_palette(spr_pal, "spr")
    writer.write_tiles(result.sms_tiles)
    writer.write_flip_index(result.flip_index)
    writer.write_tile_symbols(result.tile_metadata, "assets")

    # Warnings
    for w in result.warnings:
        print(f"[convert-gfx] WARNING: {w}")

    total_size = sum(len(t) for t in result.sms_tiles)
    print(
        f"[convert-gfx] {len(result.sms_tiles)} SMS tiles | "
        f"{total_size // 1024}KB tiles.bin | "
        f"palettes: palette_bg.bin + palette_spr.bin"
    )
    if use_multi_bank:
        print(f"[convert-gfx] Multi-bank mode: {len(chr_banks)} banks processed")


def _extract_chr_banks(chr_data: bytes, banks_config: dict) -> List[Tuple[int, bytes]]:
    """
    Extract CHR banks from CHR data based on bank configuration.

    Args:
        chr_data: Full CHR data
        banks_config: Bank configuration from banks.json

    Returns:
        List of (bank_id, chr_data) tuples
    """
    chr_banks = []
    chr_bank_size = 8192  # Standard CHR bank size (8KB)

    # Check if banks.json specifies CHR banking
    if "chr_banks" in banks_config:
        num_chr_banks = banks_config["chr_banks"]
        for i in range(num_chr_banks):
            offset = i * chr_bank_size
            bank_data = chr_data[offset : offset + chr_bank_size]
            if bank_data:
                chr_banks.append((i, bank_data))
    else:
        # Default: single bank
        chr_banks.append((0, chr_data))

    return chr_banks
