"""Control flow analyzer for 6502 code."""

from typing import List, Dict, Set, Optional

from ..interfaces.i_control_flow_analyzer import (
    IControlFlowAnalyzer,
    ControlFlowGraph,
    BasicBlock,
    LoopInfo,
    SubroutineInfo,
)
from ..interfaces.i_disassembler import ParsedInstruction


class ControlFlowAnalyzer(IControlFlowAnalyzer):
    """
    Analyzes control flow in 6502 code.

    SRP: Only analyzes control flow, doesn't translate.
    OCP: Can be extended with new analysis patterns.
    """

    # Branch instructions
    BRANCH_INSTRUCTIONS = {"BCC", "BCS", "BEQ", "BNE", "BMI", "BPL", "BVC", "BVS"}

    # Jump instructions
    JUMP_INSTRUCTIONS = {"JMP", "JSR"}

    # Return instructions (end of function)
    RETURN_INSTRUCTIONS = {"RTS", "RTI"}

    # All flow control instructions
    FLOW_CONTROL = BRANCH_INSTRUCTIONS | JUMP_INSTRUCTIONS | RETURN_INSTRUCTIONS

    def analyze(self, instructions: List[ParsedInstruction]) -> ControlFlowGraph:
        """
        Build control flow graph from instructions.

        Args:
            instructions: List of parsed 6502 instructions

        Returns:
            ControlFlowGraph with blocks, loops, subroutines
        """
        if not instructions:
            return ControlFlowGraph()

        # Sort by address
        sorted_instrs = sorted(instructions, key=lambda i: i.address)

        # Find basic blocks
        blocks = self._build_basic_blocks(sorted_instrs)

        # Build CFG
        cfg = ControlFlowGraph()
        for block in blocks:
            cfg.add_block(block)

        # Find entry points
        cfg.entry_points = self._find_entry_points(blocks, sorted_instrs)

        # Identify loops and subroutines
        cfg.loops = self.identify_loops(cfg)
        cfg.subroutines = self.identify_subroutines(cfg)

        return cfg

    def _build_basic_blocks(self, instructions: List[ParsedInstruction]) -> List[BasicBlock]:
        """
        Build basic blocks from instructions.

        A basic block boundary occurs at:
        - Function entry points
        - Branch/jump targets
        - Instructions after branches/jumps/returns
        """
        if not instructions:
            return []

        # Find block boundaries
        boundaries: Set[int] = set()

        # First instruction is always a boundary
        boundaries.add(instructions[0].address)

        # Find all branch/jump targets and instruction followers
        for instr in instructions:
            if instr.mnemonic in self.FLOW_CONTROL:
                # Target of branch/jump is a boundary
                if instr.operands:
                    target = self._parse_target(instr.operands[0])
                    if target is not None:
                        boundaries.add(target)

                # Instruction after flow control is a boundary
                next_addr = instr.address + instr.size()
                boundaries.add(next_addr)

        # Build blocks
        blocks: List[BasicBlock] = []
        current_block: Optional[BasicBlock] = None

        for instr in sorted(instructions, key=lambda i: i.address):
            if instr.address in boundaries:
                # Start new block
                if current_block is not None:
                    blocks.append(current_block)
                current_block = BasicBlock(
                    start_addr=instr.address,
                    end_addr=instr.address + instr.size(),
                )

            if current_block is not None:
                current_block.add_instruction(instr)

        # Add last block
        if current_block is not None:
            blocks.append(current_block)

        # Build predecessor/successor links
        self._build_cfg_links(blocks)

        return blocks

    def _build_cfg_links(self, blocks: List[BasicBlock]):
        """Build predecessor/successor links between blocks."""
        # Create address -> block map
        block_map = {b.start_addr: b for b in blocks}

        # Sort blocks by address
        sorted_blocks = sorted(blocks, key=lambda b: b.start_addr)

        for i, block in enumerate(sorted_blocks):
            if not block.instructions:
                continue

            last_instr = block.instructions[-1]

            # Determine successors based on last instruction
            if last_instr.mnemonic in self.RETURN_INSTRUCTIONS:
                # No successors for return
                continue

            elif last_instr.mnemonic == "JMP":
                # Unconditional jump
                if last_instr.operands:
                    target = self._parse_target(last_instr.operands[0])
                    if target is not None and target in block_map:
                        block.successors.append(target)
                        block_map[target].predecessors.append(block.start_addr)

            elif last_instr.mnemonic in self.BRANCH_INSTRUCTIONS:
                # Conditional branch - two successors
                if last_instr.operands:
                    # Branch target
                    target = self._parse_target(last_instr.operands[0])
                    if target is not None and target in block_map:
                        block.successors.append(target)
                        block_map[target].predecessors.append(block.start_addr)

                # Fall-through to next block
                if i + 1 < len(sorted_blocks):
                    next_block = sorted_blocks[i + 1]
                    block.successors.append(next_block.start_addr)
                    next_block.predecessors.append(block.start_addr)

            else:
                # Fall-through to next block
                if i + 1 < len(sorted_blocks):
                    next_block = sorted_blocks[i + 1]
                    block.successors.append(next_block.start_addr)
                    next_block.predecessors.append(block.start_addr)

    def _parse_target(self, operand: str) -> Optional[int]:
        """
        Parse branch/jump target from operand.

        Args:
            operand: Operand string (e.g., "$8000", "label", "label+1")

        Returns:
            Target address or None
        """
        if not operand:
            return None

        # Remove parentheses for indirect
        operand = operand.strip("()")

        # Handle hexadecimal
        if operand.startswith("$"):
            try:
                return int(operand[1:], 16)
            except ValueError:
                pass

        # Handle decimal
        try:
            return int(operand)
        except ValueError:
            pass

        # Label - can't resolve without symbol table
        return None

    def _find_entry_points(
        self,
        blocks: List[BasicBlock],
        instructions: List[ParsedInstruction],
    ) -> List[int]:
        """
        Find function entry points.

        Entry points are:
        - First instruction
        - Targets of JSR instructions
        """
        entries: Set[int] = set()

        # First instruction
        if instructions:
            entries.add(instructions[0].address)

        # JSR targets
        for instr in instructions:
            if instr.mnemonic == "JSR" and instr.operands:
                target = self._parse_target(instr.operands[0])
                if target is not None:
                    entries.add(target)

        return sorted(entries)

    def identify_loops(self, cfg: ControlFlowGraph) -> List[LoopInfo]:
        """
        Identify loops in control flow graph.

        Uses simple back-edge detection:
        - A back edge goes from a node to one of its dominators
        - The target of the back edge is the loop header
        """
        loops: List[LoopInfo] = []

        for block in cfg.get_ordered_blocks():
            # Check if block has back edge (successor <= block start)
            for succ_addr in block.successors:
                if succ_addr <= block.start_addr:
                    # Found back edge
                    header_block = cfg.get_block_by_entry(succ_addr)
                    if header_block:
                        loop = LoopInfo(
                            header_addr=succ_addr,
                            back_edge_from=block.start_addr,
                            body_blocks=[block.start_addr],
                        )
                        loops.append(loop)

        # Calculate nesting levels
        for loop in loops:
            loop.nesting_level = sum(
                1
                for other in loops
                if other.header_addr != loop.header_addr and loop.header_addr in other.body_blocks
            )

        return loops

    def identify_subroutines(self, cfg: ControlFlowGraph) -> Dict[int, SubroutineInfo]:
        """
        Identify subroutines in control flow graph.

        Subroutines start at entry points and end at RTS/RTI.
        """
        subroutines: Dict[int, SubroutineInfo] = {}

        for entry_addr in cfg.entry_points:
            block = cfg.get_block_by_entry(entry_addr)
            if not block:
                continue

            # Collect all blocks in this subroutine
            visited: Set[int] = set()
            queue = [entry_addr]
            subroutine_blocks: List[int] = []
            exit_addrs: List[int] = []
            jsr_addrs: List[int] = []

            while queue:
                addr = queue.pop(0)
                if addr in visited:
                    continue
                visited.add(addr)

                block = cfg.get_block_by_entry(addr)
                if not block:
                    continue

                subroutine_blocks.append(addr)

                # Check for exits and JSRs
                for instr in block.instructions:
                    if instr.mnemonic in self.RETURN_INSTRUCTIONS:
                        exit_addrs.append(instr.address)
                    elif instr.mnemonic == "JSR":
                        jsr_addrs.append(instr.address)

                # Add successors to queue (but not JSR targets)
                for succ in block.successors:
                    if succ not in visited:
                        queue.append(succ)

            if subroutine_blocks:
                subroutines[entry_addr] = SubroutineInfo(
                    entry_addr=entry_addr,
                    exit_addrs=exit_addrs,
                    calls=jsr_addrs,
                    blocks=subroutine_blocks,
                )

        return subroutines
