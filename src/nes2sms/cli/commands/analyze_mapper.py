"""Analyze mapper command."""

import json
from pathlib import Path

from ...core.nes import get_mapper_strategy
from ...infrastructure.asset_writer import AssetWriter


def cmd_analyze_mapper(args):
    """Analyze NES mapper and generate bank mapping."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Get mapper info
    nes_hdr = manifest.get("nes_header", {})
    mapper_id = nes_hdr.get("mapper", -1)
    prg_size = nes_hdr.get("prg_size", 0)
    prg_banks = prg_size // 16384 if prg_size > 0 else 0

    # Get strategy and generate mapping
    strategy = get_mapper_strategy(mapper_id)
    bank_map = strategy.map_banks(prg_banks)

    # Build banks.json
    banks = {
        "mapper_id": mapper_id,
        "strategy": strategy.name,
        "prg_size_kb": prg_size // 1024,
        "slots": [
            {"sms_bank": b.sms_bank, "nes_bank": b.nes_bank, "fixed": b.fixed} for b in bank_map
        ],
    }

    # Write outputs
    writer = AssetWriter(out_dir)
    writer.write_banks(banks)

    # Update manifest
    for warning in strategy.get_warnings():
        manifest.setdefault("warnings", []).append(warning)

    if "conversion_state" in manifest:
        manifest["conversion_state"]["analyze_mapper"] = "DONE"

    writer.write_json("manifest_sms.json", manifest, "work")

    print(f"[analyze-mapper] Mapper {mapper_id} ({strategy.name}) detected.")
    print(f"[analyze-mapper] Wrote {len(bank_map)} banks to banks.json")
