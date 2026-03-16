"""Tests for palette mapper."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from nes2sms.core.graphics.palette_mapper import PaletteMapper
from nes2sms.shared.constants import NES_PALETTE_RGB


class TestPaletteMapper:
    """Test cases for PaletteMapper."""

    def test_nes_color_to_sms(self):
        """Test NES to SMS color conversion."""
        # Test black (NES color $0F)
        sms_black = PaletteMapper.nes_color_to_sms(0x0F)
        assert isinstance(sms_black, int)
        assert 0 <= sms_black <= 63

        # Test white (approximate, NES color $30)
        sms_white = PaletteMapper.nes_color_to_sms(0x30)
        assert isinstance(sms_white, int)

    def test_reference_palette_matches_fceux_for_known_entries(self):
        assert NES_PALETTE_RGB[0x0C] == (24, 60, 92)
        assert NES_PALETTE_RGB[0x1C] == (0, 128, 136)
        assert NES_PALETTE_RGB[0x2B] == (88, 248, 152)
        assert NES_PALETTE_RGB[0x39] == (224, 252, 160)

    def test_sms_color_to_rgb(self):
        """Test SMS color to RGB conversion."""
        # Test black
        rgb = PaletteMapper.sms_color_to_rgb(0)
        assert rgb == (0, 0, 0)

        # Test white (%00111111 = 0x3F)
        rgb = PaletteMapper.sms_color_to_rgb(0x3F)
        assert rgb == (255, 255, 255)

        # Test red (%00000011 = 0x03)
        rgb = PaletteMapper.sms_color_to_rgb(0x03)
        assert rgb[0] > 0  # Red component should be non-zero

    def test_build_sms_palette_bg(self):
        """Test building SMS background palette."""
        mapper = PaletteMapper()
        palette, color_maps = mapper.build_sms_palette("bg")

        assert len(palette) == 16  # 16 colors
        assert len(color_maps) == 4  # 4 sub-palettes
        assert all(len(cm) == 4 for cm in color_maps)

    def test_build_sms_palette_spr(self):
        """Test building SMS sprite palette."""
        mapper = PaletteMapper()
        palette, color_maps = mapper.build_sms_palette("spr")

        assert len(palette) == 16
        assert len(color_maps) == 4

    def test_build_all_palettes(self):
        """Test building both palettes."""
        mapper = PaletteMapper()
        bg_pal, spr_pal, all_maps = mapper.build_all_palettes()

        assert len(bg_pal) == 16
        assert len(spr_pal) == 16
        assert len(all_maps) == 8  # 4 BG + 4 SPR

    def test_custom_palette_ram(self):
        """Test with custom palette RAM values."""
        # Custom palette: all colors = $0F (black)
        custom_pal = [0x0F] * 32

        mapper = PaletteMapper(nes_palette_ram=custom_pal)
        bg_pal, spr_pal, all_maps = mapper.build_all_palettes()

        assert len(bg_pal) == 16
        assert len(spr_pal) == 16

    def test_palette_overflow_handling(self):
        """Test that palette handles overflow gracefully."""
        # Use default palette (should not overflow)
        mapper = PaletteMapper()
        bg_pal, spr_pal, all_maps = mapper.build_all_palettes()

        # All color maps should be valid indices (0-15)
        for cm in all_maps:
            for color_idx in cm:
                assert 0 <= color_idx <= 15

    def test_rgb_distance(self):
        """Test RGB distance calculation."""
        mapper = PaletteMapper()

        # Same color should have distance 0
        dist = mapper._rgb_distance((255, 255, 255), (255, 255, 255))
        assert dist == 0

        # Different colors should have positive distance
        dist = mapper._rgb_distance((0, 0, 0), (255, 255, 255))
        assert dist > 0

    def test_bg_palette_uses_universal_backdrop_for_all_subpalettes(self):
        mapper = PaletteMapper(
            nes_palette_ram=[
                0x0C,
                0x0C,
                0x1C,
                0x39,
                0x0F,
                0x1C,
                0x2B,
                0x39,
                0x0C,
                0x0F,
                0x0F,
                0x0F,
                0x0C,
                0x0F,
                0x0F,
                0x0F,
            ]
            + [0x0F] * 16
        )

        palette, color_maps = mapper.build_sms_palette("bg")
        backdrop = PaletteMapper.nes_color_to_sms(0x0C)

        assert palette[0] == backdrop
        assert palette[4] == backdrop
        assert palette[8] == backdrop
        assert palette[12] == backdrop
        assert all(cm[0] == 0 for cm in color_maps)

    def test_lookup_table_matches_pointwise_conversion(self):
        lookup = PaletteMapper.build_nes_to_sms_lookup()

        assert len(lookup) == 64
        assert lookup == [PaletteMapper.nes_color_to_sms(index) for index in range(64)]
