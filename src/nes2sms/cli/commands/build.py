"""Build command: Compile SMS ROM."""

import os
import subprocess
import sys
from pathlib import Path


def cmd_build(args):
    """Build SMS ROM using WLA-DX."""
    build_dir = Path(args.dir)

    if not build_dir.exists():
        raise FileNotFoundError(f"Build directory not found: {build_dir}")

    # Get wla-dx paths - go up from cli/commands to project root
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    wla_dx_dir = project_root / "tools" / "wla-dx"

    env = os.environ.copy()
    print(f"[build] project_root: {project_root}")
    print(f"[build] wla_dx_dir exists: {wla_dx_dir.exists()}")

    if wla_dx_dir.exists():
        wla = str(wla_dx_dir / "wla-z80.exe")
        wlab = str(wla_dx_dir / "wlalink.exe")
        print(f"[build] Using WLA-DX from: {wla_dx_dir}")
    else:
        wla = "wla-z80"
        wlab = "wlalink"

    print(f"[build] Compiling main.asm...")
    print(f"[build] wla path: {wla}")
    print(f"[build] cwd: {build_dir}")

    # Compile main.asm (includes all other files)
    try:
        result = subprocess.run(
            [wla, "-v", "-o", "main.o", "main.asm"],
            cwd=str(build_dir),
            capture_output=False,
            env=env,
        )
    except FileNotFoundError as e:
        print(f"[build] ERROR: {e}", file=sys.stderr)
        print(f"[build] Tried to run: {wla}", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"[build] ERROR: Compilation failed", file=sys.stderr)
        sys.exit(1)

    print(f"[build] Linking game.sms...")

    # Link
    result = subprocess.run(
        [wlab, "-v", "link.sms", "game.sms"], cwd=str(build_dir), capture_output=False, env=env
    )

    if result.returncode != 0:
        print(f"[build] ERROR: Linking failed", file=sys.stderr)
        sys.exit(1)

    # Check if ROM was created
    rom_path = build_dir / "game.sms"
    if rom_path.exists():
        size = rom_path.stat().st_size
        print(f"[build] SUCCESS: ROM created at {rom_path} ({size} bytes)")
    else:
        print(f"[build] WARNING: Build succeeded but game.sms not found", file=sys.stderr)
