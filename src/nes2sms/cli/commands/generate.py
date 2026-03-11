"""Generate command: Create WLA-DX project scaffold."""

import json
from pathlib import Path

from ...infrastructure.wla_dx import WlaDxGenerator, StubGenerator
from ...infrastructure.asset_writer import AssetWriter
from ...core.nes import get_mapper_strategy


def cmd_generate(args):
    """Generate WLA-DX project scaffold."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    out_dir = Path(args.out)

    # Calculate ROM banks - need enough for PRG + assets
    prg_size = manifest.get("nes_header", {}).get("prg_size", 32768)
    # Add extra banks for assets (tiles can be up to 16KB = 1 bank)
    rom_banks = max(12, (prg_size // 16384) + 8)

    # Get mapper strategy
    mapper_id = manifest.get("nes_header", {}).get("mapper", 0)
    mapper = get_mapper_strategy(mapper_id)
    bank_map = mapper.map_banks(prg_size // 16384)

    # Write warnings
    for warning in mapper.get_warnings():
        print(f"[generate] WARNING: {warning}")

    # Write banks.json
    writer = AssetWriter(out_dir.parent)  # Write to work/ directory
    banks_dict = {
        "mapper_id": mapper_id,
        "strategy": mapper.name,
        "slots": [
            {"sms_bank": b.sms_bank, "nes_bank": b.nes_bank, "fixed": b.fixed} for b in bank_map
        ],
    }
    writer.write_banks(banks_dict)

    # Generate WLA-DX project
    assets_dir = Path(args.assets) if args.assets else None
    generator = WlaDxGenerator(out_dir)
    generator.generate(rom_banks=rom_banks, assets_dir=assets_dir)

    # Generate stubs
    symbol_map_path = out_dir.parent / "work" / "symbol_map.json"
    symbols = []
    if symbol_map_path.exists():
        symbols = json.loads(symbol_map_path.read_text())

    stub_gen = StubGenerator(symbols=symbols)
    stub_gen.write_stubs(out_dir)

    print(f"[generate] SMS project scaffold written to {out_dir}/")
    print(f"[generate] Backend: {args.backend} | ROM banks: {rom_banks}")
    print(f"[generate] Mapper: {mapper.name} (ID: {mapper_id})")
