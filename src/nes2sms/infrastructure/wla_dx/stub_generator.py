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
        "NMI_Handler",  # Defined in interrupts.asm
        "RESET_Handler",  # Defined in init.asm
        "IRQ_Handler",  # Defined in interrupts.asm
        "INT_Handler",  # Defined in interrupts.asm
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
    ):
        """
        Initialize stub generator.

        Args:
            symbols: List of symbols from 6502 disassembly
            translator: Optional translator instance (uses default if None)
            enable_translation: If True, translate 6502 to Z80
            use_flow_aware: If True, use FlowAwareTranslator for better results
        """
        self.symbols = symbols if symbols is not None else []
        # Filter symbols that are defined elsewhere
        self.symbols = [s for s in self.symbols if s.name not in self.SKIP_SYMBOLS]
        self.enable_translation = enable_translation

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

    def generate_game_logic_stub(self) -> str:
        """Generate game_logic.asm with translated code for each symbol."""
        lines = [
            "; Game Logic",
            "; Translated from NES 6502 by nes2sms",
            "",
            '.section "GameLogic" FREE',
            "",
        ]

        # Always generate GameMain entry point
        symbol_names = {s.name for s in self.symbols}
        if "GameMain" not in symbol_names:
            lines.extend(
                [
                    "; Entry point called by init.asm",
                    "GameMain:",
                    "    ; TODO: Initialize game state",
                    "    ; call InitGame",
                    "",
                    ".main_loop:",
                    "    halt",
                    "    jr   .main_loop",
                    "",
                ]
            )

        if not self.symbols:
            pass  # GameMain already added above
        else:
            for symbol in self.symbols:
                stub = self._generate_stub(symbol)
                lines.append(stub)

        lines.append(".ends")
        return "\n".join(lines)

    def generate_game_stubs(self) -> str:
        """Generate game_stubs.asm with additional helper stubs."""
        lines = [
            "; Generated stubs — one per NES subroutine",
            "; Replace each stub body with ported Z80 code.",
            "",
            '.section "GameStubs" FREE',
            "",
            ".ends",
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

            instructions = self._parse_disassembly(symbol.disassembly_snippet)
            if instructions:
                return self.translator.translate_function(
                    instructions=instructions,
                    function_name=symbol.name,
                )

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

        return "\n".join(lines)

    def _parse_disassembly(self, snippet: str) -> List:
        """
        Parse disassembly snippet into ParsedInstruction list.

        Args:
            snippet: Disassembly text

        Returns:
            List of parsed instructions
        """
        from ...core.assembly.parser import InstructionParser
        from ...core.interfaces.i_disassembler import ParsedInstruction as ParsedInstr

        parser = InstructionParser()
        instructions = []

        lines = snippet.split("\n")
        current_label = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith(";"):
                continue

            # Check for label
            if line.endswith(":"):
                current_label = line[:-1]
                continue

            # Parse instruction
            parsed = parser.parse(line)
            if parsed:
                # Create ParsedInstruction
                instr = ParsedInstr(
                    address=0,  # Unknown without full context
                    bytes_raw=b"",
                    mnemonic=parsed.mnemonic,
                    operands=[parsed.operand_text] if parsed.operand_text else [],
                    label=current_label,
                )
                instructions.append(instr)
                current_label = None

        return instructions

    def write_stubs(self, output_dir: Path):
        """
        Write stub files to disk.

        Args:
            output_dir: Directory to write stub files
        """
        stubs_dir = output_dir / "stubs"
        stubs_dir.mkdir(parents=True, exist_ok=True)

        game_logic = self.generate_game_logic_stub()
        (stubs_dir / "game_logic.asm").write_text(game_logic, encoding="utf-8")

        game_stubs = self.generate_game_stubs()
        (stubs_dir / "game_stubs.asm").write_text(game_stubs, encoding="utf-8")
