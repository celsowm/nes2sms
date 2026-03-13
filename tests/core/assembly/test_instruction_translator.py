"""Tests for 6502 to Z80 instruction translator."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from nes2sms.core.assembly.instruction_translator import InstructionTranslator
from nes2sms.core.assembly.registers import FlagMapping, RegisterMapping, CallingConvention


class TestRegisterMapping:
    """Test register mapping."""

    def test_get_z80_reg(self):
        """Test 6502 to Z80 register mapping."""
        reg_map = RegisterMapping()

        assert reg_map.get_z80_reg("A") == "a"
        assert reg_map.get_z80_reg("X") == "b"
        assert reg_map.get_z80_reg("Y") == "c"

    def test_get_6502_reg(self):
        """Test Z80 to 6502 register mapping."""
        reg_map = RegisterMapping()

        assert reg_map.get_6502_reg("a") == "A"
        assert reg_map.get_6502_reg("b") == "X"
        assert reg_map.get_6502_reg("c") == "Y"


class TestFlagMapping:
    """Test flag mapping."""

    def test_get_z80_flag(self):
        """Test 6502 to Z80 flag mapping."""
        assert FlagMapping.get_z80_flag("N") == "S"
        assert FlagMapping.get_z80_flag("Z") == "Z"
        assert FlagMapping.get_z80_flag("C") == "C"
        assert FlagMapping.get_z80_flag("V") == "P"

    def test_get_condition(self):
        """Test branch condition mapping."""
        assert FlagMapping.get_condition("BCC") == "NC"
        assert FlagMapping.get_condition("BCS") == "C"
        assert FlagMapping.get_condition("BEQ") == "Z"
        assert FlagMapping.get_condition("BNE") == "NZ"
        assert FlagMapping.get_condition("BMI") == "M"
        assert FlagMapping.get_condition("BPL") == "P"


class TestCallingConvention:
    """Test calling convention."""

    def test_default_convention(self):
        """Test default calling convention values."""
        conv = CallingConvention()

        assert conv.return_reg_8 == "a"
        assert conv.return_reg_16 == "hl"
        assert "af" in conv.caller_save


class TestInstructionTranslator:
    """Test instruction translation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.translator = InstructionTranslator()

    def test_translate_lda_immediate(self):
        """Test LDA #imm translation."""
        result = self.translator.translate_line("LDA #$42")
        assert "LD   a, $42" in result

    def test_translate_lda_absolute(self):
        """Test LDA abs translation."""
        result = self.translator.translate_line("LDA $1234")
        assert "LD   hl, $1234h" in result
        assert "LD   a, (HL)" in result

    def test_translate_sta_absolute(self):
        """Test STA abs translation."""
        result = self.translator.translate_line("STA $2123")
        assert "LD   hl, $2123h" in result
        assert "LD   (HL), a" in result

    def test_translate_ldx(self):
        """Test LDX translation."""
        result = self.translator.translate_line("LDX #$00")
        assert "LD   b, $00" in result

    def test_translate_ldy(self):
        """Test LDY translation."""
        result = self.translator.translate_line("LDY #$10")
        assert "LD   c, $10" in result

    def test_translate_stx(self):
        """Test STX translation."""
        result = self.translator.translate_line("STX $00")
        assert "LD   (00h), b" in result

    def test_translate_add(self):
        """Test ADD translation."""
        result = self.translator.translate_line("ADC #$01")
        assert "ADC" in result

    def test_translate_sub(self):
        """Test SUB/SBC translation."""
        result = self.translator.translate_line("SBC #$01")
        assert "SBC" in result

    def test_translate_and(self):
        """Test AND translation."""
        result = self.translator.translate_line("AND #$FF")
        assert "AND" in result

    def test_translate_ora(self):
        """Test ORA translation."""
        result = self.translator.translate_line("ORA #$01")
        assert "OR" in result

    def test_translate_eor(self):
        """Test EOR translation."""
        result = self.translator.translate_line("EOR #$FF")
        assert "XOR" in result

    def test_translate_cmp(self):
        """Test CMP translation."""
        result = self.translator.translate_line("CMP #$42")
        assert "CP" in result

    def test_translate_jmp(self):
        """Test JMP translation."""
        result = self.translator.translate_line("JMP $8000")
        assert "JP   $8000" in result

    def test_translate_jsr(self):
        """Test JSR translation."""
        result = self.translator.translate_line("JSR $FF00")
        assert "CALL $FF00" in result

    def test_translate_rts(self):
        """Test RTS translation."""
        result = self.translator.translate_line("RTS")
        assert "RET" in result

    def test_translate_rti(self):
        """Test RTI translation."""
        result = self.translator.translate_line("RTI")
        assert "RETI" in result

    def test_translate_branch(self):
        """Test branch translations."""
        assert "JP   NC" in self.translator.translate_line("BCC label")
        assert "JP   C" in self.translator.translate_line("BCS label")
        assert "JP   Z" in self.translator.translate_line("BEQ label")
        assert "JP   NZ" in self.translator.translate_line("BNE label")

    def test_translate_tax(self):
        """Test TAX translation."""
        result = self.translator.translate_line("TAX")
        assert "LD   b, a" in result

    def test_translate_tay(self):
        """Test TAY translation."""
        result = self.translator.translate_line("TAY")
        assert "LD   c, a" in result

    def test_translate_txa(self):
        """Test TXA translation."""
        result = self.translator.translate_line("TXA")
        assert "LD   a, b" in result

    def test_translate_tya(self):
        """Test TYA translation."""
        result = self.translator.translate_line("TYA")
        assert "LD   a, c" in result

    def test_translate_inx(self):
        """Test INX translation."""
        result = self.translator.translate_line("INX")
        assert "INC  B" in result

    def test_translate_iny(self):
        """Test INY translation."""
        result = self.translator.translate_line("INY")
        assert "INC  C" in result

    def test_translate_dex(self):
        """Test DEX translation."""
        result = self.translator.translate_line("DEX")
        assert "DEC  B" in result

    def test_translate_dey(self):
        """Test DEY translation."""
        result = self.translator.translate_line("DEY")
        assert "DEC  C" in result

    def test_translate_pha(self):
        """Test PHA translation."""
        result = self.translator.translate_line("PHA")
        assert "PUSH" in result

    def test_translate_pla(self):
        """Test PLA translation."""
        result = self.translator.translate_line("PLA")
        assert "POP" in result

    def test_translate_nop(self):
        """Test NOP translation."""
        result = self.translator.translate_line("NOP")
        assert "NOP" in result

    def test_translate_clc(self):
        """Test CLC translation."""
        result = self.translator.translate_line("CLC")
        assert "AND  A" in result  # Common Z80 idiom to clear carry

    def test_translate_sec(self):
        """Test SEC translation."""
        result = self.translator.translate_line("SEC")
        assert "SCF" in result

    def test_translate_comment(self):
        """Test that comments are preserved."""
        result = self.translator.translate_line("; This is a comment")
        assert "; This is a comment" in result

    def test_translate_label(self):
        """Test that labels are preserved."""
        result = self.translator.translate_line("MyLabel:")
        assert "MyLabel:" in result

    def test_translate_unknown(self):
        """Test unknown instruction handling."""
        result = self.translator.translate_line("UNKNOWN $42")
        assert "TODO" in result

    def test_translate_block(self):
        """Test translating a block of instructions."""
        lines = [
            "Reset:",
            "    LDA #$00",
            "    TAX",
            "    TAY",
            "    RTS",
        ]

        result = self.translator.translate_block(lines, start_address=0xFFFC)
        assert "Reset:" in result
        assert "LD   a, $00" in result
        assert "LD   b, a" in result  # TAX
        assert "LD   c, a" in result  # TAY
        assert "RET" in result
