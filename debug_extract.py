import sys

sys.path.insert(0, "src")
from nes2sms.infrastructure.rom_loader import RomLoader
from nes2sms.infrastructure.symbol_extractor import StaticSymbolExtractor
from pathlib import Path

loader = RomLoader()
loader.load(Path("homebrews/pong.nes"))

# Create extractor with debug
extractor = StaticSymbolExtractor(loader.prg_data)

# Manually call extract vectors
extractor._extract_vectors()
print(f"After vectors: {len(extractor.code_addresses)} addresses")
print(f"  Addresses: {[hex(a) for a in extractor.code_addresses]}")

# Try to follow code
print("\nCalling _follow_code...")
extractor._follow_code()
print(f"After follow_code: {len(extractor.code_addresses)} addresses")
print(f"  Visited: {len(extractor.visited)}")

# Build symbols
extractor._build_symbols()
print(f"\nTotal symbols: {len(extractor.symbols)}")
