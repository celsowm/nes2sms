"""da65 output parser - Converts disassembler output to structured data."""

import re
from typing import List, Dict, Optional, Tuple

from ...core.interfaces.i_disassembler import (
    DisassemblyDatabase,
    ParsedInstruction,
)


class Da65OutputParser:
    """
    Parses da65 disassembler output.

    SRP: Only parses text output into data structures.
    """

    # Pattern for instruction lines: address, bytes, mnemonic, operands
    # Example: "8000  A9 00    LDA #$00"
    INSTRUCTION_PATTERN = re.compile(
        r"^([0-9A-Fa-f]{4})\s+"  # Address
        r"((?:[0-9A-Fa-f]{2}\s*)+)\s+"  # Bytes (1-3 bytes)
        r"(\w+)\s*"  # Mnemonic
        r"(.*)$"  # Operands (optional)
    )

    # Pattern for labels: "LabelName:"
    LABEL_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")

    # Pattern for comments: "; comment text"
    COMMENT_PATTERN = re.compile(r"^\s*;\s*(.*)$")

    # Pattern for .byte/.word directives (data)
    DATA_PATTERN = re.compile(
        r"^([0-9A-Fa-f]{4})\s+"  # Address
        r"((?:[0-9A-Fa-f]{2}\s*)+)\s+"  # Bytes
        r"\.(byte|word|dword)\s+"  # Directive
        r"(.*)$"  # Data values
    )

    # Instructions that end a basic block
    TERMINAL_INSTRUCTIONS = {"RTS", "RTI", "JMP", "JSR"}

    def parse(self, output: str) -> DisassemblyDatabase:
        """
        Parse complete da65 output.

        Args:
            output: Raw da65 output text

        Returns:
            DisassemblyDatabase with parsed instructions
        """
        db = DisassemblyDatabase()

        lines = output.split("\n")
        current_label: Optional[str] = None
        current_comment: Optional[str] = None

        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip empty lines and page headers
            if not line.strip() or line.startswith("; da65"):
                i += 1
                continue

            # Check for label
            label_match = self.LABEL_PATTERN.match(line.strip())
            if label_match:
                # Get address from next line or current context
                current_label = label_match.group(1)
                i += 1
                continue

            # Check for comment
            comment_match = self.COMMENT_PATTERN.match(line)
            if comment_match:
                current_comment = comment_match.group(1)
                i += 1
                continue

            # Check for instruction
            instr_match = self.INSTRUCTION_PATTERN.match(line)
            if instr_match:
                addr = int(instr_match.group(1), 16)
                bytes_str = instr_match.group(2).replace(" ", "")
                bytes_raw = bytes.fromhex(bytes_str)
                mnemonic = instr_match.group(3).upper()
                operands_str = instr_match.group(4).strip()

                # Parse operands
                operands = self._parse_operands(operands_str)

                # Create instruction
                instr = ParsedInstruction(
                    address=addr,
                    bytes_raw=bytes_raw,
                    mnemonic=mnemonic,
                    operands=operands,
                    label=current_label,
                    comment=current_comment,
                )

                db.add_instruction(instr)

                # Add label if present
                if current_label:
                    db.add_label(addr, current_label)
                    current_label = None

                current_comment = None
                i += 1
                continue

            # Check for data directive
            data_match = self.DATA_PATTERN.match(line)
            if data_match:
                addr = int(data_match.group(1), 16)
                bytes_str = data_match.group(2).replace(" ", "")
                bytes_raw = bytes.fromhex(bytes_str)

                # Create pseudo-instruction for data
                instr = ParsedInstruction(
                    address=addr,
                    bytes_raw=bytes_raw,
                    mnemonic=f".{data_match.group(3).upper()}",
                    operands=[data_match.group(4).strip()],
                    label=current_label,
                    comment=current_comment,
                )

                db.add_instruction(instr)

                if current_label:
                    db.add_label(addr, current_label)
                    current_label = None

                current_comment = None
                i += 1
                continue

            i += 1

        # Identify code ranges
        db.code_ranges = self._identify_code_ranges(db)

        return db

    def _parse_operands(self, operands_str: str) -> List[str]:
        """Parse operand string into list."""
        if not operands_str:
            return []

        # Remove comments
        if ";" in operands_str:
            operands_str = operands_str.split(";")[0].strip()

        # Split by comma, but respect parentheses
        operands = []
        current = ""
        paren_depth = 0

        for char in operands_str:
            if char == "(":
                paren_depth += 1
                current += char
            elif char == ")":
                paren_depth -= 1
                current += char
            elif char == "," and paren_depth == 0:
                if current.strip():
                    operands.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            operands.append(current.strip())

        return operands

    def _identify_code_ranges(self, db: DisassemblyDatabase) -> List[Tuple[int, int]]:
        """Identify contiguous code ranges."""
        if not db.instructions:
            return []

        ranges = []
        sorted_addrs = sorted(db.instructions.keys())

        range_start = sorted_addrs[0]
        range_end = range_start

        for addr in sorted_addrs[1:]:
            # Check if contiguous (allowing for instruction size)
            prev_instr = db.get_instruction_at(range_end)
            expected_next = range_end + (prev_instr.size() if prev_instr else 1)

            if addr == expected_next:
                range_end = addr + db.instructions[addr].size()
            else:
                ranges.append((range_start, range_end))
                range_start = addr
                range_end = addr + db.instructions[addr].size()

        ranges.append((range_start, range_end))
        return ranges

    def parse_function(
        self, output: str, start_addr: int, max_instructions: int = 200
    ) -> List[ParsedInstruction]:
        """
        Parse a single function from da65 output.

        Args:
            output: da65 output text
            start_addr: Function start address
            max_instructions: Maximum instructions to parse

        Returns:
            List of instructions in function
        """
        db = self.parse(output)
        return db.get_function_at(start_addr, max_instructions)
