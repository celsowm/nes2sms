import sys

sys.path.insert(0, "src")
from nes2sms.infrastructure.symbol_extractor import StaticSymbolExtractor
from nes2sms.infrastructure.rom_loader import RomLoader
from pathlib import Path

loader = RomLoader()
loader.load(Path("homebrews/pong.nes"))

extractor = StaticSymbolExtractor(loader.prg_data)
symbols = extractor.extract()

# Check for GameMain
game_main = [s for s in symbols if "Game" in s.name or "Main" in s.name]
print("Symbols with Game/Main:", game_main)

# Check RESET handler
reset = [s for s in symbols if "RESET" in s.name]
print("RESET:", reset)
if reset:
    print(f"  Address: ${reset[0].address:04X}")
    print(
        f"  Disassembly snippet: {reset[0].disassembly_snippet[:200] if reset[0].disassembly_snippet else 'None'}..."
    )

# List all symbols
print(f"\nAll {len(symbols)} symbols:")
for s in symbols[:10]:
    print(f"  {s.name} @ ${s.address:04X}")
