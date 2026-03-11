"""6502 to Z80 register mapping and calling conventions."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class RegisterMapping:
    """Maps 6502 registers to Z80 registers."""

    a: str = "a"
    x: str = "b"
    y: str = "c"
    flags: str = "f"
    stack_pointer: str = "sp"
    program_counter: str = "pc"

    def get_6502_reg(self, z80_reg: str) -> Optional[str]:
        """Get 6502 register name from Z80 register."""
        mapping = {
            "a": "A",
            "b": "X",
            "c": "Y",
            "f": "P",
            "sp": "S",
        }
        return mapping.get(z80_reg.lower())

    def get_z80_reg(self, name_6502: str) -> str:
        """Get Z80 register name from 6502 register."""
        mapping = {
            "A": "a",
            "X": "b",
            "Y": "c",
            "P": "f",
            "S": "sp",
        }
        return mapping.get(name_6502.upper(), "hl")


@dataclass
class CallingConvention:
    """
    Z80 calling convention for ported 6502 code.

    Convention:
    - Parameters passed in: HL (first), DE (second), BC (third)
    - Return value in: A (8-bit) or HL (16-bit)
    - Caller saves: AF, BC, DE, HL
    - Callee saves: None (caller must preserve what it needs)
    """

    param_regs_16: List[str] = None
    return_reg_8: str = "a"
    return_reg_16: str = "hl"
    caller_save: List[str] = None
    callee_save: List[str] = None

    def __post_init__(self):
        if self.param_regs_16 is None:
            self.param_regs_16 = ["hl", "de", "bc"]
        if self.caller_save is None:
            self.caller_save = ["af", "bc", "de", "hl"]
        if self.callee_save is None:
            self.callee_save = []


class FlagMapping:
    """Maps 6502 flags to Z80 flags."""

    FLAG_MAP = {
        "N": "S",  # Negative → Sign
        "V": "P",  # Overflow → Parity/Overflow
        "B": None,  # Break (no Z80 equivalent)
        "D": None,  # Decimal (Z80 has DAA but no flag)
        "I": None,  # Interrupt disable (Z80 has IFF1/IFF2)
        "Z": "Z",  # Zero → Zero
        "C": "C",  # Carry → Carry
    }

    @classmethod
    def get_z80_flag(cls, flag_6502: str) -> Optional[str]:
        """Get Z80 flag from 6502 flag."""
        return cls.FLAG_MAP.get(flag_6502.upper())

    @classmethod
    def get_6502_flag(cls, flag_z80: str) -> Optional[str]:
        """Get 6502 flag from Z80 flag."""
        reverse_map = {v: k for k, v in cls.FLAG_MAP.items() if v is not None}
        return reverse_map.get(flag_z80.upper())

    @classmethod
    def get_condition(cls, condition_6502: str) -> str:
        """
        Convert 6502 branch condition to Z80 condition.

        6502 conditions:
        - BCC/BLO: Branch if Carry Clear / Lower
        - BCS/BCS: Branch if Carry Set
        - BEQ: Branch if Equal
        - BMI: Branch if Minus
        - BNE: Branch if Not Equal
        - BPL: Branch if Plus
        - BVC: Branch if Overflow Clear
        - BVS: Branch if Overflow Set
        """
        mapping = {
            "BCC": "NC",
            "BLO": "NC",
            "BCS": "C",
            "BEQ": "Z",
            "BMI": "M",
            "BNE": "NZ",
            "BPL": "P",
            "BVC": "PO",
            "BVS": "PE",
        }
        return mapping.get(condition_6502.upper(), "NZ")
