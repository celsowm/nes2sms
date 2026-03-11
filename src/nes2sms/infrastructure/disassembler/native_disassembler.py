"""Native 6502 disassembler - doesn't require external tools."""

from typing import Dict, List, Tuple, Optional

from ...core.interfaces.i_disassembler import (
    IDisassembler,
    DisassemblyResult,
    DisassemblyDatabase,
    ParsedInstruction,
)


class Native6502Disassembler(IDisassembler):
    """
    Pure Python 6502 disassembler.

    Doesn't require external tools like da65.
    Uses the same SIZE_TABLE as StaticSymbolExtractor.
    """

    # 6502 instruction size table (corrected)
    SIZE_TABLE = bytes(
        [
            1,
            2,
            3,
            3,
            2,
            2,
            3,
            3,
            1,
            3,
            0,
            0,
            2,
            2,
            3,
            3,  # 0x00-0x0F
            2,
            2,
            3,
            3,
            0,
            2,
            3,
            3,
            1,
            2,
            1,
            3,
            3,
            2,
            3,
            3,  # 0x10-0x1F
            3,
            2,
            3,
            3,
            0,
            2,
            3,
            3,
            1,
            0,
            0,
            3,
            3,
            2,
            3,
            3,  # 0x20-0x2F
            2,
            2,
            3,
            3,
            0,
            2,
            3,
            3,
            1,
            2,
            1,
            3,
            0,
            2,
            3,
            3,  # 0x30-0x3F
            1,
            2,
            3,
            3,
            2,
            2,
            3,
            3,
            1,
            0,
            0,
            3,
            3,
            2,
            3,
            3,  # 0x40-0x4F
            2,
            2,
            3,
            3,
            0,
            2,
            3,
            3,
            1,
            2,
            1,
            3,
            0,
            2,
            3,
            3,  # 0x50-0x5F
            1,
            2,
            3,
            3,
            2,
            2,
            3,
            3,
            1,
            0,
            0,
            3,
            3,
            2,
            3,
            3,  # 0x60-0x6F
            2,
            2,
            3,
            3,
            0,
            2,
            3,
            3,
            1,
            2,
            1,
            3,
            0,
            2,
            3,
            3,  # 0x70-0x7F
            2,
            2,
            2,
            3,
            0,
            2,
            3,
            3,
            1,
            2,
            0,
            3,
            0,
            2,
            3,
            3,  # 0x80-0x8F
            2,
            2,
            0,
            3,
            0,
            2,
            3,
            3,
            1,
            0,
            0,
            3,
            0,
            2,
            3,
            3,  # 0x90-0x9F
            2,
            0,
            2,
            3,
            0,
            2,
            3,
            3,
            1,
            0,
            0,
            3,
            0,
            2,
            3,
            3,  # 0xA0-0xAF
            2,
            2,
            0,
            3,
            2,
            2,
            3,
            3,
            1,
            0,
            0,
            3,
            0,
            2,
            3,
            3,  # 0xB0-0xBF
            2,
            0,
            2,
            3,
            0,
            2,
            3,
            3,
            1,
            0,
            0,
            3,
            0,
            2,
            3,
            3,  # 0xC0-0xCF
            2,
            2,
            0,
            3,
            0,
            2,
            3,
            3,
            1,
            2,
            1,
            3,
            0,
            2,
            3,
            3,  # 0xD0-0xDF
            2,
            0,
            2,
            3,
            0,
            2,
            3,
            3,
            1,
            0,
            0,
            3,
            0,
            2,
            3,
            3,  # 0xE0-0xEF
            2,
            2,
            0,
            3,
            0,
            2,
            3,
            3,
            1,
            2,
            1,
            3,
            0,
            2,
            3,
            3,  # 0xF0-0xFF
        ]
    )

    # 6502 instruction mnemonics
    MNEMONICS = {
        0x00: "BRK",
        0x01: "ORA",
        0x05: "ORA",
        0x06: "ASL",
        0x08: "PHP",
        0x09: "ORA",
        0x0A: "ASL",
        0x0D: "ORA",
        0x0E: "ASL",
        0x10: "BPL",
        0x11: "ORA",
        0x15: "ORA",
        0x16: "ASL",
        0x18: "CLC",
        0x19: "ORA",
        0x1A: "NOP",
        0x1D: "ORA",
        0x1E: "ASL",
        0x20: "JSR",
        0x21: "AND",
        0x24: "BIT",
        0x25: "AND",
        0x26: "ROL",
        0x28: "PLP",
        0x29: "AND",
        0x2A: "ROL",
        0x2C: "BIT",
        0x2D: "AND",
        0x2E: "ROL",
        0x30: "BMI",
        0x31: "AND",
        0x35: "AND",
        0x36: "ROL",
        0x38: "SEC",
        0x39: "AND",
        0x3A: "NOP",
        0x3D: "AND",
        0x3E: "ROL",
        0x40: "RTI",
        0x41: "EOR",
        0x45: "EOR",
        0x46: "LSR",
        0x48: "PHA",
        0x49: "EOR",
        0x4A: "LSR",
        0x4C: "JMP",
        0x4D: "EOR",
        0x4E: "LSR",
        0x50: "BVC",
        0x51: "EOR",
        0x55: "EOR",
        0x56: "LSR",
        0x58: "CLI",
        0x59: "EOR",
        0x5A: "NOP",
        0x5D: "EOR",
        0x5E: "LSR",
        0x60: "RTS",
        0x61: "ADC",
        0x65: "ADC",
        0x66: "ROR",
        0x68: "PLA",
        0x69: "ADC",
        0x6A: "ROR",
        0x6C: "JMP",
        0x6D: "ADC",
        0x6E: "ROR",
        0x70: "BVS",
        0x71: "ADC",
        0x75: "ADC",
        0x76: "ROR",
        0x78: "SEI",
        0x79: "ADC",
        0x7A: "NOP",
        0x7D: "ADC",
        0x7E: "ROR",
        0x81: "STA",
        0x84: "STY",
        0x85: "STA",
        0x86: "STX",
        0x88: "DEY",
        0x8A: "TXA",
        0x8C: "STY",
        0x8D: "STA",
        0x8E: "STX",
        0x90: "BCC",
        0x91: "STA",
        0x94: "STY",
        0x95: "STA",
        0x96: "STX",
        0x98: "TYA",
        0x99: "STA",
        0x9A: "TXS",
        0x9D: "STA",
        0xA0: "LDY",
        0xA2: "LDX",
        0xA5: "LDA",
        0xA6: "LDX",
        0xA8: "TAY",
        0xA9: "LDA",
        0xAA: "TAX",
        0xAC: "LDY",
        0xAD: "LDA",
        0xAE: "LDX",
        0xB0: "BCS",
        0xB1: "LDA",
        0xB4: "LDY",
        0xB5: "LDA",
        0xB6: "LDX",
        0xB8: "CLV",
        0xB9: "LDA",
        0xBA: "TSX",
        0xBC: "LDY",
        0xBD: "LDA",
        0xBE: "LDX",
        0xC0: "CPY",
        0xC4: "CPY",
        0xC5: "CMP",
        0xC6: "DEC",
        0xC8: "INY",
        0xC9: "CMP",
        0xCA: "DEX",
        0xCC: "CPY",
        0xCD: "CMP",
        0xCE: "DEC",
        0xD0: "BNE",
        0xD1: "CMP",
        0xD5: "CMP",
        0xD6: "DEC",
        0xD8: "CLD",
        0xD9: "CMP",
        0xDA: "NOP",
        0xDD: "CMP",
        0xDE: "DEC",
        0xE0: "CPX",
        0xE4: "CPX",
        0xE5: "CMP",
        0xE6: "INC",
        0xE8: "INX",
        0xE9: "SBC",
        0xEA: "NOP",
        0xEC: "CPX",
        0xED: "CMP",
        0xEE: "INC",
        0xF0: "BEQ",
        0xF1: "CMP",
        0xF5: "CMP",
        0xF6: "INC",
        0xF8: "SED",
        0xF9: "CMP",
        0xFA: "NOP",
        0xFD: "CMP",
        0xFE: "INC",
    }

    def __init__(self):
        """Initialize native disassembler."""
        pass

    def is_available(self) -> bool:
        """Native disassembler is always available."""
        return True

    def disassemble(
        self,
        prg_data: bytes,
        start_addr: int = 0x8000,
        cpu: Optional[str] = None,
        labels: Optional[Dict[int, str]] = None,
        code_ranges: Optional[List[Tuple[int, int]]] = None,
    ) -> DisassemblyResult:
        """
        Disassemble PRG data using native disassembler.

        Args:
            prg_data: PRG ROM bytes
            start_addr: Start address (default: $8000 for NES)
            cpu: CPU type (ignored, only 6502 supported)
            labels: Optional labels to guide disassembly
            code_ranges: Optional code ranges

        Returns:
            DisassemblyResult with parsed database
        """
        db = DisassemblyDatabase()

        # Add labels if provided
        if labels:
            for addr, label in labels.items():
                db.add_label(addr, label)

        # Determine addresses to disassemble
        addresses_to_process = set()
        
        # Branch/jump targets discovered during disassembly
        discovered_targets = set()

        if code_ranges:
            # Add all addresses in code ranges
            for start, end in code_ranges:
                for addr in range(start, end + 1):
                    addresses_to_process.add(addr)
        else:
            # Disassemble entire PRG linearly
            for offset in range(len(prg_data)):
                addresses_to_process.add(start_addr + offset)

        # Disassemble entire PRG - byte by byte to catch all code
        # This ensures we don't miss any code due to jumps/branches
        for offset in range(len(prg_data)):
            addr = start_addr + offset

            # Get opcode
            opcode = prg_data[offset]

            # Get instruction size
            size = self.SIZE_TABLE[opcode]
            # Fix incorrect zero sizes for immediate instructions
            if size == 0:
                # Most opcodes with size 0 are immediate (2 bytes) or special
                # LDA, LDX, LDY immediate: A9, A2, A0 = 2
                # STA, STX, STY absolute: 8D, 8E, 8C = 3
                # Others: use 2 as fallback for immediate-like ops
                size = 2
            if offset + size > len(prg_data):
                size = 1

            # Skip if we've already disassembled from this address
            if addr in db.instructions:
                continue

            # Get mnemonic
            mnemonic = self.MNEMONICS.get(opcode, f".BYTE ${opcode:02X}")

            # Get operands and check for branch targets
            operands = []
            if mnemonic in ("BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ") and size == 2:
                # Relative branch
                offset = prg_data[offset + 1]
                if offset >= 0x80:
                    offset -= 0x100
                target_addr = (addr + 2 + offset) & 0xFFFF
                operands.append(f"${target_addr:04X}")
            elif size == 2 and offset + 1 < len(prg_data):
                operands.append(f"${prg_data[offset + 1]:02X}")
            elif size == 3 and offset + 2 < len(prg_data):
                addr_val = prg_data[offset + 1] | (prg_data[offset + 2] << 8)
                if mnemonic in ("JMP", "JSR"):
                    discovered_targets.add(addr_val)
                    operands.append(f"${addr_val:04X}")
                else:
                    operands.append(f"${addr_val:04X}")

            # Create instruction
            instr = ParsedInstruction(
                address=addr,
                bytes_raw=prg_data[offset : offset + size],
                mnemonic=mnemonic,
                operands=operands,
                label=labels.get(addr) if labels else None,
            )

            db.add_instruction(instr)

        # Identify code ranges
        db.code_ranges = [(start_addr, start_addr + len(prg_data) - 1)]

        # Generate text output
        output_lines = [
            "; 6502 Disassembly",
            "; Generated by nes2sms native disassembler",
            "",
        ]

        for instr in db.to_instruction_list():
            label = db.get_label_at(instr.address)
            if label:
                output_lines.append(f"{label}:")

            bytes_str = " ".join(f"{b:02X}" for b in instr.bytes_raw)
            ops = " ".join(instr.operands)
            output_lines.append(
                f"    {instr.address:04X}: {bytes_str:10s} {instr.mnemonic:5s} {ops}"
            )

        output_lines.append("")

        return DisassemblyResult(
            output="\n".join(output_lines),
            success=True,
            database=db,
        )
