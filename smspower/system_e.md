# Sega System E Hardware Notes
(C) 2010 Charles MacDonald

## Introduction
The "System E" board is derived from the Sega Master System. It features:
- Twice as much work RAM (16K).
- Two VDPs.
- Twice the video RAM for each VDP.

## Timing
- XTAL: 10.7386 MHz.
- Z80 Clock: 5.36 MHz (XTAL/2).

## Memory Map
- $0000-$7FFF : ROM (IC7).
- $8000-$BFFF : Bank area (VDP VRAM is write-only here too).
- $C000-$FFFF : Work RAM (16K).

## Video Overview
- Two VDPs, each with 32K VRAM (split into 16K banks).
- VDP #1 is the main video source. VDP #2 is selected when VDP #1 pixels are blank (transparent).

### Layer Priority (Front to Back)
1. VDP #1 tilemap (high priority)
2. VDP #1 sprites
3. VDP #1 tilemap (low priority)
4. VDP #2 tilemap (high priority)
5. VDP #2 sprites
6. VDP #2 tilemap (low priority)
7. VDP #2 backdrop color

---
Source: https://www.smspower.org/uploads/Development/setech.txt
