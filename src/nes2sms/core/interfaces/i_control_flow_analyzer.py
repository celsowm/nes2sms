"""Control flow analyzer interface - DIP contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .i_disassembler import ParsedInstruction


@dataclass
class BasicBlock:
    """
    Basic block of code.

    A basic block is a sequence of instructions with:
    - One entry point (first instruction)
    - One exit point (last instruction is branch/jump/return)
    - No branches into the middle
    """

    start_addr: int
    end_addr: int
    instructions: List[ParsedInstruction] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)  # Target addresses
    predecessors: List[int] = field(default_factory=list)  # Addresses that jump here

    def add_instruction(self, instr: ParsedInstruction):
        """Add instruction to block."""
        self.instructions.append(instr)
        self.end_addr = instr.address + instr.size()

    def entry_point(self) -> int:
        """Get block entry point address."""
        return self.start_addr

    def exit_point(self) -> int:
        """Get block exit point address."""
        return self.end_addr

    def is_terminal(self) -> bool:
        """Check if block ends with return/jump."""
        if not self.instructions:
            return False
        last = self.instructions[-1]
        return last.mnemonic in {"RTS", "RTI", "JMP"}


@dataclass
class LoopInfo:
    """Information about a detected loop."""

    header_addr: int  # Loop header (entry point)
    back_edge_from: int  # Address of backward branch
    body_blocks: List[int] = field(default_factory=list)  # Block addresses in loop
    nesting_level: int = 0


@dataclass
class SubroutineInfo:
    """Information about a detected subroutine."""

    entry_addr: int
    exit_addrs: List[int] = field(default_factory=list)  # RTS/RTI addresses
    calls: List[int] = field(default_factory=list)  # JSR addresses within
    blocks: List[int] = field(default_factory=list)  # Block addresses


@dataclass
class ControlFlowGraph:
    """
    Control flow graph representation.

    LSP: Can be substituted by any CFG implementation.
    """

    blocks: Dict[int, BasicBlock] = field(default_factory=dict)  # addr -> block
    entry_points: List[int] = field(default_factory=list)
    loops: List[LoopInfo] = field(default_factory=list)
    subroutines: Dict[int, SubroutineInfo] = field(default_factory=dict)

    def add_block(self, block: BasicBlock):
        """Add block to CFG."""
        self.blocks[block.start_addr] = block

    def get_block_at(self, addr: int) -> Optional[BasicBlock]:
        """Get block containing address."""
        for block in self.blocks.values():
            if block.start_addr <= addr < block.end_addr:
                return block
        return None

    def get_block_by_entry(self, addr: int) -> Optional[BasicBlock]:
        """Get block by entry point address."""
        return self.blocks.get(addr)

    def find_loops(self) -> List[LoopInfo]:
        """Identify loops in CFG."""
        return self.loops

    def find_subroutines(self) -> Dict[int, SubroutineInfo]:
        """Identify subroutines in CFG."""
        return self.subroutines

    def get_ordered_blocks(self) -> List[BasicBlock]:
        """Get blocks in address order."""
        return [self.blocks[addr] for addr in sorted(self.blocks.keys())]


class IControlFlowAnalyzer(ABC):
    """
    Interface for control flow analyzers (DIP).

    Analyzes 6502 code to identify loops, branches, subroutines.
    """

    @abstractmethod
    def analyze(self, instructions: List[ParsedInstruction]) -> ControlFlowGraph:
        """
        Build control flow graph from instructions.

        Args:
            instructions: List of parsed 6502 instructions

        Returns:
            ControlFlowGraph with blocks, loops, subroutines
        """
        pass

    @abstractmethod
    def identify_loops(self, cfg: ControlFlowGraph) -> List[LoopInfo]:
        """Identify loops in control flow graph."""
        pass

    @abstractmethod
    def identify_subroutines(self, cfg: ControlFlowGraph) -> Dict[int, SubroutineInfo]:
        """Identify subroutines in control flow graph."""
        pass
