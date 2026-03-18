"""SMS asset builders derived from runtime NES graphics snapshots."""

from typing import Dict, List, Sequence, Tuple

from .runtime_capture import (
    RuntimeGraphicsCapture,
    VISIBLE_COLS,
    VISIBLE_ROWS,
    extract_visible_tile_and_palette_grids,
)
from .tile_converter import TileConverter


def build_blank_tilemap(
    blank_tile_index: int = 0,
    *,
    split_tile: int = 6,
    rows: int = VISIBLE_ROWS,
    cols: int = VISIBLE_COLS,
) -> bytes:
    """Build a blank SMS tilemap with the legacy split priority policy removed."""
    data = bytearray()
    for row in range(rows):
        for _ in range(cols):
            data.append(blank_tile_index & 0xFF)
            data.append(0x00)
    return bytes(data)


def build_blank_sat() -> Tuple[bytes, bytes]:
    """Build a neutral SAT payload that hides all sprites."""
    return bytes([0xD0]), bytes([0x00, 0x00])


def build_sms_tilemap_bytes(tile_grid: Sequence[Sequence[int]], *, split_tile: int = 6) -> bytes:
    """Encode a visible SMS tilemap from tile indices using the repo's attr convention."""
    data = bytearray()
    for row_index, row in enumerate(tile_grid):
        for tile in row:
            attr = (int(tile) >> 8) & 0x01
            data.append(int(tile) & 0xFF)
            data.append(attr)
    return bytes(data)


def build_runtime_background_assets(
    capture: RuntimeGraphicsCapture,
    *,
    chr_data: bytes,
    tile_result,
    color_maps: List[List[int]],
    split_tile: int = 6,
    rows: int = VISIBLE_ROWS,
    cols: int = VISIBLE_COLS,
) -> Dict[str, object]:
    """
    Materialize palette-specific background tile variants and a visible SMS tilemap.

    Runtime background tiles stay inside the 8-bit pattern index space already assumed
    by the current SMS HAL. When no spare blank tile is available, the base tile is kept.
    """

    warnings: List[str] = []
    if not chr_data or not tile_result.sms_tiles:
        return {"tilemap": build_blank_tilemap(split_tile=split_tile), "warnings": warnings}

    tile_grid, palette_grid = extract_visible_tile_and_palette_grids(
        capture,
        rows=rows,
        cols=cols,
    )
    bg_maps = color_maps[:4] if len(color_maps) >= 4 else [[0, 1, 2, 3]] * 4
    converter = TileConverter(color_maps=[bg_maps[0]], flip_strategy="none", max_tiles=256)

    tiles = tile_result.sms_tiles
    metadata = tile_result.tile_metadata
    max_tile_index = min(511, len(tiles) - 1, (len(chr_data) // 16) - 1)
    used_base_tiles = {
        tile
        for row in tile_grid
        for tile in row
        if isinstance(tile, int) and 0 <= tile <= max_tile_index
    }
    free_slots = [
        idx
        for idx in range(max_tile_index + 1)
        if idx not in used_base_tiles and not any(tiles[idx])
    ]

    variant_lookup: Dict[Tuple[int, int], int] = {}
    mapped_grid: List[List[int]] = []
    for row_index in range(rows):
        mapped_row: List[int] = []
        for col_index in range(cols):
            tile = tile_grid[row_index][col_index]
            palette = palette_grid[row_index][col_index]

            if not (0 <= tile <= max_tile_index):
                mapped_row.append(0)
                continue

            key = (tile, palette)
            if key in variant_lookup:
                mapped_row.append(variant_lookup[key])
                continue

            if palette == 0:
                variant_lookup[key] = tile
                mapped_row.append(tile)
                continue

            src_off = tile * 16
            variant_tile = converter.convert_tile_with_map(
                chr_data[src_off : src_off + 16],
                bg_maps[palette],
            )
            mapped_idx = _find_tile_index_within(tiles, variant_tile, max_tile_index)
            if mapped_idx is None:
                if not free_slots:
                    warnings.append(
                        f"No blank tile slots left for BG tile={tile} palette={palette}; using base tile."
                    )
                    mapped_idx = tile
                else:
                    mapped_idx = free_slots.pop(0)
                    tiles[mapped_idx] = variant_tile
                    if mapped_idx < len(metadata):
                        metadata[mapped_idx] = {
                            "bank": metadata[mapped_idx].get("bank", 0),
                            "tile_index": tile,
                            "runtime_bg_palette": palette,
                        }
                    else:
                        metadata.append(
                            {
                                "bank": 0,
                                "tile_index": tile,
                                "runtime_bg_palette": palette,
                            }
                        )

            variant_lookup[key] = mapped_idx
            mapped_row.append(mapped_idx)
        mapped_grid.append(mapped_row)

    return {
        "tilemap": build_sms_tilemap_bytes(mapped_grid, split_tile=split_tile),
        "warnings": warnings,
        "variant_lookup": variant_lookup,
    }


def _find_tile_index_within(tiles: Sequence[bytes], candidate: bytes, max_index: int) -> int | None:
    limit = min(max_index + 1, len(tiles))
    for idx in range(limit):
        if tiles[idx] == candidate:
            return idx
    return None
