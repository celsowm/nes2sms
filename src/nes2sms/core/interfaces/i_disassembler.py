"""Disassembler interface - DIP contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedInstruction:
    """Represents a disassembled instruction."""

    address: int
    bytes_raw: bytes
    mnemonic: str
    operands: list[str]
    label: str | None = None
    comment: str | None = None

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

    instructions: dict[int, ParsedInstruction] = field(default_factory=dict)
    labels: dict[int, str] = field(default_factory=dict)
    code_ranges: list[tuple[int, int]] = field(default_factory=list)
    data_ranges: list[tuple[int, int]] = field(default_factory=list)

    def get_instruction_at(self, addr: int) -> ParsedInstruction | None:
        """Get instruction at address."""
        return self.instructions.get(addr)

    def get_label_at(self, addr: int) -> str | None:
        """Get label at address."""
        return self.labels.get(addr)

    def is_code(self, addr: int) -> bool:
        """Check if address is in code range."""
        for start, end in self.code_ranges:
            if start <= addr <= end:
                return True
        return False

    def get_function_at(self, addr: int, max_instructions: int = 1000) -> list[ParsedInstruction]:
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

    def to_instruction_list(self) -> list[ParsedInstruction]:
        """Return instructions sorted by address."""
        return [self.instructions[addr] for addr in sorted(self.instructions.keys())]


@dataclass
class DisassemblyResult:
    """Result from disassembler execution."""

    output: str
    success: bool
    error_message: str | None = None
    database: DisassemblyDatabase | None = None


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
        labels: dict[int, str] | None = None,
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
