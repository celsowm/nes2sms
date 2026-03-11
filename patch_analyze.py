    def _analyze_instruction(
        self, opcode: int, offset: int, addr: int
    ) -> tuple:
        """
        Analyze 6502 instruction to determine size and control flow.
        
        Uses precomputed size table for accuracy.
        """
        # Precomputed instruction size table for 6502
        SIZE_TABLE = bytes([
            1, 2, 3, 3, 2, 2, 3, 3, 1, 3, 0, 0, 2, 2, 3, 3,  # 0x00-0x0F
            2, 2, 3, 3, 0, 2, 3, 3, 1, 2, 1, 3, 3, 2, 3, 3,  # 0x10-0x1F
            3, 2, 3, 3, 0, 2, 3, 3, 1, 0, 0, 3, 3, 2, 3, 3,  # 0x20-0x2F
            2, 2, 3, 3, 0, 2, 3, 3, 1, 2, 1, 3, 0, 2, 3, 3,  # 0x30-0x3F
            1, 2, 3, 3, 2, 2, 3, 3, 1, 0, 0, 3, 3, 2, 3, 3,  # 0x40-0x4F
            2, 2, 3, 3, 0, 2, 3, 3, 1, 2, 1, 3, 0, 2, 3, 3,  # 0x50-0x5F
            1, 2, 3, 3, 2, 2, 3, 3, 1, 0, 0, 3, 3, 2, 3, 3,  # 0x60-0x6F
            2, 2, 3, 3, 0, 2, 3, 3, 1, 2, 1, 3, 0, 2, 3, 3,  # 0x70-0x7F
            2, 2, 2, 3, 0, 2, 3, 3, 1, 2, 0, 3, 0, 2, 3, 3,  # 0x80-0x8F
            2, 2, 0, 3, 0, 2, 3, 3, 1, 0, 0, 3, 0, 2, 3, 3,  # 0x90-0x9F
            2, 0, 2, 3, 0, 2, 3, 3, 1, 0, 0, 3, 0, 2, 3, 3,  # 0xA0-0xAF
            2, 2, 0, 3, 2, 2, 3, 3, 1, 0, 0, 3, 0, 2, 3, 3,  # 0xB0-0xBF
            2, 0, 2, 3, 0, 2, 3, 3, 1, 0, 0, 3, 0, 2, 3, 3,  # 0xC0-0xCF
            2, 2, 0, 3, 0, 2, 3, 3, 1, 2, 1, 3, 0, 2, 3, 3,  # 0xD0-0xDF
            2, 0, 2, 3, 0, 2, 3, 3, 1, 0, 0, 3, 0, 2, 3, 3,  # 0xE0-0xEF
            2, 2, 0, 3, 0, 2, 3, 3, 1, 2, 1, 3, 0, 2, 3, 3,  # 0xF0-0xFF
        ])
        
        # Get base size
        instr_size = SIZE_TABLE[opcode]
        
        # Handle invalid/illegal opcodes (size 0)
        if instr_size == 0:
            instr_size = 1
        
        # Clamp to available data
        if offset + instr_size > len(self.prg_data):
            instr_size = max(1, len(self.prg_data) - offset)
        
        # Check for terminal (RTS/RTI)
        is_terminal = opcode in (0x60, 0x40)
        
        # Calculate branch/jump target
        branch_target = None
        if opcode == 0x20 and offset + 2 < len(self.prg_data):  # JSR
            branch_target = self.prg_data[offset + 1] | (self.prg_data[offset + 2] << 8)
        elif opcode == 0x4C and offset + 2 < len(self.prg_data):  # JMP abs
            branch_target = self.prg_data[offset + 1] | (self.prg_data[offset + 2] << 8)
        elif opcode in (0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0):  # Branches
            if offset + 1 < len(self.prg_data):
                rel_offset = self.prg_data[offset + 1]
                if rel_offset & 0x80:  # Negative
                    rel_offset -= 0x100
                branch_target = (addr + 2 + rel_offset) & 0xFFFF
        
        return instr_size, is_terminal, branch_target
