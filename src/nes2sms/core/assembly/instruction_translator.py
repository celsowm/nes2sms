"""6502 to Z80 instruction translator - Refactored with Strategy Pattern."""

from typing import Dict, List, Optional
from .parser import InstructionParser, ParsedInstruction, AddressingMode
from .strategies import (
    TranslationStrategy,
    LoadAccumulatorStrategy,
    StoreAccumulatorStrategy,
    StoreXStrategy,
    StoreYStrategy,
    LoadXStrategy,
    LoadYStrategy,
    JumpStrategy,
    JumpSubroutineStrategy,
    ReturnStrategy,
    ReturnInterruptStrategy,
    BranchStrategy,
    TransferStrategy,
    StackStrategy,
    FlagStrategy,
    IncrementDecrementStrategy,
    ArithmeticLogicStrategy,
    CompareRegisterStrategy,
    ShiftRotateStrategy,
    NopStrategy,
    BitTestStrategy,
)
from ..sms.hal_generator import HALGenerator
from ..nes.mapper import MapperStrategy


class InstructionTranslator:
    """
    Translates 6502 assembly to Z80 using Strategy Pattern.

    S.O.L.I.D. Principles:
    - Single Responsibility: Parser handles parsing, strategies handle translation
    - Open/Closed: New instructions added via new strategy classes
    - Liskov Substitution: All strategies implement TranslationStrategy interface
    - Interface Segregation: Small, focused strategy interfaces
    - Dependency Inversion: Depends on abstractions (Strategy interface)
    """

    def __init__(self):
        self.parser = InstructionParser()
        self.strategies: Dict[str, TranslationStrategy] = {}
        self._register_default_strategies()

    def _register_default_strategies(self):
        """Register default translation strategies."""
        self.register_strategy("LDA", LoadAccumulatorStrategy())
        self.register_strategy("STA", StoreAccumulatorStrategy())
        self.register_strategy("STX", StoreXStrategy())
        self.register_strategy("STY", StoreYStrategy())
        self.register_strategy("LDX", LoadXStrategy())
        self.register_strategy("LDY", LoadYStrategy())
        self.register_strategy("JMP", JumpStrategy())
        self.register_strategy("JSR", JumpSubroutineStrategy())
        self.register_strategy("RTS", ReturnStrategy())
        self.register_strategy("RTI", ReturnInterruptStrategy())
        self.register_strategy("TAX", TransferStrategy())
        self.register_strategy("TAY", TransferStrategy())
        self.register_strategy("TXA", TransferStrategy())
        self.register_strategy("TYA", TransferStrategy())
        self.register_strategy("TSX", TransferStrategy())
        self.register_strategy("TXS", TransferStrategy())
        self.register_strategy("PHA", StackStrategy())
        self.register_strategy("PLA", StackStrategy())
        self.register_strategy("PHP", StackStrategy())
        self.register_strategy("PLP", StackStrategy())
        self.register_strategy("CLC", FlagStrategy())
        self.register_strategy("SEC", FlagStrategy())
        self.register_strategy("CLI", FlagStrategy())
        self.register_strategy("SEI", FlagStrategy())
        self.register_strategy("CLV", FlagStrategy())
        self.register_strategy("CLD", FlagStrategy())
        self.register_strategy("SED", FlagStrategy())
        self.register_strategy("INX", IncrementDecrementStrategy())
        self.register_strategy("INY", IncrementDecrementStrategy())
        self.register_strategy("DEX", IncrementDecrementStrategy())
        self.register_strategy("DEY", IncrementDecrementStrategy())
        self.register_strategy("INC", IncrementDecrementStrategy())
        self.register_strategy("DEC", IncrementDecrementStrategy())
        self.register_strategy("ADC", ArithmeticLogicStrategy())
        self.register_strategy("SBC", ArithmeticLogicStrategy())
        self.register_strategy("AND", ArithmeticLogicStrategy())
        self.register_strategy("ORA", ArithmeticLogicStrategy())
        self.register_strategy("EOR", ArithmeticLogicStrategy())
        self.register_strategy("CMP", ArithmeticLogicStrategy())
        self.register_strategy("ADD", ArithmeticLogicStrategy())
        self.register_strategy("SUB", ArithmeticLogicStrategy())
        self.register_strategy("CPX", CompareRegisterStrategy())
        self.register_strategy("CPY", CompareRegisterStrategy())
        self.register_strategy("ASL", ShiftRotateStrategy())
        self.register_strategy("LSR", ShiftRotateStrategy())
        self.register_strategy("ROL", ShiftRotateStrategy())
        self.register_strategy("ROR", ShiftRotateStrategy())
        self.register_strategy("NOP", NopStrategy())
        self.register_strategy("BIT", BitTestStrategy())

        # Branch instructions
        for branch in ["BCC", "BCS", "BEQ", "BNE", "BMI", "BPL", "BVC", "BVS"]:
            self.register_strategy(branch, BranchStrategy())

    def register_strategy(self, mnemonic: str, strategy: TranslationStrategy):
        """
        Register a translation strategy for an instruction.

        Open/Closed: Allows adding new strategies without modifying the translator.

        Args:
            mnemonic: Instruction mnemonic (e.g., "LDA")
            strategy: TranslationStrategy instance
        """
        self.strategies[mnemonic.upper()] = strategy

    def translate(self, mnemonic: str, operand: str = "") -> List[str]:
        """
        Translate a single instruction by mnemonic and operand.

        Args:
            mnemonic: Instruction mnemonic
            operand: Operand string

        Returns:
            List of Z80 assembly lines
        """
        # Create pseudo-line for parsing
        line = f"{mnemonic} {operand}".strip()
        parsed = self.parser.parse(line)

        if not parsed:
            return [f"    ; TODO: {line}"]

        return self.translate_parsed(parsed)

    def translate_parsed(self, instruction: ParsedInstruction) -> List[str]:
        """
        Translate a parsed instruction.

        Args:
            instruction: ParsedInstruction object

        Returns:
            List of Z80 assembly lines
        """
        strategy = self.strategies.get(instruction.mnemonic)

        if strategy:
            return strategy.translate(instruction)

        # No strategy registered - return TODO
        return [f"    ; TODO: {instruction.mnemonic} {instruction.operand_text or ''}"]

    def translate_line(self, line: str, address: Optional[int] = None) -> str:
        """
        Translate a single line of assembly (legacy API).

        Args:
            line: Assembly line
            address: Optional address for comment

        Returns:
            Z80 assembly line(s) as string
        """
        line = line.strip()

        # Pass through comments, labels, empty lines
        if not line or line.startswith(";") or line.endswith(":"):
            return line

        parsed = self.parser.parse(line)

        if not parsed:
            return f"    ; TODO: {line}"

        z80_lines = self.translate_parsed(parsed)

        if address is not None:
            comment = f"; 6502: {line}"
            return f"{comment}\n" + "\n".join(z80_lines)

        return "\n".join(z80_lines)

    def translate_block(self, lines: List[str], start_address: int = 0) -> str:
        """
        Translate a block of assembly lines.

        Args:
            lines: List of assembly lines
            start_address: Starting address for reference

        Returns:
            Complete Z80 assembly as string
        """
        translated = []
        addr = start_address

        for line in lines:
            if line.strip().endswith(":") or not line.strip() or line.strip().startswith(";"):
                translated.append(line)
            else:
                result = self.translate_line(line, addr)
                translated.append(result)
                addr += self._estimate_size(line)

        return "\n".join(translated)

    def _estimate_size(self, line: str) -> int:
        """Estimate instruction size in bytes."""
        line = line.strip().split(";")[0].strip()
        if not line:
            return 0

        parts = line.split(None, 1)
        mnemonic = parts[0].upper()

        implied = [
            "RTS",
            "RTI",
            "PHA",
            "PLA",
            "PHP",
            "PLP",
            "TAX",
            "TAY",
            "TXA",
            "TYA",
            "TSX",
            "TXS",
            "NOP",
            "CLC",
            "SEC",
            "CLI",
            "SEI",
            "CLV",
            "CLD",
            "SED",
            "DEX",
            "DEY",
            "INX",
            "INY",
        ]

        if mnemonic in implied:
            return 1
        elif mnemonic.startswith("B"):
            return 2
        else:
            if len(parts) > 1:
                operand = parts[1]
                if operand.startswith("#") or (operand.startswith("$") and len(operand) == 3):
                    return 2
                else:
                    return 3
            return 1

    def get_supported_instructions(self) -> List[str]:
        """Get list of supported instruction mnemonics."""
        return sorted(self.strategies.keys())

    def is_supported(self, mnemonic: str) -> bool:
        """Check if an instruction is supported."""
        return mnemonic.upper() in self.strategies

    def get_support_code(self, mapper_strategy: MapperStrategy) -> str:
        """
        Generate the complete support library (HAL + Mapper).

        Args:
            mapper_strategy: The NES mapper strategy being used.

        Returns:
            Z80 assembly string with HAL and Mapper routines.
        """
        hal_gen = HALGenerator()
        hal_code = hal_gen.generate_all()
        
        mapper_code = "\n".join(mapper_strategy.generate_banking_code())
        
        return f"{hal_code}\n\n; Mapper Routines\n{mapper_code}"
