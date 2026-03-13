"""Bootstrap command: build a hello-world NES ROM and convert it to SMS."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ...infrastructure.rom_loader import RomLoader
from .convert import cmd_convert

FCEUX_RELEASE_API = "https://api.github.com/repos/TASEmulators/fceux/releases/latest"
BLASTEM_WIN_URL = "https://www.retrodev.com/blastem/blastem-win32-0.6.2.zip"

HELLO_WORLD_WLA_6502_ASM = """; Hello, World! for NES (WLA-6502 variant)
; Adapted from Thomas Wesley Scott (2023):
; https://github.com/thomaslantern/nes-hello-world
; This template keeps the same spirit while using WLA-6502 syntax.

.ROMBANKMAP
  BANKSTOTAL 1
  BANKSIZE $4000
  BANKS 1
.ENDRO

.MEMORYMAP
  DEFAULTSLOT 0
  SLOT 0 $8000 $4000
.ENDME

.BANK 0 SLOT 0
.ORG $0000

nmihandler:
  lda #$02
  sta $4014
  rti

irqhandler:
  rti

startgame:
  sei
  cld

  ldx #$ff
  txs
  inx
  stx $2000
  stx $2001
  stx $4015
  stx $4010
  lda #$40
  sta $4017
  lda #$00

waitvblank:
  bit $2002
  bpl waitvblank

  lda #$00
clearmemory:
  sta $0000,x
  sta $0100,x
  sta $0300,x
  sta $0400,x
  sta $0500,x
  sta $0600,x
  sta $0700,x
  lda #$ff
  sta $0200,x
  lda #$00
  inx
  cpx #$00
  bne clearmemory

waitvblank2:
  bit $2002
  bpl waitvblank2

  lda $2002
  ldx #$3f
  stx $2006
  ldx #$00
  stx $2006
  ldx #$00
copypalloop:
  lda initial_palette.W,x
  sta $2007
  inx
  cpx #$04
  bne copypalloop

  lda #$02
  sta $4014

  ldx #$00
spriteload:
  lda hello.W,x
  sta $0200,x
  inx
  cpx #$2c
  bne spriteload

  lda #%10010000
  sta $2000
  lda #%00011110
  sta $2001

forever:
  jmp forever

initial_palette:
  .DB $1f,$21,$33,$30

hello:
  .DB $6c,$00,$00,$3d
  .DB $6c,$01,$00,$46
  .DB $6c,$02,$00,$4f
  .DB $6c,$02,$00,$58
  .DB $6c,$03,$00,$61

  .DB $75,$04,$00,$3d
  .DB $75,$03,$00,$46
  .DB $75,$05,$00,$4f
  .DB $75,$02,$00,$58
  .DB $75,$06,$00,$62
  .DB $75,$07,$00,$6b

.ORG $3ffa
  .DW nmihandler
  .DW startgame
  .DW irqhandler
"""


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
    asm_path = nes_dir / "hello_world_wla.asm"
    link_path = nes_dir / "linkfile_prg"
    asm_path.write_text(HELLO_WORLD_WLA_6502_ASM, encoding="ascii")
    link_path.write_text("[objects]\nhello_prg.o\n", encoding="ascii")

    print("[bootstrap-hello] [2/5] Building PRG with wla-6502 + wlalink...")
    wla_6502, wlalink = find_wla_toolchain(project_root)
    prg_path = _compile_prg(
        nes_dir=nes_dir,
        logs_dir=logs_dir,
        wla_6502=wla_6502,
        wlalink=wlalink,
    )

    print("[bootstrap-hello] [3/5] Building CHR and packing .nes...")
    chr_path = nes_dir / "hello_world.chr"
    chr_path.write_bytes(build_hello_world_chr())
    nes_rom_path = nes_dir / "hello_world.nes"
    nes_rom_path.write_bytes(
        build_ines_header(prg_banks=1, chr_banks=1) + prg_path.read_bytes() + chr_path.read_bytes()
    )
    _validate_nes_rom(nes_rom_path)
    print(f"[bootstrap-hello] NES ROM ready: {nes_rom_path}")

    print("[bootstrap-hello] [4/5] Converting NES -> SMS with nes2sms convert...")
    sms_emulator = None
    nes_emulator = None
    if run_emulators:
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

    convert_args = SimpleNamespace(
        nes=str(nes_rom_path),
        out=str(sms_dir),
        flip_strategy="cache",
        build=True,
        run=run_emulators,
        emulator=str(sms_emulator) if sms_emulator else None,
    )
    cmd_convert(convert_args)

    print("[bootstrap-hello] [5/5] Launching emulators (default behavior)...")
    if run_emulators and nes_emulator:
        _launch_emulator(nes_emulator, nes_rom_path)
    else:
        print("[bootstrap-hello] --no-run set, skipping emulator launch")

    print("[bootstrap-hello] Success criteria: valid .nes + generated/built .sms")
    print("[bootstrap-hello] Note: NES and SMS output are not expected to be 1:1 visual matches.")


def build_ines_header(
    prg_banks: int,
    chr_banks: int,
    mapper: int = 0,
    *,
    vertical_mirroring: bool = False,
    has_battery: bool = False,
    has_trainer: bool = False,
    four_screen: bool = False,
) -> bytes:
    """Build a 16-byte iNES header."""
    if not 0 <= prg_banks <= 0xFF:
        raise ValueError("prg_banks must fit in one byte")
    if not 0 <= chr_banks <= 0xFF:
        raise ValueError("chr_banks must fit in one byte")
    if not 0 <= mapper <= 0xFF:
        raise ValueError("mapper must fit in one byte")

    flags6 = ((mapper & 0x0F) << 4) & 0xF0
    if vertical_mirroring:
        flags6 |= 0x01
    if has_battery:
        flags6 |= 0x02
    if has_trainer:
        flags6 |= 0x04
    if four_screen:
        flags6 |= 0x08

    flags7 = mapper & 0xF0
    return bytes(
        [
            0x4E,
            0x45,
            0x53,
            0x1A,
            prg_banks & 0xFF,
            chr_banks & 0xFF,
            flags6,
            flags7,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        ]
    )


def build_hello_world_chr() -> bytes:
    """Build a single 8KB CHR-ROM page from local tile data."""
    tiles = [
        [0xC3, 0xC3, 0xC3, 0xFF, 0xFF, 0xC3, 0xC3, 0xC3, 0, 0, 0, 0, 0, 0, 0, 0],  # H
        [0xFF, 0xFF, 0xC0, 0xFC, 0xFC, 0xC0, 0xFF, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0],  # E
        [0xC0, 0xC0, 0xC0, 0xC0, 0xC0, 0xC0, 0xFF, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0],  # L
        [0x7E, 0xE7, 0xC3, 0xC3, 0xC3, 0xC3, 0xE7, 0x7E, 0, 0, 0, 0, 0, 0, 0, 0],  # O
        [0xC3, 0xC3, 0xC3, 0xC3, 0xDB, 0xDB, 0xE7, 0x42, 0, 0, 0, 0, 0, 0, 0, 0],  # W
        [0x7E, 0xE7, 0xC3, 0xC3, 0xFC, 0xCC, 0xC6, 0xC3, 0, 0, 0, 0, 0, 0, 0, 0],  # R
        [0xF0, 0xCE, 0xC2, 0xC3, 0xC3, 0xC2, 0xCE, 0xF0, 0, 0, 0, 0, 0, 0, 0, 0],  # D
        [0x18, 0x18, 0x18, 0x18, 0x18, 0x00, 0x18, 0x18, 0, 0, 0, 0, 0, 0, 0, 0],  # !
    ]

    chr_data = bytearray()
    for tile in tiles:
        chr_data.extend(tile)
    if len(chr_data) > 8192:
        raise RuntimeError("CHR data overflow")
    chr_data.extend(b"\x00" * (8192 - len(chr_data)))
    return bytes(chr_data)


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


def find_wla_toolchain(project_root: Path) -> tuple[Path, Path]:
    """Find wla-6502 and wlalink in PATH or local tools/wla-dx."""
    wla_in_path = shutil.which("wla-6502.exe") or shutil.which("wla-6502")
    wlalink_in_path = shutil.which("wlalink.exe") or shutil.which("wlalink")
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


def resolve_fceux(project_root: Path, explicit_path: str | None, allow_download: bool) -> Path:
    """Resolve FCEUX path or auto-install if missing."""
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"NES emulator not found: {path}")
        return path

    detected = shutil.which("fceux.exe") or shutil.which("fceux")
    if detected:
        return Path(detected)

    local_path = project_root / "emulators" / "fceux" / "fceux.exe"
    if local_path.exists():
        return local_path

    if not allow_download:
        raise FileNotFoundError("FCEUX not found and auto-download is disabled.")

    return _install_fceux(project_root)


def resolve_blastem(project_root: Path, explicit_path: str | None, allow_download: bool) -> Path:
    """Resolve BlastEm path or auto-install if missing."""
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"SMS emulator not found: {path}")
        return path

    detected = shutil.which("blastem.exe") or shutil.which("blastem")
    if detected:
        return Path(detected)

    local_path = project_root / "emulators" / "blastem" / "blastem.exe"
    if local_path.exists():
        return local_path

    if not allow_download:
        raise FileNotFoundError("BlastEm not found and auto-download is disabled.")

    return _install_blastem(project_root)


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
        _format_process_log(assemble_proc, "wla-6502"),
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
        _format_process_log(link_proc, "wlalink"),
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
    return (
        f"== {title} ==\n"
        f"returncode: {proc.returncode}\n\n"
        f"stdout:\n{proc.stdout}\n\n"
        f"stderr:\n{proc.stderr}\n"
    )


def _install_fceux(project_root: Path) -> Path:
    target_dir = project_root / "emulators" / "fceux"
    target_dir.mkdir(parents=True, exist_ok=True)

    payload = _download_json(FCEUX_RELEASE_API)
    asset_url = select_fceux_release_asset(payload)
    zip_path = target_dir / "fceux-win64.zip"
    _download_file(asset_url, zip_path)
    _extract_zip(zip_path, target_dir)
    zip_path.unlink(missing_ok=True)

    exe_path = target_dir / "fceux.exe"
    if exe_path.exists():
        return exe_path

    discovered = _find_first_file(target_dir, "fceux.exe")
    if discovered is None:
        raise RuntimeError("FCEUX download completed but fceux.exe was not found.")
    return discovered


def _install_blastem(project_root: Path) -> Path:
    target_dir = project_root / "emulators" / "blastem"
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = project_root / "emulators" / "blastem.zip"
    _download_file(BLASTEM_WIN_URL, zip_path)
    _extract_zip(zip_path, target_dir)
    zip_path.unlink(missing_ok=True)

    exe_path = target_dir / "blastem.exe"
    if exe_path.exists():
        return exe_path

    discovered = _find_first_file(target_dir, "blastem.exe")
    if discovered is None:
        raise RuntimeError("BlastEm download completed but blastem.exe was not found.")
    return discovered


def _download_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "nes2sms-bootstrap-hello",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def _download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "nes2sms-bootstrap-hello"})
    with urllib.request.urlopen(request) as response, destination.open("wb") as out_file:
        shutil.copyfileobj(response, out_file)


def _extract_zip(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(destination)


def _find_first_file(base_dir: Path, filename: str) -> Path | None:
    for path in base_dir.rglob(filename):
        return path
    return None


def _launch_emulator(emulator_path: Path, rom_path: Path) -> None:
    subprocess.Popen([str(emulator_path), str(rom_path)])
