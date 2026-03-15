"""Tests for NES hardware register interception during translation."""

import pytest
from nes2sms.core.assembly.instruction_translator import InstructionTranslator


class TestHardwareMapping:
    """Test hardware register mapping to HAL calls."""

    def setup_method(self):
        """Set up test fixtures."""
        self.translator = InstructionTranslator()

    def test_ppu_write_interception(self):
        """Test that STA $2000 is intercepted and maps to hal_ppu_write."""
        result = self.translator.translate_line("STA $2000")
        assert "CALL hal_ppu_write" in result
        assert "LD   l, 0" in result  # Offset 0 for $2000

    def test_ppu_vram_write_interception(self):
        """Test that STA $2007 (PPU Data) is intercepted."""
        result = self.translator.translate_line("STA $2007")
        assert "CALL hal_ppu_write" in result
        assert "LD   l, 7" in result

    def test_oam_dma_interception(self):
        """Test that STA $4014 is intercepted for OAM DMA."""
        result = self.translator.translate_line("STA $4014")
        assert "CALL hal_oam_dma" in result

    def test_apu_write_interception(self):
        """Test that STA $4000 (APU Pulse 1) is intercepted."""
        result = self.translator.translate_line("STA $4000")
        assert "CALL hal_apu_write" in result
        assert "LD   l, 0" in result

    def test_input_read_interception(self):
        """Test that LDA $4016 (Joypad 1) is intercepted."""
        result = self.translator.translate_line("LDA $4016")
        assert "CALL hal_input_read" in result
        assert "LD   l, 0" in result

    def test_input_write_interception_for_4017(self):
        """Test that STA $4017 remains mapped to hal_input_write (port 1)."""
        result = self.translator.translate_line("STA $4017")
        assert "CALL hal_input_write" in result
        assert "LD   l, 1" in result

    def test_normal_memory_not_intercepted(self):
        """Test that normal RAM access is NOT intercepted."""
        result = self.translator.translate_line("STA $1234")
        assert "CALL _hal" not in result
        assert "LD   hl, $1234h" in result
        assert "LD   (HL), a" in result

    def test_zero_page_hardware_interception(self):
        """Test that hardware registers in zero-page range (if any) are intercepted."""
        # Note: NES doesn't have registers in ZP $00-$FF, but just in case
        # $2000 is not ZP. But $4000 is also not ZP.
        # However, let's test a hypothetical range if we had one.
        pass
