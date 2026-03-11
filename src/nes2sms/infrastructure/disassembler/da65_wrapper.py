"""da65 wrapper - Executes external disassembler."""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict

from ...core.interfaces.i_disassembler import DisassemblyResult


class Da65Wrapper:
    """
    Wrapper for cc65's da65 disassembler.

    SRP: Only executes the disassembler and returns raw output.
    OCP: Supports different CPU types via configuration.
    """

    SUPPORTED_CPUS = {"6502", "6502X", "65SC02", "65C02"}
    DEFAULT_CPU = "6502"

    def __init__(self, da65_path: Optional[Path] = None):
        """
        Initialize da65 wrapper.

        Args:
            da65_path: Optional path to da65 executable
        """
        self.da65_path = da65_path or self._find_da65()

    def _find_da65(self) -> Optional[Path]:
        """
        Find da65 in PATH or common locations.

        Returns:
            Path to da65 executable or None
        """
        # Try PATH first
        da65_in_path = shutil.which("da65") or shutil.which("da65.exe")
        if da65_in_path:
            return Path(da65_in_path)

        # Try common installation directories
        common_paths = [
            Path(r"C:\cc65\bin\da65.exe"),
            Path(r"C:\Program Files\cc65\bin\da65.exe"),
            Path.home() / "cc65" / "bin" / "da65",
            Path.home() / "cc65" / "bin" / "da65.exe",
            Path.cwd() / "tools" / "cc65" / "bin" / "da65.exe",
            Path.cwd() / "tools" / "cc65" / "bin" / "da65",
        ]

        for path in common_paths:
            if path.exists():
                return path

        return None

    def is_available(self) -> bool:
        """Check if da65 is available."""
        return self.da65_path is not None and self.da65_path.exists()

    def disassemble(
        self,
        input_data: bytes,
        start_addr: int = 0x8000,
        cpu: str = "6502",
        info_file: Optional[Path] = None,
        multi_pass: bool = True,
    ) -> DisassemblyResult:
        """
        Execute disassembler and return structured result.

        Args:
            input_data: PRG ROM bytes
            start_addr: Start address (default: $8000 for NES)
            cpu: CPU type (6502, 65C02, etc)
            info_file: Optional info file to guide disassembly
            multi_pass: Use multi-pass mode for better label resolution

        Returns:
            DisassemblyResult with output and metadata
        """
        if not self.is_available():
            return DisassemblyResult(
                output="",
                success=False,
                error_message="da65 not found. Install cc65 or run setup script.",
            )

        if cpu not in self.SUPPORTED_CPUS:
            return DisassemblyResult(
                output="",
                success=False,
                error_message=f"Unsupported CPU: {cpu}. Supported: {self.SUPPORTED_CPUS}",
            )

        # Create temporary files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            input_file = tmp_path / "input.bin"
            output_file = tmp_path / "output.asm"

            # Write input data
            input_file.write_bytes(input_data)

            # Build command
            cmd = [
                str(self.da65_path),
                "-o",
                str(output_file),
                "-S",
                f"${start_addr:04X}",
                "--cpu",
                cpu,
            ]

            if multi_pass:
                cmd.append("-m")

            if info_file and info_file.exists():
                cmd.extend(["-i", str(info_file)])

            cmd.append(str(input_file))

            try:
                # Execute da65
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,  # 60 second timeout
                )

                if result.returncode != 0:
                    return DisassemblyResult(
                        output="",
                        success=False,
                        error_message=result.stderr or f"da65 exited with code {result.returncode}",
                    )

                # Read output
                if output_file.exists():
                    output = output_file.read_text(encoding="utf-8")
                else:
                    output = result.stdout

                return DisassemblyResult(
                    output=output,
                    success=True,
                    error_message=None,
                )

            except subprocess.TimeoutExpired:
                return DisassemblyResult(
                    output="",
                    success=False,
                    error_message="da65 timed out after 60 seconds",
                )
            except Exception as e:
                return DisassemblyResult(
                    output="",
                    success=False,
                    error_message=f"da65 execution failed: {str(e)}",
                )

    def get_version(self) -> Optional[str]:
        """Get da65 version string."""
        if not self.is_available():
            return None

        try:
            result = subprocess.run(
                [str(self.da65_path), "-V"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None
