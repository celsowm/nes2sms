"""Tests for OAM extraction confidence filtering."""

from nes2sms.core.graphics.oam_extractor import OamExtractor


def _oam_entry(y: int, tile: int, attr: int, x: int) -> bytes:
    return bytes([y, tile, attr, x])


class TestOamExtractorConfidence:
    """Validate confidence checks for heuristic OAM extraction."""

    def test_rejects_table_when_referenced_tiles_are_empty(self):
        prg = b"".join(
            [
                _oam_entry(10, 40, 0, 16),
                _oam_entry(18, 41, 0, 24),
                _oam_entry(26, 42, 1, 32),
                _oam_entry(0, 0, 0, 0),  # terminator/invalid
            ]
        )
        extractor = OamExtractor(prg, chr_tile_count=256)
        sprites = extractor.extract_oam_table()

        assert sprites is not None
        tile_activity = [False] * 256
        assert extractor.nonempty_tile_ratio(sprites, tile_activity) == 0.0
        assert not extractor.is_confident_table(sprites, tile_activity, min_nonempty_ratio=0.5)

    def test_accepts_table_when_referenced_tiles_have_visible_data(self):
        prg = b"".join(
            [
                _oam_entry(10, 40, 0, 16),
                _oam_entry(18, 41, 0, 24),
                _oam_entry(26, 42, 1, 32),
                _oam_entry(0, 0, 0, 0),
            ]
        )
        extractor = OamExtractor(prg, chr_tile_count=256)
        sprites = extractor.extract_oam_table()

        assert sprites is not None
        tile_activity = [False] * 256
        tile_activity[40] = True
        tile_activity[41] = True
        tile_activity[42] = True

        assert extractor.nonempty_tile_ratio(sprites, tile_activity) == 1.0
        assert extractor.is_confident_table(sprites, tile_activity, min_nonempty_ratio=0.5)


class TestOamSatMapping:
    """Validate NES OAM to SMS SAT conversion behavior."""

    def test_to_sms_sat_applies_y_offset(self):
        extractor = OamExtractor(prg_data=b"", chr_tile_count=256)
        sprites = [{"y": 10, "tile": 4, "attr": 0x00, "x": 30}]

        y_table, xt_table = extractor.to_sms_sat(sprites)

        assert y_table == bytes([11, 0xD0])
        assert xt_table == bytes([30, 4])

    def test_to_sms_sat_uses_variant_lookup_for_palette_and_flip(self):
        extractor = OamExtractor(prg_data=b"", chr_tile_count=256)
        # palette=2, H+V flip -> combo 0x0E
        sprites = [{"y": 20, "tile": 7, "attr": 0xC2, "x": 40}]
        lookup = {(7, 0x0E): 99}

        y_table, xt_table = extractor.to_sms_sat(sprites, variant_lookup=lookup)

        assert y_table == bytes([21, 0xD0])
        assert xt_table == bytes([40, 99])

    def test_build_variant_profile_counts_tile_attr_combinations(self):
        sprites = [
            {"y": 10, "tile": 3, "attr": 0x00, "x": 10},
            {"y": 20, "tile": 3, "attr": 0x00, "x": 20},
            {"y": 30, "tile": 3, "attr": 0x40, "x": 30},
        ]

        profile = OamExtractor.build_variant_profile(sprites)

        assert profile[0]["tile"] == 3
        assert profile[0]["attr"] == 0x00
        assert profile[0]["count"] == 2
        assert profile[0]["combo"] == 0x00
