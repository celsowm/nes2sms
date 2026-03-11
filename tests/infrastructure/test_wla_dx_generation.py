"""Tests for WLA-DX template and stub generation safety checks."""

import re

from nes2sms.infrastructure.wla_dx.stub_generator import StubGenerator
from nes2sms.infrastructure.wla_dx.templates import ASSETS_ASM, INIT_ASM
from nes2sms.shared.models import Symbol


class TestWlaDxTemplates:
    """Validate generated templates are not placeholder-only."""

    def test_loadpalettes_is_not_placeholder(self):
        """LoadPalettes must copy data to CRAM, not immediate return."""
        assert not re.search(r"(?ms)^\s*LoadPalettes:\s*ret\b", ASSETS_ASM)
        assert "VDP_CopyBytes" in ASSETS_ASM

    def test_loadtiles_is_not_placeholder(self):
        """LoadTiles must copy tile data to VRAM, not immediate return."""
        assert not re.search(r"(?ms)^\s*LoadTiles:\s*ret\b", ASSETS_ASM)
        assert "ld   hl, $0000" in ASSETS_ASM

    def test_loadtilemap_populates_name_table(self):
        """LoadTilemap should write visible entries to name table."""
        assert not re.search(r"(?ms)^\s*LoadTilemap:\s*ret\b", ASSETS_ASM)
        assert "ld   hl, $3800" in ASSETS_ASM
        assert ".tilemap_loop:" in ASSETS_ASM

    def test_reset_boot_order_uses_mapper_init(self):
        """RESET flow should initialize mapper and keep slot 2 stable."""
        assert "call Mapper_Init" in INIT_ASM
        assert "call LoadTiles" in INIT_ASM
        assert "call LoadTilemap" in INIT_ASM
        assert "ld   ($FFFF), a" not in INIT_ASM


class TestStubGeneratorEntryPoint:
    """Validate GameMain routing in generated game_logic."""

    def test_gamemain_jumps_to_reset_handler_when_available(self):
        symbols = [
            Symbol(
                name="RESET_Handler",
                address=0x80DF,
                bank=0,
                type="code",
                comment="RESET vector handler",
            ),
            Symbol(name="sub_9000", address=0x9000, bank=0, type="code"),
        ]
        generator = StubGenerator(symbols=symbols, enable_translation=False)

        game_logic = generator.generate_game_logic_stub()

        assert "GameMain:" in game_logic
        assert "    jp   RESET_Handler" in game_logic

    def test_gamemain_uses_reset_vector_comment_as_fallback(self):
        symbols = [
            Symbol(
                name="sub_80DF",
                address=0x80DF,
                bank=0,
                type="code",
                comment="RESET vector handler",
            )
        ]
        generator = StubGenerator(symbols=symbols, enable_translation=False)

        game_logic = generator.generate_game_logic_stub()

        assert "GameMain:" in game_logic
        assert "    jp   sub_80DF" in game_logic

    def test_gamemain_keeps_safe_loop_without_reset_target(self):
        symbols = [Symbol(name="sub_9000", address=0x9000, bank=0, type="code")]
        generator = StubGenerator(symbols=symbols, enable_translation=False)

        game_logic = generator.generate_game_logic_stub()

        assert "GameMain:" in game_logic
        assert ".main_loop:" in game_logic
        assert "    halt" in game_logic
