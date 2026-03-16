"""Tests for raw NES reference rendering."""

from nes2sms.core.graphics.raw_reference_renderer import (
    build_raw_reference_report,
    render_raw_reference_frame,
)
from nes2sms.core.graphics.runtime_capture import RuntimeGraphicsCapture
from nes2sms.shared.constants import NES_PALETTE_RGB


def _base_payload() -> dict:
    return {
        "frame": 240,
        "scroll_x": 0,
        "scroll_y": 0,
        "ppuctrl": 0,
        "mirroring": "horizontal",
        "palette_ram": [0x0C] * 32,
        "ppu_vram": [0] * 0x1000,
        "oam": [0] * 256,
        "visible_rows": 28,
        "visible_cols": 32,
    }


def _tile_with_single_foreground_pixel() -> bytes:
    tile = bytearray(16)
    tile[0] = 0b10000000
    tile[8] = 0
    return bytes(tile)


def test_renderer_falls_back_to_solid_background_for_pong_like_capture():
    payload = _base_payload()
    payload["palette_ram"][0] = 0x0C
    payload["palette_ram"][17] = 0x16
    payload["oam"][0:4] = [19, 1, 0x00, 10]
    capture = RuntimeGraphicsCapture.from_dict(payload)
    chr_data = bytes(16) + _tile_with_single_foreground_pixel()

    frame = render_raw_reference_frame(capture, chr_data)
    report = build_raw_reference_report(frame)

    bg_rgb = list(NES_PALETTE_RGB[0x0C])
    sprite_rgb = list(NES_PALETTE_RGB[0x16])
    top_left = frame.rgba[0:4]
    sprite_offset = ((20 * 256) + 10) * 4
    sprite_pixel = frame.rgba[sprite_offset : sprite_offset + 4]

    assert frame.render_mode == "fallback_solid"
    assert not frame.has_useful_nametable
    assert frame.nonzero_nametable_bytes == 0
    assert frame.sprite_count == 1
    assert list(top_left[:3]) == bg_rgb
    assert list(sprite_pixel[:3]) == sprite_rgb
    assert report["dominant_colors"][0]["rgb"] == bg_rgb


def test_renderer_uses_nametable_when_background_data_exists():
    payload = _base_payload()
    payload["palette_ram"][0] = 0x0C
    payload["palette_ram"][1] = 0x1C
    payload["ppu_vram"][0] = 1
    capture = RuntimeGraphicsCapture.from_dict(payload)
    chr_data = bytes(16) + _tile_with_single_foreground_pixel()

    frame = render_raw_reference_frame(capture, chr_data)
    top_left = frame.rgba[0:4]

    assert frame.render_mode == "tilemap"
    assert frame.has_useful_nametable
    assert frame.nonzero_nametable_bytes == 1
    assert list(top_left[:3]) == list(NES_PALETTE_RGB[0x1C])
