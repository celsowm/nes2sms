---
name: nes-disasm
description: >
  End-to-end disassembly of NES ROM files (.nes). Use this skill whenever the user
  wants to disassemble, reverse-engineer, analyze, or extract data from a NES ROM,
  including header parsing (iNES / NES 2.0), PRG/CHR extraction, mapper modeling,
  bank-switching analysis, interrupt vector recovery, code-vs-data separation,
  symbol labeling, and producing ASM / JSON / HTML outputs with optional bit-perfect
  reassembly validation. Trigger on any mention of NES ROMs, .nes files, 6502
  disassembly, NES reverse engineering, NES mapper analysis, or NES ROM extraction.
---

# NES ROM End-to-End Disassembly

## Legal & Ethics — Read First

- Only disassemble ROMs you own, have explicit permission for, or that are public
  domain / openly licensed (CC0, MIT, etc.).
- Safe to distribute: scripts, symbol files, info files, patches, documentation, hashes.
- Do **not** distribute the ROM itself unless the license explicitly permits it.
- When licensing is uncertain, mark as `UNSPECIFIED` and do not publish.
- Use the CC0 "chase" demo ROM (Internet Archive) for testing and examples.

---

## Prerequisites

| Category | Tool | Notes |
|---|---|---|
| Runtime | `python3 ≥ 3.10` | stdlib only (hashlib, struct, json) |
| Utilities | `dd`, `xxd`/`hexdump`, `sha256sum` | Standard on Linux |
| Disassembler (CLI/tracing) | **retrodisasm** | Supports CDL, `-verify` flag, bank switching (experimental) |
| Disassembler (iterative) | **da65** (cc65 toolchain) | Accepts info files with labels/ranges/segments |
| RE framework | **Ghidra** + **GhidraNes** extension | iNES loader, mapper support; requires JDK 21 |
| Emulator / CDL | **FCEUX** and/or **Mesen 2** | Code/Data Logger, debugger, `.nl` label files |
| Assembler (for verification) | **ca65** + **ld65** (cc65) | Required for `-verify` and bit-perfect reassembly |

> **Note:** `udis86` is an x86/x86-64 disassembler — it does **not** apply to NES 6502 PRG-ROM.

---

## Output Structure

```
out/<rom_name>/
├── manifest.json       ← header metadata + hashes + offsets
├── header.bin
├── trainer.bin         ← only if trainer flag is set
├── prg.bin
├── chr.bin             ← only if CHR-ROM size > 0
├── disasm/
│   ├── bank_00.asm     ← one file per PRG bank
│   └── main.asm        ← top-level .incbin / .include
├── labels/
│   ├── symbols.json    ← name, CPU addr, bank, type, comment
│   └── banks.json      ← window→bank map + known swap events
├── logs/               ← CDL, trace logs, emulator output
└── validation.txt      ← hashes, commands, emulators used
```

---

## Pipeline — Step by Step

### Step 1 — Validate File

```bash
python3 scripts/parse_nes.py <rom.nes> --out out/<rom_name>
```

This script (see `scripts/parse_nes.py`):
1. Reads the 16-byte header and checks magic bytes `NES\x1A`. Abort if invalid.
2. Detects format: **NES 2.0** if `(header[7] & 0x0C) == 0x08`; otherwise **iNES**.
3. Issues a **WARNING** if bytes 12–15 are non-zero on an iNES header (possible
   "DiskDude!" pollution — mapper field may be corrupted; mask upper nibble).
4. Extracts: PRG size, CHR size, trainer flag, battery flag, mirroring, mapper,
   submapper (NES 2.0 only).
5. Writes `manifest.json`, `prg.bin`, `chr.bin`, `header.bin`, `trainer.bin`.

**Size encoding rules:**
- **iNES:** `PRG = byte[4] × 16 KiB`, `CHR = byte[5] × 8 KiB`
- **NES 2.0:** MSB nibble of byte[9]; if nibble is `0x0…0xE` → multiply form;
  if nibble is `0xF` → exponent-multiplier form → mark size as `UNSPECIFIED` (manual
  inspection required).
- If `CHR = 0`, the board uses **CHR-RAM** — there is no `chr.bin`; mark accordingly.

---

### Step 2 — Build the Bank Map

Read `scripts/parse_nes.py` output and consult `references/mappers.md` for the
detected mapper number. For each supported mapper, define:
- How many PRG banks exist and their sizes.
- Which window is fixed at `$C000–$FFFF` (contains reset/interrupt vectors).
- The register write addresses and bit fields that control bank switching.
- The CPU address → ROM offset translation formula per active bank.

**Interrupt vectors** always live at CPU `$FFFA–$FFFF` in the fixed/last PRG bank:

| Address | Vector |
|---|---|
| `$FFFA–$FFFB` | NMI handler (little-endian) |
| `$FFFC–$FFFD` | RESET handler → primary disassembly entry point |
| `$FFFE–$FFFF` | IRQ/BRK handler (shared on NES) |

Read the 3 vectors and create initial labels: `NMI_Handler`, `Reset_Handler`, `IRQ_Handler`.

For unknown mappers, see **Section: Unknown Mapper Fallback** below.

---

### Step 3 — Pre-load Hardware Labels

Before disassembly, define these as fixed symbols:

```
; PPU registers
PPUCTRL   = $2000   PPUMASK   = $2001   PPUSTATUS = $2002
OAMADDR   = $2003   OAMDATA   = $2004   PPUSCROLL = $2005
PPUADDR   = $2006   PPUDATA   = $2007

; APU / I-O
SQ1_VOL   = $4000   ...through...   APU_STATUS = $4015
OAMDMA    = $4014   JOY1      = $4016   JOY2 = $4017
```

This makes xref analysis and I/O heuristics significantly more reliable.

---

### Step 4 — Static Disassembly (First Pass)

For each PRG bank:
1. Set `ORG` to the logical CPU base address (e.g. `$8000` or `$C000`).
2. Perform **recursive disassembly** from all known entry points in this bank.
3. Mark unreached bytes as `DATA` by default.
4. Annotate all writes to mapper register addresses with the register name and
   inferred meaning.

**Recommended command:**
```bash
retrodisasm -o out/<rom>/disasm/game.asm <rom.nes>
```

For da65 (iterative workflow with info file):
```bash
da65 --info game.info prg.bin -o out/<rom>/disasm/game.asm
# Edit game.info to add labels/ranges, then re-run
```

---

### Step 5 — Dynamic Analysis (Second Pass — Recommended)

Run the ROM in an emulator with a **Code/Data Logger (CDL)** to collect real
execution evidence:

```bash
# FCEUX: File → Code/Data Logger → Start/Stop → Save .cdl
# Mesen 2: Debugger → Code/Data Logger → Save

# Re-disassemble using CDL:
retrodisasm -cdl game.cdl -o out/<rom>/disasm/game_cdl.asm <rom.nes>
```

Update code/data boundaries and labels from CDL output. CDL bytes marked as
**executed** are definitively code; bytes marked **read** are definitively data.

---

### Step 6 — Code vs Data Heuristics

Apply in priority order:

1. **CDL executed flag** → code (highest confidence).
2. **Reachability** from entry points via JSR/JMP/branch → probable code.
3. **Pointer table patterns** — sequences of little-endian words pointing into
   `$8000–$FFFF` → probable jump/pointer table (data).
4. **PPU/APU register access** — writes to `$2006/$2007` suggest tile copy routines;
   writes to `$4000–$4017` suggest audio/input routines.
5. **Opcode density** — a long valid opcode sequence is only a weak signal on 6502
   (the instruction set is dense). Do not rely on this alone.

---

### Step 7 — Symbol Labeling Strategy

- **Zero page / WRAM:** label variables as found (e.g. `player_x`, `scroll_y`).
- **Bank namespacing:** prefix labels with bank ID (e.g. `Bank00_Reset`,
  `Bank03_CopyTiles`) to avoid collisions in banked ROMs.
- **Mapper registers:** annotate all writes with register name and deduced effect.
- **IRQ/NMI stubs:** even if handlers are trivial (RTI), keep labels.
- Produce `labels/symbols.json` after each labeling pass.

---

### Step 8 — Generate Outputs

**ASM** (ca65-compatible):
```asm
; main.asm
.include "bank_00.asm"
.include "bank_01.asm"
.incbin "chr.bin"   ; if CHR-ROM exists
```

**JSON artifacts:**
- `manifest.json` — header metadata, hashes, file paths (from Step 1).
- `symbols.json` — `{name, cpu_addr, bank, type, comment}` per label.
- `banks.json` — `{bank_id, prg_offset, cpu_window, known_swap_events}`.

**Annotated HTML (optional):**
```bash
# Using pygments for syntax highlighting:
pygmentize -l asm -f html -O full -o out/<rom>/disasm/game.html out/<rom>/disasm/game.asm
```

---

### Step 9 — Validate

```bash
# Bit-perfect reassembly check (requires ca65/ld65):
retrodisasm -verify -o out/<rom>/disasm/game.asm <rom.nes>

# Manual reassembly + hash comparison:
ca65 out/<rom>/disasm/main.asm -o out/<rom>/rebuilt.o
ld65 out/<rom>/rebuilt.o -t nes -o out/<rom>/rebuilt.nes
sha256sum <rom.nes> out/<rom>/rebuilt.nes

# Record results:
echo "$(date) | original: $(sha256sum <rom.nes>) | rebuilt: $(sha256sum out/<rom>/rebuilt.nes)" \
  >> out/<rom>/validation.txt
```

Run both the original and rebuilt ROM in at least one emulator (two for MMC3/IRQ-sensitive
games). If visual or IRQ behavior diverges, revisit mapper modeling and expand CDL coverage.

---

## Unknown Mapper Fallback

If the mapper is not in the supported list above:

1. **Check for header pollution** — if bytes 12–15 are non-zero and format is iNES,
   mask the upper mapper nibble (`mapper & 0x0F`) and retry.
2. **Hash lookup** — compute SHA256/CRC32 of PRG+CHR and search ROM databases
   (requires network; if unavailable, mark `UNSPECIFIED`).
3. **Dynamic inspection** — run in emulator with breakpoints on writes to
   `$8000–$FFFF`; log address + value patterns to identify register scheme.
4. **Signature classification:**
   - PRG swap in 16 KiB + fixed last bank → UxROM/MMC1-like
   - PRG swap in 32 KiB → AxROM/GxROM-like
   - Scanline IRQ + MMC3-style register writes → MMC3-like
5. **If unclassifiable:** produce raw per-bank static disassembly only (no banking),
   mark all output as `UNSPECIFIED / UNRELIABLE`, and include evidence logs.

---

## Completion Criteria

A disassembly is considered complete when:

- [ ] `manifest.json` has no critical `UNSPECIFIED` fields (unavoidable ones are
  documented).
- [ ] Bank map is fully documented in `banks.json`.
- [ ] NMI / RESET / IRQ vectors identified and labeled.
- [ ] ASM compiles without errors; ideally passes bit-perfect hash check.
- [ ] All PPU, APU, I/O, and mapper register accesses are annotated.
- [ ] Validation results recorded in `validation.txt`.

---

## Reference Files

- `scripts/parse_nes.py` — canonical header parser and extractor (stdlib only).
- `references/mappers.md` — bank map rules and register details for mappers
  0, 1, 2, 3, 4, 7, 9, 10, 66, plus the unknown-mapper procedure.

---

## Quick Reference: NES CPU Memory Map

```
$0000–$07FF   Internal RAM (2 KiB)
$0800–$1FFF   RAM mirrors (×3)
$2000–$2007   PPU registers
$2008–$3FFF   PPU register mirrors
$4000–$4017   APU + I/O
$4018–$401F   APU test (disabled on most consoles)
$4020–$5FFF   Cartridge expansion
$6000–$7FFF   PRG-RAM / Save RAM (if present)
$8000–$FFFF   PRG-ROM + mapper registers (bank-switched)
  $FFFA–$FFFB   NMI vector
  $FFFC–$FFFD   RESET vector
  $FFFE–$FFFF   IRQ/BRK vector
```
