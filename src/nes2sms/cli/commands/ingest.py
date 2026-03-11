"""Ingest command: Load NES ROM and extract data."""

import json
from pathlib import Path

from ...infrastructure.rom_loader import RomLoader
from ...infrastructure.asset_writer import AssetWriter
from ...infrastructure.symbol_extractor import StaticSymbolExtractor


def cmd_ingest(args):
    """
    Ingest NES ROM file.

    Extracts PRG/CHR data, parses header, and writes manifest.
    """
    nes_path = Path(args.nes)
    if not nes_path.exists():
        raise FileNotFoundError(f"ROM not found: {nes_path}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load ROM
    loader = RomLoader()
    loader.load(nes_path)

    # Build manifest
    manifest = {
        "source_manifest": {},
        "nes_header": loader.get_manifest_dict(),
        "vectors": loader.vectors,
        "conversion_state": {
            "ingest": "DONE",
            "analyze_mapper": "PENDING",
            "convert_gfx": "PENDING",
            "convert_audio": "PENDING",
            "generate_scaffold": "PENDING",
            "build": "PENDING",
            "test": "PENDING",
        },
        "sms_assets": {},
        "warnings": [],
        "tool": "nes2sms",
        "source_hash_sha256": loader.sha256,
    }

    # Write extracted data
    writer = AssetWriter(out_dir)
    writer.write_binary("prg.bin", loader.prg_data, "work")

    if loader.chr_data:
        writer.write_binary("chr.bin", loader.chr_data, "work")

    if loader.trainer_data:
        writer.write_binary("trainer.bin", loader.trainer_data, "work")

    # Extract symbols from PRG
    if loader.prg_data:
        extractor = StaticSymbolExtractor(loader.prg_data)
        symbols = extractor.extract()
        symbol_dict = extractor.to_dict()
        writer.write_json("symbols.json", symbol_dict, "work")
        manifest["symbols_extracted"] = len(symbols)
    else:
        manifest["symbols_extracted"] = 0

    # Copy disasm artifacts if provided
    if args.disasm_dir:
        disasm_dir = Path(args.disasm_dir)
        for f in ["manifest.json", "symbols.json", "banks.json"]:
            if (disasm_dir / f).exists():
                import shutil

                shutil.copy(disasm_dir / f, out_dir / "work" / f)
                manifest["source_manifest"][f] = f

    writer.write_manifest(manifest)

    print(
        f"[ingest] OK — PRG {len(loader.prg_data) // 1024}KB | "
        f"CHR {len(loader.chr_data) // 1024 if loader.chr_data else 0}KB | "
        f"mapper {loader.header.mapper} | vectors {loader.vectors}"
    )
    print(f"[ingest] Wrote to {out_dir}/")
