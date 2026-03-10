---
name: nes2sms
description: >
  End-to-end retargeting pipeline from NES ROM (.nes) to Sega Master System ROM (.sms).
  Use this skill whenever the user wants to convert, port, retarget, or translate a NES
  game to the Sega Master System / Mark III, including: CHR tile and palette conversion
  from PPU 2bpp to VDP Mode 4 4bpp, sprite/OAM to SAT translation, NMI/IRQ handler
  remapping to Z80 interrupts, APU-to-PSG audio approximation, NES mapper analysis and
  SMS Sega-mapper layout generation, HAL stub scaffolding (6502 I/O → Z80 ports), and
  WLA-DX or SDCC project generation with valid SMS header and checksum. Also trigger when
  the user mentions: "NES to SMS", "NES to Master System", "port NES game", "6502 to Z80",
  "convert NES graphics/audio", or any combination thereof. Assumes the nes-disasm skill
  has already run (or will run) to produce disassembly artifacts; accepts both raw .nes
  and pre-extracted artifacts (manifest.json + prg.bin + chr.bin + labels).
---

# NES → Master System: End-to-End Retargeting Skill

## Legal & Ethics — Read First

- Only work on ROMs you own, have explicit permission for, or that are public domain /
  openly licensed (CC0, MIT, homebrew, etc.).
- **Safe to distribute:** scripts, HAL stubs, asset files, build scripts, patches,
  documentation, hashes, symbol maps.
- **Do NOT distribute** the original ROM binary or exact decompiled source unless the
  license explicitly permits it.
- When licensing is uncertain, mark all outputs as `UNSPECIFIED` and do not publish.
- Use legal homebrew ROMs (e.g., `cc65` demo, "Alter Ego", "Lawn Mower") for tests.

---

## Key Concept: This Is a Retarget, Not a Binary Conversion

NES → SMS is **not** a ROM transplant. It is a full hardware retarget:

| Layer        | NES                        | SMS                               |
|--------------|----------------------------|-----------------------------------|
| CPU          | 6502-based (~1.79 MHz)     | Z80A (~3.58 MHz)                  |
| Video        | PPU: 2bpp tiles, 4 palettes| VDP Mode 4: 4bpp tiles, 2×16 pal |
| Audio        | APU: 5 channels            | PSG SN76489: 3 tone + 1 noise    |
| Interrupts   | NMI=$FFFA, IRQ=$FFFE       | Z80 IM1: INT=$0038, NMI=$0066    |
| Banking      | Mapper-specific (MMC1 etc.)| Sega mapper: $FFFC–$FFFF slots   |
| I/O          | Memory-mapped PPU/APU regs | Port-mapped VDP/PSG               |
| Controls     | $4016/$4017 serial shift   | Ports $DC/$DD parallel            |

A fully automated code translation is high-risk. This skill targets the **Port Kit**
tier (deterministic asset conversion + scaffolding + stubs) with optional higher
automation layers. **Read `references/hardware_diff.md` for deep per-subsystem details.**

---

## Prerequisites

| Category           | Tool                         | Notes                                       |
|--------------------|------------------------------|---------------------------------------------|
| Runtime            | Python ≥ 3.10                | stdlib + optional `Pillow` for PNG export   |
| NES disassembly    | nes-disasm skill output      | manifest.json, prg.bin, chr.bin, symbols    |
| 6502 disassembler  | `da65` (cc65) or `retrodisasm` | For static analysis of NES PRG              |
| Z80 assembler      | **WLA-DX** (recommended)     | Macro assembler with SMS memory map support |
| Alt. compiler      | **SDCC** + **devkitSMS**     | C-to-Z80; good for HAL layer                |
| SMS emulator/debug | **Emulicious**, **MEKA**     | Debugging, VRAM dump, register inspection   |
| NES+SMS emulator   | **Mesen 2**                  | Cross-platform; CDL trace for both systems  |
| Checksum tool      | WLA-DX directives or script  | `scripts/sms_packer.py` handles this        |

---

## Output Structure

```
out/<rom_name>_sms/
├── manifest_sms.json          ← conversion metadata, hashes, decisions made
├── build/
│   ├── main.asm               ← WLA-DX top-level (or main.c for SDCC path)
│   ├── init.asm               ← Z80 startup: stack, VDP init, interrupt vectors
│   ├── interrupts.asm         ← INT handler ($0038), NMI/PAUSE handler ($0066)
│   ├── hal/
│   │   ├── vdp.asm            ← HAL: VDP control/data ports, tile upload, scroll
│   │   ├── psg.asm            ← HAL: SN76489 tone/noise/attenuation writes
│   │   ├── input.asm          ← HAL: $DC/$DD port reads, button mapping
│   │   └── mapper.asm         ← HAL: Sega mapper slot writes ($FFFC–$FFFF)
│   ├── stubs/
│   │   └── game_logic.asm     ← Placeholder stubs for each NES game routine
│   └── link.sms               ← WLA-DX linker script with SMS memory map
├── assets/
│   ├── tiles.bin              ← 4bpp VDP tiles (32 bytes each)
│   ├── tilemap.bin            ← Name table entries (2 bytes each, 32×28)
│   ├── palette_bg.bin         ← 16 × %00BBGGRR bytes (background palette)
│   ├── palette_spr.bin        ← 16 × %00BBGGRR bytes (sprite palette)
│   ├── sprites.bin            ← SAT: Y[64], X+tile[64] entries
│   └── audio/
│       ├── events.json        ← Extracted APU write events (note/vol/envelope)
│       └── psg_data.asm       ← PSG channel data re-mapped from APU events
├── reports/
│   ├── conversion_report.md   ← Decisions, warnings, unmapped patterns, risks
│   ├── vram_map.txt           ← VRAM layout: tiles base, nametable, SAT, palette
│   └── symbol_map.json        ← NES label → SMS label cross-reference
└── validation/
    ├── build.log              ← WLA-DX / SDCC output
    └── test_results.txt       ← Emulator boot test, frame checks
```

---

## Pipeline — Step by Step

### Step 0 — Ingest NES Artifacts

Run (or verify) the `nes-disasm` skill first. Then ingest its outputs:

```bash
python3 scripts/convert_gfx.py ingest \
  --nes game.nes \
  --disasm-dir out/game_nes \
  --out out/game_sms/work
```

The `ingest` phase:
1. Reads `manifest.json` from nes-disasm output (mapper, PRG/CHR sizes, hashes).
2. Copies `prg.bin`, `chr.bin`, `symbols.json`, `banks.json` into work directory.
3. If nes-disasm artifacts are absent, runs `parse_nes.py` minimally (reduced analysis).
4. Writes `manifest_sms.json` with a `conversion_state` block (all steps start `PENDING`).

---

### Step 1 — Analyze NES Mapper and PRG Layout

Read `references/hardware_diff.md § Mapper Mapping Table` for the supported mapper list.

```bash
python3 scripts/convert_gfx.py analyze-mapper \
  --manifest out/game_sms/work/manifest.json \
  --out out/game_sms/work
```

This step:
1. Identifies the NES mapper from `manifest.json`.
2. Constructs a logical bank map: which PRG banks are fixed, which are switched,
   and the CPU address windows (`$8000–$BFFF` / `$C000–$FFFF`).
3. Reads interrupt vectors from the **fixed PRG bank** at CPU `$FFFA–$FFFF` and
   records `NMI_addr`, `RESET_addr`, `IRQ_addr` into `manifest_sms.json`.
4. Outputs `banks.json` (SMS perspective): how to pack NES PRG banks into SMS
   16 KiB Sega-mapper slots, preserving the RESET and vector bank at page 2.
5. Flags unsupported mappers as `UNSPECIFIED` — see **Unknown Mapper Fallback** below.

**SMS Sega Mapper layout target:**

| SMS Slot | Address Range | Register | Content                      |
|----------|---------------|----------|------------------------------|
| Slot 0   | $0000–$3FFF   | $FFFD    | Z80 init + interrupt vectors |
| Slot 1   | $4000–$7FFF   | $FFFE    | Game logic (bankswitched)    |
| Slot 2   | $8000–$BFFF   | $FFFF    | Data / additional code       |
| RAM      | $C000–$DFFF   | —        | Work RAM (mirrored $E000)    |
| Mapper   | $FFFC–$FFFF   | —        | Sega mapper control regs     |

---

### Step 2 — Convert Graphics (CHR → VDP Mode 4 Tiles)

This is fully deterministic. Read `references/hardware_diff.md § Graphics Pipeline`
for the complete bit-layout spec before running.

```bash
python3 scripts/convert_gfx.py convert-gfx \
  --chr out/game_sms/work/chr.bin \
  --prg out/game_sms/work/prg.bin \
  --palette-strategy global-fit \
  --sprite-flip-strategy cache \
  --out out/game_sms/assets
```

**Sub-steps inside `convert-gfx`:**

#### 2a — Palette Mapping (NES 64-color → SMS 2-bit RGB)

1. Collect all NES palette RAM writes from CDL trace / static analysis.
   If no trace exists, use the default NES palette table (`references/nes_palette.pal`).
2. For each unique NES 6-bit color index, find the nearest SMS color using
   RGB Euclidean distance, quantized to `%00BBGGRR` (2 bits per channel, 0–3 each).
3. Build `palette_bg.bin` (16 entries) and `palette_spr.bin` (16 entries).
   - NES BG palettes 0–3 (4 colors each, 16 total) → SMS BG palette (16 slots).
   - NES SPR palettes 0–3 → SMS SPR palette (16 slots).
   - Color index 0 of each NES palette is the universal backdrop/transparent color;
     map to SMS index 0 for BG palette.
4. When total unique colors exceed 16 per palette: merge by nearest-color, duplicate
   tiles to use alternate palette bit, or re-palette per screen zone (configurable).
5. Record all merges and warnings in `reports/conversion_report.md`.

#### 2b — Tile Conversion (2bpp → 4bpp planar)

For each 8×8 tile in `chr.bin` (16 bytes, 2 bitplanes):

```
NES tile row i:  plane0 = chr[i],  plane1 = chr[i+8]
For pixel x in 0..7 (left to right):
  b0 = (plane0 >> (7-x)) & 1
  b1 = (plane1 >> (7-x)) & 1
  nes_idx = (b1 << 1) | b0        # 0..3
  sms_idx = palette_map[nes_idx]  # 0..15

SMS tile row i (4 bytes, bitplanes 0..3):
  For plane in 0..3:
    byte = 0
    for x in 0..7: byte |= ((sms_idx[x] >> plane) & 1) << (7-x)
    sms32[i*4 + plane] = byte
```

Output: `assets/tiles.bin` (each tile = 32 bytes, packed sequentially).

#### 2c — Tilemap Conversion (NES Nametable → SMS Name Table)

1. Extract NES nametable from PPU VRAM trace or static CHR usage patterns.
2. Each NES nametable entry is 1 byte (tile index). Attribute table adds palette/flip
   per 16×16-pixel region (4 tiles share one attribute byte).
3. Each SMS name table entry is **2 bytes**:
   - Bits 8–0: tile index (0–511)
   - Bit 9: horizontal flip
   - Bit 10: vertical flip
   - Bit 11: palette select (0=BG, 1=SPR palette for BG tiles)
   - Bit 12: priority (sprite over/under background)
4. Map NES 32×30 tiles (256×240) to SMS 32×28 (256×192). For the 8 missing rows:
   apply the configured `--layout-policy` (default: `crop-top-8-bottom-10`).
   Record HUD displacement in `conversion_report.md`.
5. Output: `assets/tilemap.bin` (32×28 × 2 bytes = 1792 bytes).

#### 2d — Sprite Flip Cache

NES OAM sprites have per-sprite H/V flip bits. SMS sprites have **no flip bits**.

1. Scan OAM writes in CDL trace or NES disassembly to determine which tiles use flip.
2. For each (tile_id, flip_mask) combination:
   - Generate a new tile variant by mirroring the 4bpp tile data.
   - Insert into the SMS tile bank with a new index.
   - Record `(nes_tile, flip_mask) → sms_tile_index` in `symbol_map.json`.
3. Track VRAM pressure: SMS VRAM is 16 KB. Tile bank at $0000, name table at $3800
   (standard), SAT at $3F00. Maximum ~448 tiles before collision (configurable).
4. If tile count exceeds limit: warn, offer `--dedup-tiles` (hash-based dedup) or
   `--split-screens` (reload tiles per screen boundary).
5. Output: updated `assets/tiles.bin` with flip variants appended.

---

### Step 3 — Convert Audio (APU → PSG SN76489)

Read `references/hardware_diff.md § Audio Conversion` before this step.

```bash
python3 scripts/convert_gfx.py convert-audio \
  --prg out/game_sms/work/prg.bin \
  --trace out/game_sms/work/apu_trace.json \
  --audio-strategy rearrange \
  --out out/game_sms/assets/audio
```

**APU → PSG Channel Mapping (strategy: `rearrange`, recommended):**

| NES APU Channel | PSG Channel    | Notes                                          |
|-----------------|----------------|------------------------------------------------|
| Pulse 1         | Tone 1 ($9F)   | Frequency: `f_psg = 3579545 / (32 * note_hz)` |
| Pulse 2         | Tone 2 ($BF)   | Volume: 4-bit PSG attenuation (0=max, 15=off)  |
| Triangle        | Tone 3 ($DF)   | No volume control → fixed midpoint attenuation |
| Noise           | Noise ($FF)    | Map NES noise period bits to PSG noise mode    |
| DMC (sample)    | **DROPPED**    | Log in report; offer pre-recorded SFX option   |

**APU event extraction:**
1. Collect writes to $4000–$4013 from CDL trace (or static scan of APU write routines).
2. Group by channel; decode frequency registers to Hz, volume/envelope to linear.
3. Output `audio/events.json`: `[{tick, channel, type, freq_hz, volume, envelope}]`.
4. Re-encode for PSG: compute PSG tone word from Hz, attenuation from volume.
5. Output `audio/psg_data.asm`: WLA-DX data tables for a simple PSG driver.

**Audio strategy options:**
- `rearrange` (default): Drop DMC, map triangle to fixed Tone 3, rearrange.
- `simplified`: Only map Pulse 1+2 → Tone 1+2; silence triangle and DMC.
- `stub`: Generate empty PSG stubs with TODO comments for manual implementation.

---

### Step 4 — Generate Z80 Project Scaffold

```bash
python3 scripts/sms_packer.py generate \
  --manifest out/game_sms/work/manifest_sms.json \
  --assets out/game_sms/assets \
  --backend wla-dx \
  --mapper sega \
  --out out/game_sms/build
```

This generates the complete WLA-DX project. Key files:

#### `init.asm` — Z80 Startup Sequence

```asm
.include "link.sms"
.bank 0 slot 0
.org $0000

RESET:
    di                      ; disable interrupts
    im 1                    ; interrupt mode 1 (INT → $0038)
    ld sp, $DFF0            ; stack top (SMS RAM, safe zone)
    call VDP_Init           ; set VDP registers to known state
    call PSG_Init           ; silence all PSG channels
    call ClearVRAM          ; zero all 16 KB VRAM
    call LoadPalettes       ; load palette_bg and palette_spr
    call LoadTiles          ; stream tiles.bin to VRAM $0000
    call LoadTilemap        ; stream tilemap.bin to VRAM $3800
    ei                      ; enable interrupts
    jp  GameMain            ; jump to ported game entry point
```

#### `interrupts.asm` — Interrupt Vectors

```asm
.bank 0 slot 0
.org $0038                  ; Z80 IM 1 INT vector (VBlank / line counter)
INT_Handler:
    push af \ push bc \ push de \ push hl
    in   a, ($BF)           ; read VDP status — REQUIRED to clear interrupt
    ; ---- NES NMI handler body goes here (ported from nes-disasm output) ----
    ; call NES_NMI_Equivalent
    pop hl \ pop de \ pop bc \ pop af
    ei
    reti

.org $0066                  ; Z80 NMI vector (PAUSE button on SMS)
NMI_Handler:
    retn                    ; minimal stub — expand for PAUSE menu
```

#### `hal/vdp.asm` — VDP HAL (replaces NES PPU writes)

Key mappings from NES PPU → SMS VDP:

| NES Operation              | SMS Equivalent                                 |
|----------------------------|------------------------------------------------|
| Write $2000 (PPUCTRL)      | VDP Reg 0 / Reg 1 (NMI enable, sprite size)    |
| Write $2005 (PPUSCROLL) ×2 | VDP Reg 8 (X scroll), Reg 9 (Y scroll)         |
| Write $2006/$2007 (VRAM)   | Write addr to $BF (×2), stream data to $BE     |
| Write $4014 (OAM DMA)      | Build SAT in RAM, then stream to VRAM $3F00    |
| Read $2002 (PPUSTATUS)     | Read $BF (VDP status); check bit 7 for VBlank  |

```asm
VDP_SetRegister:            ; A = reg number, B = value
    ld   c, $BF             ; VDP control port
    out  (c), b             ; data byte first
    ld   a, %10000000
    or   a                  ; set register write flag (bit 7)
    out  (c), a             ; register select byte
    ret

VDP_SetWriteAddress:        ; HL = VRAM address
    ld   a, l
    out  ($BF), a           ; low byte
    ld   a, h
    or   $40                ; set write flag (bits 7:6 = 01)
    out  ($BF), a           ; high byte
    ret
```

#### `link.sms` — Linker Script

```
[OBJECTS]
init.o interrupts.o hal/vdp.o hal/psg.o hal/input.o
hal/mapper.o stubs/game_logic.o

[OUTPUT]
ROM "game.sms" BANKED

[BANKS]
ROMBANKS 4              ; adjust to actual PRG size / 16 KiB

[MAPPING]
; Slot 0: fixed init + vectors
SLOTSIZE $4000
DEFAULTSLOT 0
SLOT 0 $0000
SLOT 1 $4000
SLOT 2 $8000

[RAM]
RAMSIZE  $2000          ; 8 KB RAM at $C000
```

---

### Step 5 — Generate Game Logic Stubs

For each subroutine identified in `symbols.json` (from nes-disasm):

```bash
python3 scripts/sms_packer.py gen-stubs \
  --symbols out/game_sms/work/symbol_map.json \
  --out out/game_sms/build/stubs
```

Each stub becomes a Z80 label with a `TODO` comment referencing the NES address
and annotated disassembly excerpt. Example output:

```asm
; ============================================================
; NES STUB: Bank00_UpdateScroll (NES addr $8042)
; NES disasm: writes $2005 twice for H/V scroll
; SMS equivalent: call SMS_VDP_SetScroll(h_scroll, v_scroll)
; TODO: port this routine manually
; ============================================================
Bank00_UpdateScroll:
    ; NES: LDA scroll_x / STA $2005 / LDA scroll_y / STA $2005
    ld   a, (scroll_x)      ; TODO: map NES ZP → SMS RAM addr
    call VDP_SetScrollX
    ld   a, (scroll_y)
    call VDP_SetScrollY
    ret
```

The stub generator produces stubs for: the RESET routine, the NMI body, the IRQ body,
and every labeled subroutine in `symbols.json`. Stubs reference HAL functions by
default; nothing crashes — the ROM boots to a blank (but valid) screen.

---

### Step 6 — Build the SMS ROM

```bash
cd out/game_sms/build
wla-z80 -o init.o init.asm
wla-z80 -o interrupts.o interrupts.asm
# ... (build each .asm file)
wlalink link.sms game.sms
```

Or use the provided Makefile:

```bash
python3 scripts/sms_packer.py write-makefile --out out/game_sms/build
make -C out/game_sms/build
```

`sms_packer.py` also verifies and patches the SMS header:

| Offset | Field          | Value                                  |
|--------|----------------|----------------------------------------|
| $7FF0  | "TMR SEGA"     | ASCII string (9 bytes)                 |
| $7FFA  | Checksum       | Sum of bytes $0000–$7FEF (little-end.) |
| $7FFC  | Product code   | 0x0000 (homebrew/unlicensed)           |
| $7FFE  | Version        | 0x00                                   |
| $7FFF  | Region/size    | Region nibble + ROM size nibble        |

---

### Step 7 — Test in Emulator

```bash
python3 scripts/sms_packer.py test \
  --rom out/game_sms/build/game.sms \
  --emulator emulicious \
  --assert-vblank \
  --report out/game_sms/validation/test_results.txt
```

Minimum test assertions:

- [ ] ROM boots without crash (PC reaches `GameMain`).
- [ ] INT handler at $0038 reads VDP status port $BF (clears interrupt flag).
- [ ] NMI handler at $0066 returns via `retn`.
- [ ] VRAM layout: name table at $3800, SAT at $3F00 (verify via VRAM dump).
- [ ] Palette registers loaded: first entry of BG palette matches expected color.
- [ ] No infinite loop / hang within 3 seconds of boot (emulator timeout check).

Additional regression tests (record after first working boot):

- Frame hash at checkpoint 1 (title screen), checkpoint 2 (first gameplay frame).
- Input response: press button 1, verify game state change.

---

### Step 8 — Iterate and Document

After the stub-only boot is confirmed:

1. Port game logic routines one by one, starting from `RESET` → `GameMain`.
2. Replace each stub body with Z80 code, using HAL functions (never raw port writes).
3. Run `make && emulicious game.sms` after each function port.
4. Update `reports/conversion_report.md` with each routing ported, decisions made.
5. For complex mapper logic (MMC3 IRQ scanline counter), see
   `references/hardware_diff.md § Mapper Mapping Table`.

---

## Unknown Mapper Fallback

If the NES mapper is not in the supported list:

1. Check `manifest.json` for iNES header pollution (bytes 12–15 non-zero → mask
   upper nibble: `mapper & 0x0F`).
2. Run a dynamic trace in Mesen 2; break on writes to `$8000–$FFFF` to identify
   register scheme.
3. Pattern match:
   - 16 KiB PRG swap + fixed last bank → UxROM profile.
   - Serial bit-banged writes to one register → MMC1 profile.
   - $8000/$A000/$C000/$E000 register writes with IRQ → MMC3 profile.
4. If unclassifiable: generate a flat (no-banking) project with all PRG banks
   concatenated; mark output as `UNSPECIFIED/UNRELIABLE`; note in `conversion_report.md`.

---

## Completion Criteria

A conversion is considered complete at each tier:

**Tier 1 — Port Kit (Minimum Viable)**
- [ ] All NES graphics converted to 4bpp tiles + tilemap + palettes.
- [ ] SMS ROM boots without crash; INT handler correct; VRAM layout correct.
- [ ] All NES subroutines have Z80 stubs; HAL layer covers all PPU/APU/input patterns.
- [ ] `manifest_sms.json` has no critical `UNSPECIFIED` fields.
- [ ] `conversion_report.md` documents all warnings and unmapped patterns.

**Tier 2 — Playable Port**
- [ ] All game logic routines ported from stubs to working Z80 code.
- [ ] Scroll, sprites, and gameplay loop functional.
- [ ] Audio driver producing sound via PSG (even if rearranged).
- [ ] Frame hash regression tests passing at title screen and first level.

**Tier 3 — Full Port**
- [ ] All APU channels mapped; music and SFX subjectively correct.
- [ ] Mapper banking reproduced faithfully via SMS Sega mapper.
- [ ] Tested on real hardware (or cycle-accurate emulator).
- [ ] `validation/test_results.txt` records all pass/fail results.

---

## Reference Files

- `scripts/convert_gfx.py` — Graphics pipeline: CHR→4bpp tiles, palette mapping,
  sprite flip cache, tilemap conversion, APU event extraction.
- `scripts/sms_packer.py` — SMS project generator: init/HAL/stubs scaffolding,
  linker script, SMS header patcher, Makefile writer, emulator test runner.
- `references/hardware_diff.md` — Deep per-subsystem technical reference:
  graphics bit layouts, mapper table (NROM/UxROM/MMC1/MMC3/Sega), VDP register
  map, PSG frequency formula, memory maps for both systems, interrupt sequences.

---

## Quick Reference: SMS Memory Map

```
$0000–$03FF   Z80 interrupt vectors + mapper slot 0 fixed area
$0000–$3FFF   ROM Slot 0  (Sega mapper reg $FFFD)
$4000–$7FFF   ROM Slot 1  (Sega mapper reg $FFFE)
$8000–$BFFF   ROM Slot 2  (Sega mapper reg $FFFF)
$C000–$DFFF   Work RAM (8 KB)
$E000–$FFFF   RAM mirror
$FFFC         Mapper control (RAM bank enable etc.)
$FFFD–$FFFF   ROM bank selects (slots 0–2)

VDP ports:
  $BE   VDP data port (read/write)
  $BF   VDP control port (address / register write; status read)
  $7E   V-counter read
  $7F   H-counter read

PSG port:
  $7F   SN76489 write (tone words and attenuation)

Input ports:
  $DC   Joypad 1 + Joypad 2 (partial)
  $DD   Joypad 2 (remaining) + misc
```

## Quick Reference: SMS VDP VRAM Layout (Standard)

```
$0000–$37FF   Pattern (tile) table (max 448 tiles × 32 bytes)
$3800–$3EFF   Name table (32×28 entries × 2 bytes = 1792 bytes)
$3F00–$3FFF   Sprite Attribute Table (SAT)
              Y positions: $3F00–$3F3F (64 bytes)
              X+tile pairs: $3F40–$3FFF (128 bytes, 2 per sprite)
```
