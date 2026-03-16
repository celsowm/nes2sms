"""Render a raw NES reference frame from runtime capture data."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from ...shared.constants import NES_PALETTE_RGB
from .runtime_capture import RuntimeGraphicsCapture


NES_FRAME_WIDTH = 256
NES_FRAME_HEIGHT = 240
NES_TILE_SIZE = 8


@dataclass
class RawReferenceFrame:
    """Rendered NES frame plus metadata about how it was reconstructed."""

    width: int
    height: int
    rgba: bytes
    render_mode: str
    has_useful_nametable: bool
    nonzero_nametable_bytes: int
    sprite_count: int
    background_rgb: Tuple[int, int, int]


def render_raw_reference_frame(
    capture: RuntimeGraphicsCapture,
    chr_data: bytes,
) -> RawReferenceFrame:
    """Render a comparison-oriented NES frame from runtime capture data."""
    nonzero_nametable_bytes = sum(1 for value in capture.ppu_vram if value)
    has_useful_nametable = nonzero_nametable_bytes > 0
    background_rgb = _resolve_nes_rgb(capture.palette_ram[0])
    rgba = bytearray(background_rgb + (255,)) * (NES_FRAME_WIDTH * NES_FRAME_HEIGHT)
    bg_opaque = [False] * (NES_FRAME_WIDTH * NES_FRAME_HEIGHT)

    if has_useful_nametable and chr_data:
        render_mode = "tilemap"
        _render_background(capture, chr_data, rgba, bg_opaque)
    else:
        render_mode = "fallback_solid"

    sprite_count = _render_sprites(capture, chr_data, rgba, bg_opaque)
    return RawReferenceFrame(
        width=NES_FRAME_WIDTH,
        height=NES_FRAME_HEIGHT,
        rgba=bytes(rgba),
        render_mode=render_mode,
        has_useful_nametable=has_useful_nametable,
        nonzero_nametable_bytes=nonzero_nametable_bytes,
        sprite_count=sprite_count,
        background_rgb=background_rgb,
    )


def summarize_rgba_frame(width: int, height: int, rgba: bytes, *, top_count: int = 5) -> Dict[str, object]:
    """Build the same high-level metrics used by screenshot-based comparison."""
    pixels = [tuple(rgba[index : index + 3]) for index in range(0, len(rgba), 4)]
    top_left = pixels[0] if pixels else (0, 0, 0)
    center = pixels[((height // 2) * width) + (width // 2)] if pixels else (0, 0, 0)
    dominant = Counter(pixels).most_common(top_count)
    return {
        "size": [width, height],
        "top_left_rgb": list(top_left),
        "center_rgb": list(center),
        "dominant_colors": [
            {
                "count": int(count),
                "rgb": list(rgb),
            }
            for rgb, count in dominant
        ],
    }


def build_raw_reference_report(frame: RawReferenceFrame) -> Dict[str, object]:
    """Return a JSON-serializable report for a rendered raw reference frame."""
    metrics = summarize_rgba_frame(frame.width, frame.height, frame.rgba)
    return {
        "source": "nes_runtime_raw",
        "render_mode": frame.render_mode,
        "has_useful_nametable": frame.has_useful_nametable,
        "nonzero_nametable_bytes": frame.nonzero_nametable_bytes,
        "sprite_count": frame.sprite_count,
        "background_rgb": list(frame.background_rgb),
        **metrics,
    }


def _render_background(
    capture: RuntimeGraphicsCapture,
    chr_data: bytes,
    rgba: bytearray,
    bg_opaque: List[bool],
) -> None:
    pattern_base = 0x1000 if (capture.ppuctrl & 0x10) else 0x0000
    fine_x = capture.scroll_x & 0x07
    fine_y = capture.scroll_y & 0x07

    for screen_y in range(NES_FRAME_HEIGHT):
        world_y = screen_y + fine_y
        tile_row = (world_y // NES_TILE_SIZE) % 30
        fine_row = world_y & 0x07
        nt_y = ((capture.ppuctrl >> 1) & 0x01) ^ ((world_y // (NES_TILE_SIZE * 30)) & 0x01)

        for screen_x in range(NES_FRAME_WIDTH):
            world_x = screen_x + fine_x
            tile_col = (world_x // NES_TILE_SIZE) % 32
            fine_col = world_x & 0x07
            nt_x = (capture.ppuctrl & 0x01) ^ ((world_x // (NES_TILE_SIZE * 32)) & 0x01)
            nt_index = (nt_y * 2) + nt_x

            tile_index = _read_nametable_tile(capture, nt_index, tile_row, tile_col)
            palette_id = _read_attribute_palette(capture, nt_index, tile_row, tile_col)
            color_index = _read_pattern_pixel(chr_data, pattern_base, tile_index, fine_row, fine_col)
            if color_index == 0:
                continue

            rgb = _resolve_bg_rgb(capture.palette_ram, palette_id, color_index)
            offset = ((screen_y * NES_FRAME_WIDTH) + screen_x) * 4
            rgba[offset : offset + 4] = bytes((rgb[0], rgb[1], rgb[2], 255))
            bg_opaque[(screen_y * NES_FRAME_WIDTH) + screen_x] = True


def _render_sprites(
    capture: RuntimeGraphicsCapture,
    chr_data: bytes,
    rgba: bytearray,
    bg_opaque: Sequence[bool],
) -> int:
    if not chr_data:
        return 0

    sprite_count = 0
    sprite_size_16 = bool(capture.ppuctrl & 0x20)
    sprite_base = 0x1000 if (capture.ppuctrl & 0x08) else 0x0000

    for base in range(252, -1, -4):
        y = int(capture.oam[base]) & 0xFF
        tile = int(capture.oam[base + 1]) & 0xFF
        attr = int(capture.oam[base + 2]) & 0xFF
        x = int(capture.oam[base + 3]) & 0xFF
        if y >= 0xEF or (y == 0 and tile == 0 and attr == 0 and x == 0):
            continue

        sprite_count += 1
        sprite_y = y + 1
        palette_id = attr & 0x03
        behind_bg = bool(attr & 0x20)
        flip_h = bool(attr & 0x40)
        flip_v = bool(attr & 0x80)
        sprite_height = 16 if sprite_size_16 else 8

        for local_y in range(sprite_height):
            screen_y = sprite_y + local_y
            if not (0 <= screen_y < NES_FRAME_HEIGHT):
                continue
            sample_y = (sprite_height - 1 - local_y) if flip_v else local_y
            tile_offset = sample_y // 8
            pixel_row = sample_y & 0x07

            if sprite_size_16:
                tile_base = tile & 0xFE
                pattern_base = (tile & 0x01) * 0x1000
                tile_index = tile_base + tile_offset
            else:
                pattern_base = sprite_base
                tile_index = tile

            for local_x in range(8):
                screen_x = x + local_x
                if not (0 <= screen_x < NES_FRAME_WIDTH):
                    continue
                sample_x = 7 - local_x if flip_h else local_x
                color_index = _read_pattern_pixel(
                    chr_data,
                    pattern_base,
                    tile_index,
                    pixel_row,
                    sample_x,
                )
                if color_index == 0:
                    continue

                pixel_index = (screen_y * NES_FRAME_WIDTH) + screen_x
                if behind_bg and bg_opaque[pixel_index]:
                    continue

                rgb = _resolve_sprite_rgb(capture.palette_ram, palette_id, color_index)
                offset = pixel_index * 4
                rgba[offset : offset + 4] = bytes((rgb[0], rgb[1], rgb[2], 255))

    return sprite_count


def _read_pattern_pixel(
    chr_data: bytes,
    pattern_base: int,
    tile_index: int,
    row: int,
    col: int,
) -> int:
    offset = pattern_base + (tile_index * 16)
    if offset < 0 or (offset + 15) >= len(chr_data):
        return 0

    plane0 = chr_data[offset + row]
    plane1 = chr_data[offset + row + 8]
    bit0 = (plane0 >> (7 - col)) & 0x01
    bit1 = (plane1 >> (7 - col)) & 0x01
    return (bit1 << 1) | bit0


def _resolve_bg_rgb(palette_ram: Sequence[int], palette_id: int, color_index: int) -> Tuple[int, int, int]:
    if color_index == 0:
        return _resolve_nes_rgb(palette_ram[0])
    palette_offset = (palette_id & 0x03) * 4
    return _resolve_nes_rgb(palette_ram[palette_offset + color_index])


def _resolve_sprite_rgb(palette_ram: Sequence[int], palette_id: int, color_index: int) -> Tuple[int, int, int]:
    palette_offset = 16 + ((palette_id & 0x03) * 4)
    return _resolve_nes_rgb(palette_ram[palette_offset + color_index])


def _resolve_nes_rgb(color_index: int) -> Tuple[int, int, int]:
    rgb = NES_PALETTE_RGB[int(color_index) & 0x3F]
    return int(rgb[0]), int(rgb[1]), int(rgb[2])


def _resolve_physical_nametable(nt_index: int, mirroring: str) -> int:
    mirroring = (mirroring or "horizontal").lower()
    if mirroring == "vertical":
        return [0, 1, 0, 1][nt_index & 0x03]
    if mirroring == "horizontal":
        return [0, 0, 1, 1][nt_index & 0x03]
    return nt_index & 0x03


def _read_nametable_tile(capture: RuntimeGraphicsCapture, nt_index: int, row: int, col: int) -> int:
    physical_nt = _resolve_physical_nametable(nt_index, capture.mirroring)
    offset = (physical_nt * 0x400) + ((row % 30) * 32) + (col % 32)
    return capture.ppu_vram[offset] & 0xFF


def _read_attribute_palette(capture: RuntimeGraphicsCapture, nt_index: int, row: int, col: int) -> int:
    physical_nt = _resolve_physical_nametable(nt_index, capture.mirroring)
    attr_offset = (physical_nt * 0x400) + 0x3C0 + (((row % 30) // 4) * 8) + ((col % 32) // 4)
    attr = capture.ppu_vram[attr_offset] & 0xFF
    shift = (((row % 4) // 2) * 4) + (((col % 4) // 2) * 2)
    return (attr >> shift) & 0x03
