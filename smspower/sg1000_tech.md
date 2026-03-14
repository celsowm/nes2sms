# Sega Game 1000 (SG-1000) Specifications
by Omar Cornut / Zoop (1999)

## Hardware
- **CPU**: Zilog Z-80 at ~3.58 MHz.
- **Video**: TMS9918 (256x192).
- **Sound**: SN76489 PSG.
- **RAM**: 8 KB (mirrored at $C000).
- **VRAM**: 16 KB.

## Memory Map
| Range | Function |
| :--- | :--- |
| $0000-$7FFF | ROM |
| $8000-$9FFF | Unused |
| $A000-$BFFF | RAM |
| $C000-$FFFF | Mirror of RAM |

## I/O Ports
- **$DC / $C0**: Joypad 1 (Read).
- **$DD / $C1**: Joypad 2 (Read).
- **$7E / $7F**: PSG Output (Write).
- **$BE**: VDP Data (Read/Write).
- **$BF**: VDP Address (Write) / Status (Read).

## Interrupts
- **Mode 1**: Jump to $0038 every 1/60th second.
- **NMI**: Jump to $0066 when Pause is pressed.

## VDP Registers Summary
- **Register 0/1**: Mode bits and display settings.
- **Register 2**: Tile Map Address (VRAM).
- **Register 3**: Color Map Address (VRAM).
- **Register 4**: Tiles Starting Address (VRAM).
- **Register 5**: Sprite Table Address (VRAM).
- **Register 6**: Sprite Starting Tile Address (VRAM).
- **Register 7**: Background/Border color.

---
Source: https://www.smspower.org/uploads/Development/sg1000.txt
