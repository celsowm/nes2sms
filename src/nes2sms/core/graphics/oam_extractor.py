"""NES OAM/sprite data extractor from PRG ROM."""

from typing import List, Dict, Optional, Tuple


class OamExtractor:
    """
    Extracts OAM sprite data from NES PRG ROM.

    NES OAM format: 4 bytes per sprite (Y, tile, attributes, X)
    SMS SAT format: Y table at $3F00, X/tile table at $3F80
    """

    def __init__(self, prg_data: bytes, chr_tile_count: int, base_address: int = 0x8000):
        self.prg_data = prg_data
        self.chr_tile_count = chr_tile_count
        self.base_address = base_address

    def extract_oam_table(self) -> Optional[List[Dict]]:
        """
        Search PRG for OAM-like data tables.

        Looks for sequences of 4-byte entries matching NES OAM format:
        - Y: 0-239 (visible range)
        - Tile: 0 to chr_tile_count-1
        - Attributes: typically 0-3 (palette bits) in low bits
        - X: 0-255

        Returns:
            List of sprite dicts with y, tile, attr, x keys, or None
        """
        best_table = None
        best_count = 0

        # Scan PRG for OAM-like data runs
        for offset in range(len(self.prg_data) - 3):
            sprites = self._try_parse_oam_at(offset)
            if sprites and len(sprites) > best_count:
                best_count = len(sprites)
                best_table = sprites

        if best_table and best_count >= 3:
            return best_table
        return None

    def _try_parse_oam_at(self, offset: int) -> Optional[List[Dict]]:
        """Try to parse an OAM table starting at offset."""
        sprites = []
        pos = offset
        max_sprites = 64  # NES supports 64 sprites

        while pos + 3 < len(self.prg_data) and len(sprites) < max_sprites:
            y = self.prg_data[pos]
            tile = self.prg_data[pos + 1]
            attr = self.prg_data[pos + 2]
            x = self.prg_data[pos + 3]

            # Validate as OAM entry
            if not self._is_valid_oam_entry(y, tile, attr, x):
                break

            sprites.append({"y": y, "tile": tile, "attr": attr, "x": x})
            pos += 4

        return sprites if len(sprites) >= 3 else None

    def _is_valid_oam_entry(self, y: int, tile: int, attr: int, x: int) -> bool:
        """Check if 4 bytes look like a valid OAM entry."""
        # Y must be in visible range (not hidden at 0xEF+)
        if y == 0 or y >= 0xF0:
            return False
        # Tile must be within CHR range
        if tile >= self.chr_tile_count:
            return False
        # Attributes: low 2 bits = palette, bit 5 = priority, bit 6 = H-flip, bit 7 = V-flip
        # Upper unused bits should be 0 for simple ROMs
        if attr & 0b00011100:
            return False
        # X should be in reasonable range
        if x == 0:
            return False
        return True

    @staticmethod
    def build_tile_activity(tiles: List[bytes]) -> List[bool]:
        """Build a per-tile visibility mask from converted tile data."""
        return [any(tile) for tile in tiles]

    @staticmethod
    def nonempty_tile_ratio(sprites: List[Dict], tile_activity: Optional[List[bool]]) -> float:
        """
        Calculate how many referenced sprite tiles are visually non-empty.

        Returns:
            Ratio in range [0.0, 1.0]. Returns 1.0 when no activity map is provided.
        """
        if not sprites:
            return 0.0
        if tile_activity is None:
            return 1.0

        referenced_tiles = [
            spr["tile"]
            for spr in sprites
            if isinstance(spr.get("tile"), int) and 0 <= spr["tile"] < len(tile_activity)
        ]
        if not referenced_tiles:
            return 0.0

        nonempty_count = sum(1 for tile in referenced_tiles if tile_activity[tile])
        return nonempty_count / len(referenced_tiles)

    @classmethod
    def is_confident_table(
        cls,
        sprites: List[Dict],
        tile_activity: Optional[List[bool]] = None,
        min_nonempty_ratio: float = 0.5,
    ) -> bool:
        """
        Validate whether an extracted OAM table is likely to be real sprite data.

        A table is considered low confidence when most referenced tiles are empty
        after graphics conversion.
        """
        if not sprites or len(sprites) < 3:
            return False
        if tile_activity is None:
            return True

        ratio = cls.nonempty_tile_ratio(sprites, tile_activity)
        if ratio < min_nonempty_ratio:
            return False
        return True

    def to_sms_sat(self, sprites: List[Dict]) -> Tuple[bytes, bytes]:
        """
        Convert NES OAM entries to SMS SAT format.

        Returns:
            Tuple of (y_table, xt_table)
            - y_table: Y positions + $D0 terminator
            - xt_table: X,tile pairs
        """
        y_table = bytearray()
        xt_table = bytearray()

        for spr in sprites:
            # NES Y is offset by 1 (Y=0 means scanline 1)
            # SMS sprites also have a similar offset
            y_table.append(spr["y"])
            xt_table.append(spr["x"])
            xt_table.append(spr["tile"])

        # Add terminator
        y_table.append(0xD0)

        return bytes(y_table), bytes(xt_table)
