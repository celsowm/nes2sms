"""Tests for FCEUX screenshot decoding helpers."""

from pathlib import Path
import struct

from nes2sms.infrastructure.fceux_screenshot_capture import gd_screenshot_to_rgba, write_rgba_png


def test_gd_screenshot_to_rgba_decodes_argb_payload():
    header = b"gd_header11"
    payload = bytes(
        [
            0x00,
            0x11,
            0x22,
            0x33,
            0x00,
            0x44,
            0x55,
            0x66,
        ]
    )

    width, height, rgba = gd_screenshot_to_rgba(header + payload, width=2)

    assert (width, height) == (2, 1)
    assert rgba == bytes([0x11, 0x22, 0x33, 0xFF, 0x44, 0x55, 0x66, 0xFF])


def test_write_rgba_png_writes_valid_png_header(tmp_path: Path):
    out_path = tmp_path / "frame.png"
    rgba = bytes(
        [
            0x10,
            0x20,
            0x30,
            0xFF,
            0x40,
            0x50,
            0x60,
            0xFF,
        ]
    )

    write_rgba_png(out_path, 2, 1, rgba)

    data = out_path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", data[16:24]) == (2, 1)
