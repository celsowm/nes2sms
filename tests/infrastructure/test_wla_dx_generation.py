"""Tests for WLA-DX template and stub generation safety checks."""

import re

from nes2sms.infrastructure.wla_dx.stub_generator import StubGenerator
from nes2sms.infrastructure.wla_dx.templates import ASSETS_ASM, INIT_ASM, INTERRUPTS_ASM
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
        assert "ld   bc, Tiles_End - Tiles" in ASSETS_ASM

    def test_loadtilemap_populates_name_table(self):
        """LoadTilemap should write visible entries to name table."""
        assert not re.search(r"(?ms)^\s*LoadTilemap:\s*ret\b", ASSETS_ASM)
        assert "ld   hl, $3800" in ASSETS_ASM
        assert ".row_loop:" in ASSETS_ASM
        assert ".col_loop:" in ASSETS_ASM
        assert "PRIORITY_SPLIT_TILE" in ASSETS_ASM

    def test_sprite_variant_map_is_declared(self):
        """Assets template must expose SpriteVariantMap for runtime OAM remapping."""
        assert "SpriteVariantMap:" in ASSETS_ASM
        assert '.INCBIN "assets/sprite_variant_map.bin"' in ASSETS_ASM

    def test_reset_boot_order_uses_mapper_init(self):
        """RESET flow should initialize mapper and keep slot 2 stable."""
        assert "call Mapper_Init" in INIT_ASM
        assert "call LoadTiles" in INIT_ASM
        assert "call LoadTilemap" in INIT_ASM
        assert "ld   ($FFFF), a" not in INIT_ASM

    def test_interrupt_handler_always_dispatches_nmi_handler(self):
        """INT handler should always dispatch to game NMI routine."""
        assert "call NMI_Handler" in INTERRUPTS_ASM
        assert ".ifdef NMI_Handler" not in INTERRUPTS_ASM

    def test_pause_nmi_arms_virtual_start_hook(self):
        """SMS PAUSE/NMI path should arm the virtual Start pulse in HAL."""
        assert "SMS_NMI_Handler:" in INTERRUPTS_ASM
        assert "call hal_input_on_pause_nmi" in INTERRUPTS_ASM
        assert "retn" in INTERRUPTS_ASM


class TestStubGeneratorEntryPoint:
    """Validate GameMain routing in generated game_logic."""

    def test_gamemain_jumps_to_reset_handler_symbol(self):
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

    def test_gamemain_jumps_to_reset_handler_by_comment(self):
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

    def test_brk_translation_does_not_leave_todo_placeholder(self):
        symbols = [
            Symbol(
                name="sub_83ED",
                address=0x83ED,
                bank=0,
                type="code",
                disassembly_snippet="BRK",
            )
        ]
        generator = StubGenerator(symbols=symbols, enable_translation=True, use_flow_aware=False)

        game_logic = generator.generate_game_logic_stub()

        assert "sub_83ED:" in game_logic
        assert "TODO: BRK" not in game_logic
        assert "    RET" in game_logic
