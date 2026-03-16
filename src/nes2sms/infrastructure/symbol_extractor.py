"""Static symbol extractor for 6502 PRG ROMs."""

from pathlib import Path
from typing import List, Dict, Tuple, Optional, TYPE_CHECKING

try:
    from ..shared.models import Symbol
except ImportError:
    from nes2sms.shared.models import Symbol

if TYPE_CHECKING:
    from ..core.interfaces.i_disassembler import IDisassembler, DisassemblyDatabase


class StaticSymbolExtractor:
    """
    Extracts symbols from 6502 PRG ROM using static analysis.

    This is a basic extractor that:
    - Reads interrupt vectors ($FFFA-$FFFF)
    - Follows JSR/JMP targets to discover routines
    - Identifies potential code vs data regions

    DIP: Accepts optional IDisassembler for enhanced extraction.
    """

    VECTORS = {
        "NMI": 0xFFFA,
        "RESET": 0xFFFC,
        "IRQ": 0xFFFE,
    }

    def __init__(
        self,
        prg_data: bytes,
        base_address: int = 0x8000,
        disassembler: Optional["IDisassembler"] = None,
    ):
        """
        Initialize symbol extractor.

        Args:
            prg_data: PRG ROM data
            base_address: Base address where PRG is mapped (default: $8000)
            disassembler: Optional disassembler for code extraction
        """
        self.prg_data = prg_data
        self.base_address = base_address
        self.disassembler = disassembler
        self.symbols: List[Symbol] = []
        self.code_addresses: set = set()
        self.data_addresses: set = set()
        self.visited: set = set()
        self.disassembly_db: Optional["DisassemblyDatabase"] = None

    def extract(self) -> List[Symbol]:
        """
        Extract symbols from PRG data.

        Returns:
            List of Symbol objects with disassembly snippets if available
        """
        # Step 1: Run disassembler if available
        if self.disassembler:
            self._run_disassembly()

        # Step 2: Extract vectors
        self._extract_vectors()

        # Step 3: Follow code
        self._follow_code()

        # Step 4: Build symbols
        self._build_symbols()

        # Step 5: Enrich with disassembly
        if self.disassembly_db:
            self._enrich_with_disassembly()

        return self.symbols

    def _run_disassembly(self):
        """Run disassembler on PRG data."""
        if not self.disassembler:
            return

        result = self.disassembler.disassemble(
            prg_data=self.prg_data,
            start_addr=self.base_address,
        )

        if result.success and result.database:
            self.disassembly_db = result.database

    def _enrich_with_disassembly(self):
        """Enrich symbols with disassembly snippets from database."""
        if not self.disassembly_db:
            return

        if not self.disassembly_db:
            return

        # Step 1: Sync all symbol names to the disassembly database as labels
        # This ensures get_function_at includes these labels in the snippets
        for symbol in self.symbols:
            self.disassembly_db.add_label(symbol.address, symbol.name)

        # Step 2: Process symbols in order of address to handle overlaps correctly
        self.symbols.sort(key=lambda s: s.address)
        processed_addresses = set()
        emitted_labels = set()
        
        for symbol in self.symbols:
            # If this starting address is already covered by a previous snippet, 
            # we don't need to generate a new starting point for it (the label
            # is already embedded in the parent snippet).
            if symbol.address in processed_addresses:
                symbol.is_embedded = True
                continue
                
            # Get function instructions
            instructions = self.disassembly_db.get_function_at(symbol.address)

            if instructions:
                # Mark all these addresses as covered
                for instr in instructions:
                    for i in range(instr.size()):
                        processed_addresses.add(instr.address + i)
                    
                # Convert to assembly text
                lines = []
                for instr in instructions:
                    # Check for label at this address in the DB (includes our symbols)
                    label = self.disassembly_db.get_label_at(instr.address)
                    if label and label not in emitted_labels:
                        lines.append(f"{label}:")
                        emitted_labels.add(label)
                    
                    line = instr.to_string()
                    if instr.comment:
                        line += f" ; {instr.comment}"
                    lines.append(f"    {line}")

                symbol.disassembly_snippet = "\n".join(lines)

    def _extract_vectors(self):
        """Extract interrupt vector handlers."""
        # Vectors are at the end of the PRG (last 6 bytes)
        # For a PRG mapped at $8000, vectors appear at CPU addresses $FFFA-$FFFF
        # but are stored at the end of the PRG data
        vector_offset = len(self.prg_data) - 6

        if vector_offset < 0:
            return  # PRG too small

        for i, (name, _) in enumerate(self.VECTORS.items()):
            offset = vector_offset + (i * 2)
            if offset + 1 < len(self.prg_data):
                handler_addr = self.prg_data[offset] | (self.prg_data[offset + 1] << 8)
                if self._is_valid_address(handler_addr):
                    self.code_addresses.add(handler_addr)
                    self.symbols.append(
                        Symbol(
                            name=f"{name}_Handler",
                            address=handler_addr,
                            bank=self._addr_to_bank(handler_addr),
                            type="code",
                            comment=f"{name} vector handler",
                        )
                    )

    def _follow_code(self):
        """
        Follow JSR/JMP targets and do linear disassembly to discover code.
        """
        queue = list(self.code_addresses)

        while queue:
            addr = queue.pop(0)
            if addr in self.visited:
                continue

            # Disassemble linearly from this address
            self._disassemble_from(addr, queue)

    def _disassemble_from(self, start_addr: int, queue: list):
        """
        Disassemble code linearly from start_addr.

        Args:
            start_addr: Starting address
            queue: Queue of addresses to process
        """
        addr = start_addr
        max_iterations = 1000  # Prevent infinite loops
        iterations = 0

        while iterations < max_iterations:
            iterations += 1
            offset = self._addr_to_offset(addr)

            if offset >= len(self.prg_data) or addr in self.visited:
                break

            self.visited.add(addr)
            self.code_addresses.add(addr)

            # Read opcode
            opcode = self.prg_data[offset]

            # Determine instruction size and check for control flow
            instr_size, is_terminal, branch_target = self._analyze_instruction(opcode, offset, addr)

            # Add branch/jump targets to queue
            if branch_target is not None and self._is_valid_address(branch_target):
                if branch_target not in self.visited:
                    queue.append(branch_target)

            # Stop at terminal instructions
            if is_terminal:
                break

            # Move to next instruction
            addr += instr_size

            # Handle wrap-around at $FFFF
            if addr > 0xFFFF:
                break

    def _build_symbols(self):
        """Build symbol list from discovered addresses."""
        existing_addrs = {s.address for s in self.symbols}

        # When we have a disassembly database, only create symbols for
        # JSR/JMP/branch targets (real entry points), not every visited byte
        if self.disassembly_db:
            target_addrs = set()
            for instr in self.disassembly_db.instructions.values():
                if instr.mnemonic in ("JSR", "JMP"):
                    if instr.operands:
                        try:
                            target = instr.operands[0].strip("()")
                            addr_val = int(target.lstrip("#$"), 16)
                            if self._is_valid_address(addr_val):
                                target_addrs.add(addr_val)
                        except (ValueError, IndexError):
                            pass
                elif instr.mnemonic in ("BCC", "BCS", "BEQ", "BNE", "BMI", "BPL", "BVC", "BVS"):
                    if instr.operands:
                        try:
                            addr_val = int(instr.operands[0].lstrip("$"), 16)
                            if self._is_valid_address(addr_val):
                                target_addrs.add(addr_val)
                        except (ValueError, IndexError):
                            pass
            addresses_to_add = target_addrs
        else:
            addresses_to_add = self.code_addresses

        for addr in sorted(addresses_to_add):
            if addr not in existing_addrs:
                self.symbols.append(
                    Symbol(
                        name=f"sub_{addr:04X}",
                        address=addr,
                        bank=self._addr_to_bank(addr),
                        type="code",
                    )
                )
                existing_addrs.add(addr)

    def _is_valid_address(self, addr: int) -> bool:
        """Check if address is within valid PRG range."""
        return self.base_address <= addr < self.base_address + len(self.prg_data)

    def _addr_to_offset(self, addr: int) -> int:
        """Convert CPU address to PRG offset."""
        return addr - self.base_address

    def _analyze_instruction(self, opcode: int, offset: int, addr: int) -> tuple:
        """
        Analyze 6502 instruction to determine size and control flow.

        Uses precomputed size table for accuracy.
        """
        # Precomputed instruction size table for 6502
        SIZE_TABLE = bytes(
            [
                1, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # 00-0F
                2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # 10-1F
                3, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # 20-2F
                2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # 30-3F
                1, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # 40-4F
                2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # 50-5F
                1, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # 60-6F
                2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # 70-7F
                2, 2, 0, 0, 2, 2, 2, 0, 1, 0, 1, 0, 3, 3, 3, 0, # 80-8F
                2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 0, 3, 0, 0, # 90-9F
                2, 2, 2, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # A0-AF
                2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # B0-BF
                2, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # C0-CF
                2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # D0-DF
                2, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # E0-EF
                2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # F0-FF
            ]
        )

        # Get base size
        instr_size = SIZE_TABLE[opcode]

        # Handle invalid/illegal opcodes (size 0)
        if instr_size == 0:
            instr_size = 1

        # Clamp to available data
        if offset + instr_size > len(self.prg_data):
            instr_size = max(1, len(self.prg_data) - offset)

        # Check for terminal (RTS/RTI)
        is_terminal = opcode in (0x60, 0x40)

        # Calculate branch/jump target
        branch_target = None
        if opcode == 0x20 and offset + 2 < len(self.prg_data):  # JSR
            branch_target = self.prg_data[offset + 1] | (self.prg_data[offset + 2] << 8)
        elif opcode == 0x4C and offset + 2 < len(self.prg_data):  # JMP abs
            branch_target = self.prg_data[offset + 1] | (self.prg_data[offset + 2] << 8)
        elif opcode in (0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0):  # Branches
            if offset + 1 < len(self.prg_data):
                rel_offset = self.prg_data[offset + 1]
                if rel_offset & 0x80:  # Negative
                    rel_offset -= 0x100
                branch_target = (addr + 2 + rel_offset) & 0xFFFF

        return instr_size, is_terminal, branch_target

    def _addr_to_bank(self, addr: int) -> int:
        """Convert CPU address to bank number."""
        if addr < 0xC000:
            return (addr - self.base_address) // 0x4000
        else:
            return -1

    def get_code_ranges(self) -> List[Tuple[int, int]]:
        """
        Get contiguous code ranges.

        Returns:
            List of (start, end) tuples for code regions
        """
        if not self.code_addresses:
            return []

        ranges = []
        sorted_addrs = sorted(self.code_addresses)
        start = sorted_addrs[0]
        end = start

        for addr in sorted_addrs[1:]:
            if addr == end + 1:
                end = addr
            else:
                ranges.append((start, end))
                start = addr
                end = addr

        ranges.append((start, end))
        return ranges

    def get_data_ranges(self) -> List[Tuple[int, int]]:
        """
        Get potential data ranges (everything not identified as code).

        Returns:
            List of (start, end) tuples for data regions
        """
        if not self.prg_data:
            return []

        ranges = []
        in_data = False
        data_start = 0

        for i in range(len(self.prg_data)):
            addr = self.base_address + i
            is_code = addr in self.code_addresses

            if not is_code and not in_data:
                in_data = True
                data_start = addr
            elif is_code and in_data:
                in_data = False
                ranges.append((data_start, addr - 1))

        if in_data:
            ranges.append((data_start, self.base_address + len(self.prg_data) - 1))

        return ranges

    def to_dict(self) -> Dict:
        """
        Export symbols to dictionary format.

        Returns:
            Dictionary with symbols list and metadata
        """
        return {
            "symbols": [
                {
                    "name": s.name,
                    "address": f"${s.address:04X}",
                    "bank": s.bank,
                    "type": s.type,
                    "comment": s.comment or "",
                    "disassembly_snippet": getattr(s, "disassembly_snippet", "") or "",
                    "is_embedded": bool(getattr(s, "is_embedded", False)),
                }
                for s in self.symbols
            ],
            "code_ranges": [f"${s:04X}-${e:04X}" for s, e in self.get_code_ranges()],
            "data_ranges": [f"${s:04X}-${e:04X}" for s, e in self.get_data_ranges()],
            "total_symbols": len(self.symbols),
        }


def extract_symbols_from_prg(
    prg_path: Path,
    base_address: int = 0x8000,
    output_path: Optional[Path] = None,
) -> Dict:
    """
    Convenience function to extract symbols from PRG file.

    Args:
        prg_path: Path to PRG file
        base_address: Base address where PRG is mapped
        output_path: Optional path to write JSON output

    Returns:
        Dictionary with extracted symbols
    """
    prg_data = prg_path.read_bytes()
    extractor = StaticSymbolExtractor(prg_data, base_address)
    symbols = extractor.extract()
    result = extractor.to_dict()

    if output_path:
        import json

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result
