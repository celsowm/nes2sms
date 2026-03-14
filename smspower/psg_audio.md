# SN76489 (PSG) Technical Notes
by Charles MacDonald

## Registers
The SN76489 has 8 registers:
- 4 x 4-bit Volume registers.
- 3 x 10-bit Tone registers.
- 1 x 4-bit Noise register.

## Register Map
| Channel | Volume | Tone/Noise |
| :--- | :--- | :--- |
| 0 (%00) | Vol0 | Tone0 |
| 1 (%01) | Vol1 | Tone1 |
| 2 (%10) | Vol2 | Tone2 |
| 3 (%11) | Vol3 | Noise |

## Programming
### Latch/Data (Bit 7 = 1)
`%1 cct dddd`
- **cc**: Channel.
- **t**: Type (0 = Tone/Noise, 1 = Volume).
- **dddd**: Data.

### Data (Bit 7 = 0)
`%0 x dddddd`
- Updates the high 6 bits of a 10-bit tone register, or the low 4 bits otherwise.

## Frequency Calculation
Frequency = Clock / (32 * Register Value)
- NTSC Clock: 3.579545 MHz.
- PAL Clock: 3.546893 MHz.

---
Source: https://www.smspower.org/uploads/Development/SN76489-20030421.txt
