"""Build, scaffold, and emulator helpers for the convert command."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def build_rom(out_dir: Path) -> bool:
    """
    Build SMS ROM using wla-dx.

    Returns:
        True if build succeeded, False otherwise
    """
    build_dir = out_dir / "build"
    if not build_dir.exists():
        print("      ERROR: Build directory not found")
        return False

    wla_path = shutil.which("wla-z80") or shutil.which("wla-z80.exe")
    if not wla_path:
        script_dir = Path(__file__).parent.parent.parent.parent.parent
        local_paths = [
            script_dir / "tools" / "wla-dx",
            Path.cwd() / "tools" / "wla-dx",
            Path.home() / "tools" / "wla-dx",
        ]
        for local_path in local_paths:
            if (local_path / "wla-z80.exe").exists():
                wla_path = str(local_path / "wla-z80.exe")
                break
            if (local_path / "wla-z80").exists():
                wla_path = str(local_path / "wla-z80")
                break

    if not wla_path:
        print("      wla-dx not found. Install with: pip install wla-dx")
        print(f"      Or run: .{chr(92)}setup.bat (Windows) or .{chr(47)}setup.sh (Linux/macOS)")
        return False

    wla_dir = Path(wla_path).parent
    env = dict(os.environ)
    env["PATH"] = str(wla_dir) + os.pathsep + env.get("PATH", "")

    try:
        result = subprocess.run(
            [wla_path, "-o", "main.o", "main.asm"],
            cwd=str(build_dir),
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            print(f"      Assemble failed: {result.stderr}")
            return False

        linker_path = (
            wla_dir / "wlalink.exe"
            if (wla_dir / "wlalink.exe").exists()
            else shutil.which("wlalink") or shutil.which("wlalink.exe")
        )
        if not linker_path or not Path(linker_path).exists():
            print("      wlalink not found. Install with: pip install wla-dx")
            return False

        result = subprocess.run(
            [str(linker_path), "-v", "link.sms", "game.sms"],
            cwd=str(build_dir),
            capture_output=True,
            text=True,
            env=env,
        )
        if not (build_dir / "game.sms").exists():
            print(f"      Link failed: {result.stderr}")
            return False

        print(f"      Build successful! ({(build_dir / 'game.sms').stat().st_size} bytes)")
        return True
    except Exception as exc:
        print(f"      Build error: {exc}")
        return False


def generate_wla_project(
    out_dir: Path,
    bank_map: dict,
    loader,
    mapper_strategy=None,
    translator=None,
    split_y: int = 48,
) -> None:
    """Generate the WLA-DX project scaffold for the converted ROM."""
    from ...infrastructure.wla_dx.templates import (
        ASSETS_ASM,
        HAL_INPUT_ASM,
        HAL_MAPPER_ASM,
        HAL_PSG_ASM,
        HAL_VDP_ASM,
        INIT_ASM,
        INTERRUPTS_ASM,
        LINKER_SCRIPT,
        MAIN_ASM,
        MAKEFILE_CONTENT,
        MEMORY_INC,
    )

    build_dir = out_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "hal").mkdir(exist_ok=True)
    (build_dir / "assets").mkdir(exist_ok=True)
    (build_dir / "stubs").mkdir(exist_ok=True)

    prg_banks = bank_map.get("prg_banks", 2)
    rom_banks = prg_banks + 1

    (build_dir / "main.asm").write_text(MAIN_ASM.replace("NUM_BANKS", str(rom_banks)), encoding="utf-8")
    (build_dir / "memory.inc").write_text(
        MEMORY_INC.replace("NUM_ROM_BANKS", str(rom_banks)),
        encoding="utf-8",
    )
    (build_dir / "init.asm").write_text(INIT_ASM, encoding="utf-8")
    (build_dir / "interrupts.asm").write_text(INTERRUPTS_ASM, encoding="utf-8")
    (build_dir / "assets.asm").write_text(ASSETS_ASM, encoding="utf-8")
    (build_dir / "hal" / "vdp.asm").write_text(HAL_VDP_ASM, encoding="utf-8")
    (build_dir / "hal" / "psg.asm").write_text(HAL_PSG_ASM, encoding="utf-8")
    (build_dir / "hal" / "input.asm").write_text(HAL_INPUT_ASM, encoding="utf-8")
    (build_dir / "hal" / "mapper.asm").write_text(HAL_MAPPER_ASM, encoding="utf-8")

    if translator and mapper_strategy:
        support_code = translator.get_support_code(mapper_strategy, split_y=split_y)
        (build_dir / "hal" / "support.asm").write_text(support_code, encoding="utf-8")

    _copy_generated_dir(out_dir / "stubs", build_dir / "stubs")
    _copy_generated_dir(out_dir / "assets", build_dir / "assets")

    (build_dir / "link.sms").write_text(
        LINKER_SCRIPT.replace("NUM_BANKS", str(rom_banks)),
        encoding="utf-8",
    )
    (build_dir / "Makefile").write_text(MAKEFILE_CONTENT, encoding="utf-8")

    print("      WLA-DX project generated")
    print(f"      ROM banks: {rom_banks}")


def launch_emulator(out_dir: Path, emulator_path: Optional[str] = None) -> None:
    """Launch the built SMS ROM in an emulator."""
    min_rom_size = 1024
    sms_rom = _find_built_sms_rom(out_dir, min_rom_size=min_rom_size)
    if not sms_rom:
        print("      ERROR: No valid SMS ROM found")
        print("      Build may have failed or produced no output")
        print("      Check build logs above for errors")
        print("      Note: --run requires successful --build")
        print("      Install wla-dx: pip install wla-dx")
        return

    if not emulator_path:
        emulator_path = detect_emulator()

    if not emulator_path or not Path(emulator_path).exists():
        print("      ERROR: Emulator not found")
        print("      Specify with: --emulator /path/to/emulator.exe")
        return

    print(f"      Emulator: {emulator_path}")
    print(f"      ROM: {sms_rom} ({sms_rom.stat().st_size} bytes)")

    try:
        subprocess.Popen([emulator_path, str(sms_rom)])
        print("      Launched!")
    except Exception as exc:
        print(f"      ERROR: Failed to launch emulator: {exc}")


def detect_emulator() -> Optional[str]:
    """Auto-detect common SMS emulators."""
    emulator_names = {
        "Windows": [
            "blastem.exe",
            "mesen.exe",
            "fceux.exe",
            "genesis-plus-gx.exe",
            "retroarch.exe",
        ],
        "Linux": ["blastem", "mesen", "fceux", "retroarch"],
        "Darwin": ["blastem", "mesen", "retroarch"],
    }

    emulators = emulator_names.get(platform.system(), emulator_names["Linux"])
    for exe in emulators:
        path = shutil.which(exe)
        if path:
            return path

    project_emulator_dir = Path(__file__).resolve().parents[4] / "emulators"
    if project_emulator_dir.exists():
        for exe in emulators:
            for match in project_emulator_dir.rglob(exe):
                if match.is_file():
                    return str(match)

    common_paths = [
        Path.home() / "Games" / "Emulators",
        Path.home() / "emulators",
        Path("C:\\Games\\Emulators"),
        Path("C:\\Program Files\\Emulators"),
    ]
    for base_dir in common_paths:
        if not base_dir.exists():
            continue
        for exe in emulators:
            exe_path = base_dir / exe
            if exe_path.exists():
                return str(exe_path)

    return None


def _copy_generated_dir(src_dir: Path, dst_dir: Path) -> None:
    if not src_dir.exists():
        return
    for entry in src_dir.glob("*"):
        if entry.is_file():
            shutil.copy2(entry, dst_dir)


def _find_built_sms_rom(out_dir: Path, *, min_rom_size: int) -> Optional[Path]:
    search_paths = [out_dir / "build", out_dir]
    for search_path in search_paths:
        if not search_path.exists():
            continue
        for rom in search_path.glob("*.sms"):
            if rom.name != "link.sms" and rom.stat().st_size >= min_rom_size:
                return rom
        for rom in search_path.glob("*.bin"):
            if rom.name == "link.bin" or rom.stat().st_size < min_rom_size:
                continue
            if "sms" in rom.name.lower() or rom.parent.name == "build":
                return rom
    return None
