"""ROM file loading and extraction."""

import hashlib
from pathlib import Path
from typing import Tuple, Optional

from ..core.nes.header import parse_ines_header, extract_sections, read_vectors
from ..shared.models import NesHeader


class RomLoader:
    """Loads and parses NES ROM files."""

    def __init__(self):
        self.data: Optional[bytes] = None
        self.header: Optional[NesHeader] = None
        self.prg_data: Optional[bytes] = None
        self.chr_data: Optional[bytes] = None
        self.trainer_data: Optional[bytes] = None
        self.vectors: Optional[dict] = None
        self.sha256: Optional[str] = None

    def load(self, rom_path: Path) -> "RomLoader":
        """
        Load NES ROM from file.

        Args:
            rom_path: Path to .nes file

        Returns:
            Self for method chaining
        """
        self.data = rom_path.read_bytes()
        self.header = parse_ines_header(self.data[:16])
        self.prg_data, self.chr_data, self.trainer_data = extract_sections(self.data, self.header)
        self.vectors = read_vectors(self.prg_data)
        self.sha256 = hashlib.sha256(self.data).hexdigest()
        return self

    def get_manifest_dict(self) -> dict:
        """Get manifest dictionary for JSON serialization."""
        return {
            "format": self.header.format,
            "mapper": self.header.mapper,
            "prg_banks": self.header.prg_banks,
            "prg_size": self.header.prg_size,
            "chr_banks": self.header.chr_banks,
            "chr_size": self.header.chr_size,
            "chr_ram": self.header.chr_ram,
            "trainer": self.header.trainer,
            "battery": self.header.battery,
            "mirroring": self.header.mirroring,
        }
