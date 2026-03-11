"""Hardware interception logic for redirecting NES memory-mapped I/O to SMS HAL."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class IHardwareInterceptor(ABC):
    """Interface for hardware register interception."""

    @abstractmethod
    def can_intercept(self, address: int) -> bool:
        """Check if this interceptor handles the given address."""
        pass

    @abstractmethod
    def intercept_write(self, address: int, value_source: str) -> List[str]:
        """Generate Z80 code for a write to this hardware register."""
        pass

    @abstractmethod
    def intercept_read(self, address: int, target_reg: str) -> List[str]:
        """Generate Z80 code for a read from this hardware register."""
        pass


class BaseHardwareInterceptor(IHardwareInterceptor):
    """Base class for hardware interceptors with range checking."""

    def __init__(self, start_addr: int, end_addr: int):
        self.start_addr = start_addr
        self.end_addr = end_addr

    def can_intercept(self, address: int) -> bool:
        return self.start_addr <= address <= self.end_addr


class PpuInterceptor(BaseHardwareInterceptor):
    """Interceptors for NES PPU registers ($2000-$2007, $4014)."""

    def __init__(self):
        super().__init__(0x2000, 0x2007)

    def can_intercept(self, address: int) -> bool:
        return super().can_intercept(address) or address == 0x4014

    def intercept_write(self, address: int, value_source: str) -> List[str]:
        if address == 0x4014:
            return [
                f"    LD   a, {value_source}",
                "    CALL hal_oam_dma"
            ]
        
        # Generic PPU write (maps to hal_ppu_write which handles sub-registers via A/L)
        reg_offset = address & 0x0007
        return [
            f"    LD   a, {value_source}",
            f"    LD   l, {reg_offset}",
            "    CALL hal_ppu_write"
        ]

    def intercept_read(self, address: int, target_reg: str) -> List[str]:
        reg_offset = address & 0x0007
        return [
            f"    LD   l, {reg_offset}",
            "    CALL hal_ppu_read",
            f"    LD   {target_reg}, a"
        ]


class ApuInterceptor(BaseHardwareInterceptor):
    """Interceptors for NES APU registers ($4000-$4013, $4015)."""

    def __init__(self):
        super().__init__(0x4000, 0x4015)

    def can_intercept(self, address: int) -> bool:
        # Exclude $4014 (PPU DMA)
        return super().can_intercept(address) and address != 0x4014

    def intercept_write(self, address: int, value_source: str) -> List[str]:
        reg_offset = address & 0x001F
        return [
            f"    LD   a, {value_source}",
            f"    LD   l, {reg_offset}",
            "    CALL hal_apu_write"
        ]

    def intercept_read(self, address: int, target_reg: str) -> List[str]:
        reg_offset = address & 0x001F
        return [
            f"    LD   l, {reg_offset}",
            "    CALL hal_apu_read",
            f"    LD   {target_reg}, a"
        ]


class InputInterceptor(BaseHardwareInterceptor):
    """Interceptors for NES Input registers ($4016, $4017)."""

    def __init__(self):
        super().__init__(0x4016, 0x4017)

    def intercept_write(self, address: int, value_source: str) -> List[str]:
        port = address & 0x0001
        return [
            f"    LD   a, {value_source}",
            f"    LD   l, {port}",
            "    CALL hal_input_write"
        ]

    def intercept_read(self, address: int, target_reg: str) -> List[str]:
        port = address & 0x0001
        return [
            f"    LD   l, {port}",
            "    CALL hal_input_read",
            f"    LD   {target_reg}, a"
        ]


class HardwareInterceptorRegistry:
    """Registry to manage and query hardware interceptors."""

    def __init__(self):
        self.interceptors: List[IHardwareInterceptor] = [
            PpuInterceptor(),
            ApuInterceptor(),
            InputInterceptor(),
        ]

    def get_interceptor(self, address: int) -> Optional[IHardwareInterceptor]:
        """Find an interceptor for the given address."""
        for interceptor in self.interceptors:
            if interceptor.can_intercept(address):
                return interceptor
        return None

    def intercept_write(self, address: int, value_source: str) -> Optional[List[str]]:
        """Intercept a write if an interceptor exists."""
        interceptor = self.get_interceptor(address)
        if interceptor:
            return interceptor.intercept_write(address, value_source)
        return None

    def intercept_read(self, address: int, target_reg: str) -> Optional[List[str]]:
        """Intercept a read if an interceptor exists."""
        interceptor = self.get_interceptor(address)
        if interceptor:
            return interceptor.intercept_read(address, target_reg)
        return None
