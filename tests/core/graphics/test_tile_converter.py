"""Tests for tile converter."""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from nes2sms.core.graphics.tile_converter import TileConverter


class TestTileConverter:
    """Test cases for TileConverter."""

    def test_convert_single_tile(self):
        """Test converting a single NES tile to SMS format."""
        # Create a simple test tile (all zeros)
        tile_16bpp = bytes([0] * 16)

        converter = TileConverter(color_maps=[[0, 1, 2, 3]], flip_strategy="none")
        result = converter.convert(tile_16bpp)

        assert len(result.sms_tiles) == 1
        assert len(result.sms_tiles[0]) == 32  # SMS tiles are 32 bytes

    def test_convert_multiple_tiles(self):
        """Test converting multiple tiles."""
        # Create 4 test tiles
        chr_data = bytes([0] * 64)  # 4 tiles × 16 bytes

        converter = TileConverter(color_maps=[[0, 1, 2, 3]], flip_strategy="none")
        result = converter.convert(chr_data)

        assert len(result.sms_tiles) == 4

    def test_convert_with_color_mapping(self):
        """Test tile conversion with color mapping."""
        # Create a tile with specific pattern
        tile_16bpp = bytes([0xFF] * 8 + [0xFF] * 8)  # All pixels = 3

        color_map = [0, 5, 10, 15]  # Map NES colors 0-3 to SMS indices
        converter = TileConverter(color_maps=[color_map], flip_strategy="none")
        result = converter.convert(tile_16bpp)

        assert len(result.sms_tiles) == 1
        assert len(result.sms_tiles[0]) == 32

    def test_flip_horizontal(self):
        """Test horizontal flip generation."""
        tile_16bpp = bytes([0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80] * 2)

        converter = TileConverter(color_maps=[[0, 1, 2, 3]], flip_strategy="cache")
        result = converter.convert(tile_16bpp)

        assert "0_H" in result.flip_index
        assert "0_V" in result.flip_index
        assert "0_HV" in result.flip_index

    def test_flip_variants_unique(self):
        """Test that flip variants are unique."""
        # Create asymmetric tile pattern
        tile_16bpp = bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00] * 2)

        converter = TileConverter(color_maps=[[0, 1, 2, 3]], flip_strategy="cache")
        result = converter.convert(tile_16bpp)

        h_idx = result.flip_index.get("0_H")
        v_idx = result.flip_index.get("0_V")
        hv_idx = result.flip_index.get("0_HV")

        assert h_idx is not None
        assert v_idx is not None
        assert hv_idx is not None
        assert h_idx != v_idx
        assert h_idx != hv_idx
        assert v_idx != hv_idx

    def test_multi_bank_conversion(self):
        """Test multi-bank tile conversion."""
        # Create 2 banks of tiles
        bank0 = bytes([0] * 16)  # 1 tile
        bank1 = bytes([0xFF] * 16)  # 1 tile

        converter = TileConverter(color_maps=[[0, 1, 2, 3]], flip_strategy="none")
        result = converter.convert_multi_bank([(0, bank0), (1, bank1)])

        assert len(result.sms_tiles) == 2
        assert result.tile_metadata[0]["bank"] == 0
        assert result.tile_metadata[1]["bank"] == 1
        assert result.tile_metadata[0]["tile_index"] == 0
        assert result.tile_metadata[1]["tile_index"] == 0

    def test_incomplete_tile_warning(self):
        """Test warning for incomplete tile data."""
        # 17 bytes = 1 complete tile + 1 extra byte
        chr_data = bytes([0] * 17)

        converter = TileConverter(color_maps=[[0, 1, 2, 3]], flip_strategy="none")
        result = converter.convert(chr_data)

        assert len(result.warnings) == 1
        assert "extra bytes" in result.warnings[0]

    def test_tile_metadata_bank_tracking(self):
        """Test that tile metadata tracks bank information."""
        chr_data = bytes([0] * 48)  # 3 tiles

        converter = TileConverter(color_maps=[[0, 1, 2, 3]], flip_strategy="none")
        result = converter.convert(chr_data, bank_id=2)

        assert len(result.tile_metadata) == 3
        for meta in result.tile_metadata:
            assert meta["bank"] == 2
