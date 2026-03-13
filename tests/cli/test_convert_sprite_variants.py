"""Tests for profiled sprite variant mapping in convert pipeline."""

from nes2sms.cli.commands.convert import (
    _apply_profiled_sprite_variants,
    _build_default_sprite_variant_map,
)
from nes2sms.core.graphics.tile_converter import TileConverter
from nes2sms.shared.models import TileConversionResult


def test_default_sprite_variant_map_is_identity():
    variant_map = _build_default_sprite_variant_map()
    assert len(variant_map) == 256 * 16
    for tile in (0, 1, 10, 255):
        for combo in (0, 1, 7, 15):
            assert variant_map[tile * 16 + combo] == tile


def test_profiled_variant_mapping_resolves_tile_attr_combo():
    # Build minimal base tiles: 2 tiles with room in sprite range.
    chr_data = bytes([0xFF] * 16 + [0x00] * 16)
    converter = TileConverter(color_maps=[[0, 1, 2, 3]], flip_strategy="none")
    base_result = converter.convert(chr_data)
    tile_result = TileConversionResult(
        sms_tiles=list(base_result.sms_tiles),
        flip_index=dict(base_result.flip_index),
        warnings=list(base_result.warnings),
        tile_metadata=list(base_result.tile_metadata),
    )

    # 8 color maps (4 BG + 4 SPR); make sprite palette 1 distinct from palette 0.
    color_maps = [
        [0, 1, 2, 3],
        [0, 1, 2, 3],
        [0, 1, 2, 3],
        [0, 1, 2, 3],
        [0, 4, 5, 6],  # SPR palette 0
        [0, 7, 8, 9],  # SPR palette 1
        [0, 10, 11, 12],  # SPR palette 2
        [0, 13, 14, 15],  # SPR palette 3
    ]

    # attr 0x41 => palette 1 + H flip
    oam_sprites = [{"y": 40, "tile": 0, "attr": 0x41, "x": 20}]
    result = _apply_profiled_sprite_variants(
        chr_data=chr_data,
        tile_result=tile_result,
        oam_sprites=oam_sprites,
        color_maps=color_maps,
        split_y=48,
    )

    combo = 0x05  # palette 1 + H flip
    mapped = result["lookup"][(0, combo)]
    assert 0 <= mapped <= 255
    assert result["variant_map"][0 * 16 + combo] == mapped
    assert result["profile"]["resolved_variants"][0]["mapped_tile"] == mapped
