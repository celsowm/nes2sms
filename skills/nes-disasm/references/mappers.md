# Mapper Reference — NES Disassembly Skill

This file documents bank-map rules and register details for the mappers supported
by the `nes-disasm` skill. Claude reads this file when the detected mapper number
matches one of the sections below.

## Table of Contents

- [Mapper 0 — NROM](#mapper-0--nrom)
- [Mapper 1 — MMC1 / SxROM](#mapper-1--mmc1--sxrom)
- [Mapper 2 — UxROM / UNROM](#mapper-2--uxrom--unrom)
- [Mapper 3 — CNROM](#mapper-3--cnrom)
- [Mapper 4 — MMC3 / TxROM](#mapper-4--mmc3--txrom)
- [Mapper 7 — AxROM](#mapper-7--axrom)
- [Mapper 9 — MMC2 / PxROM](#mapper-9--mmc2--pxrom)
- [Mapper 10 — MMC4 / FxROM](#mapper-10--mmc4--fxrom)
- [Mapper 66 — GxROM / GNROM](#mapper-66--gxrom--gnrom)
- [Unknown Mapper Procedure](#unknown-mapper-procedure)

---

## Mapper 0 — NROM

**No bank switching.**

| PRG Size | CPU Layout |
|---|---|
| 16 KiB (NROM-128) | `$8000–$BFFF` = Bank 0; `$C000–$FFFF` = Bank 0 (mirror) |
| 32 KiB (NROM-256) | `$8000–$FFFF` = Bank 0 (linear) |

- CHR: fixed 8 KiB at PPU `$0000–$1FFF` (or CHR-RAM if CHR byte = 0).
- Mirroring: hard-wired from header (horizontal or vertical).
- Vectors: always in the single PRG bank at CPU `$FFFA–$FFFF`.

**CPU → ROM offset formula:**
```
NROM-128: rom_offset = (cpu_addr - $8000) % $4000
NROM-256: rom_offset = cpu_addr - $8000
```

---

## Mapper 1 — MMC1 / SxROM

**Serial shift register, 5 writes to latch a value.**

### Registers (write to `$8000–$FFFF`, bit 7 = reset shift)

| Address Range | Register | Bits | Effect |
|---|---|---|---|
| `$8000–$9FFF` | Control | `[4:0]` | Mirroring (bits 0-1), PRG mode (bits 2-3), CHR mode (bit 4) |
| `$A000–$BFFF` | CHR bank 0 | `[4:0]` | Select CHR bank for lower window |
| `$C000–$DFFF` | CHR bank 1 | `[4:0]` | Select CHR bank for upper window (32 KiB CHR mode: ignored) |
| `$E000–$FFFF` | PRG bank | `[3:0]` | Select 16 KiB PRG bank; bit 4 = PRG-RAM enable |

### PRG Modes (Control bits 3-2)

| Mode | `$8000–$BFFF` | `$C000–$FFFF` |
|---|---|---|
| 0 / 1 | Swap full 32 KiB | Swap full 32 KiB |
| 2 | Fixed to first bank | Switchable |
| 3 (default) | Switchable | Fixed to last bank |

### Mirroring (Control bits 1-0)

| Value | Mirroring |
|---|---|
| 0 | Single-screen (lower) |
| 1 | Single-screen (upper) |
| 2 | Vertical |
| 3 | Horizontal |

**Note:** Shift register resets on any write with bit 7 set. Five consecutive writes
(bit 0 of each) latch the 5-bit value into the targeted register.

---

## Mapper 2 — UxROM / UNROM

**Simple 16 KiB PRG bank switch; last bank fixed.**

- Write to `$8000–$FFFF` selects the 16 KiB PRG bank at `$8000–$BFFF`.
- `$C000–$FFFF` always maps to the **last** PRG bank (fixed).
- CHR: 8 KiB CHR-RAM (no CHR-ROM switching).
- Mirroring: hard-wired from header.

**Bus conflicts warning:** Some UNROM boards have bus conflicts. The correct bank-
select value must be `DATA AND value` when executed from ROM. Check submapper or
board revision if this matters.

**CPU → ROM offset:**
```
$8000–$BFFF: rom_offset = (selected_bank * $4000) + (cpu_addr - $8000)
$C000–$FFFF: rom_offset = (last_bank    * $4000) + (cpu_addr - $C000)
```

---

## Mapper 3 — CNROM

**CHR bank switch only; PRG fixed.**

- PRG: 16 KiB mirrored (or 32 KiB linear) at `$8000–$FFFF`; **no PRG switching**.
- CHR: write to `$8000–$FFFF` selects an 8 KiB CHR bank.
- Mirroring: hard-wired from header.
- Bus conflicts possible (submapper-dependent).

---

## Mapper 4 — MMC3 / TxROM

**Fine-grained PRG + CHR banking with scanline IRQ.**

### Registers

| Address | R/W | Register |
|---|---|---|
| `$8000` (even) | W | Bank Select — bits `[2:0]` select target R0–R7; bit 6 = PRG mode; bit 7 = CHR mode |
| `$8001` (odd)  | W | Bank Data — write value for selected register |
| `$A000` (even) | W | Mirroring — bit 0: 0=vertical, 1=horizontal |
| `$A001` (odd)  | W | PRG-RAM protect |
| `$C000` (even) | W | IRQ latch |
| `$C001` (odd)  | W | IRQ reload |
| `$E000` (even) | W | IRQ disable + acknowledge |
| `$E001` (odd)  | W | IRQ enable |

### Bank registers R0–R7

| Register | Maps to |
|---|---|
| R0, R1 | 2 KiB CHR banks (PPU `$0000` or `$1000` depending on CHR mode bit) |
| R2–R5 | 1 KiB CHR banks |
| R6, R7 | 8 KiB PRG banks at `$8000` / `$A000` |
| Fixed  | Last two 8 KiB PRG banks at `$C000` / `$E000` (or first two in PRG mode 1) |

### IRQ behavior
- Counter decrements on each PPU A12 rising edge (scanline).
- When counter hits 0 and IRQ is enabled → fire CPU IRQ.
- Frequently used for horizontal split-scroll effects.
- **Validate with two emulators** — MMC3 IRQ timing varies between chip revisions
  (MMC3A, MMC3B, MMC6). FCEUX and Mesen 2 differ in edge cases.

---

## Mapper 7 — AxROM

**32 KiB PRG swap + single-screen mirroring select.**

- Write to `$8000–$FFFF`:
  - Bits `[2:0]`: select 32 KiB PRG bank mapped to `$8000–$FFFF`.
  - Bit 4: select single-screen nametable (0 = lower, 1 = upper).
- CHR: 8 KiB CHR-RAM.
- No separate fixed bank — the entire 32 KiB window swaps.

---

## Mapper 9 — MMC2 / PxROM

**Automatic CHR latch switching triggered by PPU tile fetches.**

### PRG Banking
- `$8000–$9FFF`: switchable 8 KiB PRG bank.
- `$A000–$FFFF`: fixed (last three 8 KiB banks).

### CHR Latches
MMC2 maintains two independent 4 KiB CHR latches (latch 0 for `$0000–$0FFF`,
latch 1 for `$1000–$1FFF`). The latch flips automatically when the PPU fetches
tiles with ID `$FD` or `$FE`:

| PPU fetch tile | Latch 0 selects | Latch 1 selects |
|---|---|---|
| Tile `$FD` in `$0xxx` | CHR bank from reg `$B000` | — |
| Tile `$FE` in `$0xxx` | CHR bank from reg `$C000` | — |
| Tile `$FD` in `$1xxx` | — | CHR bank from reg `$D000` |
| Tile `$FE` in `$1xxx` | — | CHR bank from reg `$E000` |

**Modeling requirement:** You must track PPU tile accesses to correctly reconstruct
which CHR bank was active at any point. Static analysis alone is insufficient.

### Registers

| Address | Register |
|---|---|
| `$A000–$AFFF` | PRG bank select |
| `$B000–$BFFF` | CHR latch-0 FD select |
| `$C000–$CFFF` | CHR latch-0 FE select |
| `$D000–$DFFF` | CHR latch-1 FD select |
| `$E000–$EFFF` | CHR latch-1 FE select |
| `$F000–$FFFF` | Mirroring select |

---

## Mapper 10 — MMC4 / FxROM

Functionally similar to MMC2 with these differences:
- PRG: `$8000–$BFFF` is a switchable 16 KiB bank; `$C000–$FFFF` is fixed (last bank).
- CHR latching mechanism is the same FD/FE tile-trigger model as MMC2.
- Some configurations include SRAM at `$6000–$7FFF`.

Refer to the MMC2 latch table above — same register layout for CHR, adjusted PRG
window sizes.

---

## Mapper 66 — GxROM / GNROM

**Simple discrete-logic mapper: PRG 32 KiB + CHR 8 KiB swap via single register.**

- Write to `$8000–$FFFF`:
  - Bits `[5:4]`: select 32 KiB PRG bank.
  - Bits `[1:0]`: select 8 KiB CHR bank.
- Mirroring: hard-wired from header.
- No IRQ, no PRG-RAM.

---

## Unknown Mapper Procedure

When the mapper number is not in the list above:

### 1 — Header Sanity Check
If iNES bytes 12–15 are non-zero, try masking the upper nibble:
```
safe_mapper = mapper & 0x0F
```
If `safe_mapper` matches a known mapper, proceed with a warning.

### 2 — Hash Lookup (requires network)
Compute SHA256, SHA1, CRC32 of the full ROM and search NES ROM databases.
If no match is found, mark mapper as `UNSPECIFIED`.

### 3 — Dynamic Inspection
Run in emulator with breakpoints on writes to `$8000–$FFFF`. Log:
- Write address
- Written value
- PC of the write instruction

Look for patterns of which bits change and which address ranges are targeted.

### 4 — Signature Classification

| Pattern | Likely mapper type |
|---|---|
| PRG swapped in 16 KiB, last bank fixed | UxROM / MMC1-like |
| PRG swapped in 32 KiB | AxROM / GxROM-like |
| Fine PRG + CHR banking + scanline IRQ writes | MMC3-like |
| Serial 5-write protocol | MMC1-like |
| CHR latch behavior on FD/FE tiles | MMC2/MMC4-like |

### 5 — Fallback Output
If classification fails:
- Extract PRG/CHR as raw binary blobs.
- Produce per-bank static disassembly without banking (flat disassembly).
- Mark all ASM output as `; UNSPECIFIED — mapper unknown, banking not modeled`.
- Save dynamic evidence (write logs, traces) in `out/<rom>/logs/`.
