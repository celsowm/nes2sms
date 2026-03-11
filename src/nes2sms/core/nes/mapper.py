"""NES Mapper strategies for bank mapping to SMS Sega mapper."""

from abc import ABC, abstractmethod
from typing import List, Dict

from ...shared.models import BankMapping


class MapperStrategy(ABC):
    """Strategy pattern for mapping NES PRG banks to SMS Sega mapper slots."""

    @property
    @abstractmethod
    def mapper_id(self) -> int:
        """Return the NES mapper ID."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return human-readable mapper name."""
        pass

    @abstractmethod
    def map_banks(self, prg_banks: int) -> List[BankMapping]:
        """
        Map NES PRG banks to SMS Sega mapper slots.

        Args:
            prg_banks: Number of 16KB PRG banks in NES ROM

        Returns:
            List of BankMapping objects
        """
        pass

    @abstractmethod
    def generate_banking_code(self) -> List[str]:
        """Generate Z80 routine for handles mapper-specific bank switching."""
        pass

    def get_warnings(self) -> List[str]:
        """Return any warnings about this mapper."""
        return []


class NROMMapper(MapperStrategy):
    """NROM (mapper 0) - fixed PRG, no banking."""

    @property
    def mapper_id(self) -> int:
        return 0

    @property
    def name(self) -> str:
        return "NROM"

    def map_banks(self, prg_banks: int) -> List[BankMapping]:
        return [BankMapping(sms_bank=i, nes_bank=i, fixed=True) for i in range(prg_banks)]

    def generate_banking_code(self) -> List[str]:
        return ["; NROM has no banking"]


class CNROMMapper(MapperStrategy):
    """CNROM (mapper 3) - CHR banking only, PRG fixed."""

    @property
    def mapper_id(self) -> int:
        return 3

    @property
    def name(self) -> str:
        return "CNROM"

    def map_banks(self, prg_banks: int) -> List[BankMapping]:
        return [BankMapping(sms_bank=i, nes_bank=i, fixed=True) for i in range(prg_banks)]

    def generate_banking_code(self) -> List[str]:
        return ["; CNROM has no PRG banking (CHR banking only)"]


class UxROMMapper(MapperStrategy):
    """UxROM (mapper 2) - PRG banking, last bank fixed."""

    @property
    def mapper_id(self) -> int:
        return 2

    @property
    def name(self) -> str:
        return "UxROM"

    def map_banks(self, prg_banks: int) -> List[BankMapping]:
        return [
            BankMapping(sms_bank=i, nes_bank=i, fixed=(i == prg_banks - 1))
            for i in range(prg_banks)
        ]

    def generate_banking_code(self) -> List[str]:
        return [
            "hal_uxrom_switch:",
            "    ; UxROM switch: Write to ROM area selects bank 0-7 at $8000",
            "    ld   ($ffff), a",
            "    ret"
        ]


class MMC1Mapper(MapperStrategy):
    """MMC1 (mapper 1) - serial register banking."""

    @property
    def mapper_id(self) -> int:
        return 1

    @property
    def name(self) -> str:
        return "MMC1"

    def map_banks(self, prg_banks: int) -> List[BankMapping]:
        return [
            BankMapping(sms_bank=i, nes_bank=i, fixed=(i == prg_banks - 1))
            for i in range(prg_banks)
        ]

    def generate_banking_code(self) -> List[str]:
        return [
            "hal_mmc1_switch:",
            "    ; MMC1 serial switch emulation",
            "    ld   ($ffff), a",
            "    ret"
        ]


class MMC3Mapper(MapperStrategy):
    """
    MMC3 (mapper 4) - complex scanline-based banking.

    Note: Full MMC3 support requires tracking IRQ state and PPU A12 lines.
    This is a simplified mapping that may not work for all MMC3 games.
    """

    @property
    def mapper_id(self) -> int:
        return 4

    @property
    def name(self) -> str:
        return "MMC3"

    def map_banks(self, prg_banks: int) -> List[BankMapping]:
        return [BankMapping(sms_bank=i, nes_bank=i, fixed=False) for i in range(prg_banks)]

    def generate_banking_code(self) -> List[str]:
        return [
            "hal_mmc3_switch:",
            "    ; MMC3 complex bank switch",
            "    ld   ($ffff), a",
            "    ret"
        ]

    def get_warnings(self) -> List[str]:
        return [
            "MMC3 bank switching requires advanced Z80 interrupt translations. "
            "Manual intervention may be needed."
        ]


class UnsupportedMapper(MapperStrategy):
    """Fallback for unsupported mappers."""

    def __init__(self, mapper_id: int):
        self._mapper_id = mapper_id

    @property
    def mapper_id(self) -> int:
        return self._mapper_id

    @property
    def name(self) -> str:
        return f"Unsupported (mapper {self._mapper_id})"

    def map_banks(self, prg_banks: int) -> List[BankMapping]:
        return [BankMapping(sms_bank=i, nes_bank=i, fixed=False) for i in range(prg_banks)]

    def generate_banking_code(self) -> List[str]:
        return [f"; Unsupported mapper {self._mapper_id}"]

    def get_warnings(self) -> List[str]:
        return [
            f"Unsupported mapper {self._mapper_id}. "
            f"Generated flat export - manual intervention required."
        ]


# Mapper registry
_MAPPER_REGISTRY = {
    0: NROMMapper,
    1: MMC1Mapper,
    2: UxROMMapper,
    3: CNROMMapper,
    4: MMC3Mapper,
}


def get_mapper_strategy(mapper_id: int) -> MapperStrategy:
    """
    Get the appropriate mapper strategy for a given mapper ID.

    Args:
        mapper_id: NES mapper number

    Returns:
        MapperStrategy instance
    """
    cls = _MAPPER_REGISTRY.get(mapper_id, UnsupportedMapper)
    return cls(mapper_id) if cls == UnsupportedMapper else cls()
