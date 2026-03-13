"""Tests for static symbol extractor."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from nes2sms.infrastructure.symbol_extractor import StaticSymbolExtractor
from nes2sms.shared.models import Symbol


class TestStaticSymbolExtractor:
    """Test cases for StaticSymbolExtractor."""

    def test_extract_vectors(self):
        """Test interrupt vector extraction."""
        # Create PRG with vectors at the end (relative to base address)
        # Vectors are at offset 0x3FFE from base for 16KB PRG
        prg_data = bytearray([0] * 0x4000)  # 16KB PRG

        # Set vectors at end of PRG (offset 0x3FFE)
        prg_data[0x3FFE] = 0x00  # NMI low
        prg_data[0x3FFF] = 0x80  # NMI high -> $8000

        extractor = StaticSymbolExtractor(bytes(prg_data), base_address=0x8000)
        symbols = extractor.extract()

        # Should find at least the NMI handler
        assert len(symbols) >= 1

    def test_follow_jsr_targets(self):
        """Test following JSR targets."""
        # Create PRG with JSR instruction and vectors
        prg_data = bytearray([0] * 0x4000)  # 16KB PRG

        # JSR $8100 at offset 0 (address $8000)
        prg_data[0] = 0x20  # JSR opcode
        prg_data[1] = 0x00  # Low byte
        prg_data[2] = 0x81  # High byte

        # Set RESET vector to point to start
        prg_data[0x3FFE] = 0x00
        prg_data[0x3FFF] = 0x80

        extractor = StaticSymbolExtractor(bytes(prg_data), base_address=0x8000)
        symbols = extractor.extract()

        # Should find the JSR target
        symbol_addrs = [s.address for s in symbols]
        assert 0x8100 in symbol_addrs

    def test_follow_jmp_targets(self):
        """Test following JMP targets."""
        prg_data = bytearray([0] * 0x4000)  # 16KB PRG

        # JMP $8200 at offset 0
        prg_data[0] = 0x4C  # JMP absolute opcode
        prg_data[1] = 0x00  # Low byte
        prg_data[2] = 0x82  # High byte

        # Set RESET vector
        prg_data[0x3FFE] = 0x00
        prg_data[0x3FFF] = 0x80

        extractor = StaticSymbolExtractor(bytes(prg_data), base_address=0x8000)
        symbols = extractor.extract()

        symbol_addrs = [s.address for s in symbols]
        assert 0x8200 in symbol_addrs

    def test_stop_at_rts(self):
        """Test that code following stops at RTS."""
        prg_data = bytearray([0] * 0x4000)  # 16KB PRG

        # RTS at offset 0
        prg_data[0] = 0x60  # RTS opcode

        # Set RESET vector
        prg_data[0x3FFE] = 0x00
        prg_data[0x3FFF] = 0x80

        extractor = StaticSymbolExtractor(bytes(prg_data), base_address=0x8000)
        symbols = extractor.extract()

        # Should have visited the RESET handler
        assert len(extractor.visited) >= 1

    def test_get_code_ranges(self):
        """Test getting code ranges."""
        prg_data = bytes([0] * 0x100)

        extractor = StaticSymbolExtractor(prg_data, base_address=0x8000)
        extractor.code_addresses = {0x8000, 0x8001, 0x8002, 0x8010, 0x8011}

        ranges = extractor.get_code_ranges()
        assert len(ranges) == 2
        assert (0x8000, 0x8002) in ranges
        assert (0x8010, 0x8011) in ranges

    def test_get_data_ranges(self):
        """Test getting data ranges."""
        prg_data = bytes([0] * 0x100)

        extractor = StaticSymbolExtractor(prg_data, base_address=0x8000)
        extractor.code_addresses = {0x8000, 0x8001, 0x8002}

        ranges = extractor.get_data_ranges()
        assert len(ranges) >= 1
        assert ranges[0][0] > 0x8002  # Data starts after code

    def test_to_dict(self):
        """Test exporting to dictionary."""
        prg_data = bytes([0] * 0x100)

        extractor = StaticSymbolExtractor(prg_data, base_address=0x8000)
        extractor.symbols = [
            Symbol(
                name="Test",
                address=0x8000,
                bank=0,
                type="code",
                comment="Test symbol",
            )
        ]

        result = extractor.to_dict()

        assert "symbols" in result
        assert result["total_symbols"] == 1
        assert result["symbols"][0]["name"] == "Test"

    def test_is_valid_address(self):
        """Test address validation."""
        prg_data = bytes([0] * 0x4000)  # 16KB PRG

        extractor = StaticSymbolExtractor(prg_data, base_address=0x8000)

        assert extractor._is_valid_address(0x8000)
        assert extractor._is_valid_address(0xBFFF)
        assert not extractor._is_valid_address(0x7FFF)
        assert not extractor._is_valid_address(0xC000)

    def test_addr_to_offset(self):
        """Test address to offset conversion."""
        prg_data = bytes([0] * 0x4000)

        extractor = StaticSymbolExtractor(prg_data, base_address=0x8000)

        assert extractor._addr_to_offset(0x8000) == 0
        assert extractor._addr_to_offset(0x8010) == 0x10
        assert extractor._addr_to_offset(0xBFFF) == 0x3FFF

    def test_addr_to_bank(self):
        """Test address to bank conversion."""
        prg_data = bytes([0] * 0x4000)

        extractor = StaticSymbolExtractor(prg_data, base_address=0x8000)

        assert extractor._addr_to_bank(0x8000) == 0
        assert extractor._addr_to_bank(0xBFFF) == 0  # Still bank 0 for 16KB PRG
