# Sega Master System (Mark III) Official Software Reference Manual
Summary based on Official Documentation

## THE CPU
- **Z80A** clocked at **3.58 MHz**.
- **RESET**: Only occurs on power-up. The console RESET button is for software polling, not hardware Z80 reset.
- **Interrupts**:
    - **NMI ($0066)**: Connected to the **PAUSE** button. Edge-triggered. Must end with `RETN`.
    - **INT ($0038)**: Mode 1 only. Triggered by VDP (VBlank or H-Line). Cleared by reading port $BF.
- **Port $BF (VDP Status Read)**:
    - Bit 7: VBlank Interrupt flag.
    - Bit 6: 9 sprites on a line flag.
    - Bit 5: Sprite Collision flag.

## VIDEO DISPLAY PROCESSOR (VDP)
- Derived from TMS9918A.
- **Resolution**: 256x192, 16 colors from a palette of 64.
- **VRAM**: 16 KB, separate from Z80 space.
- **Background**: 32x24 tiles (8x8 pixels). Screen map is 1792 bytes.
- **Sprites**: 64 independent sprites. 8x8 or 8x16 pixels. Up to 8 per line.
- **Color RAM**: 32 6-bit values (two banks of 16).

## MEMORY MANAGEMENT
- **Z80 Space**: 64 KB.
- **On-board RAM**: 8 KB (mapped at $C000-$DFFF and mirrored at $E000-$FFFF).
- **Control Register ($3E)**: Enables/disables System ROM, RAM, Card, Cartridge, and External slots.
- **Paging (Mega Cartridges)**: Uses a register at **$FFFF** to switch 16 KB ROM banks into $8000-$BFFF.
- **Duplicates**: Writes to $FFFF are mirrored in RAM at $FFFF, making it effectively read/write.

## CARTRIDGE HEADER
Located at **$7FF0-$7FFF**:
- **$7FF0**: "TMR SEGA  " (Magic string).
- **$7FFA**: Checksum (16-bit).
- **$7FFC**: Serial Number.
- **$7FFE**: Software Revision.
- **$7FFF**: ROM Size code.

## I/O PORTS
- **$3E**: Memory Enable.
- **$3F**: Controller Port Control (Strobes and Direction).
- **$7E/$7F**: PSG.
- **$BE**: VDP Data.
- **$BF**: VDP Control/Status.
- **$DC/$DD**: Joystick/Gun/Trackball inputs.

---
Source: https://www.smspower.org/Development/SMSOfficialDocs
