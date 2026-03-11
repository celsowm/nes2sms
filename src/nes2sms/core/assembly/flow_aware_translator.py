"""Flow-aware translator for 6502 to Z80."""

from typing import List, Optional

from .control_flow_analyzer import ControlFlowAnalyzer
from .translation_context import TranslationContext
from .instruction_translator import InstructionTranslator
from ..interfaces.i_disassembler import ParsedInstruction
from ..interfaces.i_translator import ITranslator


class FlowAwareTranslator(ITranslator):
    """
    Translator that considers control flow structure.

    OCP: Can extend with new translation patterns.
    DIP: Depends on interfaces (ITranslator, IControlFlowAnalyzer).
    """

    def __init__(
        self,
        instruction_translator: Optional[InstructionTranslator] = None,
        flow_analyzer: Optional[ControlFlowAnalyzer] = None,
    ):
        """
        Initialize flow-aware translator.

        Args:
            instruction_translator: Base instruction translator
            flow_analyzer: Control flow analyzer
        """
        self.instruction_translator = instruction_translator or InstructionTranslator()
        self.flow_analyzer = flow_analyzer or ControlFlowAnalyzer()
        self.context = TranslationContext()

    def translate_line(self, line: str, address: Optional[int] = None) -> str:
        """
        Translate a single line (legacy API).

        Args:
            line: 6502 assembly instruction
            address: Optional address

        Returns:
            Z80 assembly line(s)
        """
        return self.instruction_translator.translate_line(line, address)

    def translate_block(self, lines: List[str], start_address: int = 0) -> str:
        """
        Translate a block of 6502 assembly (legacy API).

        Args:
            lines: List of 6502 instructions
            start_address: Starting address

        Returns:
            Complete Z80 assembly
        """
        return self.instruction_translator.translate_block(lines, start_address)

    def translate_function(
        self,
        instructions: List[ParsedInstruction],
        function_name: str,
    ) -> str:
        """
        Translate complete function with control flow awareness.

        Args:
            instructions: Parsed 6502 instructions
            function_name: Function name for label

        Returns:
            Complete Z80 assembly for function
        """
        self.context.reset()
        self.context.enter_subroutine(function_name)

        # Analyze control flow
        cfg = self.flow_analyzer.analyze(instructions)

        # Identify loops for label generation
        for loop in cfg.loops:
            self.context.enter_loop(loop.header_addr)

        # Translate each instruction in order
        sorted_instrs = sorted(instructions, key=lambda i: i.address)

        for instr in sorted_instrs:
            self._translate_instruction(instr)

        self.context.exit_subroutine()
        return self.context.get_code()

    def _translate_instruction(self, instr: ParsedInstruction):
        """
        Translate single instruction with flow awareness.

        Args:
            instr: Parsed instruction
        """
        # Add label if present
        if instr.label:
            self.context.add_label(instr.label)

        # Check if this is a loop header
        if instr.address in self.context.loop_labels:
            loop_label = self.context.loop_labels[instr.address]
            self.context.add_label(loop_label)

        # Translate based on instruction type
        if instr.mnemonic in {"BCC", "BCS", "BEQ", "BNE", "BMI", "BPL", "BVC", "BVS"}:
            self._translate_branch(instr)
        elif instr.mnemonic == "JMP":
            self._translate_jump(instr)
        elif instr.mnemonic == "JSR":
            self._translate_call(instr)
        elif instr.mnemonic in {"RTS", "RTI"}:
            self._translate_return(instr)
        else:
            self._translate_regular(instr)

    def _translate_branch(self, instr: ParsedInstruction):
        """Translate branch instruction."""
        # Get Z80 condition
        condition_map = {
            "BCC": "NC",
            "BCS": "C",
            "BEQ": "Z",
            "BNE": "NZ",
            "BMI": "M",
            "BPL": "NZ",
            "BVC": "PO",
            "BVS": "PE",
        }
        condition = condition_map.get(instr.mnemonic, "NZ")

        # Get target operand
        if not instr.operands:
            self.context.add_code(f"    ; TODO: {instr.mnemonic} - no target")
            return

        target = instr.operands[0]

        # Calculate absolute address from relative offset
        target_addr = None
        if target.startswith("$") or target.startswith("#$"):
            # Extract numeric value
            clean_target = target.lstrip("#$")
            try:
                offset_val = int(clean_target, 16)
                # Sign-extend if high bit is set (branch offset)
                if offset_val >= 0x80:
                    offset_val = offset_val - 0x100
                # Calculate absolute address: current + 2 (branch size) + offset
                target_addr = (instr.address + 2 + offset_val) & 0xFFFF
                # Use absolute address in hex format
                target = f"${target_addr:04X}"
            except ValueError:
                pass

        # Check if target is a known label (via loop labels)
        if target_addr and target_addr in self.context.loop_labels:
            target_label = self.context.loop_labels[target_addr]
            self.context.add_code(f"    JP   {condition}, {target_label}")
            return

        # Use the calculated absolute address (already formatted as $XXXX)
        self.context.add_code(f"    JP   {condition}, {target}")

    def _translate_jump(self, instr: ParsedInstruction):
        """Translate JMP instruction."""
        target = instr.operands[0] if instr.operands else "unknown"

        # Check if target is a loop header
        target_addr = self._parse_address(target)
        if target_addr and target_addr in self.context.loop_labels:
            target_label = self.context.loop_labels[target_addr]
            self.context.add_code(f"    JR   {target_label}")
        else:
            self.context.add_code(f"    JP   {target}")

    def _translate_call(self, instr: ParsedInstruction):
        """Translate JSR instruction."""
        target = instr.operands[0] if instr.operands else "unknown"
        self.context.add_code(f"    CALL {target}")

    def _translate_return(self, instr: ParsedInstruction):
        """Translate RTS/RTI instruction."""
        if instr.mnemonic == "RTI":
            self.context.add_code("    EI")
            self.context.add_code("    RETI")
        else:
            self.context.add_code("    RET")

    def _translate_regular(self, instr: ParsedInstruction):
        """Translate regular instruction."""
        # Handle both interface ParsedInstruction and parser ParsedInstruction
        if hasattr(instr, "to_string"):
            # Interface ParsedInstruction
            line = instr.to_string()
        else:
            # Parser ParsedInstruction
            ops = " ".join(instr.operands) if instr.operands else ""
            line = f"{instr.mnemonic} {ops}".strip()

        translated = self.instruction_translator.translate_line(line)

        # Add to context
        for line in translated.split("\n"):
            if line.strip():
                self.context.add_code(line)

    def _parse_address(self, operand: str) -> Optional[int]:
        """Parse address from operand string."""
        if not operand:
            return None

        # Remove parentheses
        operand = operand.strip("()")

        # Hexadecimal
        if operand.startswith("$"):
            try:
                return int(operand[1:], 16)
            except ValueError:
                pass

        # Decimal
        try:
            return int(operand)
        except ValueError:
            pass

        return None

    def is_supported(self, mnemonic: str) -> bool:
        """Check if instruction is supported."""
        return self.instruction_translator.is_supported(mnemonic)

    def get_supported_instructions(self) -> List[str]:
        """Get list of supported instructions."""
        return self.instruction_translator.get_supported_instructions()
