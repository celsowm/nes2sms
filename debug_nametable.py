"""Debug: check nametable data from the runtime capture JSON."""
import json, sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Load the runtime capture
with open("out/pong_sms/work/runtime_capture/runtime_capture.json") as f:
    capture = json.load(f)

vram = capture["ppu_vram"]
palette = capture["palette_ram"]
oam = capture["oam"]

print(f"Total VRAM bytes: {len(vram)}")
print(f"Nonzero VRAM bytes: {sum(1 for v in vram if v)}")
print(f"Palette RAM: {palette}")
print(f"OAM nonzero entries: {sum(1 for i in range(0, 256, 4) if oam[i] < 0xEF and (oam[i] or oam[i+1] or oam[i+2] or oam[i+3]))}")

# Check what the Pong ROM PRG writes to PPU nametable
# Read the PRG data and scan for $2006/$2007 write patterns
with open("out/pong_sms/work/prg.bin", "rb") as f:
    prg = f.read()

print(f"\nPRG size: {len(prg)} bytes")

# Find palette write addresses in PRG
# LDA #$20, STA $2006 (sets PPU addr high byte to nametable)
for i in range(len(prg) - 5):
    if prg[i] == 0xA9 and prg[i+1] == 0x20 and prg[i+2] == 0x8D and prg[i+3] == 0x06 and prg[i+4] == 0x20:
        print(f"Found LDA #$20, STA $2006 at PRG offset ${i:04X} (addr ${0x8000+i:04X})")
    if prg[i] == 0xA9 and prg[i+1] == 0x21 and prg[i+2] == 0x8D and prg[i+3] == 0x06 and prg[i+4] == 0x20:
        print(f"Found LDA #$21, STA $2006 at PRG offset ${i:04X} (addr ${0x8000+i:04X})")
    # Also check for LDX pattern
    if prg[i] == 0xA2 and prg[i+1] == 0x20 and prg[i+2] == 0x8E and prg[i+3] == 0x06 and prg[i+4] == 0x20:
        print(f"Found LDX #$20, STX $2006 at PRG offset ${i:04X} (addr ${0x8000+i:04X})")

# Let's also check the NES CHR data for tile 0
with open("out/pong_sms/work/chr.bin", "rb") as f:
    chr_data = f.read()

print(f"\nCHR tile 0 (16 bytes): {chr_data[:16].hex()}")
print(f"CHR tile 0 is all zeros: {not any(chr_data[:16])}")

# Check first 10 non-zero tiles
print("\nFirst 10 non-zero NES tiles:")
count = 0
for i in range(len(chr_data) // 16):
    tile = chr_data[i*16:(i+1)*16]
    if any(tile):
        print(f"  Tile {i:3d} (0x{i:02X}): {tile.hex()}")
        count += 1
        if count >= 10:
            break
