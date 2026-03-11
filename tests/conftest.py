"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_chr_data():
    """Sample CHR data for testing (4 tiles)."""
    return bytes([0] * 64)  # 4 tiles × 16 bytes


@pytest.fixture
def sample_prg_data():
    """Sample PRG data for testing."""
    # Minimal PRG with RESET vector
    prg = bytes([0] * 0x3FFE)
    prg += bytes([0x00, 0x80])  # RESET -> $8000
    return prg


@pytest.fixture
def sample_6502_code():
    """Sample 6502 assembly code for testing translation."""
    return [
        "Reset:",
        "    SEI",
        "    CLD",
        "    LDX #$FF",
        "    TXS",
        "    LDA #$00",
        "    STA $2000",
        "Loop:",
        "    JMP Loop",
    ]


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory for tests."""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    return out_dir
