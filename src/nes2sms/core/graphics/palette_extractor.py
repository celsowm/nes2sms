"""Extract palette data written to NES PPU from PRG ROM code."""

from typing import List, Optional


class PaletteExtractor:
    """
    Scans NES PRG code for palette writes to PPU $3F00+.

    Detects the pattern:
      LDA/LDX #$3F → STA/STX $2006
      LDA/LDX #$xx → STA/STX $2006   (sets PPU address to $3Fxx)
      ... data loaded and written to $2007
    """

    def __init__(self, prg_data: bytes, base_address: int = 0x8000):
        self.prg_data = prg_data
        self.base_address = base_address

    def extract_palette(self) -> Optional[List[int]]:
        """
        Extract NES palette colors from PRG code.

        Returns:
            List of up to 32 NES color indices (BG + SPR palettes), or None
        """
        # Find PPU $2006 write pairs targeting $3Fxx
        ppu_addr, data_src, count = self._find_palette_write()
        if ppu_addr is None:
            return None

        # Build 32-entry palette RAM (BG 0-15, SPR 16-31)
        palette_ram = [0x0F] * 32  # default to black

        offset = ppu_addr - 0x3F00
        if data_src is not None and count > 0:
            src_offset = data_src - self.base_address
            for i in range(count):
                if src_offset + i < len(self.prg_data):
                    color = self.prg_data[src_offset + i] & 0x3F
                    idx = offset + i
                    if idx < 32:
                        palette_ram[idx] = color

        # Mirror BG palette 0 to SPR palette 0 if SPR palette wasn't set
        # (many simple ROMs only set BG palette)
        if all(c == 0x0F for c in palette_ram[16:20]):
            for i in range(4):
                palette_ram[16 + i] = palette_ram[i]

        return palette_ram

    def _find_palette_write(self):
        """
        Find the palette write pattern in PRG code.

        Returns:
            Tuple of (ppu_target_addr, data_source_addr, byte_count) or (None, None, None)
        """
        prg = self.prg_data

        for i in range(len(prg) - 10):
            # Look for: LDA/LDX #$3F followed by STA/STX $2006
            if not self._is_load_imm(prg, i, 0x3F):
                continue
            if not self._is_store_2006(prg, i + 2):
                continue

            # Next: LDA/LDX #$xx followed by STA/STX $2006
            if not self._is_load_imm_any(prg, i + 5):
                continue
            if not self._is_store_2006(prg, i + 7):
                continue

            low_byte = prg[i + 6]  # the #$xx value
            ppu_addr = 0x3F00 | low_byte

            # Now find the data source - scan ahead for the write loop
            data_src, count = self._find_data_source(i + 10)
            if data_src is not None:
                return ppu_addr, data_src, count

        return None, None, None

    def _find_data_source(self, start_pos: int):
        """
        Find the data source address and byte count for PPU $2007 writes.

        Looks for patterns like:
          LDA addr,X / STA $2007 / INX / CPX #count / BNE
        """
        prg = self.prg_data

        for i in range(start_pos, min(start_pos + 20, len(prg) - 5)):
            # LDA absolute,X: BD xx xx
            if prg[i] == 0xBD and i + 5 < len(prg):
                data_addr = prg[i + 1] | (prg[i + 2] << 8)
                # Look for CPX #count nearby
                for j in range(i + 3, min(i + 15, len(prg) - 1)):
                    if prg[j] == 0xE0:  # CPX immediate
                        count = prg[j + 1]
                        return data_addr, count

            # LDA absolute,Y: B9 xx xx
            if prg[i] == 0xB9 and i + 5 < len(prg):
                data_addr = prg[i + 1] | (prg[i + 2] << 8)
                for j in range(i + 3, min(i + 15, len(prg) - 1)):
                    if prg[j] == 0xC0:  # CPY immediate
                        count = prg[j + 1]
                        return data_addr, count

        return None, None

    @staticmethod
    def _is_load_imm(prg: bytes, pos: int, value: int) -> bool:
        """Check for LDA #value or LDX #value at pos."""
        if pos + 1 >= len(prg):
            return False
        return prg[pos] in (0xA9, 0xA2) and prg[pos + 1] == value

    @staticmethod
    def _is_load_imm_any(prg: bytes, pos: int) -> bool:
        """Check for LDA #xx or LDX #xx at pos."""
        if pos >= len(prg):
            return False
        return prg[pos] in (0xA9, 0xA2)

    @staticmethod
    def _is_store_2006(prg: bytes, pos: int) -> bool:
        """Check for STA $2006 or STX $2006 at pos."""
        if pos + 2 >= len(prg):
            return False
        return prg[pos] in (0x8D, 0x8E) and prg[pos + 1] == 0x06 and prg[pos + 2] == 0x20
