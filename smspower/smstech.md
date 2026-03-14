# SMS/GG Hardware Notes
by Charles MacDonald

## Overview
The main differences between various Sega consoles are what slots are available, if there is a YM2413 sound chip, and if there is a reset or pause button.

| Console | Cart | Card | Exp. | BIOS | YM2413 | Reset | Pause |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Mark III | y | y | y | y | *1 | n | y |
| Japanese SMS | y | y | y | y | y | n | y |
| SMS | y | y | y | y | n | y | y |
| SMS 2 | y | n | n | y | n | n | y |
| Genesis | y | n | n | n | n | n | n |
| Genesis+PBC | y | y | n | n | n | n | y |
| GameGear | y | n | n | *2 | n | n | y |

## Z80 Memory Map
- $0000-$BFFF : Slot area
- $C000-$FFFF : Work RAM (8K, mirrored at $E000-$FFFF)

### 3D Glasses
Register at $FFF8 (mirrors at $FFF9-$FFFB). Bit 0 toggles shutter.

## Z80 I/O Ports
Common ports:
- $3E : Memory control
- $3F : I/O port control
- $7E : V counter / PSG
- $7F : H counter / PSG
- $BE : VDP data
- $BF : VDP control
- $DC : I/O port A/B
- $DD : I/O port B/misc.

## I/O Port Registers
### Port $3E : Memory control
- D7 : Expansion slot enable
- D6 : Cartridge slot enable
- D5 : Card slot disabled
- D4 : Work RAM disabled
- D3 : BIOS ROM disabled
- D2 : I/O chip disabled

## Interrupts
- NMI: PAUSE button ($0066).
- IM 1: PC set to $0038.
- IM 2: Returns $FF (vectors from $C0FF on Genesis/SMS2).

## Sound Hardware
- Game Gear: Port $06 for stereo control.
- YM2413: Ports $F0-$F2.

---
Source: https://www.smspower.org/uploads/Development/smstech-20021112.txt
