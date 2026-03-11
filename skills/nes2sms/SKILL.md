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
│   ├── vram_map.txt           ← VRAM layout: tiles base, nametable, # NES → Master System: End-to-End Retargeting Skill

## Pipeline — Step by Step (Using Modular CLI)

The pipeline is now centralized in the `nes2sms` CLI.

### Step 0 — Ingest NES Artifacts
```bash
nes2sms ingest --nes game.nes --out out/game_sms
```

### Step 1 — Analyze NES Mapper
```bash
nes2sms analyze-mapper --manifest out/game_sms/work/manifest_sms.json --out out/game_sms/work
```

### Step 2 — Convert Graphics
```bash
nes2sms convert-gfx --chr out/game_sms/work/chr.bin --prg out/game_sms/work/prg.bin --out out/game_sms/assets
```

### Step 3 — Convert Audio
```bash
nes2sms convert-audio --prg out/game_sms/work/prg.bin --out out/game_sms/assets/audio
```

### Step 4 — Generate Z80 Project
```bash
nes2sms generate --manifest out/game_sms/work/manifest_sms.json --assets out/game_sms/assets --out out/game_sms/build
```

### Step 5 — Translate Assembly (Optional but Recommended)
```bash
nes2sms translate-asm --input out/game_nes/disasm.asm --out out/game_sms/build/stubs
```

### Step 6 — Build ROM
```bash
nes2sms build --dir out/game_sms/build
```

### Step 7 — One-Step Conversion (Alternative)
```bash
nes2sms convert --nes game.nes --out out/game_sms --build --run
```

## Legacy Scripts
> [!IMPORTANT]
> Scripts like `sms_packer.py` and `convert_gfx.py` are deprecated and have been replaced by the `nes2sms` package. Use the CLI commands as documented above.
s and attenuation)

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
