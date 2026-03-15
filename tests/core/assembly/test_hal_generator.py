"""Tests for HAL generation regressions."""

from nes2sms.core.sms.hal_generator import HALGenerator


class TestHalGenerator:
    """Validate critical HAL write paths."""

    def test_ppu_2007_nametable_is_not_noop(self):
        ppu_code = HALGenerator().generate_ppu_routines()

        start = ppu_code.index("_ppu_2007_nametable:")
        end = ppu_code.index("_ppu_2001:")
        block = ppu_code[start:end]

        assert "out  ($BE), a" in block
        assert "ld   a, b" in block
        assert "Disabled:" not in block

    def test_attribute_table_writes_are_handled_separately(self):
        ppu_code = HALGenerator().generate_ppu_routines()
        assert "_ppu_2006_attribute:" in ppu_code
        assert "_ppu_2007_attribute:" in ppu_code
        assert "_ppu_attr_write_2x2:" in ppu_code
        assert "_ppu_attr_write_cell:" in ppu_code

    def test_nametable_path_sets_vdp_increment_to_two(self):
        ppu_code = HALGenerator().generate_ppu_routines()
        start = ppu_code.index("_ppu_2006_nametable:")
        end = ppu_code.index("_ppu_2006_attribute:")
        block = ppu_code[start:end]

        assert "ld   a, $02" in block
        assert "call _ppu_set_vdp_increment" in block

    def test_ppu_scroll_writes_update_vdp_regs(self):
        ppu_code = HALGenerator().generate_ppu_routines()
        start = ppu_code.index("_ppu_2005: ; PPUSCROLL")
        end = ppu_code.index("_ppu_2006: ; PPUADDR")
        block = ppu_code[start:end]

        assert "_ppu_2005_y:" in block
        assert "ld   a, 8" in block
        assert "ld   a, 9" in block
        assert "call VDP_WriteReg" in block
        assert "ld   (_ppu_addr_toggle), a" in block

    def test_first_ppuaddr_write_resets_write_mode(self):
        ppu_code = HALGenerator().generate_ppu_routines()
        start = ppu_code.index("_ppu_2006: ; PPUADDR")
        end = ppu_code.index("_ppu_2006_lo:")
        block = ppu_code[start:end]

        assert "ld   (_ppu_write_mode), a" in block

    def test_ppudata_paths_advance_virtual_ppu_address(self):
        ppu_code = HALGenerator().generate_ppu_routines()
        assert "_ppu_advance_vram_addr:" in ppu_code

        start = ppu_code.index("_ppu_2007_palette:")
        end = ppu_code.index("_ppu_2001:")
        block = ppu_code[start:end]

        assert "call _ppu_advance_vram_addr" in block

    def test_chr_mode_is_selected_and_dispatched(self):
        ppu_code = HALGenerator().generate_ppu_routines()

        start_mode = ppu_code.index("_ppu_2006_chr:")
        end_mode = ppu_code.index("_ppu_2007: ; PPUDATA")
        mode_block = ppu_code[start_mode:end_mode]

        assert "ld   a, $04" in mode_block
        assert "ld   (_ppu_write_mode), a" in mode_block

        start_dispatch = ppu_code.index("_ppu_2007: ; PPUDATA")
        end_dispatch = ppu_code.index("_ppu_2007_palette:")
        dispatch_block = ppu_code[start_dispatch:end_dispatch]

        assert "cp   $04" in dispatch_block
        assert "jp   z, _ppu_2007_chr" in dispatch_block
        assert "_ppu_2007_chr:" in ppu_code

    def test_oam_dma_applies_nes_to_sms_y_adjustment(self):
        oam_code = HALGenerator().generate_oam_dma_routine()
        start = oam_code.index("_oam_y_loop:")
        end = oam_code.index("_oam_xt_loop:")
        block = oam_code[start:end]

        assert "ld   a, (hl)" in block
        assert "inc  a" in block
        assert "out  ($BE), a" in block

    def test_oam_dma_uses_sprite_variant_lookup_table(self):
        oam_code = HALGenerator().generate_oam_dma_routine()

        assert "_oam_map_variant_tile:" in oam_code
        assert "ld   de, SpriteVariantMap" in oam_code
        assert "call _oam_map_variant_tile" in oam_code

    def test_oam_dma_embeds_priority_split_threshold(self):
        oam_code = HALGenerator(split_y=64).generate_oam_dma_routine()
        assert "cp   64" in oam_code

    def test_input_hal_exports_pause_nmi_hook(self):
        input_code = HALGenerator().generate_input_routines()
        assert ".export hal_input_on_pause_nmi" in input_code
        assert "hal_input_on_pause_nmi:" in input_code
        assert "_input_start_p1_pending" in input_code

    def test_input_hal_tracks_shared_strobe_and_live_states(self):
        input_code = HALGenerator().generate_input_routines()
        assert "_input_strobe" in input_code
        assert "_input_strobe_p1" not in input_code
        assert "_input_strobe_p2" not in input_code
        assert "_input_live_p1" in input_code
        assert "_input_live_p2" in input_code
        assert ".db $00" not in input_code

    def test_input_hal_ignores_4017_strobe_writes(self):
        input_code = HALGenerator().generate_input_routines()
        write_start = input_code.index("hal_input_write:")
        write_end = input_code.index("hal_input_on_pause_nmi:")
        block = input_code[write_start:write_end]

        assert "_input_write_ignore_p2:" in block
        assert "$4017" in block

    def test_input_hal_reads_p2_from_dc_and_dd(self):
        input_code = HALGenerator().generate_input_routines()
        start = input_code.index("_input_read_sms_p2:")
        end = input_code.index("_map_sms_to_nes:")
        block = input_code[start:end]

        assert "in   a, ($DC)" in block
        assert "and  $C0" in block
        assert "in   a, ($DD)" in block
        assert "and  $0F" in block
        assert "set  0, a" in block
        assert "set  5, a" in block

    def test_input_hal_shift_path_fills_high_bit_with_one(self):
        input_code = HALGenerator().generate_input_routines()
        assert "_read_p1_shift:" in input_code
        assert "_read_p2_shift:" in input_code
        assert "set  7, a" in input_code

    def test_input_hal_uses_shared_strobe_for_both_ports(self):
        input_code = HALGenerator().generate_input_routines()
        start = input_code.index("hal_input_read:")
        end = input_code.index("; Input state variables are absolute WRAM labels")
        block = input_code[start:end]

        assert block.count("ld   a, (_input_strobe)") == 2

    def test_input_hal_maps_select_from_dual_buttons(self):
        input_code = HALGenerator().generate_input_routines()
        assert "set  2, a                    ; Select = BTN1+BTN2" in input_code
