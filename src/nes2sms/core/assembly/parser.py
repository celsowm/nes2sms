"""6502 instruction parsing and representation."""

from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum


class AddressingMode(Enum):
    """6502 addressing modes."""

    IMPLIED = "implied"
    IMMEDIATE = "immediate"
    ZERO_PAGE = "zero_page"
    ZERO_PAGE_X = "zero_page_x"
    ZERO_PAGE_Y = "zero_page_y"
    ABSOLUTE = "absolute"
    ABSOLUTE_X = "absolute_x"
    ABSOLUTE_Y = "absolute_y"
    INDIRECT = "indirect"
    INDIRECT_X = "indirect_x"
    INDIRECT_Y = "indirect_y"
    RELATIVE = "relative"


@dataclass
class ParsedInstruction:
    """Represents a parsed 6502 instruction."""

    mnemonic: str
    addressing_mode: AddressingMode
    operand_value: Optional[int] = None
    operand_text: Optional[str] = None

    def is_immediate(self) -> bool:
        return self.addressing_mode == AddressingMode.IMMEDIATE

    def is_absolute(self) -> bool:
        return self.addressing_mode in (
            AddressingMode.ABSOLUTE,
            AddressingMode.ABSOLUTE_X,
            AddressingMode.ABSOLUTE_Y,
        )

    def is_zero_page(self) -> bool:
        return self.addressing_mode in (
            AddressingMode.ZERO_PAGE,
            AddressingMode.ZERO_PAGE_X,
            AddressingMode.ZERO_PAGE_Y,
        )


class InstructionParser:
    """
    Parses 6502 assembly instructions into structured format.

    Single Responsibility: Only parsing, no translation logic.
    """

    def __init__(self):
        self._mode_cache = {}

    def parse(self, line: str) -> Optional[ParsedInstruction]:
        """
        Parse a single assembly line.

        Args:
            line: Assembly instruction line

        Returns:
            ParsedInstruction or None if not a valid instruction
        """
        line = line.strip()

        # Skip comments, labels, empty lines
        if not line or line.startswith(";") or line.endswith(":"):
            return None

        # Split mnemonic and operand
        parts = line.split(None, 1)
        if not parts:
            return None

        mnemonic = parts[0].upper()
        operand = parts[1] if len(parts) > 1 else ""

        # Validate mnemonic
        if not self._is_valid_mnemonic(mnemonic):
            return None

        # Parse addressing mode
        mode, value, text = self._parse_operand(operand, mnemonic)

        return ParsedInstruction(
            mnemonic=mnemonic, addressing_mode=mode, operand_value=value, operand_text=text
        )

    def _is_valid_mnemonic(self, mnemonic: str) -> bool:
        """Check if mnemonic is a valid 6502 instruction."""
        valid = {
            "LDA",
            "LDX",
            "LDY",
            "STA",
            "STX",
            "STY",
            "ADD",
            "ADC",
            "SUB",
            "SBC",
            "AND",
            "ORA",
            "EOR",
            "CMP",
            "CPX",
            "CPY",
            "INC",
            "DEC",
            "ASL",
            "LSR",
            "ROL",
            "ROR",
            "JMP",
            "JSR",
            "RTS",
            "RTI",
            "BCC",
            "BCS",
            "BEQ",
            "BMI",
            "BNE",
            "BPL",
            "BVC",
            "BVS",
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
            "BIT",
            "DEX",
            "DEY",
            "INX",
            "INY",
            "BRK",
        }
        return mnemonic in valid

    def _parse_operand(
        self, operand: str, mnemonic: str = ""
    ) -> Tuple[AddressingMode, Optional[int], str]:
        """
        Parse operand to determine addressing mode.

        Returns:
            Tuple of (mode, numeric_value, original_text)
        """
        operand = operand.strip()

        # Branch instructions always use relative addressing
        BRANCH_MNEMONICS = {"BPL", "BMI", "BEQ", "BNE", "BCC", "BCS", "BVC", "BVS", "BRA"}
        if mnemonic.upper() in BRANCH_MNEMONICS:
            value = self._parse_value(operand)
            return (AddressingMode.RELATIVE, value, operand)

        if not operand:
            return (AddressingMode.IMPLIED, None, "")

        # Immediate: #value
        if operand.startswith("#"):
            value = self._parse_value(operand[1:])
            return (AddressingMode.IMMEDIATE, value, operand)

        # Indirect X: (value,X)
        if operand.startswith("(") and ",X)" in operand.upper():
            inner = operand[1:-3]
            value = self._parse_value(inner)
            return (AddressingMode.INDIRECT_X, value, operand)

        # Indirect Y: (value),Y
        if operand.startswith("(") and "),Y" in operand.upper():
            inner = operand[1:-3]
            value = self._parse_value(inner)
            return (AddressingMode.INDIRECT_Y, value, operand)

        # Absolute/Zero Page with X/Y suffix
        if "," in operand:
            parts = operand.split(",")
            base = parts[0].strip()
            suffix = parts[1].strip().upper()
            base_value = self._parse_value(base)

            if suffix == "X":
                if len(base.lstrip("$")) <= 2:
                    return (AddressingMode.ZERO_PAGE_X, base_value, operand)
                else:
                    return (AddressingMode.ABSOLUTE_X, base_value, operand)
            elif suffix == "Y":
                if len(base.lstrip("$")) <= 2:
                    return (AddressingMode.ZERO_PAGE_Y, base_value, operand)
                else:
                    return (AddressingMode.ABSOLUTE_Y, base_value, operand)

        # Absolute or Zero Page
        value = self._parse_value(operand)
        if len(operand.lstrip("$")) <= 2:
            return (AddressingMode.ZERO_PAGE, value, operand)
        else:
            return (AddressingMode.ABSOLUTE, value, operand)

    def _parse_value(self, text: str) -> Optional[int]:
        """Parse numeric value from text (hex, decimal, binary)."""
        text = text.strip().upper()

        try:
            if text.startswith("$"):
                return int(text[1:], 16)
            elif text.startswith("%"):
                return int(text[1:], 2)
            elif text.startswith("0X"):
                return int(text[2:], 16)
            else:
                return int(text, 10)
        except ValueError:
            return None
