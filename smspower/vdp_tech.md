# Sega Master System VDP Documentation
by Charles MacDonald

## Introduction
The VDP is derived from the TMS9918. Versions include:
- **315-5124**: Mark III, SMS.
- **315-5246**: SMS 2.
- **315-5378**: Game Gear.
- **315-5313**: Genesis (Mode 4).

## VDP Ports
- **$7E**: V-Counter (Read) / PSG Data (Write).
- **$7F**: H-Counter (Read) / PSG Data (Write, mirror).
- **$BE**: Data Port (Read/Write).
- **$BF**: Control Port (Read/Write).

## VDP Programming
### Control Port
Two-byte command sequence:
- **CD1 CD0 A13-A08** (Second byte).
- **A07-A00** (First byte).

**Code Register (CD) Actions:**
- 0: VRAM Read.
- 1: VRAM Write.
- 2: VDP Register Write.
- 3: CRAM Write.

### Data Port
Reads are buffered. Writing to the data port also loads the buffer.

## Status Flags (Port $BF Read)
- **INT**: Frame interrupt pending.
- **OVR**: Sprite overflow (>8 sprites on a line).
- **COL**: Sprite collision (two opaque pixels overlap).

---
Source: https://www.smspower.org/uploads/Development/msvdp-20021112.txt
