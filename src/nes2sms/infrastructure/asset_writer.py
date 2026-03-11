"""Asset file writing utilities."""

import json
from pathlib import Path
from typing import List, Dict, Any


class AssetWriter:
    """Writes converted assets to disk."""

    def __init__(self, output_dir: Path):
        """
        Initialize asset writer.

        Args:
            output_dir: Base output directory
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_binary(self, filename: str, data: bytes, subdir: str = None):
        """Write binary data to file."""
        if subdir:
            path = self.output_dir / subdir / filename
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path = self.output_dir / filename
        path.write_bytes(data)

    def write_text(self, filename: str, content: str, subdir: str = None):
        """Write text data to file."""
        if subdir:
            path = self.output_dir / subdir / filename
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path = self.output_dir / filename
        path.write_text(content, encoding="utf-8")

    def write_json(self, filename: str, data: Any, subdir: str = None, indent: int = 2):
        """Write JSON data to file."""
        if subdir:
            path = self.output_dir / subdir / filename
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path = self.output_dir / filename
        path.write_text(json.dumps(data, indent=indent), encoding="utf-8")

    def write_tiles(self, tiles: List[bytes]):
        """Write tile data to tiles.bin."""
        data = b"".join(tiles)
        self.write_binary("tiles.bin", data, "assets")

    def write_palette(self, palette: bytes, name: str):
        """Write palette data (bg or spr)."""
        self.write_binary(f"palette_{name}.bin", palette, "assets")

    def write_flip_index(self, flip_index: Dict):
        """Write flip index JSON."""
        # Convert keys to strings for JSON serialization
        serializable = {str(k): v for k, v in flip_index.items()}
        self.write_json("flip_index.json", serializable, "assets")

    def write_manifest(self, manifest: Dict):
        """Write conversion manifest."""
        self.write_json("manifest_sms.json", manifest, "work")

    def write_banks(self, banks: Dict):
        """Write bank mapping."""
        self.write_json("banks.json", banks, "work")

    def write_symbol_map(self, symbols: List):
        """Write symbol map (from disassembler)."""
        self.write_json("symbol_map.json", symbols, "work")
