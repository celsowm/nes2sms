"""FCEUX-backed reference frame capture for NES screenshots."""

from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .fceux_runtime_capture import (
    LUA_WINDOW_TITLE,
    RUN_BUTTON_ID,
    SCRIPT_PATH_EDIT_ID,
    _ensure_windows_capture_support,
    _find_dialog_control,
    _open_lua_dialog,
    _resolve_fceux_path,
    _set_window_text,
    _terminate_process_tree,
    _wait_for_main_window,
    _wait_for_window_title,
)


@dataclass
class FceuxScreenshotCaptureConfig:
    """Configuration for one NES screenshot capture."""

    nes_path: Path
    output_dir: Path
    capture_frame: int = 120
    timeout_seconds: int = 30
    emulator_path: Optional[str] = None


def capture_reference_frame(config: FceuxScreenshotCaptureConfig) -> Path:
    """Capture a NES reference frame to PNG and return the image path."""
    _ensure_windows_capture_support()
    emulator_path = _resolve_fceux_path(config.emulator_path)
    runtime_dir = config.output_dir
    runtime_dir.mkdir(parents=True, exist_ok=True)

    raw_gd_path = runtime_dir / "frame.gd"
    ready_path = runtime_dir / "frame_ready.json"
    png_path = runtime_dir / "frame.png"
    script_path = runtime_dir / "capture_frame.lua"
    script_path.write_text(
        _build_lua_script(
            raw_gd_path=raw_gd_path,
            ready_path=ready_path,
            capture_frame=config.capture_frame,
        ),
        encoding="utf-8",
    )

    import subprocess
    import time

    proc = subprocess.Popen([str(emulator_path), str(config.nes_path)])
    try:
        main_window = _wait_for_main_window(proc.pid, timeout_seconds=10)
        _open_lua_dialog(main_window)
        lua_window = _wait_for_window_title(proc.pid, LUA_WINDOW_TITLE, timeout_seconds=10)
        script_edit = _find_dialog_control(lua_window, SCRIPT_PATH_EDIT_ID)
        run_button = _find_dialog_control(lua_window, RUN_BUTTON_ID)
        _set_window_text(script_edit, str(script_path))
        from .fceux_runtime_capture import BM_CLICK, user32

        user32.SendMessageW(run_button, BM_CLICK, 0, 0)
        _wait_for_output_files(raw_gd_path, ready_path, timeout_seconds=config.timeout_seconds)
    finally:
        _terminate_process_tree(proc)

    metadata = json.loads(ready_path.read_text(encoding="utf-8"))
    gd_bytes = raw_gd_path.read_bytes()
    width, height, rgba = gd_screenshot_to_rgba(gd_bytes)
    write_rgba_png(png_path, width, height, rgba)
    metadata["png_path"] = str(png_path.resolve())
    ready_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return png_path


def _build_lua_script(raw_gd_path: Path, ready_path: Path, capture_frame: int) -> str:
    template_path = Path(__file__).with_name("fceux_screenshot_capture.lua")
    return (
        template_path.read_text(encoding="utf-8")
        .replace("__RAW_GD_PATH__", raw_gd_path.resolve().as_posix())
        .replace("__READY_PATH__", ready_path.resolve().as_posix())
        .replace("__CAPTURE_FRAME__", str(int(capture_frame)))
    )


def _wait_for_output_files(raw_gd_path: Path, ready_path: Path, timeout_seconds: int) -> None:
    import time

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if raw_gd_path.exists() and raw_gd_path.stat().st_size > 11 and ready_path.exists():
            return
        time.sleep(0.1)
    raise RuntimeError(
        f"Timed out waiting for FCEUX screenshot outputs: {raw_gd_path.name}, {ready_path.name}"
    )


def gd_screenshot_to_rgba(gd_bytes: bytes, *, width: int = 256) -> tuple[int, int, bytes]:
    """Decode FCEUX gui.gdscreenshot() output into RGBA pixels."""
    if len(gd_bytes) <= 11:
        raise ValueError("GD screenshot is too small to contain pixel data.")

    payload = gd_bytes[11:]
    if len(payload) % 4 != 0:
        raise ValueError("GD screenshot payload is not aligned to 32-bit pixels.")
    if len(payload) % (width * 4) != 0:
        raise ValueError("GD screenshot payload does not divide evenly into rows.")

    height = len(payload) // (width * 4)
    rgba = bytearray(width * height * 4)
    out = 0
    for index in range(0, len(payload), 4):
        # FCEUX exports pixels as A, R, G, B where A is always zero.
        _, red, green, blue = payload[index : index + 4]
        rgba[out : out + 4] = bytes((red, green, blue, 0xFF))
        out += 4
    return width, height, bytes(rgba)


def write_rgba_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    """Write a RGBA framebuffer to a PNG file without external dependencies."""
    stride = width * 4
    if len(rgba) != stride * height:
        raise ValueError("RGBA payload size does not match the image dimensions.")

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag)
        crc = zlib.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    for row in range(height):
        start = row * stride
        raw.append(0)
        raw.extend(rgba[start : start + stride])

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
    png.extend(chunk(b"IDAT", zlib.compress(bytes(raw), level=9)))
    png.extend(chunk(b"IEND", b""))
    path.write_bytes(bytes(png))
