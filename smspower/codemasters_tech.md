# Codemasters and Extended VDP Modes
by Jason Starr (2001)

## Codemasters Games
- Use a different mapper accessed at **$8000** (pages ROM into $8000-$BFFF).
- Cartridges are connected to the Z80 CLK line.
- Use a **256x224** display mode (extended from 256x192).

## Extended Display (256x224)
- Enabled by setting **Bit 4 of VDP Register 1** (potentially in conjunction with others).
- In some documentation, this is referred to as the "Mode 1" bit stretching the screen from 24 to 28 rows.
- Sprite processing typically stops at Y=208; it's unclear how this is handled in 224-line mode.

## VDP Register 0/1 Findings
- Bit 2 of VDP Register 0 may relate to enabling "stretched" screens or TMS9918 modes.
- F16 Fighter is a rare game that uses a legacy TMS9918 mode.

---
Source: https://www.smspower.org/uploads/Development/techdoc.txt
