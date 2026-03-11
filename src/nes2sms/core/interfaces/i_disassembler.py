"""Disassembler interface - DIP contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional


@dataclass
class ParsedInstruction:
    """Represents a disassembled instruction."""

    address: int
    bytes_raw: bytes
    mnemonic: str
    operands: List[str]
    label: Optional[str] = None
    comment: Optional[str] = None

    def to_string(self) -> str:
        """Convert to assembly string."""
        ops = " ".join(self.operands) if self.operands else ""
        return f"{self.mnemonic} {ops}".strip()

    def size(self) -> int:
        """Return instruction size in bytes."""
        return len(self.bytes_raw)


@dataclass
class DisassemblyDatabase:
    """
    Repository of disassembled code.

    LSP: Can be substituted by any implementation.
    """

    instructions: Dict[int, ParsedInstruction] = field(default_factory=dict)
    labels: Dict[int, str] = field(default_factory=dict)
    code_ranges: List[Tuple[int, int]] = field(default_factory=list)
    data_ranges: List[Tuple[int, int]] = field(default_factory=list)

    def get_instruction_at(self, addr: int) -> Optional[ParsedInstruction]:
        """Get instruction at address."""
        return self.instructions.get(addr)

    def get_label_at(self, addr: int) -> Optional[str]:
        """Get label at address."""
        return self.labels.get(addr)

    def is_code(self, addr: int) -> bool:
        """Check if address is in code range."""
        for start, end in self.code_ranges:
            if start <= addr <= end:
                return True
        return False

    def get_function_at(self, addr: int, max_instructions: int = 1000) -> List[ParsedInstruction]:
        """Get all instructions from addr until RTS/RTI or max."""
        result = []
        current = addr
        returns = {"RTS", "RTI"}

        for _ in range(max_instructions):
            instr = self.get_instruction_at(current)
            if not instr:
                break
            result.append(instr)
            if instr.mnemonic in returns:
                break
            current += instr.size()

        return result

    def add_instruction(self, instr: ParsedInstruction):
        """Add instruction to database."""
        self.instructions[instr.address] = instr

    def add_label(self, addr: int, label: str):
        """Add label to database."""
        self.labels[addr] = label

    def to_instruction_list(self) -> List[ParsedInstruction]:
        """Return instructions sorted by address."""
        return [self.instructions[addr] for addr in sorted(self.instructions.keys())]


@dataclass
class DisassemblyResult:
    """Result from disassembler execution."""

    output: str
    success: bool
    error_message: Optional[str] = None
    database: Optional[DisassemblyDatabase] = None


class IDisassembler(ABC):
    """
    Interface for disassemblers (DIP).

    Allows swapping between da65, native disassembler, etc.
    """

    @abstractmethod
    def disassemble(
        self,
        prg_data: bytes,
        start_addr: int = 0x8000,
        cpu: str = "6502",
        labels: Optional[Dict[int, str]] = None,
    ) -> DisassemblyResult:
        """
        Disassemble PRG data.

        Args:
            prg_data: PRG ROM bytes
            start_addr: Start address (default: $8000 for NES)
            cpu: CPU type (6502, 65C02, etc)
            labels: Optional labels to guide disassembly

        Returns:
            DisassemblyResult with output and parsed database
        """
        pass
