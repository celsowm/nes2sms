import sys

sys.path.insert(0, "src")
from nes2sms.infrastructure.rom_loader import RomLoader
from pathlib import Path

loader = RomLoader()
loader.load(Path("homebrews/pong.nes"))

prg_data = loader.prg_data
base_address = 0x8000

# SIZE TABLE - CORRECTED
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


def disassemble_from(start_addr, prg_data, base):
    addr = start_addr
    visited = set()
    queue = []

    print(f"Starting from ${start_addr:04X}")

    iterations = 0
    while iterations < 500 and (addr is not None or queue):
        if addr is not None and addr not in visited:
            visited.add(addr)
            offset = addr - base

            if offset >= len(prg_data) or offset < 0:
                print(f"  [{iterations}] ${addr:04X}: OUT OF BOUNDS")
                addr = None
                continue

            opcode = prg_data[offset]
            size = SIZE_TABLE[opcode]
            if size == 0:
                size = 1

            # Check control flow
            if opcode == 0x60 or opcode == 0x40:  # RTS/RTI
                print(f"  [{iterations}] ${addr:04X}: ${opcode:02X} (RTS/RTI)")
                addr = None
            elif opcode == 0x20 and offset + 2 < len(prg_data):  # JSR
                target = prg_data[offset + 1] | (prg_data[offset + 2] << 8)
                print(f"  [{iterations}] ${addr:04X}: ${opcode:02X} JSR ${target:04X}")
                queue.append(target)
                addr += size
            elif opcode == 0x4C and offset + 2 < len(prg_data):  # JMP
                target = prg_data[offset + 1] | (prg_data[offset + 2] << 8)
                print(f"  [{iterations}] ${addr:04X}: ${opcode:02X} JMP ${target:04X}")
                addr = None  # JMP ends this path
            elif opcode in (0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0):  # Branch
                if offset + 1 < len(prg_data):
                    rel = prg_data[offset + 1]
                    if rel & 0x80:
                        rel -= 0x100
                    target = (addr + 2 + rel) & 0xFFFF
                    print(f"  [{iterations}] ${addr:04X}: ${opcode:02X} branch ${target:04X}")
                    queue.append(target)  # Add branch target
                    addr += size  # Also continue to next instruction
            else:
                if iterations < 30:
                    print(f"  [{iterations}] ${addr:04X}: ${opcode:02X} (size {size})")
                addr += size
        else:
            addr = None

        # Get next from queue if current is done
        if addr is None and queue:
            next_addr = queue.pop(0)
            if next_addr not in visited:
                addr = next_addr
                print(f"\n  -> Jumping to ${addr:04X} from queue")

        iterations += 1

    return visited


visited = disassemble_from(0x80DF, prg_data, base_address)
print(f"\nTotal visited: {len(visited)}")
