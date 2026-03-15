"""Toolchain and emulator helpers for bootstrap_hello."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable


FCEUX_RELEASE_API = "https://api.github.com/repos/TASEmulators/fceux/releases/latest"
BLASTEM_WIN_URL = "https://www.retrodev.com/blastem/blastem-win32-0.6.2.zip"


def select_fceux_release_asset(release_payload: dict[str, Any]) -> str:
    """Pick the preferred FCEUX Windows asset URL from release payload."""
    assets = release_payload.get("assets", [])
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if name.endswith("win64.zip") and "qtsdl" not in name:
            return str(asset["browser_download_url"])
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if "win64" in name and name.endswith(".zip"):
            return str(asset["browser_download_url"])
    raise RuntimeError("Could not find a suitable FCEUX win64 zip asset")


def find_wla_toolchain(
    project_root: Path,
    *,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> tuple[Path, Path]:
    """Find wla-6502 and wlalink in PATH or local tools/wla-dx."""
    wla_in_path = which_fn("wla-6502.exe") or which_fn("wla-6502")
    wlalink_in_path = which_fn("wlalink.exe") or which_fn("wlalink")
    if wla_in_path and wlalink_in_path:
        return Path(wla_in_path), Path(wlalink_in_path)

    local_dir = project_root / "tools" / "wla-dx"
    candidates = [
        (local_dir / "wla-6502.exe", local_dir / "wlalink.exe"),
        (local_dir / "wla-6502", local_dir / "wlalink"),
    ]
    for wla, linker in candidates:
        if wla.exists() and linker.exists():
            return wla, linker

    raise FileNotFoundError(
        "wla-6502/wlalink not found. Install WLA-DX or place binaries in tools/wla-dx."
    )


def resolve_fceux(
    project_root: Path,
    explicit_path: str | None,
    allow_download: bool,
    *,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> Path:
    """Resolve FCEUX path or auto-install if missing."""
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"NES emulator not found: {path}")
        return path

    detected = (
        which_fn("fceux64.exe")
        or which_fn("fceux.exe")
        or which_fn("fceux64")
        or which_fn("fceux")
    )
    if detected:
        return Path(detected)

    for local_path in (
        project_root / "emulators" / "fceux" / "fceux64.exe",
        project_root / "emulators" / "fceux" / "fceux.exe",
    ):
        if local_path.exists():
            return local_path

    if not allow_download:
        raise FileNotFoundError("FCEUX not found and auto-download is disabled.")
    return install_fceux(project_root)


def resolve_blastem(
    project_root: Path,
    explicit_path: str | None,
    allow_download: bool,
    *,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> Path:
    """Resolve BlastEm path or auto-install if missing."""
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"SMS emulator not found: {path}")
        return path

    detected = which_fn("blastem.exe") or which_fn("blastem")
    if detected:
        return Path(detected)

    local_path = project_root / "emulators" / "blastem" / "blastem.exe"
    if local_path.exists():
        return local_path

    if not allow_download:
        raise FileNotFoundError("BlastEm not found and auto-download is disabled.")
    return install_blastem(project_root)


def install_fceux(project_root: Path) -> Path:
    target_dir = project_root / "emulators" / "fceux"
    target_dir.mkdir(parents=True, exist_ok=True)

    payload = download_json(FCEUX_RELEASE_API)
    asset_url = select_fceux_release_asset(payload)
    zip_path = target_dir / "fceux-win64.zip"
    download_file(asset_url, zip_path)
    extract_zip(zip_path, target_dir)
    zip_path.unlink(missing_ok=True)

    exe_path = target_dir / "fceux.exe"
    if exe_path.exists():
        return exe_path

    discovered = find_first_file(target_dir, "fceux.exe")
    if discovered is None:
        raise RuntimeError("FCEUX download completed but fceux.exe was not found.")
    return discovered


def install_blastem(project_root: Path) -> Path:
    target_dir = project_root / "emulators" / "blastem"
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = project_root / "emulators" / "blastem.zip"
    download_file(BLASTEM_WIN_URL, zip_path)
    extract_zip(zip_path, target_dir)
    zip_path.unlink(missing_ok=True)

    exe_path = target_dir / "blastem.exe"
    if exe_path.exists():
        return exe_path

    discovered = find_first_file(target_dir, "blastem.exe")
    if discovered is None:
        raise RuntimeError("BlastEm download completed but blastem.exe was not found.")
    return discovered


def compile_prg(
    nes_dir: Path,
    logs_dir: Path,
    wla_6502: Path,
    wlalink: Path,
    *,
    format_process_log_fn: Callable[[subprocess.CompletedProcess[str], str], str],
) -> Path:
    asm_name = "hello_world_wla.asm"
    obj_name = "hello_prg.o"
    link_name = "linkfile_prg"
    out_name = "hello_prg.bin"

    assemble_proc = subprocess.run(
        [str(wla_6502), "-o", obj_name, asm_name],
        cwd=str(nes_dir),
        capture_output=True,
        text=True,
    )
    (logs_dir / "wla6502.log").write_text(
        format_process_log_fn(assemble_proc, "wla-6502"),
        encoding="utf-8",
    )
    if assemble_proc.returncode != 0:
        raise RuntimeError(f"wla-6502 failed. See {logs_dir / 'wla6502.log'}")

    link_proc = subprocess.run(
        [str(wlalink), link_name, out_name],
        cwd=str(nes_dir),
        capture_output=True,
        text=True,
    )
    (logs_dir / "wlalink.log").write_text(
        format_process_log_fn(link_proc, "wlalink"),
        encoding="utf-8",
    )
    if link_proc.returncode != 0:
        raise RuntimeError(f"wlalink failed. See {logs_dir / 'wlalink.log'}")

    prg_path = nes_dir / out_name
    if not prg_path.exists():
        raise RuntimeError("PRG file was not generated.")
    if prg_path.stat().st_size != 16384:
        raise RuntimeError(f"Expected 16384-byte PRG, got {prg_path.stat().st_size}")
    return prg_path


def format_process_log(proc: subprocess.CompletedProcess[str], title: str) -> str:
    return (
        f"== {title} ==\n"
        f"returncode: {proc.returncode}\n\n"
        f"stdout:\n{proc.stdout}\n\n"
        f"stderr:\n{proc.stderr}\n"
    )


def download_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "nes2sms-bootstrap-hello",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "nes2sms-bootstrap-hello"})
    with urllib.request.urlopen(request) as response, destination.open("wb") as out_file:
        shutil.copyfileobj(response, out_file)


def extract_zip(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(destination)


def find_first_file(base_dir: Path, filename: str) -> Path | None:
    for path in base_dir.rglob(filename):
        return path
    return None
