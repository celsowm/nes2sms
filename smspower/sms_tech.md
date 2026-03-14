# Sega Master System Technical Information
by Richard Talbot-Watkins

## Technical Specifications
- **CPU**: Z80 running at ~3.3MHz - ~4MHz.
- **VDP**: Derived from TMS9918/9928.
    - 256x192 resolution.
    - 64 sprites (8x8, 8x16, 16x16).
    - 32 colors (16 background, 16 sprites) from a palette of 64.
- **VRAM**: 16K, accessed via ports.
- **PSG**: SN76489 (3 square-wave channels, 1 noise channel).
- **RAM**: 8K on-board (mirrored at $E000-$FFFF).

## Memory Map
| Range | Target |
| :--- | :--- |
| $0000-$03FF | First 1k of ROM (fixed) |
| $0400-$3FFF | 15k ROM Page 0 |
| $4000-$7FFF | 16k ROM Page 1 |
| $8000-$BFFF | 16k ROM Page 2 / Cartridge RAM |
| $C000-$DFFF | 8k on-board RAM |
| $E000-$FFFF | Mirror of RAM |
| $FFFC-$FFFF | Paging Registers |

## I/O Ports
- **$DC**: Joypad port 1 (Read).
- **$DD**: Joypad port 2 (Read).
- **$3F**: Nationalization / I/O control (Write).
- **$7F**: PSG output / V-Counter (Read/Write).
- **$BE**: VDP Data (Read/Write).
- **$BF**: VDP Control/Status (Read/Write).

---
Source: https://www.smspower.org/uploads/Development/richard.txt
