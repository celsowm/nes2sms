"""Shared models and constants."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class NesHeader:
    """NES iNES/NES2.0 header information."""

    format: str
    mapper: int
    prg_banks: int
    prg_size: int
    chr_banks: int
    chr_size: int
    chr_ram: bool
    trainer: bool
    battery: bool
    mirroring: str


@dataclass
class Symbol:
    """Represents a symbol (label) from disassembly."""

    name: str
    address: int
    bank: int
    type: str  # 'code', 'data', 'pointer'
    comment: Optional[str] = None
    disassembly_snippet: Optional[str] = None


@dataclass
class BankMapping:
    """Maps NES PRG bank to SMS Sega mapper slot."""

    sms_bank: int
    nes_bank: int
    fixed: bool


@dataclass
class TileConversionResult:
    """Result of tile conversion."""

    sms_tiles: List[bytes]
    flip_index: Dict
    warnings: List[str] = field(default_factory=list)
    tile_metadata: List[Dict] = field(default_factory=list)


@dataclass
class ConversionManifest:
    """Main manifest for conversion state."""

    source_hash_sha256: str
    nes_header: Dict
    vectors: Dict
    conversion_state: Dict = field(default_factory=dict)
    sms_assets: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
