"""NES to SMS tile converter (2bpp to 4bpp)."""

from typing import List, Dict, Tuple, Optional
from ...shared.models import TileConversionResult


class TileConverter:
    """
    Converts NES 2bpp tiles to SMS 4bpp format.

    NES tiles: 16 bytes (8x8 pixels, 2 bits per pixel)
    SMS tiles: 32 bytes (8x8 pixels, 4 bits per pixel)
    """

    def __init__(self, color_maps: List[List[int]], flip_strategy: str = "cache"):
        """
        Initialize tile converter.

        Args:
            color_maps: List of 4 color maps, each mapping NES color (0-3) to SMS index (0-15)
            flip_strategy: 'cache' to generate flip variants, 'none' to skip
        """
        self.color_maps = color_maps
        self.flip_strategy = flip_strategy

    def convert(self, chr_data: bytes, bank_id: Optional[int] = 0) -> TileConversionResult:
        """
        Convert all tiles in CHR data.

        Args:
            chr_data: Raw CHR data (16 bytes per tile)
            bank_id: CHR bank ID (for multi-bank games)

        Returns:
            TileConversionResult with SMS tiles, flip index, and metadata
        """
        tiles = []
        flip_index = {}
        warnings = []
        metadata = []

        num_tiles = len(chr_data) // 16

        for i in range(num_tiles):
            tile_2bpp = chr_data[i * 16 : (i + 1) * 16]
            sms_tile = self._convert_tile(tile_2bpp)
            tiles.append(sms_tile)
            metadata.append({"bank": bank_id, "tile_index": i})

            if self.flip_strategy == "cache":
                self._handle_flip_variants(i, sms_tile, flip_index, bank_id or 0)

        if len(chr_data) % 16 != 0:
            warnings.append(f"CHR data has {len(chr_data) % 16} extra bytes (incomplete tile)")

        return TileConversionResult(
            sms_tiles=tiles, flip_index=flip_index, warnings=warnings, tile_metadata=metadata
        )

    def convert_multi_bank(self, chr_banks: List[Tuple[int, bytes]]) -> TileConversionResult:
        """
        Convert tiles from multiple CHR banks.

        Args:
            chr_banks: List of (bank_id, chr_data) tuples

        Returns:
            TileConversionResult with all tiles and bank metadata
        """
        all_tiles = []
        all_flip_index = {}
        all_warnings = []
        all_metadata = []

        for bank_id, chr_data in chr_banks:
            result = self.convert(chr_data, bank_id=bank_id)
            all_tiles.extend(result.sms_tiles)
            all_flip_index.update(result.flip_index)
            all_warnings.extend(result.warnings)
            all_metadata.extend(result.tile_metadata)

        return TileConversionResult(
            sms_tiles=all_tiles,
            flip_index=all_flip_index,
            warnings=all_warnings,
            tile_metadata=all_metadata,
        )

    def _convert_tile(self, tile_16bpp: bytes) -> bytes:
        """
        Convert single 16-byte NES tile to 32-byte SMS tile.

        Args:
            tile_16bpp: NES tile data (2 bitplanes)

        Returns:
            SMS tile data (4 bitplanes)
        """
        sms32 = bytearray(32)

        for row in range(8):
            plane0 = tile_16bpp[row]
            plane1 = tile_16bpp[row + 8]

            # Extract NES pixel indices (0-3)
            pixels = []
            for x in range(8):
                b0 = (plane0 >> (7 - x)) & 1
                b1 = (plane1 >> (7 - x)) & 1
                nes_idx = (b1 << 1) | b0
                pixels.append(nes_idx)

            # Convert to SMS 4bpp format (4 bitplanes)
            for plane in range(4):
                byte = 0
                for x in range(8):
                    # Use first color map (BG palette by default)
                    sms_idx = self.color_maps[0][pixels[x]] if self.color_maps else pixels[x]
                    byte |= ((sms_idx >> plane) & 1) << (7 - x)
                sms32[row * 4 + plane] = byte

        return bytes(sms32)

    def _handle_flip_variants(
        self, tile_index: int, sms_tile: bytes, flip_index: Dict, bank_id: Optional[int] = 0
    ):
        """
        Handle flip variant generation for sprite cache.

        Args:
            tile_index: Original tile index
            sms_tile: Converted SMS tile data
            flip_index: Dictionary to populate with flip variants
            bank_id: CHR bank ID for unique keys
        """
        prefix = f"B{bank_id}_{tile_index}" if bank_id else f"{tile_index}"
        # H flip
        h_flip = self._flip_tile_h(sms_tile)
        flip_index[f"{prefix}_H"] = len(flip_index) + 1

        # V flip
        v_flip = self._flip_tile_v(sms_tile)
        flip_index[f"{prefix}_V"] = len(flip_index) + 2

        # HV flip
        hv_flip = self._flip_tile_v(self._flip_tile_h(v_flip))
        flip_index[f"{prefix}_HV"] = len(flip_index) + 3

    @staticmethod
    def _flip_tile_h(tile32: bytes) -> bytes:
        """Flip tile horizontally (reverse pixel order in each row)."""
        out = bytearray(32)
        for i, b in enumerate(tile32):
            out[i] = int(f"{b:08b}"[::-1], 2)
        return bytes(out)

    @staticmethod
    def _flip_tile_v(tile32: bytes) -> bytes:
        """Flip tile vertically (reverse row order)."""
        out = bytearray(32)
        for row in range(8):
            for plane in range(4):
                out[row * 4 + plane] = tile32[(7 - row) * 4 + plane]
        return bytes(out)
