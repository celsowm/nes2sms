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
            1, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # 00-0F
            2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # 10-1F
            3, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # 20-2F
            2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # 30-3F
            1, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # 40-4F
            2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # 50-5F
            1, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # 60-6F
            2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # 70-7F
            2, 2, 0, 0, 2, 2, 2, 0, 1, 0, 1, 0, 3, 3, 3, 0, # 80-8F
            2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 0, 3, 0, 0, # 90-9F
            2, 2, 2, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # A0-AF
            2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # B0-BF
            2, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # C0-CF
            2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # D0-DF
            2, 2, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 3, 3, 3, 0, # E0-EF
            2, 2, 0, 0, 2, 2, 2, 0, 1, 3, 1, 0, 3, 3, 3, 0, # F0-FF
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
        0xA1: "LDA",
        0xA4: "LDY",
        0xC1: "CMP",
        0xE1: "SBC",
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
        0xE5: "SBC",
        0xE6: "INC",
        0xE8: "INX",
        0xE9: "SBC",
        0xEA: "NOP",
        0xEC: "CPX",
        0xED: "SBC",
        0xEE: "INC",
        0xF0: "BEQ",
        0xF1: "SBC",
        0xF5: "SBC",
        0xF6: "INC",
        0xF8: "SED",
        0xF9: "SBC",
        0xFA: "NOP",
        0xFD: "SBC",
        0xFE: "INC",
    }

    # Opcodes that use immediate addressing mode (operand is #$XX)
    IMMEDIATE_OPCODES = {
        0x09, 0x29, 0x49, 0x69, 0xA0, 0xA2, 0xA9,
        0xC0, 0xC9, 0xE0, 0xE9,
    }

    # Opcodes that use indirect-indexed addressing: ($XX),Y
    INDIRECT_Y_OPCODES = {0x11, 0x31, 0x51, 0x71, 0x91, 0xB1, 0xD1, 0xF1}

    # Opcodes that use indexed-indirect addressing: ($XX,X)
    INDIRECT_X_OPCODES = {0x01, 0x21, 0x41, 0x61, 0x81, 0xA1, 0xC1, 0xE1}

    # Opcodes that use zero-page,X addressing
    ZP_X_OPCODES = {0x15, 0x16, 0x35, 0x36, 0x55, 0x56, 0x75, 0x76, 0x95, 0x94, 0xB4, 0xB5, 0xD5, 0xD6, 0xF5, 0xF6}

    # Opcodes that use zero-page,Y addressing
    ZP_Y_OPCODES = {0x96, 0xB6}

    # Opcodes that use absolute,X addressing
    ABS_X_OPCODES = {0x1D, 0x1E, 0x3D, 0x3E, 0x5D, 0x5E, 0x7D, 0x7E, 0x9D, 0xBC, 0xBD, 0xDD, 0xDE, 0xFD, 0xFE}

    # Opcodes that use absolute,Y addressing
    ABS_Y_OPCODES = {0x19, 0x39, 0x59, 0x79, 0x99, 0xB9, 0xBE, 0xD9, 0xF9}

    # JMP indirect opcode
    JMP_INDIRECT = 0x6C

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
        pending_addresses = []
        discovered_targets = set()
        if code_ranges:
            for start, end in code_ranges:
                pending_addresses.append(start)
        elif labels:
            # Use label addresses as entry points for flow-following
            for addr in sorted(labels.keys()):
                pending_addresses.append(addr)
        else:
            # Fallback: use NES vectors from end of PRG
            end_addr = start_addr + len(prg_data)
            vec_offset = len(prg_data) - 6
            if vec_offset >= 0:
                for i in range(3):
                    vec_addr = prg_data[vec_offset + i * 2] | (prg_data[vec_offset + i * 2 + 1] << 8)
                    if start_addr <= vec_addr < end_addr:
                        pending_addresses.append(vec_addr)
            if not pending_addresses:
                pending_addresses.append(start_addr)

        processed_addresses = set()
        while pending_addresses:
            addr = pending_addresses.pop(0)
            if addr in db.instructions or addr in processed_addresses:
                continue
            
            offset = addr - start_addr
            if offset < 0 or offset >= len(prg_data):
                continue

            # Get opcode
            opcode = prg_data[offset]
            size = self.SIZE_TABLE[opcode]
            
            # Use size 1 for unknowns or if it would exceed ROM
            if size == 0 or offset + size > len(prg_data):
                size = 1

            # Mark ALL bytes of this instruction as processed so operand
            # bytes don't get re-interpreted as opcodes
            for b in range(size):
                processed_addresses.add(addr + b)

            # Get mnemonic
            mnemonic = self.MNEMONICS.get(opcode)
            if not mnemonic:
                mnemonic = ".BYTE"
                size = 1
                # Re-mark only this byte
                processed_addresses.discard(addr)
                processed_addresses.add(addr)
                operands = [f"${opcode:02X}"]
            else:
                operands = []
                is_branch = mnemonic in ("BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ")
                if is_branch and size == 2:
                    # Relative branch
                    rel_offset = prg_data[offset + 1]
                    if rel_offset >= 0x80:
                        rel_offset -= 0x100
                    target_addr = (addr + 2 + rel_offset) & 0xFFFF
                    operands.append(f"${target_addr:04X}")
                    discovered_targets.add(target_addr)
                    pending_addresses.append(addr + size)
                    pending_addresses.append(target_addr)
                elif size == 2:
                    byte_val = prg_data[offset + 1]
                    if opcode in self.IMMEDIATE_OPCODES:
                        operands.append(f"#${byte_val:02X}")
                    elif opcode in self.INDIRECT_X_OPCODES:
                        operands.append(f"(${byte_val:02X},X)")
                    elif opcode in self.INDIRECT_Y_OPCODES:
                        operands.append(f"(${byte_val:02X}),Y")
                    elif opcode in self.ZP_X_OPCODES:
                        operands.append(f"${byte_val:02X},X")
                    elif opcode in self.ZP_Y_OPCODES:
                        operands.append(f"${byte_val:02X},Y")
                    else:
                        operands.append(f"${byte_val:02X}")
                    pending_addresses.append(addr + size)
                elif size == 3:
                    addr_val = prg_data[offset + 1] | (prg_data[offset + 2] << 8)
                    if opcode == self.JMP_INDIRECT:
                        operands.append(f"(${addr_val:04X})")
                    elif opcode in self.ABS_X_OPCODES:
                        operands.append(f"${addr_val:04X},X")
                    elif opcode in self.ABS_Y_OPCODES:
                        operands.append(f"${addr_val:04X},Y")
                    else:
                        operands.append(f"${addr_val:04X}")
                    if mnemonic in ("JMP", "JSR"):
                        discovered_targets.add(addr_val)
                        pending_addresses.append(addr_val)
                    if mnemonic != "JMP":
                        pending_addresses.append(addr + size)
                else:
                    # Size 1 (implied/accumulator)
                    if mnemonic not in ("RTS", "RTI", "BRK"):
                        pending_addresses.append(addr + size)

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
