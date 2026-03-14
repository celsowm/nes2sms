# TMS9918A VDP Specification
by Sean Young

## Overview
Simple VDP with 16kB or 4kB VRAM and a 256x192 resolution.
- **Sprites**: Maximum 4 per horizontal line.
- **Versions**: PAL (50Hz) and NTSC (60Hz).

## Registers
- **8 Control Registers (0-7)**: Manage screen mode, colors, and table addresses.
- **1 Status Register**: Reports VBlank (INT), Fifth Sprite (5S), and Collision (C).

## Colors
Supports 15 solid colors and transparency.

---
Source: https://www.smspower.org/uploads/Development/tms9918a.txt
