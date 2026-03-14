# SMS VDP and Character Format Notes
from Neon Spiral Injector Mail Extract (neonmail.txt)

## ROM Loading
- Master System real hardware checks checksums; emulators often don't.
- ROMs should be multiples of 16k.

## Character Format (Bitplanes)
- Characters are 8x8 pixels, 4 bitplanes.
- Byte 0: Bit 0 of all 8 pixels in a row.
- Byte 1: Bit 1 of all 8 pixels in a row.
- Byte 2: Bit 2 of all 8 pixels in a row.
- Byte 3: Bit 3 of all 8 pixels in a row.
- Total: 32 bytes per character.
- Bit 7 is the leftmost pixel; bit 0 is the rightmost.

## VRAM Mapping
- Plane 0, Line Y of Char X: `(X * 32) + (Y * 4)`
- Plane 1, Line Y of Char X: `(X * 32) + (Y * 4) + 1`
- Plane 2, Line Y of Char X: `(X * 32) + (Y * 4) + 2`
- Plane 3, Line Y of Char X: `(X * 32) + (Y * 4) + 3`
- VRAM is 16k, mirrored at $0000, $4000, $8000.
- **Guideline**: Only write to $4000+ and read from $0000+.

## VDP Registers (Correction to Unofficial Specs)
- **VREG 0**: Bit 4 enables/disables H-interrupt.
- **VREG 1**:
    - Bit 6: Enable screen (1) / Disable screen (0).
    - Bit 5: Enable V-interrupt (1) / Disable V-interrupt (0).
- **VREG 5**: Sprite Attribute Table base address. Bits 6-1 represent A13-A8.
- **Sprites**: 8x16 sprites must use even-numbered characters.

## FM Sound (YM2413)
- Port 240 ($F0): Register select.
- Port 241 ($F1): Data write.
- Port 242 ($F2): Detection.

---
Source: https://www.smspower.org/uploads/Development/neonmail.txt
