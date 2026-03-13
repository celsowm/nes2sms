"""Tests for flow-aware branch condition translation."""

from nes2sms.core.assembly.flow_aware_translator import FlowAwareTranslator
from nes2sms.core.interfaces.i_disassembler import ParsedInstruction


class TestFlowAwareTranslator:
    """Validate condition mapping in flow-aware branch translation."""

    def test_bpl_relative_uses_positive_flag(self):
        translator = FlowAwareTranslator()
        instr = ParsedInstruction(
            address=0x80F8,
            bytes_raw=b"\x10\xFE",
            mnemonic="BPL",
            operands=["$FE"],
        )

        translator._translate_branch(instr)
        assert "JP   P, $80F8" in translator.context.get_code()

    def test_bmi_absolute_uses_minus_flag(self):
        translator = FlowAwareTranslator(symbol_map={0x811C: "sub_811C"})
        instr = ParsedInstruction(
            address=0x80F8,
            bytes_raw=b"\x30\x22",
            mnemonic="BMI",
            operands=["$811C"],
        )

        translator._translate_branch(instr)
        assert "JP   M, sub_811C" in translator.context.get_code()

    def test_pong_cpx_bcc_sequence_keeps_6502_carry(self):
        translator = FlowAwareTranslator(symbol_map={0x826A: "sub_826A"})
        instructions = [
            ParsedInstruction(
                address=0x8248,
                bytes_raw=b"\xE0\x01",
                mnemonic="CPX",
                operands=["#$01"],
            ),
            ParsedInstruction(
                address=0x824A,
                bytes_raw=b"\x90\x1E",
                mnemonic="BCC",
                operands=["$826A"],
            ),
        ]

        result = translator.translate_function(instructions=instructions, function_name="sub_8248")
        assert "CP   $01" in result
        assert "CCF" in result
        assert "JP   NC, sub_826A" in result
