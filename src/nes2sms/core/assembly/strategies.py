"""Z80 code generation strategies for 6502 instructions."""

from abc import ABC, abstractmethod
from typing import List, Optional
from .parser import ParsedInstruction, AddressingMode
from .hardware_interceptor import HardwareInterceptorRegistry

# Central registry for hardware redirection
_INTERCEPTOR = HardwareInterceptorRegistry()

# NES RAM ($0000-$07FF) is relocated to SMS RAM ($C000-$C7FF)
NES_RAM_BASE = 0x0000
NES_RAM_END = 0x07FF
SMS_RAM_BASE = 0xC000


def _relocate_address(addr: int) -> int:
    """Relocate NES RAM address to SMS RAM space."""
    if NES_RAM_BASE <= addr <= NES_RAM_END:
        return addr + SMS_RAM_BASE
    return addr


def _hex8h(val: int) -> str:
    """Format 8-bit value as WLA-DX hex (e.g., 0xA2 -> 0A2h)."""
    hex_str = f"{val:02X}"
    if hex_str[0].isalpha():
        return f"0{hex_str}h"
    return f"{hex_str}h"


def _hex16h(val: int) -> str:
    """Format 16-bit value as WLA-DX hex (e.g., 0xBCDE -> 0BCDEh)."""
    hex_str = f"{val:04X}"
    if hex_str[0].isalpha():
        return f"0{hex_str}h"
    return f"{hex_str}h"


def _hex_paren(val: int, bits: int = 16) -> str:
    """Format address in parentheses. Always use 16-bit for Z80 memory operands."""
    return f"({_hex16h(val)})"


def _normalize_hex(text: Optional[str]) -> str:
    """Convert 6502 hex format ($XX or $XXXX) to WLA-DX format (XXh or XXXXh).

    Also handles malformed addresses like $009D which should be $9D (zero page).
    """
    if not text:
        return text or ""
    if text.startswith("$"):
        hex_part = text[1:]
        try:
            val = int(hex_part, 16)
        except ValueError:
            return text
        if val <= 0xFF:
            return f"{val:02X}h"
        else:
            return f"{val:04X}h"
    return text


def _normalize_hex_paren(text: Optional[str], force_paren: bool = False) -> str:
    """Convert 6502 hex in parentheses to WLA-DX format.

    Args:
        text: The operand text (e.g., "$9D" or "($9D)")
        force_paren: If True, always wrap in parentheses (for memory operations)
    """
    if not text:
        return text or ""

    original = text

    if text.startswith("(") and text.endswith(")"):
        inner = text[1:-1]
        return f"({_normalize_hex(inner)})"

    if force_paren or (text.startswith("$") and not text.startswith("#")):
        return f"({_normalize_hex(text)})"

    return text


class TranslationStrategy(ABC):
    """
    Strategy interface for instruction translation.

    Open/Closed Principle: New instructions can be added without modifying existing code.
    """

    @abstractmethod
    def translate(self, instruction: ParsedInstruction) -> List[str]:
        """
        Translate instruction to Z80 assembly.

        Args:
            instruction: Parsed 6502 instruction

        Returns:
            List of Z80 assembly lines
        """
        pass


class LoadAccumulatorStrategy(TranslationStrategy):
    """Translation strategy for LDA instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        mode = instruction.addressing_mode
        addr_val = instruction.operand_value

        if mode == AddressingMode.IMMEDIATE:
            return [f"    LD   a, ${_hex8h(addr_val or 0)}"]

        elif mode == AddressingMode.IMPLIED:
            # LDA without operand - likely misinterpreted opcode, use A register
            return ["    ; LDA implied - use A directly"]

        elif mode == AddressingMode.ABSOLUTE:
            if addr_val is not None:
                intercept = _INTERCEPTOR.intercept_read(addr_val, "a")
                if intercept:
                    return intercept
                relocated = _relocate_address(addr_val)
                return [
                    f"    LD   hl, ${_hex16h(relocated)}",
                    "    LD   a, (HL)",
                ]
            return ["    ; TODO: LDA"]

        elif mode == AddressingMode.ZERO_PAGE:
            if addr_val is not None:
                intercept = _INTERCEPTOR.intercept_read(addr_val, "a")
                if intercept:
                    return intercept
            relocated = _relocate_address(addr_val or 0)
            return [f"    LD   a, {_hex_paren(relocated, 8)}"]

        elif mode == AddressingMode.ABSOLUTE_X:
            relocated = _relocate_address(addr_val or 0)
            return [
                "    LD   e, b",
                "    LD   d, 0",
                f"    LD   hl, ${_hex16h(relocated)}",
                "    ADD  HL, DE",
                "    LD   a, (HL)",
            ]

        elif mode == AddressingMode.ABSOLUTE_Y:
            relocated = _relocate_address(addr_val or 0)
            return [
                "    LD   e, c",
                "    LD   d, 0",
                f"    LD   hl, ${_hex16h(relocated)}",
                "    ADD  HL, DE",
                "    LD   a, (HL)",
            ]

        return [f"    LD   a, {instruction.operand_text}"]


class StoreAccumulatorStrategy(TranslationStrategy):
    """Translation strategy for STA instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        mode = instruction.addressing_mode
        addr_val = instruction.operand_value or 0

        if mode == AddressingMode.ABSOLUTE:
            if addr_val is not None:
                # Check for hardware interception
                intercept = _INTERCEPTOR.intercept_write(addr_val, "a")
                if intercept:
                    return intercept
                relocated = _relocate_address(addr_val)
                return [
                    f"    LD   hl, ${_hex16h(relocated)}",
                    "    LD   (HL), a",
                ]

        elif mode == AddressingMode.ZERO_PAGE:
            if addr_val is not None:
                intercept = _INTERCEPTOR.intercept_write(addr_val, "a")
                if intercept:
                    return intercept
            relocated = _relocate_address(addr_val or 0)
            return [f"    LD   {_hex_paren(relocated, 8)}, a"]

        elif mode in (AddressingMode.ABSOLUTE_X, AddressingMode.ZERO_PAGE_X):
            relocated = _relocate_address(addr_val)
            return [
                "    LD   e, b",
                "    LD   d, 0",
                f"    LD   hl, ${_hex16h(relocated)}",
                "    ADD  HL, DE",
                "    LD   (HL), a",
            ]

        elif mode == AddressingMode.ABSOLUTE_Y:
            relocated = _relocate_address(addr_val)
            return [
                "    LD   e, c",
                "    LD   d, 0",
                f"    LD   hl, ${_hex16h(relocated)}",
                "    ADD  HL, DE",
                "    LD   (HL), a",
            ]

        return [f"    LD   ({instruction.operand_text}), a"]


class StoreXStrategy(TranslationStrategy):
    """Translation strategy for STX instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        mode = instruction.addressing_mode
        val = instruction.operand_value

        if mode == AddressingMode.ABSOLUTE:
            if val is not None:
                intercept = _INTERCEPTOR.intercept_write(val, "b")
                if intercept:
                    return intercept
                relocated = _relocate_address(val)
                return [
                    f"    LD   hl, ${_hex16h(relocated)}",
                    "    LD   (HL), b",
                ]
            return [f"    LD   ({instruction.operand_text}), b"]

        elif mode == AddressingMode.ZERO_PAGE:
            if val is not None:
                intercept = _INTERCEPTOR.intercept_write(val, "b")
                if intercept:
                    return intercept
                relocated = _relocate_address(val)
                return [
                    f"    LD   hl, ${_hex16h(relocated)}",
                    "    LD   (HL), b",
                ]
            return [
                f"    LD   hl, {_normalize_hex(instruction.operand_text)}",
                "    LD   (HL), b",
            ]

        return [
            f"    LD   hl, {_normalize_hex(instruction.operand_text)}",
            "    LD   (HL), b",
        ]


class StoreYStrategy(TranslationStrategy):
    """Translation strategy for STY instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        mode = instruction.addressing_mode
        val = instruction.operand_value or 0

        if mode == AddressingMode.ABSOLUTE:
            intercept = _INTERCEPTOR.intercept_write(val, "c")
            if intercept:
                return intercept
            relocated = _relocate_address(val)
            return [
                f"    LD   hl, ${_hex16h(relocated)}",
                "    LD   (HL), c",
            ]

        elif mode == AddressingMode.ZERO_PAGE:
            intercept = _INTERCEPTOR.intercept_write(val, "c")
            if intercept:
                return intercept
            relocated = _relocate_address(val)
            return [
                f"    LD   hl, ${_hex16h(relocated)}",
                "    LD   (HL), c",
            ]

        return [
            f"    LD   hl, {_normalize_hex(instruction.operand_text)}",
            "    LD   (HL), c",
        ]


class LoadXStrategy(TranslationStrategy):
    """Translation strategy for LDX instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        val = instruction.operand_value or 0
        if instruction.addressing_mode == AddressingMode.IMMEDIATE:
            return [f"    LD   b, ${_hex8h(val)}"]
        elif instruction.addressing_mode == AddressingMode.ABSOLUTE:
            intercept = _INTERCEPTOR.intercept_read(val, "b")
            if intercept:
                return intercept
            relocated = _relocate_address(val)
            return [
                f"    LD   hl, ${_hex16h(relocated)}",
                "    LD   b, (HL)",
            ]
        elif instruction.addressing_mode == AddressingMode.ZERO_PAGE:
            intercept = _INTERCEPTOR.intercept_read(val, "b")
            if intercept:
                return intercept
            relocated = _relocate_address(val)
            return [
                f"    LD   hl, ${_hex16h(relocated)}",
                "    LD   b, (HL)",
            ]
        return [f"    LD   b, {instruction.operand_text}"]


class LoadYStrategy(TranslationStrategy):
    """Translation strategy for LDY instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        val = instruction.operand_value or 0
        if instruction.addressing_mode == AddressingMode.IMMEDIATE:
            return [f"    LD   c, ${_hex8h(val)}"]
        elif instruction.addressing_mode == AddressingMode.ABSOLUTE:
            intercept = _INTERCEPTOR.intercept_read(val, "c")
            if intercept:
                return intercept
            relocated = _relocate_address(val)
            return [
                f"    LD   hl, ${_hex16h(relocated)}",
                "    LD   c, (HL)",
            ]
        elif instruction.addressing_mode == AddressingMode.ZERO_PAGE:
            intercept = _INTERCEPTOR.intercept_read(val, "c")
            if intercept:
                return intercept
            relocated = _relocate_address(val)
            return [
                f"    LD   hl, ${_hex16h(relocated)}",
                "    LD   c, (HL)",
            ]
        return [f"    LD   c, {instruction.operand_text}"]


class JumpStrategy(TranslationStrategy):
    """Translation strategy for JMP instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        return [f"    JP   {instruction.operand_text}"]


class JumpSubroutineStrategy(TranslationStrategy):
    """Translation strategy for JSR instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        return [f"    CALL {instruction.operand_text}"]


class ReturnStrategy(TranslationStrategy):
    """Translation strategy for RTS instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        return ["    RET"]


class ReturnInterruptStrategy(TranslationStrategy):
    """Translation strategy for RTI instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        return ["    EI", "    RETI"]


class BranchStrategy(TranslationStrategy):
    """Translation strategy for branch instructions."""

    CONDITION_MAP = {
        "BCC": "NC",
        "BCS": "C",
        "BEQ": "Z",
        "BNE": "NZ",
        "BMI": "M",
        "BPL": "P",
        "BVC": "PO",
        "BVS": "PE",
    }

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        condition = self.CONDITION_MAP.get(instruction.mnemonic, "NZ")
        target = _normalize_hex(instruction.operand_text)
        return [f"    JP   {condition}, {target}"]


class TransferStrategy(TranslationStrategy):
    """Translation strategy for transfer instructions (TAX, TAY, etc.)."""

    TRANSFER_MAP = {
        "TAX": ["    LD   b, a"],
        "TAY": ["    LD   c, a"],
        "TXA": ["    LD   a, b"],
        "TYA": ["    LD   a, c"],
        "TSX": ["    LD   b, L"],
        "TXS": ["    ; TXS: X→SP - use LD SP, HL after loading X to H"],
    }

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        return self.TRANSFER_MAP.get(instruction.mnemonic, ["    ; TODO"])


class StackStrategy(TranslationStrategy):
    """Translation strategy for stack instructions."""

    STACK_MAP = {
        "PHA": ["    PUSH AF"],
        "PLA": ["    POP  AF"],
        "PHP": ["    PUSH AF"],
        "PLP": ["    POP  AF"],
    }

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        return self.STACK_MAP.get(instruction.mnemonic, ["    ; TODO"])


class FlagStrategy(TranslationStrategy):
    """Translation strategy for flag instructions."""

    FLAG_MAP = {
        "CLC": ["    AND  A"],  # Clear carry
        "SEC": ["    SCF"],  # Set carry
        "CLI": ["    EI"],  # Enable interrupts
        "SEI": ["    DI"],  # Disable interrupts
        "CLV": ["    ; CLV - no Z80 equivalent"],
        "CLD": ["    ; CLD - Z80 DAA different"],
        "SED": ["    ; SED - Z80 DAA different"],
    }

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        return self.FLAG_MAP.get(instruction.mnemonic, ["    ; TODO"])


class IncrementDecrementStrategy(TranslationStrategy):
    """Translation strategy for INC/DEC instructions."""

    REG_MAP = {
        "INX": "B",
        "INY": "C",
        "DEX": "B",
        "DEY": "C",
    }

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        mnemonic = instruction.mnemonic

        # Register operations
        if mnemonic in self.REG_MAP:
            reg = self.REG_MAP[mnemonic]
            op = "INC" if mnemonic.startswith("IN") else "DEC"
            return [f"    {op}  {reg}"]

        # Memory operations
        if instruction.addressing_mode == AddressingMode.IMPLIED:
            return [f"    INC  A" if mnemonic == "INC" else f"    DEC  A"]
        elif instruction.addressing_mode == AddressingMode.ABSOLUTE:
            op = "INC" if mnemonic == "INC" else "DEC"
            addr_val = instruction.operand_value or 0
            relocated = _relocate_address(addr_val)
            return [
                f"    LD   hl, ${_hex16h(relocated)}",
                f"    {op}  (HL)",
            ]
        elif instruction.addressing_mode == AddressingMode.ZERO_PAGE:
            op = "INC" if mnemonic == "INC" else "DEC"
            relocated = _relocate_address(instruction.operand_value or 0)
            return [f"    {op}  {_hex_paren(relocated, 8)}"]

        return [f"    ; TODO: {mnemonic} {instruction.operand_text}"]


class ArithmeticLogicStrategy(TranslationStrategy):
    """Translation strategy for arithmetic and logic instructions."""

    OPCODE_MAP = {
        "ADC": "ADC",
        "SBC": "SBC",
        "AND": "AND",
        "ORA": "OR",
        "EOR": "XOR",
        "CMP": "CP",
        "ADD": "ADD",
        "SUB": "SUB",
    }

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        mnemonic = instruction.mnemonic
        z80_op = self.OPCODE_MAP.get(mnemonic)

        if not z80_op:
            return [f"    ; TODO: {mnemonic}"]

        if instruction.addressing_mode == AddressingMode.IMMEDIATE:
            imm = f"    {z80_op}  ${_hex8h(instruction.operand_value or 0)}"
            if mnemonic == "SBC":
                # 6502 carry is "no borrow", Z80 carry is "borrow".
                return ["    CCF", imm, "    CCF"]
            if mnemonic == "CMP":
                return [imm, "    CCF"]
            return [imm]

        elif instruction.addressing_mode in (AddressingMode.ABSOLUTE, AddressingMode.ZERO_PAGE):
            addr_val = instruction.operand_value or 0
            relocated = _relocate_address(addr_val)
            lines = [f"    LD   hl, ${_hex16h(relocated)}"]
            if mnemonic == "SBC":
                lines.append("    CCF")
            lines.append(f"    {z80_op}  (HL)")
            if mnemonic in {"SBC", "CMP"}:
                lines.append("    CCF")
            return lines

        lines = []
        if mnemonic == "SBC":
            lines.append("    CCF")
        lines.append(f"    {z80_op}  {instruction.operand_text}")
        if mnemonic in {"SBC", "CMP"}:
            lines.append("    CCF")
        return lines


class CompareRegisterStrategy(TranslationStrategy):
    """Translation strategy for CPX/CPY instructions."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        mnemonic = instruction.mnemonic
        reg = "B" if mnemonic == "CPX" else "C"
        addr_val = instruction.operand_value or 0

        if instruction.addressing_mode == AddressingMode.IMMEDIATE:
            return [
                "    LD   d, a",
                f"    LD   a, {reg}",
                f"    CP   ${_hex8h(addr_val)}",
                "    CCF",
                "    LD   a, d",
            ]
        elif instruction.addressing_mode == AddressingMode.ABSOLUTE:
            relocated = _relocate_address(addr_val)
            return [
                "    LD   d, a",
                f"    LD   hl, ${_hex16h(relocated)}",
                f"    LD   a, {reg}",
                "    CP   (HL)",
                "    CCF",
                "    LD   a, d",
            ]
        elif instruction.addressing_mode == AddressingMode.ZERO_PAGE:
            relocated = _relocate_address(addr_val)
            return [
                "    LD   d, a",
                f"    LD   hl, ${_hex16h(relocated)}",
                f"    LD   a, {reg}",
                "    CP   (HL)",
                "    CCF",
                "    LD   a, d",
            ]

        addr = _normalize_hex_paren(instruction.operand_text)
        return [
            "    LD   d, a",
            f"    LD   a, {reg}",
            f"    CP   {addr}",
            "    CCF",
            "    LD   a, d",
        ]


class ShiftRotateStrategy(TranslationStrategy):
    """Translation strategy for shift and rotate instructions."""

    OPCODE_MAP = {
        "ASL": "ADD",  # ASL A = ADD A,A
        "LSR": "SRL",
        "ROL": "RL",
        "ROR": "RR",
    }

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        mnemonic = instruction.mnemonic

        if instruction.addressing_mode == AddressingMode.IMPLIED:
            if mnemonic == "ASL":
                return ["    ADD  A"]
            else:
                op = self.OPCODE_MAP.get(mnemonic, "NOP")
                return [f"    {op}  A"]

        # Memory operations
        if instruction.addressing_mode == AddressingMode.ABSOLUTE:
            addr_val = instruction.operand_value or 0
            relocated = _relocate_address(addr_val)
            op = self.OPCODE_MAP.get(mnemonic, "NOP")
            if mnemonic == "ASL":
                return [
                    f"    LD   hl, ${_hex16h(relocated)}",
                    "    LD   a, (HL)",
                    "    ADD  A",
                    "    LD   (HL), a",
                ]
            else:
                return [
                    f"    LD   hl, ${_hex16h(relocated)}",
                    "    LD   a, (HL)",
                    f"    {op}  A",
                    "    LD   (HL), a",
                ]
        elif instruction.addressing_mode == AddressingMode.ZERO_PAGE:
            op = self.OPCODE_MAP.get(mnemonic, "NOP")
            relocated = _relocate_address(instruction.operand_value or 0)
            addr = f"({_hex16h(relocated)})"
            if mnemonic == "ASL":
                return [
                    f"    LD   a, {addr}",
                    "    ADD  A",
                    f"    LD   {addr}, a",
                ]
            else:
                return [
                    f"    LD   a, {addr}",
                    f"    {op}  A",
                    f"    LD   {addr}, a",
                ]

        return [f"    ; TODO: {mnemonic} {instruction.operand_text}"]


class NopStrategy(TranslationStrategy):
    """Translation strategy for NOP instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        return ["    NOP"]


class BreakStrategy(TranslationStrategy):
    """Translation strategy for BRK instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        # Phase 1 fallback: treat BRK as a soft-abort path and return.
        return ["    RET"]


class BitTestStrategy(TranslationStrategy):
    """Translation strategy for BIT instruction."""

    def translate(self, instruction: ParsedInstruction) -> List[str]:
        addr_val = instruction.operand_value
        if addr_val is not None:
            # Check for hardware interception (e.g., $2002)
            intercept = _INTERCEPTOR.intercept_read(addr_val, "a")
            if intercept:
                # Interceptor returns CALL hal_...
                # We need to ensure flags are updated after the call
                return intercept + ["    AND  A"]

            # Normal memory BIT: AND a, (hl) but without affecting A
            relocated = _relocate_address(addr_val)
            return [
                f"    LD   hl, ${_hex16h(relocated)}",
                "    PUSH AF",
                "    AND  (HL)",
                "    POP  AF",
                "    ; Note: BIT also affects N/V, omitted here for simplicity",
            ]

        # Bit test with constant (BIT #$XX) - not standard 6502, but for completeness
        return [f"    BIT  {instruction.operand_text or ''}"]
