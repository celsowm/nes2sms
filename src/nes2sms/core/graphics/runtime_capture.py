"""Runtime graphics snapshot parsing and visible-grid helpers."""

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


VISIBLE_COLS = 32
VISIBLE_ROWS = 28


@dataclass
class RuntimeGraphicsCapture:
    """Parsed runtime graphics snapshot captured from a NES emulator."""

    frame: int
    scroll_x: int
    scroll_y: int
    ppuctrl: int
    mirroring: str
    palette_ram: List[int]
    ppu_vram: List[int]
    oam: List[int]
    visible_rows: int = VISIBLE_ROWS
    visible_cols: int = VISIBLE_COLS
    source: str = "fceux_lua"

    @classmethod
    def from_dict(cls, payload: Dict) -> "RuntimeGraphicsCapture":
        """Validate and build a runtime capture object from decoded JSON."""
        required = (
            "frame",
            "scroll_x",
            "scroll_y",
            "ppuctrl",
            "palette_ram",
            "ppu_vram",
            "oam",
        )
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"Missing runtime capture fields: {', '.join(missing)}")

        palette_ram = [int(v) & 0x3F for v in payload["palette_ram"]]
        ppu_vram = [int(v) & 0xFF for v in payload["ppu_vram"]]
        oam = [int(v) & 0xFF for v in payload["oam"]]

        if len(palette_ram) != 32:
            raise ValueError(f"Expected 32 palette bytes, got {len(palette_ram)}")
        if len(ppu_vram) != 0x1000:
            raise ValueError(f"Expected 4096 nametable bytes, got {len(ppu_vram)}")
        if len(oam) != 256:
            raise ValueError(f"Expected 256 OAM bytes, got {len(oam)}")

        return cls(
            frame=int(payload["frame"]),
            scroll_x=int(payload["scroll_x"]) & 0xFF,
            scroll_y=int(payload["scroll_y"]) & 0xFF,
            ppuctrl=int(payload["ppuctrl"]) & 0xFF,
            mirroring=str(payload.get("mirroring", "horizontal")),
            palette_ram=palette_ram,
            ppu_vram=ppu_vram,
            oam=oam,
            visible_rows=int(payload.get("visible_rows", VISIBLE_ROWS)),
            visible_cols=int(payload.get("visible_cols", VISIBLE_COLS)),
            source=str(payload.get("source", "fceux_lua")),
        )


def assess_runtime_capture(capture: "RuntimeGraphicsCapture") -> Tuple[bool, str]:
    """Return whether a runtime snapshot is usable as a startup graphics source."""
    nonzero_vram = sum(1 for value in capture.ppu_vram if value)
    nondefault_palette = sum(1 for value in capture.palette_ram if value != 0x0F)
    sprite_count = len(sprites_from_runtime_oam(capture.oam))

    if nonzero_vram == 0 and nondefault_palette == 0 and sprite_count == 0:
        return False, "PPU nametable, palette, and OAM capture are all empty."
    return True, ""


def sprites_from_runtime_oam(oam_bytes: Sequence[int]) -> List[Dict[str, int]]:
    """Convert captured OAM bytes into NES-style sprite dictionaries."""
    sprites: List[Dict[str, int]] = []
    for base in range(0, min(len(oam_bytes), 256), 4):
        y = int(oam_bytes[base]) & 0xFF
        tile = int(oam_bytes[base + 1]) & 0xFF
        attr = int(oam_bytes[base + 2]) & 0xFF
        x = int(oam_bytes[base + 3]) & 0xFF
        if y >= 0xEF or (y == 0 and tile == 0 and attr == 0 and x == 0):
            continue
        sprites.append({"y": y, "tile": tile, "attr": attr, "x": x})
    return sprites


def extract_visible_tile_and_palette_grids(
    capture: RuntimeGraphicsCapture,
    *,
    rows: int = VISIBLE_ROWS,
    cols: int = VISIBLE_COLS,
) -> Tuple[List[List[int]], List[List[int]]]:
    """Resolve the visible nametable tiles and 2-bit palette IDs from captured VRAM."""
    base_nt = capture.ppuctrl & 0x03
    coarse_x = (capture.scroll_x // 8) & 0x1F
    coarse_y = (capture.scroll_y // 8) & 0x1F
    tile_grid: List[List[int]] = []
    palette_grid: List[List[int]] = []

    for row in range(rows):
        tile_row: List[int] = []
        palette_row: List[int] = []
        for col in range(cols):
            virtual_col = coarse_x + col
            virtual_row = coarse_y + row
            nt_x = (base_nt & 0x01) ^ ((virtual_col // 32) & 0x01)
            nt_y = ((base_nt >> 1) & 0x01) ^ ((virtual_row // 30) & 0x01)
            nt_index = (nt_y * 2) + nt_x
            local_col = virtual_col % 32
            local_row = virtual_row % 30
            tile_val = _read_nametable_tile(capture, nt_index, local_row, local_col)
            if capture.ppuctrl & 0x10:
                tile_val += 256
            tile_row.append(tile_val)
            palette_row.append(_read_attribute_palette(capture, nt_index, local_row, local_col))
        tile_grid.append(tile_row)
        palette_grid.append(palette_row)

    return tile_grid, palette_grid


def _resolve_physical_nametable(nt_index: int, mirroring: str) -> int:
    mirroring = (mirroring or "horizontal").lower()
    if mirroring == "vertical":
        return [0, 1, 0, 1][nt_index & 0x03]
    if mirroring == "horizontal":
        return [0, 0, 1, 1][nt_index & 0x03]
    return nt_index & 0x03


def _read_nametable_tile(
    capture: RuntimeGraphicsCapture,
    nt_index: int,
    row: int,
    col: int,
) -> int:
    physical_nt = _resolve_physical_nametable(nt_index, capture.mirroring)
    offset = (physical_nt * 0x400) + (row * 32) + col
    return capture.ppu_vram[offset] & 0xFF


def _read_attribute_palette(
    capture: RuntimeGraphicsCapture,
    nt_index: int,
    row: int,
    col: int,
) -> int:
    physical_nt = _resolve_physical_nametable(nt_index, capture.mirroring)
    attr_offset = (physical_nt * 0x400) + 0x3C0 + ((row // 4) * 8) + (col // 4)
    attr = capture.ppu_vram[attr_offset] & 0xFF
    shift = ((row % 4) // 2) * 4 + ((col % 4) // 2) * 2
    return (attr >> shift) & 0x03
