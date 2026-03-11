import sys

sys.path.insert(0, "src")
from nes2sms.infrastructure.rom_loader import RomLoader
from pathlib import Path

loader = RomLoader()
loader.load(Path("homebrews/pong.nes"))

prg_data = loader.prg_data
base_address = 0x8000


def addr_to_offset(addr):
    return addr - base_address


def is_valid_address(addr):
    return base_address <= addr < base_address + len(prg_data)


# Start from RESET
start_addr = 0x80DF
addr = start_addr
visited = set()

print(f"Starting disassembly from ${start_addr:04X}")
print(f"Offset: ${addr_to_offset(start_addr):04X}")

for iteration in range(50):
    offset = addr_to_offset(addr)

    if offset >= len(prg_data):
        print(f"  [{iteration}] ${addr:04X}: OUT OF BOUNDS (offset {offset})")
        break

    if addr in visited:
        print(f"  [{iteration}] ${addr:04X}: ALREADY VISITED")
        break

    visited.add(addr)
    opcode = prg_data[offset]

    # Simple size lookup
    if opcode in (0x20, 0x4C, 0x6C):  # JSR, JMP
        size = 3
        if offset + 2 < len(prg_data):
            target = prg_data[offset + 1] | (prg_data[offset + 2] << 8)
            print(f"  [{iteration}] ${addr:04X}: {hex(opcode):02X} -> target ${target:04X}")
    elif opcode in (0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0):  # Branches
        size = 2
        if offset + 1 < len(prg_data):
            rel = prg_data[offset + 1]
            if rel & 0x80:
                rel -= 0x100
            target = (addr + 2 + rel) & 0xFFFF
            print(f"  [{iteration}] ${addr:04X}: {hex(opcode):02X} -> branch ${target:04X}")
    elif opcode in (0x60, 0x40):  # RTS, RTI
        print(f"  [{iteration}] ${addr:04X}: {hex(opcode):02X} (RTS/RTI) - STOP")
        break
    else:
        # Default size
        size = 1
        if opcode > 0xA0:
            size = 2 if (opcode & 0x03) != 3 else 3

    print(f"  [{iteration}] ${addr:04X}: ${opcode:02X} (size {size})")
    addr += size

    if addr > 0xFFFF:
        break

print(f"\nTotal visited: {len(visited)}")
