from typing import List, Dict, Optional
from abc import ABC, abstractmethod

class IHalComponent(ABC):
    """
    Base interface for any HAL generator component (VDP, PSG, Input, Mapper).
    Enforces that all components can provide their Z80 Assembly source.
    """
    
    @abstractmethod
    def get_asm(self) -> str:
        pass

class Z80ProjectBuilder(ABC):
    """
    Orchestrates the creation of the Z80 project scaffold.
    """
    
    def __init__(self):
        self.components: List[IHalComponent] = []
        
    def add_component(self, component: IHalComponent):
        self.components.append(component)
        
    @abstractmethod
    def build(self, out_dir: str, rom_banks: int):
        pass
