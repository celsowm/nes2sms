"""Bootstrap command: build a hello-world NES ROM and convert it to SMS."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

from ...infrastructure.rom_loader import RomLoader
from ._bootstrap_hello_assets import (
    HELLO_WORLD_WLA_6502_ASM,
    build_hello_world_chr as _build_hello_world_chr_impl,
    build_ines_header as _build_ines_header_impl,
)
from ._bootstrap_tooling import (
    compile_prg as _compile_prg_impl,
    find_wla_toolchain as _find_wla_toolchain_impl,
    format_process_log as _format_process_log_impl,
    resolve_blastem as _resolve_blastem_impl,
    resolve_fceux as _resolve_fceux_impl,
    select_fceux_release_asset as _select_fceux_release_asset_impl,
)
from .convert import cmd_convert


def cmd_bootstrap_hello(args) -> None:
    """Generate/compile a NES hello world, then convert/build SMS."""
    run_emulators = not args.no_run
    project_root = _project_root()
    out_dir = Path(args.out)

    print(f"[bootstrap-hello] Output directory: {out_dir}")
    _reset_output_dir(out_dir)

    nes_dir = out_dir / "nes"
    sms_dir = out_dir / "sms"
    logs_dir = out_dir / "logs"
    nes_dir.mkdir(parents=True, exist_ok=True)
    sms_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    print("[bootstrap-hello] [1/5] Preparing local NES hello template...")
    _write_hello_sources(nes_dir)

    print("[bootstrap-hello] [2/5] Building PRG with wla-6502 + wlalink...")
    wla_6502, wlalink = find_wla_toolchain(project_root)
    prg_path = _compile_prg(
        nes_dir=nes_dir,
        logs_dir=logs_dir,
        wla_6502=wla_6502,
        wlalink=wlalink,
    )

    print("[bootstrap-hello] [3/5] Building CHR and packing .nes...")
    nes_rom_path = _build_hello_nes_rom(nes_dir, prg_path)
    _validate_nes_rom(nes_rom_path)
    print(f"[bootstrap-hello] NES ROM ready: {nes_rom_path}")

    print("[bootstrap-hello] [4/5] Converting NES -> SMS with nes2sms convert...")
    sms_emulator, nes_emulator = _resolve_requested_emulators(args, project_root, run_emulators)
    cmd_convert(_build_convert_args(nes_rom_path, sms_dir, run_emulators, sms_emulator))

    print("[bootstrap-hello] [5/5] Launching emulators (default behavior)...")
    if run_emulators and nes_emulator:
        _launch_emulator(nes_emulator, nes_rom_path)
    else:
        print("[bootstrap-hello] --no-run set, skipping emulator launch")

    print("[bootstrap-hello] Success criteria: valid .nes + generated/built .sms")
    print("[bootstrap-hello] Note: NES and SMS output are not expected to be 1:1 visual matches.")


def build_ines_header(*args, **kwargs) -> bytes:
    return _build_ines_header_impl(*args, **kwargs)


def build_hello_world_chr() -> bytes:
    return _build_hello_world_chr_impl()


def select_fceux_release_asset(release_payload):
    return _select_fceux_release_asset_impl(release_payload)


def find_wla_toolchain(project_root: Path) -> tuple[Path, Path]:
    return _find_wla_toolchain_impl(project_root, which_fn=shutil.which)


def resolve_fceux(project_root: Path, explicit_path: str | None, allow_download: bool) -> Path:
    return _resolve_fceux_impl(
        project_root,
        explicit_path,
        allow_download,
        which_fn=shutil.which,
    )


def resolve_blastem(project_root: Path, explicit_path: str | None, allow_download: bool) -> Path:
    return _resolve_blastem_impl(
        project_root,
        explicit_path,
        allow_download,
        which_fn=shutil.which,
    )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _reset_output_dir(out_dir: Path) -> None:
    if out_dir.exists():
        if out_dir.is_file():
            out_dir.unlink()
        else:
            shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)


def _compile_prg(nes_dir: Path, logs_dir: Path, wla_6502: Path, wlalink: Path) -> Path:
    return _compile_prg_impl(
        nes_dir,
        logs_dir,
        wla_6502,
        wlalink,
        format_process_log_fn=_format_process_log,
    )


def _validate_nes_rom(rom_path: Path) -> None:
    loader = RomLoader().load(rom_path)
    if loader.header.mapper != 0:
        raise RuntimeError(f"Expected mapper 0, got mapper {loader.header.mapper}")
    if loader.header.prg_banks != 1:
        raise RuntimeError(f"Expected 1 PRG bank, got {loader.header.prg_banks}")
    if loader.header.chr_banks != 1:
        raise RuntimeError(f"Expected 1 CHR bank, got {loader.header.chr_banks}")
    if not loader.vectors or "reset" not in loader.vectors:
        raise RuntimeError("Missing reset vector in generated ROM.")
    if loader.vectors["reset"] == "$0000":
        raise RuntimeError("Invalid reset vector ($0000).")


def _format_process_log(proc: subprocess.CompletedProcess[str], title: str) -> str:
    return _format_process_log_impl(proc, title)


def _write_hello_sources(nes_dir: Path) -> None:
    (nes_dir / "hello_world_wla.asm").write_text(HELLO_WORLD_WLA_6502_ASM, encoding="ascii")
    (nes_dir / "linkfile_prg").write_text("[objects]\nhello_prg.o\n", encoding="ascii")


def _build_hello_nes_rom(nes_dir: Path, prg_path: Path) -> Path:
    chr_path = nes_dir / "hello_world.chr"
    chr_path.write_bytes(build_hello_world_chr())
    nes_rom_path = nes_dir / "hello_world.nes"
    nes_rom_path.write_bytes(
        build_ines_header(prg_banks=1, chr_banks=1) + prg_path.read_bytes() + chr_path.read_bytes()
    )
    return nes_rom_path


def _resolve_requested_emulators(args, project_root: Path, run_emulators: bool) -> tuple[Path | None, Path | None]:
    if not run_emulators:
        return None, None
    sms_emulator = resolve_blastem(
        project_root=project_root,
        explicit_path=args.sms_emulator,
        allow_download=True,
    )
    nes_emulator = resolve_fceux(
        project_root=project_root,
        explicit_path=args.nes_emulator,
        allow_download=True,
    )
    return sms_emulator, nes_emulator


def _build_convert_args(
    nes_rom_path: Path,
    sms_dir: Path,
    run_emulators: bool,
    sms_emulator: Path | None,
):
    return SimpleNamespace(
        nes=str(nes_rom_path),
        out=str(sms_dir),
        flip_strategy="cache",
        graphics_source="hybrid",
        capture_frame=120,
        capture_timeout_seconds=30,
        build=True,
        run=run_emulators,
        emulator=str(sms_emulator) if sms_emulator else None,
    )


def _launch_emulator(emulator_path: Path, rom_path: Path) -> None:
    subprocess.Popen([str(emulator_path), str(rom_path)])
