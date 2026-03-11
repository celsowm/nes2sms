"""WLA-DX project generation."""

from pathlib import Path
from typing import Dict, List

from .templates import (
    MAIN_ASM,
    MEMORY_INC,
    INIT_ASM,
    INTERRUPTS_ASM,
    ASSETS_ASM,
    HAL_VDP_ASM,
    HAL_PSG_ASM,
    HAL_INPUT_ASM,
    HAL_MAPPER_ASM,
    GAME_LOGIC_STUB,
    GAME_STUBS_EMPTY,
    MAKEFILE_CONTENT,
    LINKER_SCRIPT,
)


class WlaDxGenerator:
    """Generates WLA-DX assembler project scaffold for SMS."""

    def __init__(self, output_dir: Path):
        """
        Initialize generator.

        Args:
            output_dir: Build output directory
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, rom_banks: int = 12, assets_dir: Path = None):
        """
        Generate complete WLA-DX project.

        Args:
            rom_banks: Number of 16KB ROM banks
            assets_dir: Optional path to assets directory for copying
        """
        # Create subdirectories
        (self.output_dir / "hal").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "stubs").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "assets").mkdir(parents=True, exist_ok=True)

        # Write main files with dynamic bank count
        (self.output_dir / "main.asm").write_text(MAIN_ASM, encoding="utf-8")
        (self.output_dir / "memory.inc").write_text(
            MEMORY_INC.format(banks=rom_banks), encoding="utf-8"
        )
        (self.output_dir / "init.asm").write_text(
            INIT_ASM.format(banks=rom_banks), encoding="utf-8"
        )
        (self.output_dir / "interrupts.asm").write_text(
            INTERRUPTS_ASM.format(banks=rom_banks), encoding="utf-8"
        )
        (self.output_dir / "assets.asm").write_text(
            ASSETS_ASM.format(banks=rom_banks), encoding="utf-8"
        )

        # Write HAL files
        (self.output_dir / "hal" / "vdp.asm").write_text(
            HAL_VDP_ASM.format(banks=rom_banks), encoding="utf-8"
        )
        (self.output_dir / "hal" / "psg.asm").write_text(
            HAL_PSG_ASM.format(banks=rom_banks), encoding="utf-8"
        )
        (self.output_dir / "hal" / "input.asm").write_text(
            HAL_INPUT_ASM.format(banks=rom_banks), encoding="utf-8"
        )
        (self.output_dir / "hal" / "mapper.asm").write_text(
            HAL_MAPPER_ASM.format(banks=rom_banks), encoding="utf-8"
        )

        # Write stubs
        (self.output_dir / "stubs" / "game_logic.asm").write_text(
            GAME_LOGIC_STUB.format(banks=rom_banks), encoding="utf-8"
        )
        (self.output_dir / "stubs" / "game_stubs.asm").write_text(
            GAME_STUBS_EMPTY.format(banks=rom_banks), encoding="utf-8"
        )

        # Copy assets to build/assets/ directory
        if assets_dir and assets_dir.exists():
            import shutil

            build_assets = self.output_dir / "assets"
            build_assets.mkdir(parents=True, exist_ok=True)
            for f in assets_dir.iterdir():
                if f.is_file() and f.suffix in [".bin", ".json"]:
                    shutil.copy(f, build_assets / f.name)

        # Write linker script
        (self.output_dir / "link.sms").write_text(
            LINKER_SCRIPT.format(banks=rom_banks), encoding="utf-8"
        )

        # Write Makefile
        (self.output_dir / "Makefile").write_text(MAKEFILE_CONTENT, encoding="utf-8")

        # Copy assets if provided
        if assets_dir and assets_dir.exists():
            import shutil

            for f in assets_dir.iterdir():
                if f.is_file():
                    shutil.copy(f, self.output_dir / "assets" / f.name)
