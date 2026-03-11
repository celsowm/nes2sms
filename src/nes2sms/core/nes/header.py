"""NES iNES/NES2.0 header parser."""

import struct
from typing import Tuple, Dict, Any

from ...shared.constants import INES_MAGIC
from ...shared.models import NesHeader


def parse_ines_header(data: bytes) -> NesHeader:
    """
    Parse iNES/NES2.0 header from ROM data.

    Args:
        data: First 16 bytes of ROM file

    Returns:
        NesHeader dataclass with parsed information
    """
    if len(data) < 16:
        raise ValueError("File too short to contain a 16-byte NES header.")

    if data[:4] != INES_MAGIC:
        raise ValueError(f"Invalid magic bytes: expected 'NES\\x1A', got {data[:4]!r}")

    flags6 = data[6]
    flags7 = data[7]

    # Detect NES2.0 format
    is_nes20 = (flags7 & 0x0C) == 0x08

    trainer_bytes = 512 if (flags6 & 0x04) else 0
    battery = bool(flags6 & 0x02)

    # Mirroring
    if flags6 & 0x08:
        mirroring = "four-screen"
    elif flags6 & 0x01:
        mirroring = "horizontal"
    else:
        mirroring = "vertical"

    prg_lsb = data[4]
    chr_lsb = data[5]

    if is_nes20:
        # NES2.0 format
        mapper_lo = (flags6 >> 4) & 0x0F
        mapper_mid = (flags7 >> 4) & 0x0F
        mapper_hi = data[8] & 0x0F
        mapper = mapper_lo | (mapper_mid << 4) | (mapper_hi << 8)

        size_msb = data[9]
        prg_msb_nibble = size_msb & 0x0F
        chr_msb_nibble = (size_msb >> 4) & 0x0F

        # Simple form vs exponent form
        if prg_msb_nibble <= 0x0E:
            prg_size = ((prg_msb_nibble << 8) | prg_lsb) * 16 * 1024
        else:
            prg_size = -1  # UNSPECIFIED

        if chr_msb_nibble <= 0x0E:
            chr_size = ((chr_msb_nibble << 8) | chr_lsb) * 8 * 1024
        else:
            chr_size = -1  # UNSPECIFIED

        fmt = "NES2.0"

    else:
        # iNES format
        mapper = ((flags6 >> 4) & 0x0F) | (flags7 & 0xF0)
        prg_size = prg_lsb * 16 * 1024
        chr_size = chr_lsb * 8 * 1024
        fmt = "iNES"

        # Check for polluted header
        if data[12:16] != b"\x00\x00\x00\x00":
            fmt = "iNES (warning: bytes12-15 nonzero)"

    prg_banks = prg_size // 16384 if prg_size > 0 else 0
    chr_banks = chr_size // 8192 if chr_size > 0 else 0
    chr_ram = chr_size == 0

    return NesHeader(
        format=fmt,
        mapper=mapper,
        prg_banks=prg_banks,
        prg_size=prg_size,
        chr_banks=chr_banks,
        chr_size=chr_size,
        chr_ram=chr_ram,
        trainer=bool(trainer_bytes),
        battery=battery,
        mirroring=mirroring,
    )


def extract_sections(data: bytes, hdr: NesHeader) -> Tuple[bytes, bytes, bytes]:
    """
    Extract PRG, CHR, and trainer data from ROM.

    Args:
        data: Full ROM data
        hdr: Parsed NesHeader

    Returns:
        Tuple of (prg_data, chr_data, trainer_data)
    """
    offset = 16
    trainer_data = b""

    if hdr.trainer:
        trainer_data = data[offset : offset + 512]
        offset += 512

    prg_data = b""
    if hdr.prg_size > 0:
        prg_data = data[offset : offset + hdr.prg_size]
        offset += hdr.prg_size

    chr_data = b""
    if hdr.chr_size > 0:
        chr_data = data[offset : offset + hdr.chr_size]

    return prg_data, chr_data, trainer_data


def read_vectors(prg: bytes) -> Dict[str, str]:
    """
    Read interrupt vectors from last 6 bytes of PRG.

    Args:
        prg: PRG data (vectors are at the end of the last bank)

    Returns:
        Dict with 'nmi', 'reset', 'irq' addresses as hex strings
    """
    if len(prg) < 6:
        return {}

    tail = prg[-6:]
    nmi = struct.unpack_from("<H", tail, 0)[0]
    rst = struct.unpack_from("<H", tail, 2)[0]
    irq = struct.unpack_from("<H", tail, 4)[0]

    return {"nmi": f"${nmi:04X}", "reset": f"${rst:04X}", "irq": f"${irq:04X}"}
