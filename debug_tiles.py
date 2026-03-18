import sys
import os

# add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from nes2sms.core.graphics.palette_mapper import PaletteMapper
from nes2sms.core.graphics.tile_converter import TileConverter
from nes2sms.infrastructure.rom_loader import RomLoader
from nes2sms.core.graphics.runtime_capture import RuntimeGraphicsCapture
from nes2sms.core.graphics.runtime_asset_builder import build_runtime_background_assets
import json

def main():
    from pathlib import Path
    loader = RomLoader()
    loader.load(Path("homebrews/pong.nes"))
    
    chr_data = loader.chr_data
    
    # We know frame 120 has the capture. Let's just create a dummy capture
    # Actually wait, we can just grab a tile from pong.nes that is not empty.
    # Tile $2d is the '-' sign, tile $14 is 'T', etc.
    # Let's dump the first 64 tiles
    
    mapper = PaletteMapper()
    bg_pal, spr_pal, all_maps = mapper.build_all_palettes()
    
    print("Color maps:", all_maps)
    
    converter = TileConverter(color_maps=[all_maps[0]], flip_strategy="none", max_tiles=256)
    
    for i in range(64):
        tile_offset = i * 16
        tile_16bpp = chr_data[tile_offset:tile_offset+16]
        if not any(tile_16bpp):
            continue
        print(f"\\nTile {hex(i)}")
        # print NES pixels
        for row in range(8):
            plane0 = tile_16bpp[row]
            plane1 = tile_16bpp[row + 8]
            pixels = []
            for x in range(8):
                b0 = (plane0 >> (7 - x)) & 1
                b1 = (plane1 >> (7 - x)) & 1
                pixels.append(str((b1 << 1) | b0))
            print("NES[" + str(row) + "]: " + "".join(pixels))
            
        sms_tile = converter.convert_tile_with_map(tile_16bpp, all_maps[0])
        print("Mapped sms plane data bytes:", [hex(b) for b in sms_tile[:4]])

if __name__ == "__main__":
    main()
