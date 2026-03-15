"""Tests for runtime graphics snapshot parsing and asset building."""

from nes2sms.core.graphics.runtime_asset_builder import (
    build_blank_sat,
    build_blank_tilemap,
    build_runtime_background_assets,
)
from nes2sms.core.graphics.runtime_capture import (
    RuntimeGraphicsCapture,
    assess_runtime_capture,
    sprites_from_runtime_oam,
)
from nes2sms.core.graphics.tile_converter import TileConverter
from nes2sms.shared.models import TileConversionResult


def _capture_payload() -> dict:
    ppu_vram = [0] * 0x1000
    ppu_vram[0] = 1  # top-left visible tile
    ppu_vram[0x3C0] = 0x02  # top-left quadrant uses BG palette 2
    return {
        "frame": 120,
        "scroll_x": 0,
        "scroll_y": 0,
        "ppuctrl": 0,
        "mirroring": "horizontal",
        "palette_ram": [0x0F] * 32,
        "ppu_vram": ppu_vram,
        "oam": [0] * 256,
        "visible_rows": 28,
        "visible_cols": 32,
    }


def test_runtime_capture_requires_all_required_fields():
    payload = _capture_payload()
    del payload["oam"]

    try:
        RuntimeGraphicsCapture.from_dict(payload)
        assert False, "Expected missing-field validation to raise"
    except ValueError as exc:
        assert "oam" in str(exc)


def test_runtime_capture_validates_payload_lengths():
    payload = _capture_payload()
    payload["palette_ram"] = [0x0F] * 16

    try:
        RuntimeGraphicsCapture.from_dict(payload)
        assert False, "Expected palette length validation to raise"
    except ValueError as exc:
        assert "32 palette bytes" in str(exc)


def test_assess_runtime_capture_rejects_empty_nametable_snapshot():
    payload = _capture_payload()
    payload["ppu_vram"] = [0] * 0x1000
    capture = RuntimeGraphicsCapture.from_dict(payload)

    usable, reason = assess_runtime_capture(capture)

    assert not usable
    assert "all empty" in reason.lower()


def test_assess_runtime_capture_accepts_nonempty_snapshot():
    payload = _capture_payload()
    payload["palette_ram"][1] = 0x21
    payload["oam"][0:4] = [20, 3, 0, 40]
    capture = RuntimeGraphicsCapture.from_dict(payload)

    usable, reason = assess_runtime_capture(capture)

    assert usable
    assert reason == ""


def test_blank_tilemap_and_sat_are_always_nonempty():
    tilemap = build_blank_tilemap(blank_tile_index=3, split_tile=2, rows=4, cols=2)
    sat_y, sat_xt = build_blank_sat()

    assert len(tilemap) == 16
    assert tilemap[:4] == bytes([3, 0x00, 3, 0x00])
    assert tilemap[-4:] == bytes([3, 0x10, 3, 0x10])
    assert sat_y == bytes([0xD0])
    assert sat_xt == bytes([0x00, 0x00])


def test_runtime_background_builder_materializes_palette_variants_into_blank_slots():
    capture = RuntimeGraphicsCapture.from_dict(_capture_payload())
    chr_data = bytes([0x00] * 16 + [0xFF] * 16 + [0x00] * (16 * 6))
    converter = TileConverter(color_maps=[[0, 1, 2, 3]], flip_strategy="none", max_tiles=256)
    base_result = converter.convert(chr_data)
    tile_result = TileConversionResult(
        sms_tiles=list(base_result.sms_tiles),
        flip_index=dict(base_result.flip_index),
        warnings=list(base_result.warnings),
        tile_metadata=list(base_result.tile_metadata),
    )
    color_maps = [
        [0, 1, 2, 3],
        [0, 4, 5, 6],
        [0, 7, 8, 9],
        [0, 10, 11, 12],
    ]

    result = build_runtime_background_assets(
        capture,
        chr_data=chr_data,
        tile_result=tile_result,
        color_maps=color_maps,
        split_tile=1,
        rows=1,
        cols=1,
    )

    mapped = result["variant_lookup"][(1, 2)]
    assert mapped != 1
    assert result["tilemap"] == bytes([mapped, 0x10])
    assert tile_result.sms_tiles[mapped] != tile_result.sms_tiles[1]


def test_sprites_from_runtime_oam_filters_hidden_entries():
    oam = [0] * 256
    oam[0:4] = [10, 3, 0x41, 22]
    oam[4:8] = [0xF0, 4, 0x00, 30]

    sprites = sprites_from_runtime_oam(oam)

    assert sprites == [{"y": 10, "tile": 3, "attr": 0x41, "x": 22}]
