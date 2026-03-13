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
