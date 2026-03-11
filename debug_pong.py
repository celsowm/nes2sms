import sys

sys.path.insert(0, "src")
from nes2sms.infrastructure.rom_loader import RomLoader
from pathlib import Path

loader = RomLoader()
loader.load(Path("homebrews/pong.nes"))

print(f"Header: {loader.header}")
print(f"PRG size: {len(loader.prg_data)} bytes")
print(f"PRG banks: {loader.header.prg_banks}")
print(f"CHR size: {loader.header.chr_size}")

# Print first bytes of PRG
print(f"\nFirst 64 bytes of PRG (hex):")
print(" ".join(f"{b:02X}" for b in loader.prg_data[:64]))

# Check vectors at end
print(f"\nLast 6 bytes (vectors):")
vectors = loader.prg_data[-6:]
nmi_addr = vectors[0] | (vectors[1] << 8)
reset_addr = vectors[2] | (vectors[3] << 8)
irq_addr = vectors[4] | (vectors[5] << 8)
print(f"NMI: ${nmi_addr:04X}")
print(f"RESET: ${reset_addr:04X}")
print(f"IRQ: ${irq_addr:04X}")

# Check what's at RESET address
offset = reset_addr - 0x8000
print(f"\nCode at RESET (offset {offset}):")
print(" ".join(f"{b:02X}" for b in loader.prg_data[offset : offset + 32]))
