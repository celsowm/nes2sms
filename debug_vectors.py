import sys

sys.path.insert(0, "src")
from nes2sms.infrastructure.rom_loader import RomLoader
from pathlib import Path

loader = RomLoader()
loader.load(Path("homebrews/pong.nes"))

print(f"PRG size: {len(loader.prg_data)} bytes ({len(loader.prg_data) // 1024}KB)")
print(f"Base address: $8000")
print(f"Max valid address: ${0x8000 + len(loader.prg_data) - 1:04X}")

# Check if RESET is valid
reset_addr = 0x80DF
offset = reset_addr - 0x8000
print(f"\nRESET at $80DF:")
print(f"  Offset: {offset} (${offset:04X})")
print(f"  Valid? {0 <= offset < len(loader.prg_data)}")

# Check NMI
nmi_addr = 0x8197
nmi_offset = nmi_addr - 0x8000
print(f"\nNMI at $8197:")
print(f"  Offset: {nmi_offset} (${nmi_offset:04X})")
print(f"  Valid? {0 <= nmi_offset < len(loader.prg_data)}")

# Check what vectors point to
vectors = loader.prg_data[-6:]
nmi_target = vectors[0] | (vectors[1] << 8)
reset_target = vectors[2] | (vectors[3] << 8)
irq_target = vectors[4] | (vectors[5] << 8)

print(f"\nVector targets:")
print(f"  NMI: ${nmi_target:04X} (offset ${nmi_target - 0x8000:04X})")
print(f"  RESET: ${reset_target:04X} (offset ${reset_target - 0x8000:04X})")
print(f"  IRQ: ${irq_target:04X} (offset ${irq_target - 0x8000:04X})")

# Check if targets are valid
for name, target in [("NMI", nmi_target), ("RESET", reset_target), ("IRQ", irq_target)]:
    off = target - 0x8000
    valid = 0 <= off < len(loader.prg_data)
    print(f"  {name} valid? {valid}")
