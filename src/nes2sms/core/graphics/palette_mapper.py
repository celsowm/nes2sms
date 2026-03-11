"""NES to SMS palette mapping."""

from typing import List, Tuple, Optional
from ...shared.constants import NES_PALETTE_RGB


class PaletteMapper:
    """
    Maps NES palette colors to SMS palette format.

    NES: 64 colors (6-bit index) → RGB
    SMS: 64 colors (2 bits per channel: %00BBGGRR)
    """

    def __init__(self, nes_palette_ram: Optional[List[int]] = None):
        """
        Initialize palette mapper.

        Args:
            nes_palette_ram: List of 32 NES palette RAM values (default: standard NES palette)
        """
        if nes_palette_ram is None:
            self.nes_palette_ram = self._default_nes_palette()
        else:
            self.nes_palette_ram = nes_palette_ram

    @staticmethod
    def _default_nes_palette() -> List[int]:
        """Return default NES palette RAM values."""
        # Background palettes (4 × 4 colors)
        bg = [
            0x0F,
            0x01,
            0x11,
            0x21,
            0x0F,
            0x06,
            0x16,
            0x26,
            0x0F,
            0x09,
            0x19,
            0x29,
            0x0F,
            0x0C,
            0x1C,
            0x2C,
        ]
        # Sprite palettes (4 × 4 colors)
        spr = [
            0x0F,
            0x16,
            0x27,
            0x38,
            0x0F,
            0x02,
            0x12,
            0x22,
            0x0F,
            0x05,
            0x15,
            0x25,
            0x0F,
            0x0A,
            0x1A,
            0x2A,
        ]
        return bg + spr

    @staticmethod
    def nes_color_to_sms(nes_idx: int) -> int:
        """
        Convert NES 6-bit color index to SMS %00BBGGRR byte.

        Args:
            nes_idx: NES color index (0-63)

        Returns:
            SMS color byte (%00BBGGRR)
        """
        r, g, b = NES_PALETTE_RGB[nes_idx & 0x3F]
        rr = round(r / 255 * 3) & 0x3
        gg = round(g / 255 * 3) & 0x3
        bb = round(b / 255 * 3) & 0x3
        return (bb << 4) | (gg << 2) | rr

    @staticmethod
    def sms_color_to_rgb(sms_byte: int) -> Tuple[int, int, int]:
        """
        Convert SMS color byte to RGB tuple.

        Args:
            sms_byte: SMS color byte (%00BBGGRR)

        Returns:
            Tuple of (R, G, B) values (0-255)
        """
        rr = (sms_byte & 0x03) * 85
        gg = ((sms_byte >> 2) & 0x03) * 85
        bb = ((sms_byte >> 4) & 0x03) * 85
        return (rr, gg, bb)

    @staticmethod
    def _rgb_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
        """Calculate Euclidean distance between two RGB colors."""
        return sum((a - b) ** 2 for a, b in zip(c1, c2))

    def build_sms_palette(self, slot: str = "bg") -> Tuple[bytes, List[List[int]]]:
        """
        Build 16-entry SMS palette from NES palette RAM.

        Args:
            slot: 'bg' for background, 'spr' for sprites

        Returns:
            Tuple of (palette_bytes, color_maps)
            - palette_bytes: 16 bytes for SMS CRAM
            - color_maps: 4 lists of 4 colors each (NES idx 0-3 → SMS idx 0-15)
        """
        # Select appropriate palette RAM section
        if slot == "bg":
            palette_ram = self.nes_palette_ram[:16]
        else:
            palette_ram = self.nes_palette_ram[16:32]

        # Convert to SMS format
        sms_palette = bytearray(16)
        for i, nes_color in enumerate(palette_ram[:16]):
            sms_palette[i] = self.nes_color_to_sms(nes_color)

        # Build color maps for each of the 4 sub-palettes
        color_maps = []
        for pal in range(4):
            cm = [0] * 4
            for c in range(4):
                idx = pal * 4 + c
                if idx < len(palette_ram):
                    nes_idx = palette_ram[idx]
                else:
                    nes_idx = 0

                # Find nearest SMS palette slot
                sms_col = self.nes_color_to_sms(nes_idx)
                best = 0
                best_dist = float("inf")

                for j in range(16):
                    d = self._rgb_distance(
                        self.sms_color_to_rgb(sms_palette[j]), self.sms_color_to_rgb(sms_col)
                    )
                    if d < best_dist:
                        best_dist = d
                        best = j
                cm[c] = best
            color_maps.append(cm)

        return bytes(sms_palette), color_maps

    def build_all_palettes(self) -> Tuple[bytes, bytes, List[List[int]]]:
        """
        Build both BG and SPR palettes.

        Returns:
            Tuple of (bg_palette, spr_palette, all_color_maps)
        """
        bg_pal, bg_maps = self.build_sms_palette("bg")
        spr_pal, spr_maps = self.build_sms_palette("spr")
        return bg_pal, spr_pal, bg_maps + spr_maps
