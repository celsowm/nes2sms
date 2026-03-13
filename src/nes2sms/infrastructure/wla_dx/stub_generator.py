"""Z80 stub generator from 6502 disassembly symbols."""

from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from ...shared.models import Symbol
from ...core.assembly.instruction_translator import InstructionTranslator
from ...core.assembly.flow_aware_translator import FlowAwareTranslator

if TYPE_CHECKING:
    from ...core.interfaces.i_translator import ITranslator
    from ...core.interfaces.i_disassembler import ParsedInstruction


class StubGenerator:
    """
    Generates Z80 stub files from 6502 disassembly symbols.

    DIP: Accepts ITranslator interface for flexibility.
    SRP: Only generates stub files.
    """

    # Symbols that have HAL implementations or are defined elsewhere
    SKIP_SYMBOLS = {
        "VDP_Init",  # HAL
        "PSG_Init",  # HAL
        "ClearVRAM",  # HAL
        "LoadPalettes",  # HAL
        "LoadTilemap",  # HAL
        "LoadSAT",  # HAL
        "LoadTiles",  # HAL
    }

    def __init__(
        self,
        symbols: Optional[List[Symbol]] = None,
        translator: Optional["ITranslator"] = None,
        enable_translation: bool = True,
        use_flow_aware: bool = True,
        prg_data: Optional[bytes] = None,
        data_ranges: Optional[List[tuple]] = None,
        prg_base_address: int = 0x8000,
    ):
        """
        Initialize stub generator.

        Args:
            symbols: List of symbols from 6502 disassembly
            translator: Optional translator instance (uses default if None)
            enable_translation: If True, translate 6502 to Z80
            use_flow_aware: If True, use FlowAwareTranslator for better results
            prg_data: Raw PRG ROM bytes for emitting data tables
            data_ranges: List of (start, end) address tuples for data regions
            prg_base_address: Base address of PRG data (default: $8000)
        """
        self.symbols = symbols if symbols is not None else []
        self.prg_data = prg_data
        self.data_ranges = data_ranges or []
        self.prg_base_address = prg_base_address
        # Filter symbols that are defined elsewhere
        self.symbols = [s for s in self.symbols if s.name not in self.SKIP_SYMBOLS]
        self.enable_translation = enable_translation

        # Build address->label map for all symbols
        self.symbol_map = {}
        for s in self.symbols:
            self.symbol_map[s.address] = s.name

        # Initialize translator
        if translator:
            self.translator = translator
        elif enable_translation:
            if use_flow_aware:
                self.translator = FlowAwareTranslator()
            else:
                self.translator = InstructionTranslator()
        else:
            self.translator = None

        # Inject symbol_map into FlowAwareTranslator
        if isinstance(self.translator, FlowAwareTranslator):
            self.translator.symbol_map = self.symbol_map
        
        # Track all labels emitted across all snippets to ensure global uniqueness
        self.global_seen_labels = set()

    def generate_game_logic_stub(self) -> str:
        """Generate game_logic.asm with translated code for each symbol."""
        lines = [
            "; Game Logic",
            "; Translated from NES 6502 by nes2sms",
            "",
        ]

        symbol_names = {s.name for s in self.symbols}

        # Always generate GameMain entry point under converter control.
        # The bootstrap (init.asm) already loads palettes, tiles, tilemap, and SAT,
        # so GameMain just needs to jump to the game's entry point.
        entry_target = self._find_reset_entry_target(symbol_names)
        
        if entry_target:
            lines.extend(
                [
                    "; Entry point called by init.asm",
                    "GameMain:",
                    f"    jp   {entry_target}",
                ]
            )
        else:
            lines.extend(
                [
                    "; Entry point called by init.asm",
                    "GameMain:",
                    ".main_loop:",
                    "    halt",
                    "    jr   .main_loop",
                ]
            )
        lines.append("")
        lines.append("")

        if not self.symbols:
            pass  # GameMain already added above
        else:
            for symbol in self.symbols:
                if symbol.is_embedded:
                    continue
                if symbol.name == "GameMain":
                    continue
                stub = self._generate_stub(symbol)
                lines.append(stub)

        # Emit referenced data tables from PRG
        data_tables = self._generate_data_tables()
        if data_tables:
            lines.append(data_tables)

        lines.append("")
        return "\n".join(lines)

    def _generate_data_tables(self) -> str:
        """Emit data ranges from NES PRG as .db directives.

        Only emits data ranges that are referenced by translated code
        (i.e., addresses used in absolute,X or absolute,Y indexed loads).
        """
        if not self.prg_data or not self.data_ranges:
            return ""

        # Filter to data ranges that fall within the PRG address space
        # and are large enough to be meaningful (skip single-byte gaps
        # and huge padding ranges)
        MIN_TABLE_SIZE = 4
        MAX_TABLE_SIZE = 1024
        tables = []
        for start, end in self.data_ranges:
            size = end - start + 1
            if size < MIN_TABLE_SIZE or size > MAX_TABLE_SIZE:
                continue
            offset_start = start - self.prg_base_address
            offset_end = end - self.prg_base_address + 1
            if offset_start < 0 or offset_end > len(self.prg_data):
                continue
            tables.append((start, end))

        if not tables:
            return ""

        lines = [
            "",
            "; ============================================================",
            "; Data tables from NES PRG",
            "; ============================================================",
        ]

        for start, end in tables:
            offset_start = start - self.prg_base_address
            offset_end = end - self.prg_base_address + 1
            data = self.prg_data[offset_start:offset_end]

            lines.append(f"_data_{start:04X}:")

            # Emit in rows of 16 bytes
            for i in range(0, len(data), 16):
                chunk = data[i : i + 16]
                hex_bytes = ",".join(f"${b:02X}" for b in chunk)
                lines.append(f"    .db {hex_bytes}")

            lines.append("")

        return "\n".join(lines)

    def _find_reset_entry_target(self, symbol_names: set) -> Optional[str]:
        """Pick the best translated routine to boot the game."""
        preferred_labels = (
            "RESET_Handler",
            "Reset_Handler",
            "reset_handler",
            "RESET",
            "Reset",
            "START",
            "Start",
            "start",
        )
        for label in preferred_labels:
            if label in symbol_names:
                return label

        for symbol in self.symbols:
            if symbol.comment and "reset vector handler" in symbol.comment.lower():
                return symbol.name

        return None

    def generate_game_stubs(self) -> str:
        """Generate game_stubs.asm with additional helper stubs."""
        lines = [
            "; Generated stubs — one per NES subroutine",
            "; Replace each stub body with ported Z80 code.",
            "",
            ".ifndef NMI_Handler",
            "NMI_Handler:",
            "    ret",
            ".endif",
            "",
        ]
        return "\n".join(lines)

    def _generate_stub(self, symbol: Symbol) -> str:
        """Generate single Z80 stub from 6502 symbol."""
        lines = [
            f"; ============================================================",
            f"; NES: {symbol.name} @ ${symbol.address:04X}",
            f"; Type: {symbol.type} | Bank: {symbol.bank}",
        ]

        if symbol.comment:
            lines.append(f"; Comment: {symbol.comment}")

        lines.append(f"; ============================================================")
        lines.append(f"{symbol.name}:")

        # Generate translated code if available
        if symbol.disassembly_snippet and self.translator:
            translated = self._translate_symbol(symbol)
            if translated:
                lines.append(translated)
            else:
                lines.append("    ; TODO: Translation failed")
                lines.append("    ret")
        elif symbol.disassembly_snippet:
            # Has disassembly but no translator
            lines.append(f"; Original 6502 code:")
            for line in symbol.disassembly_snippet.split("\n"):
                lines.append(f";   {line}")
            lines.append("    ; TODO: Implement")
            lines.append("    ret")
        else:
            # No disassembly - just a stub
            lines.append("    ; TODO: Implement")
            lines.append("    ret")

        lines.append("")
        return "\n".join(lines)

    def _translate_symbol(self, symbol: Symbol) -> Optional[str]:
        """
        Translate symbol's disassembly to Z80.

        Args:
            symbol: Symbol with disassembly_snippet

        Returns:
            Translated Z80 code or None
        """
        if not symbol.disassembly_snippet or not self.translator:
            return None

        # Check if we have FlowAwareTranslator
        if isinstance(self.translator, FlowAwareTranslator):
            # Parse instructions and translate with flow awareness
            from ...core.interfaces.i_disassembler import ParsedInstruction

            instructions = self._parse_disassembly(symbol.disassembly_snippet, base_address=symbol.address)
            if instructions:
                result = self.translator.translate_function(
                    instructions=instructions,
                    function_name=symbol.name,
                )
                return self._replace_data_table_refs(result)

        # Fallback to line-by-line translation
        lines = []
        for line in symbol.disassembly_snippet.split("\n"):
            line = line.strip()
            if line and not line.startswith(";"):
                translated = self.translator.translate_line(line)
                lines.append(translated)
            elif line:
                lines.append(f"; {line}")

        if not any("ret" in line.lower() or "reti" in line.lower() for line in lines):
            lines.append("    ret")

        return self._replace_data_table_refs("\n".join(lines))

    def _replace_data_table_refs(self, code: str) -> str:
        """Replace hardcoded data table addresses with _data_XXXX labels.

        Scans translated code for LD hl, $XXXXh instructions where XXXX
        falls within a known data range, and replaces with the label.
        Only considers addresses in the PRG ROM range, not RAM addresses.
        """
        import re

        if not self.data_ranges:
            return code

        MIN_TABLE_SIZE = 4
        prg_end = self.prg_base_address + len(self.prg_data) if self.prg_data else 0xFFFF

        def _replace_match(match):
            full_hex = match.group(1)
            addr = int(full_hex, 16)
            # Only replace addresses within PRG ROM range,
            # excluding relocated SMS RAM ($C000-$DFFF)
            if addr < self.prg_base_address or addr >= prg_end:
                return match.group(0)
            if 0xC000 <= addr <= 0xDFFF:
                return match.group(0)
            for start, end in self.data_ranges:
                if end - start + 1 < MIN_TABLE_SIZE:
                    continue
                if start <= addr <= end:
                    offset = addr - start
                    if offset == 0:
                        return f"LD   hl, _data_{start:04X}"
                    else:
                        return f"LD   hl, _data_{start:04X} + {offset}"
            return match.group(0)

        # Match patterns like "LD   hl, $83A9h" or "LD   hl, $083A9h"
        return re.sub(r"LD   hl, \$0?([0-9A-Fa-f]{4,5})h", _replace_match, code)

    def _parse_disassembly(self, snippet: str, base_address: int = 0) -> List:
        """
        Parse disassembly snippet into ParsedInstruction list.

        Args:
            snippet: Disassembly text
            base_address: Starting address of the symbol

        Returns:
            List of parsed instructions
        """
        from ...core.assembly.parser import InstructionParser
        from ...core.interfaces.i_disassembler import ParsedInstruction as ParsedInstr

        parser = InstructionParser()
        instructions = []

        lines = snippet.split("\n")
        current_label = None
        current_address = base_address

        for line in lines:
            line = line.strip()
            if not line or line.startswith(";"):
                continue

            # Check for label
            if line.endswith(":"):
                current_label = line[:-1]
                # If this label is in symbol_map, update address
                for addr, name in self.symbol_map.items():
                    if name == current_label:
                        current_address = addr
                        break
                continue

            # Parse instruction
            parsed = parser.parse(line)
            if parsed:
                instr_size = self._estimate_6502_size(parsed.mnemonic, parsed.operand_text)

                instr = ParsedInstr(
                    address=current_address,
                    bytes_raw=b"\x00" * instr_size,
                    mnemonic=parsed.mnemonic,
                    operands=[parsed.operand_text] if parsed.operand_text else [],
                    label=current_label,
                )
                instructions.append(instr)
                current_label = None
                current_address += instr_size

        return instructions

    def _estimate_6502_size(self, mnemonic: str, operand: str) -> int:
        """Estimate 6502 instruction size from mnemonic and operand."""
        implied = {
            "RTS", "RTI", "PHA", "PLA", "PHP", "PLP", "TAX", "TAY",
            "TXA", "TYA", "TSX", "TXS", "NOP", "CLC", "SEC", "CLI",
            "SEI", "CLV", "CLD", "SED", "DEX", "DEY", "INX", "INY",
            "BRK", "ASL", "LSR", "ROL", "ROR",
        }

        if not operand:
            if mnemonic.upper() in implied:
                return 1
            return 1

        operand = operand.strip()

        # Branches are always 2 bytes
        if mnemonic.upper() in {"BCC", "BCS", "BEQ", "BNE", "BMI", "BPL", "BVC", "BVS"}:
            return 2

        # Immediate: #$XX = 2 bytes
        if operand.startswith("#"):
            return 2

        # Check for addressing mode by operand format
        base = operand.split(",")[0].strip()

        if base.startswith("$"):
            hex_part = base[1:]
            if len(hex_part) <= 2:
                return 2  # Zero page
            else:
                return 3  # Absolute

        if base.startswith("("):
            return 3  # Indirect

        return 3  # Default to 3 for safety

    def _deduplicate_labels(self, content: str) -> str:
        """Remove duplicate labels across all snippets using regex."""
        import re
        lines = content.split("\n")
        deduped = []
        # Match label (optional whitespace + name + colon)
        label_pattern = re.compile(r"^(\s*)([a-zA-Z0-9_]+):")
        
        for line in lines:
            match = label_pattern.search(line)
            if match and not line.strip().startswith(";"):
                label_name = match.group(2)
                if label_name in self.global_seen_labels:
                    # Comment it out instead of removing to preserve structure
                    indent = match.group(1)
                    deduped.append(f"{indent}; DUPLICATE LABEL SUPPRESSED: {label_name}:")
                    continue
                self.global_seen_labels.add(label_name)
            deduped.append(line)
        return "\n".join(deduped)

    def write_stubs(self, output_dir: Path):
        """
        Write stub files to disk.

        Args:
            output_dir: Directory to write stub files
        """
        stubs_dir = output_dir / "stubs"
        stubs_dir.mkdir(parents=True, exist_ok=True)

        game_logic = self.generate_game_logic_stub()
        game_logic = self._deduplicate_labels(game_logic)
        (stubs_dir / "game_logic.asm").write_text(game_logic, encoding="utf-8")

        game_stubs = self.generate_game_stubs()
        game_stubs = self._deduplicate_labels(game_stubs)
        (stubs_dir / "game_stubs.asm").write_text(game_stubs, encoding="utf-8")
