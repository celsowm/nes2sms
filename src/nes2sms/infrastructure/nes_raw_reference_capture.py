"""Capture and render a raw NES reference frame for comparison."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..core.graphics.raw_reference_renderer import (
    build_raw_reference_report,
    render_raw_reference_frame,
)
from .fceux_runtime_capture import FceuxRuntimeCaptureConfig, capture_runtime_graphics
from .fceux_screenshot_capture import write_rgba_png
from .rom_loader import RomLoader


@dataclass
class NesRawReferenceCaptureConfig:
    """Configuration for one raw-reference capture run."""

    nes_path: Path
    output_dir: Path
    capture_frame: int = 120
    timeout_seconds: int = 30
    emulator_path: Optional[str] = None


def capture_raw_reference_frame(config: NesRawReferenceCaptureConfig) -> tuple[Path, Path]:
    """Capture runtime state, render a raw NES reference frame, and persist report artifacts."""
    loader = RomLoader().load(config.nes_path)
    runtime_capture = capture_runtime_graphics(
        FceuxRuntimeCaptureConfig(
            nes_path=config.nes_path,
            output_dir=config.output_dir,
            mirroring=loader.header.mirroring,
            capture_frame=config.capture_frame,
            timeout_seconds=config.timeout_seconds,
            emulator_path=config.emulator_path,
        )
    )
    frame = render_raw_reference_frame(runtime_capture, loader.chr_data or b"")
    png_path = config.output_dir / "raw_reference.png"
    report_path = config.output_dir / "raw_reference_report.json"
    write_rgba_png(png_path, frame.width, frame.height, frame.rgba)

    report = build_raw_reference_report(frame)
    report["frame"] = runtime_capture.frame
    report["png_path"] = str(png_path.resolve())
    report["runtime_capture_path"] = str((config.output_dir / "runtime_capture.json").resolve())
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return png_path, report_path
