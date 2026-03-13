"""Tests for bootstrap-hello command orchestration and helpers."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from nes2sms.cli.commands import bootstrap_hello


def _write_fake_prg(path: Path) -> None:
    data = bytearray(16384)
    # NMI, RESET, IRQ vectors -> $8000
    data[0x3FFA] = 0x00
    data[0x3FFB] = 0x80
    data[0x3FFC] = 0x00
    data[0x3FFD] = 0x80
    data[0x3FFE] = 0x00
    data[0x3FFF] = 0x80
    path.write_bytes(data)


def test_build_ines_header_mapper_and_sizes():
    header = bootstrap_hello.build_ines_header(
        prg_banks=2,
        chr_banks=1,
        mapper=0x31,
        vertical_mirroring=True,
        has_battery=True,
    )

    assert len(header) == 16
    assert header[:4] == b"NES\x1A"
    assert header[4] == 2
    assert header[5] == 1
    assert header[6] == 0x13
    assert header[7] == 0x30


def test_select_fceux_release_asset_prefers_non_qtsdl_win64():
    payload = {
        "assets": [
            {
                "name": "fceux-2.6.6-win64-QtSDL.zip",
                "browser_download_url": "https://example/qtsdl.zip",
            },
            {
                "name": "fceux-2.6.6-win64.zip",
                "browser_download_url": "https://example/win64.zip",
            },
        ]
    }
    assert (
        bootstrap_hello.select_fceux_release_asset(payload)
        == "https://example/win64.zip"
    )


def test_find_wla_toolchain_prefers_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def fake_which(name: str):
        if "wla-6502" in name:
            return "C:/bin/wla-6502.exe"
        if "wlalink" in name:
            return "C:/bin/wlalink.exe"
        return None

    monkeypatch.setattr(bootstrap_hello.shutil, "which", fake_which)

    wla, linker = bootstrap_hello.find_wla_toolchain(tmp_path)
    assert str(wla).lower().endswith("wla-6502.exe")
    assert str(linker).lower().endswith("wlalink.exe")


def test_find_wla_toolchain_falls_back_to_local_tools(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(bootstrap_hello.shutil, "which", lambda _name: None)

    local_tools = tmp_path / "tools" / "wla-dx"
    local_tools.mkdir(parents=True, exist_ok=True)
    (local_tools / "wla-6502.exe").write_bytes(b"")
    (local_tools / "wlalink.exe").write_bytes(b"")

    wla, linker = bootstrap_hello.find_wla_toolchain(tmp_path)
    assert wla == local_tools / "wla-6502.exe"
    assert linker == local_tools / "wlalink.exe"


def test_cmd_bootstrap_hello_no_run_does_not_resolve_or_launch_emulators(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    out_dir = tmp_path / "out"
    calls: dict[str, object] = {}

    monkeypatch.setattr(bootstrap_hello, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        bootstrap_hello, "find_wla_toolchain", lambda _root: (Path("wla"), Path("link"))
    )

    def fake_compile_prg(nes_dir: Path, logs_dir: Path, wla_6502: Path, wlalink: Path) -> Path:
        assert logs_dir.exists()
        assert wla_6502.name == "wla"
        assert wlalink.name == "link"
        out = nes_dir / "hello_prg.bin"
        _write_fake_prg(out)
        return out

    monkeypatch.setattr(bootstrap_hello, "_compile_prg", fake_compile_prg)
    monkeypatch.setattr(
        bootstrap_hello,
        "resolve_fceux",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not resolve NES")),
    )
    monkeypatch.setattr(
        bootstrap_hello,
        "resolve_blastem",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not resolve SMS")),
    )
    monkeypatch.setattr(
        bootstrap_hello,
        "_launch_emulator",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not launch")),
    )

    def fake_convert(ns):
        calls["convert"] = ns

    monkeypatch.setattr(bootstrap_hello, "cmd_convert", fake_convert)

    args = SimpleNamespace(out=str(out_dir), no_run=True, nes_emulator=None, sms_emulator=None)
    bootstrap_hello.cmd_bootstrap_hello(args)

    rom_path = out_dir / "nes" / "hello_world.nes"
    assert rom_path.exists()
    assert rom_path.stat().st_size == 16 + 16384 + 8192

    convert_args = calls["convert"]
    assert convert_args.build is True
    assert convert_args.run is False
    assert convert_args.emulator is None
    assert Path(convert_args.out) == out_dir / "sms"
    assert Path(convert_args.nes) == rom_path


def test_cmd_bootstrap_hello_run_passes_sms_emulator_and_launches_nes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    out_dir = tmp_path / "out"
    captured: dict[str, object] = {}
    blastem = tmp_path / "emulators" / "blastem" / "blastem.exe"
    fceux = tmp_path / "emulators" / "fceux" / "fceux.exe"
    blastem.parent.mkdir(parents=True, exist_ok=True)
    fceux.parent.mkdir(parents=True, exist_ok=True)
    blastem.write_text("", encoding="utf-8")
    fceux.write_text("", encoding="utf-8")

    monkeypatch.setattr(bootstrap_hello, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        bootstrap_hello, "find_wla_toolchain", lambda _root: (Path("wla"), Path("link"))
    )

    def fake_compile_prg(nes_dir: Path, logs_dir: Path, wla_6502: Path, wlalink: Path) -> Path:
        out = nes_dir / "hello_prg.bin"
        _write_fake_prg(out)
        return out

    monkeypatch.setattr(bootstrap_hello, "_compile_prg", fake_compile_prg)
    monkeypatch.setattr(bootstrap_hello, "resolve_blastem", lambda **_kwargs: blastem)
    monkeypatch.setattr(bootstrap_hello, "resolve_fceux", lambda **_kwargs: fceux)

    def fake_convert(ns):
        captured["convert"] = ns

    def fake_launch(emulator_path: Path, rom_path: Path):
        captured["launch"] = (emulator_path, rom_path)

    monkeypatch.setattr(bootstrap_hello, "cmd_convert", fake_convert)
    monkeypatch.setattr(bootstrap_hello, "_launch_emulator", fake_launch)

    args = SimpleNamespace(out=str(out_dir), no_run=False, nes_emulator=None, sms_emulator=None)
    bootstrap_hello.cmd_bootstrap_hello(args)

    convert_args = captured["convert"]
    assert convert_args.run is True
    assert convert_args.build is True
    assert convert_args.emulator == str(blastem)

    launch_emulator, launch_rom = captured["launch"]
    assert launch_emulator == fceux
    assert launch_rom == out_dir / "nes" / "hello_world.nes"
