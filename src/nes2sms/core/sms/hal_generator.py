"""HAL generator for creating Z80 hardware emulation routines."""

from ._hal_input import generate_input_routines
from ._hal_misc import (
    generate_apu_routines,
    generate_footer,
    generate_header,
    generate_utility_routines,
)
from ._hal_oam import generate_oam_dma_routine
from ._hal_ppu import generate_ppu_routines


class HALGenerator:
    """Compose subsystem-specific HAL sections into one support blob."""

    def __init__(self, split_y: int = 48):
        self.split_y = max(0, min(239, int(split_y)))

    def generate_all(self) -> str:
        """Generate the complete HAL library."""
        sections = [
            self.generate_header(),
            self.generate_ppu_routines(),
            self.generate_apu_routines(),
            self.generate_input_routines(),
            self.generate_oam_dma_routine(),
            self.generate_utility_routines(),
            self.generate_footer(),
        ]
        return "\n\n".join(sections)

    def generate_header(self) -> str:
        return generate_header()

    def generate_ppu_routines(self) -> str:
        return generate_ppu_routines()

    def generate_apu_routines(self) -> str:
        return generate_apu_routines()

    def generate_input_routines(self) -> str:
        return generate_input_routines()

    def generate_oam_dma_routine(self) -> str:
        return generate_oam_dma_routine(self.split_y)

    def generate_utility_routines(self) -> str:
        return generate_utility_routines()

    def generate_footer(self) -> str:
        return generate_footer()
