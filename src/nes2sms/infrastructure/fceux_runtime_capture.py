"""FCEUX-backed runtime graphics capture for NES ROMs."""

from __future__ import annotations

import ctypes
import json
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..core.graphics.runtime_capture import RuntimeGraphicsCapture


WM_COMMAND = 0x0111
WM_SETTEXT = 0x000C
BM_CLICK = 0x00F5
MF_BYPOSITION = 0x0400

LUA_WINDOW_TITLE = "Lua Script"
SCRIPT_PATH_EDIT_ID = 1251
RUN_BUTTON_ID = 1249
OUTPUT_EDIT_ID = 1252
FILE_MENU_INDEX = 0
LUA_SUBMENU_INDEX = 7
NEW_LUA_WINDOW_INDEX = 1


user32 = ctypes.windll.user32 if platform.system() == "Windows" and hasattr(ctypes, "windll") else None


@dataclass
class FceuxRuntimeCaptureConfig:
    """Configuration for one runtime capture invocation."""

    nes_path: Path
    output_dir: Path
    mirroring: str
    capture_frame: int = 120
    timeout_seconds: int = 30
    emulator_path: Optional[str] = None


def capture_runtime_graphics(config: FceuxRuntimeCaptureConfig) -> RuntimeGraphicsCapture:
    """Capture a runtime graphics snapshot from FCEUX and return the parsed result."""
    _ensure_windows_capture_support()
    emulator_path = _resolve_fceux_path(config.emulator_path)
    runtime_dir = config.output_dir
    runtime_dir.mkdir(parents=True, exist_ok=True)

    capture_path = runtime_dir / "runtime_capture.json"
    script_path = runtime_dir / "capture_runtime.lua"
    script_path.write_text(
        _build_lua_script(
            output_path=capture_path,
            capture_frame=config.capture_frame,
            mirroring=config.mirroring,
        ),
        encoding="utf-8",
    )

    proc = subprocess.Popen([str(emulator_path), str(config.nes_path)])
    try:
        main_window = _wait_for_main_window(proc.pid, timeout_seconds=10)
        _open_lua_dialog(main_window)
        lua_window = _wait_for_window_title(proc.pid, LUA_WINDOW_TITLE, timeout_seconds=10)
        script_edit = _find_dialog_control(lua_window, SCRIPT_PATH_EDIT_ID)
        run_button = _find_dialog_control(lua_window, RUN_BUTTON_ID)
        _set_window_text(script_edit, str(script_path))
        user32.SendMessageW(run_button, BM_CLICK, 0, 0)
        _wait_for_capture_file(capture_path, lua_window, config.timeout_seconds)
    finally:
        _terminate_process_tree(proc)

    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    return RuntimeGraphicsCapture.from_dict(payload)


def _build_lua_script(output_path: Path, capture_frame: int, mirroring: str) -> str:
    template_path = Path(__file__).with_name("fceux_runtime_capture.lua")
    return (
        template_path.read_text(encoding="utf-8")
        .replace("__OUTPUT_PATH__", output_path.resolve().as_posix())
        .replace("__CAPTURE_FRAME__", str(int(capture_frame)))
        .replace("__MIRRORING__", mirroring)
        .replace("__VISIBLE_ROWS__", "28")
        .replace("__VISIBLE_COLS__", "32")
    )


def _resolve_fceux_path(explicit_path: Optional[str]) -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"FCEUX not found: {path}")
        return path

    for name in ("fceux64.exe", "fceux.exe", "fceux64", "fceux"):
        detected = shutil.which(name)
        if detected:
            return Path(detected)

    project_root = Path(__file__).resolve().parents[3]
    local_candidates = [
        project_root / "emulators" / "fceux" / "fceux64.exe",
        project_root / "emulators" / "fceux" / "fceux.exe",
    ]
    for candidate in local_candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError("FCEUX not found. Install FCEUX or pass --emulator /path/to/fceux.")


def _ensure_windows_capture_support() -> None:
    if user32 is None:
        raise RuntimeError("Runtime graphics capture currently requires Windows + Win32 user32 access.")


def _terminate_process_tree(proc: subprocess.Popen) -> None:
    try:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except Exception:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def _wait_for_main_window(process_id: int, timeout_seconds: int) -> int:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        window = _find_visible_window(process_id)
        if window:
            return window
        time.sleep(0.1)
    raise RuntimeError("Timed out waiting for FCEUX main window.")


def _wait_for_window_title(process_id: int, title: str, timeout_seconds: int) -> int:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        window = _find_visible_window(process_id, title=title)
        if window:
            return window
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for window '{title}'.")


def _open_lua_dialog(main_window: int) -> None:
    menu = user32.GetMenu(main_window)
    file_menu = user32.GetSubMenu(menu, FILE_MENU_INDEX)
    lua_menu = user32.GetSubMenu(file_menu, LUA_SUBMENU_INDEX)
    command_id = user32.GetMenuItemID(lua_menu, NEW_LUA_WINDOW_INDEX)
    user32.PostMessageW(main_window, WM_COMMAND, command_id, 0)


def _wait_for_capture_file(capture_path: Path, lua_window: int, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if capture_path.exists() and capture_path.stat().st_size > 0:
            return
        time.sleep(0.1)
    output_text = _read_lua_output(lua_window)
    detail = f" Lua output: {output_text}" if output_text else ""
    raise RuntimeError(f"Timed out waiting for runtime capture at {capture_path}.{detail}")


def _set_window_text(window_handle: int, text: str) -> None:
    user32.SendMessageW(window_handle, WM_SETTEXT, 0, ctypes.c_wchar_p(text))


def _find_dialog_control(parent_handle: int, control_id: int) -> int:
    handles: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _lparam):
        if user32.GetDlgCtrlID(hwnd) == control_id:
            handles.append(hwnd)
            return False
        return True

    user32.EnumChildWindows(parent_handle, callback, 0)
    if not handles:
        raise RuntimeError(f"FCEUX Lua dialog control id {control_id} not found.")
    return handles[0]


def _find_visible_window(process_id: int, title: Optional[str] = None) -> int:
    handles: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _lparam):
        target_pid = ctypes.c_uint()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
        if target_pid.value != process_id or not user32.IsWindowVisible(hwnd):
            return True
        if title is not None and _get_window_text(hwnd) != title:
            return True
        handles.append(hwnd)
        return False

    user32.EnumWindows(callback, 0)
    return handles[0] if handles else 0


def _get_window_text(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _read_lua_output(lua_window: int) -> str:
    try:
        output_handle = _find_dialog_control(lua_window, OUTPUT_EDIT_ID)
    except RuntimeError:
        return ""
    buffer = ctypes.create_unicode_buffer(8192)
    user32.GetWindowTextW(output_handle, buffer, len(buffer))
    return buffer.value.strip()
