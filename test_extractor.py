import sys

sys.path.insert(0, "src")
from nes2sms.infrastructure.symbol_extractor import StaticSymbolExtractor
from nes2sms.infrastructure.rom_loader import RomLoader
from pathlib import Path

# Load ROM
loader = RomLoader()
loader.load(Path("homebrews/pong.nes"))

# Extract symbols
extractor = StaticSymbolExtractor(loader.prg_data)
symbols = extractor.extract()

print(f"Found {len(symbols)} symbols:")
for sym in symbols[:20]:  # First 20
    print(f"  ${sym.address:04X} {sym.name} ({sym.type})")

if len(symbols) > 20:
    print(f"  ... and {len(symbols) - 20} more")

print(f"\nCode ranges: {len(extractor.get_code_ranges())}")
for start, end in extractor.get_code_ranges()[:5]:
    print(f"  ${start:04X} - ${end:04X}")

print(f"\nVisited addresses: {len(extractor.visited)}")
print(f"Code addresses: {len(extractor.code_addresses)}")
