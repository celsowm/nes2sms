"""Translator interface - DIP contract."""

from abc import ABC, abstractmethod
from typing import List, Optional


class ITranslator(ABC):
    """
    Interface for 6502 to Z80 translators (DIP).

    Allows swapping between simple translator, flow-aware translator, etc.
    """

    @abstractmethod
    def translate_line(self, line: str, address: Optional[int] = None) -> str:
        """
        Translate a single line of 6502 assembly to Z80.

        Args:
            line: 6502 assembly instruction
            address: Optional address for context

        Returns:
            Z80 assembly line(s) as string
        """
        pass

    @abstractmethod
    def translate_block(self, lines: List[str], start_address: int = 0) -> str:
        """
        Translate a block of 6502 assembly to Z80.

        Args:
            lines: List of 6502 assembly instructions
            start_address: Starting address for reference

        Returns:
            Complete Z80 assembly as string
        """
        pass

    @abstractmethod
    def is_supported(self, mnemonic: str) -> bool:
        """Check if instruction mnemonic is supported."""
        pass

    @abstractmethod
    def get_supported_instructions(self) -> List[str]:
        """Get list of supported instruction mnemonics."""
        pass
