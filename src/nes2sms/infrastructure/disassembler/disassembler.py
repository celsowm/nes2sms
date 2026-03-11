"""da65 disassembler implementation - Implements IDisassembler interface."""

from pathlib import Path
from typing import Optional, Dict, List

from ...core.interfaces.i_disassembler import (
    IDisassembler,
    DisassemblyResult,
    DisassemblyDatabase,
)
from .da65_wrapper import Da65Wrapper
from .da65_output_parser import Da65OutputParser
from .info_file_generator import InfoFileGenerator, CodeRange, Label, InfoFileOptions


class Da65Disassembler(IDisassembler):
    """
    da65 implementation of IDisassembler interface.

    DIP: Implements interface for dependency injection.
    SRP: Only handles disassembly orchestration.
    """

    def __init__(
        self,
        da65_path: Optional[Path] = None,
        cpu: str = "6502",
        multi_pass: bool = True,
    ):
        """
        Initialize da65 disassembler.

        Args:
            da65_path: Optional path to da65 executable
            cpu: CPU type (6502, 65C02, etc)
            multi_pass: Use multi-pass mode
        """
        self.wrapper = Da65Wrapper(da65_path)
        self.parser = Da65OutputParser()
        self.cpu = cpu
        self.multi_pass = multi_pass

    def is_available(self) -> bool:
        """Check if da65 is available."""
        return self.wrapper.is_available()

    def disassemble(
        self,
        prg_data: bytes,
        start_addr: int = 0x8000,
        cpu: Optional[str] = None,
        labels: Optional[Dict[int, str]] = None,
        code_ranges: Optional[List[tuple]] = None,
    ) -> DisassemblyResult:
        """
        Disassemble PRG data using da65.

        Args:
            prg_data: PRG ROM bytes
            start_addr: Start address (default: $8000 for NES)
            cpu: CPU type (overrides constructor)
            labels: Optional labels to guide disassembly
            code_ranges: Optional code ranges for better accuracy

        Returns:
            DisassemblyResult with parsed database
        """
        cpu = cpu or self.cpu

        # Generate info file if labels or ranges provided
        info_file: Optional[Path] = None

        if labels or code_ranges:
            info_file = self._generate_info_file(
                labels=labels,
                code_ranges=code_ranges,
                start_addr=start_addr,
                cpu=cpu,
            )

        # Execute da65
        result = self.wrapper.disassemble(
            input_data=prg_data,
            start_addr=start_addr,
            cpu=cpu,
            info_file=info_file,
            multi_pass=self.multi_pass,
        )

        # Parse output if successful
        if result.success:
            db = self.parser.parse(result.output)
            result.database = db

        # Cleanup temp file
        if info_file and info_file.exists():
            try:
                info_file.unlink()
            except Exception:
                pass

        return result

    def _generate_info_file(
        self,
        labels: Optional[Dict[int, str]],
        code_ranges: Optional[List[tuple]],
        start_addr: int,
        cpu: str,
    ) -> Path:
        """
        Generate temporary info file.

        Args:
            labels: Label dictionary
            code_ranges: Code ranges
            start_addr: Start address
            cpu: CPU type

        Returns:
            Path to temporary info file
        """
        import tempfile
        from pathlib import Path

        options = InfoFileOptions(
            start_addr=start_addr,
            cpu=cpu,
        )
        generator = InfoFileGenerator(options)

        # Convert labels
        label_objs = []
        if labels:
            for addr, name in labels.items():
                label_objs.append(Label(name=name, address=addr))

        # Convert code ranges
        range_objs = []
        if code_ranges:
            for start, end in code_ranges:
                range_objs.append(CodeRange(start=start, end=end, range_type="CODE"))

        # Generate content
        content = generator.generate(
            code_ranges=range_objs,
            labels=label_objs,
        )

        # Write to temp file
        tmp_path = Path(tempfile.mktemp(suffix=".info"))
        tmp_path.write_text(content, encoding="utf-8")

        return tmp_path

    def disassemble_function(
        self,
        prg_data: bytes,
        function_addr: int,
        start_addr: int = 0x8000,
        cpu: Optional[str] = None,
    ) -> DisassemblyResult:
        """
        Disassemble a single function.

        Args:
            prg_data: PRG ROM bytes
            function_addr: Function start address
            start_addr: PRG base address
            cpu: CPU type

        Returns:
            DisassemblyResult with function instructions
        """
        # For single function, disassemble all and extract
        result = self.disassemble(
            prg_data=prg_data,
            start_addr=start_addr,
            cpu=cpu,
        )

        if result.success and result.database:
            # Extract just the function
            function_instrs = result.database.get_function_at(function_addr)

            # Create new database with just function
            filtered_db = DisassemblyDatabase()
            for instr in function_instrs:
                filtered_db.add_instruction(instr)

            result.database = filtered_db

        return result
