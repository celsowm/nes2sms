#!/usr/bin/env python3
"""
parse_nes.py — NES ROM header parser and extractor (iNES / NES 2.0)

Usage:
    python3 parse_nes.py <rom.nes> [--out <output_dir>]

Outputs:
    <out>/manifest.json  — header metadata, hashes, file paths
    <out>/header.bin
    <out>/trainer.bin    — only if trainer flag is set
    <out>/prg.bin
    <out>/chr.bin        — only if CHR-ROM size > 0

Values of -1 or null in manifest.json mean UNSPECIFIED and require manual inspection.
"""

import argparse
import hashlib
import json
import os
import struct
from dataclasses import asdict, dataclass
from typing import Optional, Dict, Any

NES_MAGIC = b"NES\x1A"


@dataclass
class NesHeader:
    format: str             # "iNES" | "NES2.0" | "iNES (warning: bytes12-15 nonzero)"
    prg_bytes: int          # -1 = UNSPECIFIED (exponent-multiplier form)
    chr_bytes: int          # -1 = UNSPECIFIED; 0 = CHR-RAM (no chr.bin)
    trainer_bytes: int      # 0 or 512
    mapper: int
    submapper: Optional[int]  # NES 2.0 only; None for iNES
    mirroring: str          # "horizontal"|"vertical"|"four-screen"|"mapper-controlled"
    battery: bool


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_header(raw: bytes, rom_size: int) -> NesHeader:
    if len(raw) < 16:
        raise ValueError("File too short to contain a 16-byte NES header.")
    if raw[:4] != NES_MAGIC:
        raise ValueError(f"Invalid magic bytes: expected 'NES\\x1A', got {raw[:4]!r}")

    flags6 = raw[6]
    flags7 = raw[7]

    # NES 2.0 identification: bits 3-2 of byte 7 must be 0b10
    is_nes20 = (flags7 & 0x0C) == 0x08

    trainer_bytes = 512 if (flags6 & 0x04) else 0
    battery = bool(flags6 & 0x02)

    # Hard-wired mirroring (many mappers override this via registers)
    if flags6 & 0x08:
        mirroring = "four-screen"
    elif flags6 & 0x01:
        mirroring = "horizontal"
    else:
        mirroring = "vertical"

    prg_lsb = raw[4]
    chr_lsb = raw[5]

    if is_nes20:
        # Mapper: 12-bit; submapper: 4-bit
        mapper_lo  = (flags6 >> 4) & 0x0F
        mapper_mid = (flags7 >> 4) & 0x0F
        mapper_hi  = raw[8] & 0x0F
        submapper  = (raw[8] >> 4) & 0x0F
        mapper     = mapper_lo | (mapper_mid << 4) | (mapper_hi << 8)

        size_msb       = raw[9]
        prg_msb_nibble = size_msb & 0x0F
        chr_msb_nibble = (size_msb >> 4) & 0x0F

        # Simple form (nibble 0x0–0xE): multiply mode
        # Exponent form (nibble 0xF): UNSPECIFIED for automated extraction
        if prg_msb_nibble <= 0x0E:
            prg_bytes = ((prg_msb_nibble << 8) | prg_lsb) * 16 * 1024
        else:
            prg_bytes = -1  # UNSPECIFIED: exponent-multiplier form

        if chr_msb_nibble <= 0x0E:
            chr_bytes = ((chr_msb_nibble << 8) | chr_lsb) * 8 * 1024
        else:
            chr_bytes = -1  # UNSPECIFIED: exponent-multiplier form

        fmt = "NES2.0"

    else:
        # iNES: mapper from nibbles in flags6 / flags7
        mapper    = ((flags6 >> 4) & 0x0F) | (flags7 & 0xF0)
        submapper = None
        prg_bytes = prg_lsb * 16 * 1024
        chr_bytes = chr_lsb * 8 * 1024
        fmt       = "iNES"

        # Heuristic: if bytes 12–15 are non-zero this is likely a "DiskDude!"-style
        # polluted header — the upper mapper nibble may be corrupted.
        if raw[12:16] != b"\x00\x00\x00\x00":
            fmt = "iNES (warning: bytes12-15 nonzero — mapper may be corrupted)"

    return NesHeader(
        format=fmt,
        prg_bytes=prg_bytes,
        chr_bytes=chr_bytes,
        trainer_bytes=trainer_bytes,
        mapper=mapper,
        submapper=submapper,
        mirroring=mirroring,
        battery=battery,
    )


def extract(rom_path: str, out_dir: str) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)

    with open(rom_path, "rb") as f:
        data = f.read()

    hdr_raw = data[:16]
    h = parse_header(hdr_raw, len(data))
    rom_sha256 = sha256_of(data)

    # Compute byte offsets
    offset = 16
    trainer_data = data[offset : offset + h.trainer_bytes]
    offset += h.trainer_bytes

    prg_data = b""
    chr_data = b""

    if h.prg_bytes > 0:
        prg_data = data[offset : offset + h.prg_bytes]
        offset += h.prg_bytes
    elif h.prg_bytes == -1:
        print("[WARN] PRG size is UNSPECIFIED (exponent-multiplier). Skipping PRG extraction.")

    if h.chr_bytes > 0:
        chr_data = data[offset : offset + h.chr_bytes]
        offset += h.chr_bytes
    elif h.chr_bytes == 0:
        print("[INFO] CHR size = 0 → board uses CHR-RAM. No chr.bin produced.")
    elif h.chr_bytes == -1:
        print("[WARN] CHR size is UNSPECIFIED (exponent-multiplier). Skipping CHR extraction.")

    trailing = len(data) - offset
    if trailing > 0:
        print(f"[INFO] {trailing} trailing bytes after CHR (possible Misc ROM or padding).")

    # Write binary blobs
    paths: Dict[str, Optional[str]] = {}

    def write_blob(name: str, blob: bytes) -> str:
        path = os.path.join(out_dir, name)
        with open(path, "wb") as f:
            f.write(blob)
        return name

    paths["header"]  = write_blob("header.bin", hdr_raw)
    paths["trainer"] = write_blob("trainer.bin", trainer_data) if h.trainer_bytes else None
    paths["prg"]     = write_blob("prg.bin", prg_data)         if prg_data else None
    paths["chr"]     = write_blob("chr.bin", chr_data)         if chr_data else None

    manifest: Dict[str, Any] = {
        "rom":            os.path.basename(rom_path),
        "sha256":         rom_sha256,
        "header_format":  h.format,
        "mapper":         h.mapper,
        "submapper":      h.submapper,
        "prg_bytes":      h.prg_bytes,
        "chr_bytes":      h.chr_bytes,
        "trainer_bytes":  h.trainer_bytes,
        "battery":        h.battery,
        "mirroring":      h.mirroring,
        "chr_ram":        h.chr_bytes == 0,
        "paths":          paths,
        "trailing_bytes": trailing if trailing > 0 else 0,
        "note":           "Values of -1 or null mean UNSPECIFIED and require manual inspection.",
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Parse a NES ROM header (iNES / NES 2.0) and extract PRG/CHR blobs."
    )
    ap.add_argument("rom", help="Path to the .nes file")
    ap.add_argument("--out", default="out", help="Output directory (default: out/)")
    args = ap.parse_args()

    result = extract(args.rom, args.out)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
