"""Convert graphics command."""

import json
from pathlib import Path

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

    # Load CHR data
    chr_data = chr_path.read_bytes()

    # Build palettes
    palette_mapper = PaletteMapper()
    bg_pal, spr_pal, color_maps = palette_mapper.build_all_palettes()

    # Convert tiles
    tile_converter = TileConverter(
        color_maps=color_maps[:4],  # Use BG color maps for tiles
        flip_strategy=args.sprite_flip_strategy,
    )
    result = tile_converter.convert(chr_data)

    # Write outputs
    writer = AssetWriter(out_dir)
    writer.write_palette(bg_pal, "bg")
    writer.write_palette(spr_pal, "spr")
    writer.write_tiles(result.sms_tiles)
    writer.write_flip_index(result.flip_index)

    # Warnings
    for w in result.warnings:
        print(f"[convert-gfx] WARNING: {w}")

    total_size = sum(len(t) for t in result.sms_tiles)
    print(
        f"[convert-gfx] {len(result.sms_tiles)} SMS tiles | "
        f"{total_size // 1024}KB tiles.bin | "
        f"palettes: palette_bg.bin + palette_spr.bin"
    )
