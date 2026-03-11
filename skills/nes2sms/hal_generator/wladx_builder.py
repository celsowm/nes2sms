from typing import Dict, Any
from pathlib import Path
from . import Z80ProjectBuilder
from .wladx_simple_components import WlaDxInputHal, WlaDxPsgHal, WlaDxMapperHal
from .wladx_ppu_components import VirtualPpuWlaDx

class WlaDxBuilder(Z80ProjectBuilder):
    def __init__(self):
        super().__init__()
        # Injeção de Dependência Fixa por enquanto (pode vir de Factory em projetos maiores)
        self.add_component(VirtualPpuWlaDx())
        self.add_component(WlaDxPsgHal())
        self.add_component(WlaDxInputHal())
        self.add_component(WlaDxMapperHal())

    def build(self, out_dir: Path, rom_banks: int):
        hal_dir = out_dir / 'hal'
        hal_dir.mkdir(parents=True, exist_ok=True)
        
        # O Virtual PPU engloba o VDP
        # Components map index to expected HAL file for backwards compatibility with sms_packer.py link.sms
        # [0] = VDP/PPU, [1] = PSG, [2] = Input, [3] = Mapper
        (hal_dir / 'vdp.asm').write_text(self.components[0].get_asm(), encoding='utf-8')
        (hal_dir / 'psg.asm').write_text(self.components[1].get_asm(), encoding='utf-8')
        (hal_dir / 'input.asm').write_text(self.components[2].get_asm(), encoding='utf-8')
        (hal_dir / 'mapper.asm').write_text(self.components[3].get_asm(), encoding='utf-8')
        
        print(f"[WlaDxBuilder] Gerou os componentes do HAL (VDP/VirtualPPU, PSG, Input, Mapper) em {hal_dir}")
