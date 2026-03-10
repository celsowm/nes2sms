# NES → SMS: Hardware Differences Deep Reference

## Table of Contents
1. Graphics Pipeline (PPU → VDP Mode 4)
2. Sprite System (OAM → SAT)
3. Palette System
4. Scroll Engine
5. Interrupt Architecture
6. Memory Maps
7. Mapper Mapping Table
8. Audio Conversion (APU → PSG)
9. Input / Control Mapping
10. VDP Register Map
11. SMS Header Format

---

## 1. Graphics Pipeline (PPU → VDP Mode 4)

### NES PPU Tile Format (2bpp, 16 bytes per 8×8 tile)
```
Bytes 0–7:  Bitplane 0 (LSB of each pixel)
Bytes 8–15: Bitplane 1 (MSB of each pixel)

Pixel x of row r:
  b0 = (chr[r]   >> (7-x)) & 1
  b1 = (chr[r+8] >> (7-x)) & 1
  color_index = (b1 << 1) | b0   → 0..3
```

### SMS VDP Mode 4 Tile Format (4bpp, 32 bytes per 8×8 tile)
```
4 bytes per row (bitplanes 0..3 interleaved, big-endian pixel order):
  sms_tile[r*4 + plane] = packed bits of plane `plane` for all 8 pixels of row r

Pixel x of row r:
  sms_idx = (bit3 << 3) | (bit2 << 2) | (bit1 << 1) | bit0   → 0..15
  plane p contributes: ((sms_idx >> p) & 1) << (7-x)
```

### Conversion Formula
```python
def nes_tile_to_sms(chr16, color_map):
    """chr16: 16-byte NES tile, color_map: int[4] mapping NES idx→SMS idx"""
    sms32 = bytearray(32)
    for row in range(8):
        plane0 = chr16[row]
        plane1 = chr16[row + 8]
        pixels = []
        for x in range(8):
            b0 = (plane0 >> (7 - x)) & 1
            b1 = (plane1 >> (7 - x)) & 1
            pixels.append(color_map[(b1 << 1) | b0])
        for plane in range(4):
            byte = 0
            for x in range(8):
                byte |= ((pixels[x] >> plane) & 1) << (7 - x)
            sms32[row * 4 + plane] = byte
    return sms32
```

### CHR-ROM vs CHR-RAM
- **CHR-ROM**: tiles stored in ROM, loaded during VBlank via DMA. Extract from chr.bin.
- **CHR-RAM**: tiles generated at runtime by game code (writes to PPU $2007).
  Requires tracing PPU VRAM writes during emulation to capture tile data.
  Mark all CHR-RAM tiles as `DYNAMIC` in manifest_sms.json.

---

## 2. Sprite System (OAM → SAT)

### NES OAM Entry (4 bytes per sprite, 64 sprites)
```
Byte 0: Y position (top edge, minus 1; $EF = off-screen)
Byte 1: Tile index
Byte 2: Attributes:
         bits 1:0 = palette (0–3 of sprite palettes)
         bit  5   = priority (0=front, 1=behind background)
         bit  6   = flip horizontal
         bit  7   = flip vertical
Byte 3: X position (left edge)
```

### SMS SAT Layout (in VRAM at $3F00)
```
$3F00–$3F3F: Y positions (64 bytes, one per sprite)
             Value $D0 = end of sprite list (in 192-line mode)
$3F40–$3FFF: X + tile index pairs (128 bytes, 2 bytes per sprite)
             Byte 0: X position
             Byte 1: tile index (0–255; or 256+ with high bit from VDP reg)
```

### Key Differences
- SMS has **no per-sprite flip bits**. Flipped variants must be pre-generated.
- SMS sprite coordinate Y is drawn at row `y + 1` (add 1 to NES Y for same visual).
- NES sprite priority bit (behind bg) → SMS uses VDP register priority bit per BG tile.
- SMS sprite size: 8×8 (default) or 8×16 (VDP reg 1 bit 1). NES also supports 8×16
  (OAM bit 5 of tile index selects table; top/bottom halves are consecutive tiles).

### Flip Cache Implementation
```python
def generate_flip_variants(tile_4bpp_32bytes):
    """Returns dict of flip variants: {'H': bytes, 'V': bytes, 'HV': bytes}"""
    t = tile_4bpp_32bytes
    variants = {}
    # Horizontal flip: reverse pixel order within each row
    h_flip = bytearray(32)
    for row in range(8):
        for plane in range(4):
            original = t[row * 4 + plane]
            flipped = int(f'{original:08b}'[::-1], 2)  # reverse bit order
            h_flip[row * 4 + plane] = flipped
    variants['H'] = bytes(h_flip)
    # Vertical flip: reverse row order
    v_flip = bytearray(32)
    for row in range(8):
        for plane in range(4):
            v_flip[row * 4 + plane] = t[(7 - row) * 4 + plane]
    variants['V'] = bytes(v_flip)
    # HV: apply both
    variants['HV'] = bytes(nes_tile_flip(h_flip, 'V'))  # chain
    return variants
```

---

## 3. Palette System

### NES Palette Structure
- 64 hardware output colors (6-bit index; only ~54 are distinct).
- Palette RAM: 32 bytes in PPU address space $3F00–$3F1F.
  - $3F00–$3F0F: 4 BG palettes × 4 colors (index 0 = universal backdrop)
  - $3F10–$3F1F: 4 SPR palettes × 4 colors (mirrors $3F00 for index 0)
- NES attribute table selects palette per 16×16-pixel region (2 bits per block).

### SMS Palette Structure
- 2 palettes × 16 colors = 32 entries in CRAM (Color RAM).
- Each color: `%00BBGGRR` (2 bits per channel → 4 levels each → 64 total colors).
- BG tiles select BG or SPR palette via name table bit 11.
- Sprites always use SPR palette.

### NES → SMS Color Conversion
```python
# Standard NES palette in RGB (use authoritative .pal file for accuracy):
NES_PALETTE_RGB = [...]  # 64 × (R, G, B) tuples, values 0–255

def nes_color_to_sms(nes_index):
    r, g, b = NES_PALETTE_RGB[nes_index & 0x3F]
    # Quantize to 2-bit per channel (0–3), SMS format %00BBGGRR
    rr = round(r / 255 * 3) & 0x3
    gg = round(g / 255 * 3) & 0x3
    bb = round(b / 255 * 3) & 0x3
    return (bb << 4) | (gg << 2) | rr
```

### Palette Overflow Handling
When NES game uses more than 16 unique colors for BG or sprites:
1. **Nearest-color merge** (default): combine two NES palette slots whose SMS
   approximations are most similar; log merged pairs in conversion_report.md.
2. **Palette bit trick**: some BG tiles can reference SPR palette (name table bit 11)
   if no sprites are visible in that area. Gives up to 32 BG colors total.
3. **Per-zone re-palette**: use line interrupt (VDP reg 10) to swap palettes between
   scanline zones (e.g., HUD vs gameplay area). High effort; mark as `ADVANCED`.

---

## 4. Scroll Engine

### NES PPU Scrolling
- `$2005` write (first): X scroll (0–255)
- `$2005` write (second): Y scroll (0–239)
- "Loopy scroll" — internal VRAM address register technique; many games manipulate
  `$2006`/`$2005` mid-frame for split-scroll effects.
- NMI handler typically resets scroll for stable display.
- NES display: 256×240 (with ~8px overscan each edge on real hardware).

### SMS VDP Scrolling
- VDP Reg 8: horizontal scroll (0–255, scrolls right as value increases).
- VDP Reg 9: vertical scroll (0–223 for 192-line mode).
- VDP Reg 10: line interrupt counter (generates INT on specific scanlines).
- Scroll direction: NES and SMS scroll in opposite horizontal directions.
  **Invert the X scroll value**: `sms_x_scroll = 256 - nes_x_scroll`.
- Split-scroll effects: use line interrupt (Reg 10) to reload VDP regs mid-frame.

### Display Size Difference
- NES visible: 256×240 (30 tile rows)
- SMS visible: 256×192 (24 tile rows)  ← 6 fewer rows
- Policy options for the missing 48 pixels (3 tile rows top + bottom each):
  - `crop-top-8-bottom-10`: crop 1 tile row top, 1.25 at bottom (common).
  - `crop-symmetric`: remove 3 rows top and 3 bottom (loses HUD elements).
  - `hud-relocate`: detect HUD tiles, move to top 2 rows, crop gameplay area.
  - `scale`: not recommended (distorts tiles).

---

## 5. Interrupt Architecture

### NES Interrupts
```
$FFFA/$FFFB: NMI vector  → fires on VBlank start (PPU timing)
$FFFC/$FFFD: RESET vector → entry point after power-on/reset
$FFFE/$FFFF: IRQ/BRK vector → APU frame counter, mapper (MMC3), BRK opcode
```
NMI is the primary "game loop tick" handler on NES. It is non-maskable.

### SMS / Z80 IM 1 Interrupts
```
$0038: INT handler → VBlank (VDP bit 7 of status) or line counter (bit 6)
$0066: NMI handler → PAUSE button only (non-maskable)
```
- **Critical**: INT handler MUST read VDP status port $BF to clear the interrupt.
  Failure to read $BF will cause the interrupt to re-fire immediately.
- VDP status register (read $BF):
  - Bit 7: Frame interrupt (VBlank occurred)
  - Bit 6: Sprite overflow
  - Bit 5: Sprite collision
- Z80 EI + RETI to return from INT; RETN to return from NMI.

### NMI Body → INT Handler Mapping
The NES NMI body (typically: update OAM DMA, update scroll, run game logic tick)
maps to the SMS INT handler:
```asm
; NES NMI pattern:
;   LDA #$00 / STA $2003 / LDA #$02 / STA $4014  → OAM DMA
;   LDA scroll_x / STA $2005 / LDA scroll_y / STA $2005 → scroll update

; SMS INT equivalent:
INT_Handler:
    push af \ push bc \ push de \ push hl \ push ix \ push iy
    in   a, ($BF)           ; READ VDP STATUS — mandatory
    call UpdateSAT          ; replaces OAM DMA
    call UpdateScroll       ; calls VDP_SetScrollX / VDP_SetScrollY
    call GameLogicTick      ; ported NMI game-update body
    pop iy \ pop ix \ pop hl \ pop de \ pop bc \ pop af
    ei
    reti
```

---

## 6. Memory Maps

### NES CPU Memory Map
```
$0000–$00FF   Zero page RAM (fast-access; heavily used as pseudo-registers)
$0100–$01FF   Stack (grows down from $01FF)
$0200–$07FF   General RAM
$0800–$1FFF   RAM mirrors (×3)
$2000–$2007   PPU registers (mirrored $2008–$3FFF)
$4000–$4013   APU channel registers
$4014         OAM DMA
$4015         APU status/enable
$4016         Joypad 1 (write: strobe; read: serial shift)
$4017         Joypad 2 / APU frame counter
$4020–$5FFF   Cartridge expansion
$6000–$7FFF   PRG-RAM / battery-backed SRAM
$8000–$FFFF   PRG-ROM (bank-switched by mapper)
  $FFFA–$FFFF  Vectors (NMI, RESET, IRQ)
```

### SMS Z80 Memory Map
```
$0000–$03FF   Fixed ROM (always page 0 of slot 0; contains $0038/$0066 vectors)
$0000–$3FFF   ROM Slot 0  (selected by mapper reg $FFFD)
$4000–$7FFF   ROM Slot 1  (selected by mapper reg $FFFE)
$8000–$BFFF   ROM Slot 2  (selected by mapper reg $FFFF)
$C000–$DFFF   Work RAM (8 KB; mirrored at $E000–$FFFF)
$FFFC         Sega mapper control (RAM mapping)
$FFFD         Slot 0 bank select
$FFFE         Slot 1 bank select
$FFFF         Slot 2 bank select
```

### NES ZP Variables → SMS RAM Remapping
NES zero page ($00–$FF) is latency-critical. On Z80, use `IX` or `IY` as frame pointers
pointing into $C000+ RAM to keep hotpath variables in a contiguous block.
Alternatively, directly assign static SMS RAM addresses to each NES ZP variable name.

---

## 7. Mapper Mapping Table

### Supported NES Mapper → SMS Bank Strategy

| NES Mapper | ID  | PRG Layout             | SMS Strategy                                      |
|------------|-----|------------------------|---------------------------------------------------|
| NROM       | 0   | 16K or 32K fixed       | Fits in slots 0+1 (32K) with no banking needed   |
| UxROM      | 2   | 16K switchable + 16K fixed at end | Slot 1 = switchable, Slot 0 = fixed (vectors) |
| CNROM      | 3   | 32K PRG fixed + CHR bank switch | Same as NROM; CHR switch → reload tiles DMA |
| MMC1       | 1   | 16K or 32K, serial regs | Re-link to Sega mapper; 4 banks → 4 SMS banks   |
| MMC3       | 4   | 8K PRG banks × 4 windows + IRQ | Use SMS line interrupt for scanline IRQ equiv; re-bank manually |
| AxROM      | 7   | 32K switchable (single reg) | Slot 0+1 = switchable pair; update $FFFD+$FFFE together |
| GxROM      | 66  | 32K + 8K CHR banks     | Same as AxROM; CHR → reload tiles per bank switch |

### MMC3 IRQ → SMS Line Interrupt
MMC3 uses PPU A12 transitions (nametable/pattern table address bit 12) to count
scanlines and fire an IRQ. On SMS, use VDP Reg 10 (line interrupt counter):
```asm
; Set line interrupt to fire every N lines:
ld   a, N
call VDP_SetRegister_10     ; load A=10, B=N → VDP reg 10
; Enable line interrupt: VDP Reg 0 bit 4 = 1
```
The equivalence is approximate; per-scanline counting may differ by 1–2 lines.

### Unsupported Mapper Fallback
- Mappers not in the table above: generate flat bank dump (all PRG concatenated).
- Mark all banking-related stubs as `; TODO: MAPPER UNSUPPORTED`.
- Record mapper number and write addresses observed in conversion_report.md.

---

## 8. Audio Conversion (APU → PSG SN76489)

### NES APU Channels
| Channel  | Regs      | Description                                    |
|----------|-----------|------------------------------------------------|
| Pulse 1  | $4000–$4003 | 11-bit period, 4-bit volume, duty, envelope  |
| Pulse 2  | $4004–$4007 | Same as Pulse 1                              |
| Triangle | $4008–$400B | 11-bit period, linear counter (no volume)    |
| Noise    | $400C–$400F | Short/long mode, 4-bit volume                |
| DMC      | $4010–$4013 | 1-bit delta PCM sample playback              |

### SMS PSG SN76489 Channels
| Channel | Control Byte | Attenuation Byte |
|---------|-------------|-----------------|
| Tone 1  | `%1000xxxx` + period high | `%10010xxx` |
| Tone 2  | `%1010xxxx` + period high | `%10110xxx` |
| Tone 3  | `%1100xxxx` + period high | `%11010xxx` |
| Noise   | `%1110 00fb` | `%11110xxx` |

Noise byte: `f` = frequency shift, `b` = 1 for white noise, 0 for periodic.

### Frequency Conversion
```
PSG_period = clock / (32 * target_Hz)
  where clock = 3579545 Hz (SMS NTSC)

NES APU period to Hz:
  f_pulse = 1789773 / (16 * (period + 1))
  f_triangle = 1789773 / (32 * (period + 1))
  f_noise = noise_table[period_index]  # lookup table

SMS tone period:
  sms_period = round(3579545 / (32 * nes_hz))  # 10-bit value
  Write: out ($7F), 0x80 | (channel_latch << 5) | (sms_period & 0xF)
         out ($7F), (sms_period >> 4) & 0x3F
```

### Volume / Attenuation Mapping
```
NES volume (0–15, 15=loudest) → PSG attenuation (0–15, 0=loudest, 15=silent)
  psg_atten = 15 - nes_volume

NES envelope (decreasing): capture envelope period and replicate via IRQ tick counter.
NES constant volume: use direct attenuation mapping.
```

### DMC Handling
DMC (delta PCM) samples have no equivalent in PSG. Options:
1. **Drop** (default): silence DMC, log in conversion_report.md.
2. **Substitute**: replace with a Tone 3 burst of similar pitch/duration.
3. **Pre-record**: capture DMC playback as raw audio, store as data, play via
   a software sample engine (very advanced; out of scope for Port Kit tier).

---

## 9. Input / Control Mapping

### NES Controller ($4016/$4017)
Read sequence: write $01 to $4016 (strobe), write $00, then read $4016 8 times.
Button order: A, B, Select, Start, Up, Down, Left, Right.

### SMS Joypad ($DC/$DD)
Direct parallel read (no strobe required):
- Port $DC: Joypad 1 bits [5:0] = Up, Down, Left, Right, Button1, Button2
            Joypad 2 bits [7:6] = Up, Down (remaining bits in $DD)
- Port $DD: Joypad 2 bits [3:0] = Left, Right, Button1, Button2
- All bits: 0 = pressed, 1 = released (active low).
- PAUSE button generates NMI (not readable via ports).

### Default Button Mapping
| NES        | SMS         | Notes                              |
|------------|-------------|------------------------------------|
| A          | Button 1    |                                    |
| B          | Button 2    |                                    |
| Start      | PAUSE (NMI) | NES Start is often pause/menu key  |
| Select     | Button1+2   | Hold both buttons simultaneously   |
| D-Pad      | D-Pad       | Direct 1:1                         |

NMI on PAUSE: the NMI handler ($0066) must implement what the NES Start ISR did.

---

## 10. VDP Register Map (SMS Mode 4)

| Reg | Name             | Key Bits                                                      |
|-----|------------------|---------------------------------------------------------------|
| 0   | Mode Control 1   | Bit4=line IRQ enable, Bit3=shift sprites left 8px, Bit1=M4   |
| 1   | Mode Control 2   | Bit6=display enable, Bit5=VBlank IRQ enable, Bit1=sprite 8×16|
| 2   | Name Table Base  | Bits 3:1 → VRAM addr / $400 (typically $06 → $3800)          |
| 3   | Color Table Base | Ignored in Mode 4                                             |
| 4   | BG Pattern Base  | Ignored in Mode 4 (tiles always from $0000)                  |
| 5   | SAT Base         | Bits 6:1 → VRAM addr / $100 (typically $7E → $3F00)          |
| 6   | Sprite Pattern   | Bit 2 → sprite tiles from $2000 if set                       |
| 7   | Border Color     | Bits 3:0 = BG palette color for overscan border              |
| 8   | Scroll X         | Horizontal scroll value (subtract from name table start X)    |
| 9   | Scroll Y         | Vertical scroll value                                         |
| 10  | Line Counter     | Line interrupt reload value (fires when counter underflows)   |

### VDP Init Sequence (WLA-DX)
```asm
VDP_Init:
    ld   hl, VDP_INIT_TABLE
    ld   b, VDP_INIT_TABLE_END - VDP_INIT_TABLE
    ld   c, $BF
    ld   d, $80             ; register write command base
    ld   e, 0               ; register index
.loop:
    outi                    ; write data byte to $BF
    ld   a, d
    or   e
    out  (c), a             ; write register select byte
    inc  e
    djnz .loop
    ret

VDP_INIT_TABLE:
    .db $04                 ; Reg 0: Mode 4, line IRQ off initially
    .db $64                 ; Reg 1: display on, VBlank IRQ on
    .db $FF & ($3800>>10)<<1 | 1  ; Reg 2: name table at $3800
    .db $FF                 ; Reg 3: ignored
    .db $FF                 ; Reg 4: ignored
    .db $FF & ($3F00>>8)<<1 | 1   ; Reg 5: SAT at $3F00
    .db $FB                 ; Reg 6: sprite tiles from $0000
    .db $00                 ; Reg 7: border color 0
    .db $00                 ; Reg 8: X scroll = 0
    .db $00                 ; Reg 9: Y scroll = 0
    .db $FF                 ; Reg 10: line counter (disabled)
VDP_INIT_TABLE_END:
```

---

## 11. SMS ROM Header Format

Located at ROM offset `$7FF0` (for 32 KB ROM; varies by size — see table).

| Offset | Size | Field          | Value / Notes                              |
|--------|------|----------------|--------------------------------------------|
| $7FF0  | 8    | Magic string   | `"TMR SEGA"` (ASCII, no null)              |
| $7FF8  | 2    | Reserved       | $00 $00                                    |
| $7FFA  | 2    | Checksum       | Little-endian sum of bytes $0000–$7FEF     |
| $7FFC  | 3    | Product code   | BCD encoded (homebrew: $00 $00 $00)        |
| $7FFF  | 1    | Region + size  | High nibble: region (5=GG, 6=SMS overseas) |
|        |      |                | Low nibble: $A=8KB, $B=16KB, $C=32KB, $D=48KB, $E=64KB, $F=128KB |

### Checksum Computation
```python
def sms_checksum(rom_bytes):
    """Sum of all bytes except $7FF0–$7FFF header region."""
    total = 0
    for i, b in enumerate(rom_bytes):
        if 0x7FF0 <= i <= 0x7FFF:
            continue
        total += b
    return total & 0xFFFF
```

Header offset varies for larger ROMs (e.g., 64 KB ROM: header at $BFF0;
128 KB+: additional headers may exist at $3FF0 and $7FF0).
