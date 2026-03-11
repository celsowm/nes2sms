#!/usr/bin/env python3
"""
nes2sms/scripts/convert_gfx.py
NES → SMS graphics, palette, tilemap, sprite, and audio conversion pipeline.

Usage:
  python3 convert_gfx.py ingest --nes game.nes [--disasm-dir out/nes] --out work/
  python3 convert_gfx.py analyze-mapper --manifest work/manifest.json --out work/
  python3 convert_gfx.py convert-gfx --chr work/chr.bin --prg work/prg.bin \
          [--palette-strategy global-fit] [--sprite-flip-strategy cache] --out assets/
  python3 convert_gfx.py convert-audio --prg work/prg.bin \
          [--trace work/apu_trace.json] [--audio-strategy rearrange] --out assets/audio/
  python3 convert_gfx.py report --manifest work/manifest_sms.json --out reports/
"""

import sys
import os
import json
import struct
import hashlib
import argparse
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# NES default palette (NTSC approximation, 64 entries, RGB 0–255)
# Based on common .pal reference files for NES hardware.
# ---------------------------------------------------------------------------
NES_PALETTE_RGB = [
    (84,84,84),(0,30,116),(8,16,144),(48,0,136),(68,0,100),(92,0,48),(84,4,0),
    (60,24,0),(32,42,0),(8,58,0),(0,64,0),(0,60,0),(0,50,60),(0,0,0),(0,0,0),
    (0,0,0),(152,150,152),(8,76,196),(48,50,236),(92,30,228),(136,20,176),
    (160,20,100),(152,34,32),(120,60,0),(84,90,0),(40,114,0),(8,124,0),
    (0,118,40),(0,102,120),(0,0,0),(0,0,0),(0,0,0),(236,238,236),(76,154,236),
    (120,124,236),(176,98,236),(228,84,236),(236,88,180),(236,106,100),
    (212,136,32),(160,170,0),(116,196,0),(76,208,32),(56,204,108),(56,180,204),
    (60,60,60),(0,0,0),(0,0,0),(236,238,236),(168,204,236),(188,188,236),
    (212,178,236),(236,174,236),(236,174,212),(236,180,176),(228,196,144),
    (204,210,120),(180,222,120),(168,226,144),(152,226,180),(160,214,228),
    (160,162,160),(0,0,0),(0,0,0),
]


def nes_color_to_sms(nes_idx: int) -> int:
    """Convert NES 6-bit color index to SMS %00BBGGRR byte."""
    r, g, b = NES_PALETTE_RGB[nes_idx & 0x3F]
    rr = round(r / 255 * 3) & 0x3
    gg = round(g / 255 * 3) & 0x3
    bb = round(b / 255 * 3) & 0x3
    return (bb << 4) | (gg << 2) | rr


def rgb_distance(c1, c2):
    return sum((a - b) ** 2 for a, b in zip(c1, c2))


def sms_color_to_rgb(sms_byte: int):
    rr = (sms_byte & 0x03)
    gg = (sms_byte >> 2) & 0x03
    bb = (sms_byte >> 4) & 0x03
    return (rr * 85, gg * 85, bb * 85)


# ---------------------------------------------------------------------------
# NES iNES Header Parser (minimal — use nes-disasm skill for full analysis)
# ---------------------------------------------------------------------------

INES_MAGIC = b'NES\x1a'

def parse_ines_header(data: bytes) -> dict:
    if data[:4] != INES_MAGIC:
        raise ValueError("Not a valid iNES ROM (bad magic bytes).")
    prg_banks = data[4]
    chr_banks = data[5]
    flags6 = data[6]
    flags7 = data[7]
    mapper = (flags7 & 0xF0) | (flags6 >> 4)
    nes2 = (flags7 & 0x0C) == 0x08
    trainer = bool(flags6 & 0x04)
    battery = bool(flags6 & 0x02)
    mirroring = 'vertical' if (flags6 & 0x01) else 'horizontal'
    if flags6 & 0x08:
        mirroring = 'four-screen'
    return {
        'format': 'NES2.0' if nes2 else 'iNES',
        'mapper': mapper,
        'prg_banks': prg_banks,
        'prg_size': prg_banks * 16384,
        'chr_banks': chr_banks,
        'chr_size': chr_banks * 8192,
        'chr_ram': chr_banks == 0,
        'trainer': trainer,
        'battery': battery,
        'mirroring': mirroring,
    }


def extract_sections(data: bytes, hdr: dict) -> tuple:
    offset = 16
    trainer_data = b''
    if hdr['trainer']:
        trainer_data = data[offset:offset + 512]
        offset += 512
    prg = data[offset:offset + hdr['prg_size']]
    offset += hdr['prg_size']
    chr_ = data[offset:offset + hdr['chr_size']] if not hdr['chr_ram'] else b''
    return prg, chr_, trainer_data


def read_vectors(prg: bytes) -> dict:
    """Read interrupt vectors from the last 6 bytes of the last PRG bank."""
    if len(prg) < 6:
        return {}
    tail = prg[-6:]
    nmi  = struct.unpack_from('<H', tail, 0)[0]
    rst  = struct.unpack_from('<H', tail, 2)[0]
    irq  = struct.unpack_from('<H', tail, 4)[0]
    return {'nmi': f'${nmi:04X}', 'reset': f'${rst:04X}', 'irq': f'${irq:04X}'}


# ---------------------------------------------------------------------------
# Tile Conversion: NES 2bpp → SMS 4bpp
# ---------------------------------------------------------------------------

def nes_tile_to_sms(chr16: bytes, color_map: list) -> bytes:
    """
    chr16: 16-byte NES tile (plane0 = bytes 0..7, plane1 = bytes 8..15)
    color_map: list of 4 ints mapping NES color index (0..3) → SMS index (0..15)
    Returns: 32-byte SMS Mode 4 tile
    """
    sms32 = bytearray(32)
    for row in range(8):
        plane0 = chr16[row]
        plane1 = chr16[row + 8]
        pixels = []
        for x in range(8):
            b0 = (plane0 >> (7 - x)) & 1
            b1 = (plane1 >> (7 - x)) & 1
            nes_idx = (b1 << 1) | b0
            pixels.append(color_map[nes_idx])
        for plane in range(4):
            byte = 0
            for x in range(8):
                byte |= ((pixels[x] >> plane) & 1) << (7 - x)
            sms32[row * 4 + plane] = byte
    return bytes(sms32)


def flip_tile_h(tile32: bytes) -> bytes:
    """Flip 32-byte SMS tile horizontally (reverse bit order in each byte)."""
    out = bytearray(32)
    for i, b in enumerate(tile32):
        out[i] = int(f'{b:08b}'[::-1], 2)
    return bytes(out)


def flip_tile_v(tile32: bytes) -> bytes:
    """Flip 32-byte SMS tile vertically (reverse row order)."""
    out = bytearray(32)
    for row in range(8):
        for plane in range(4):
            out[row * 4 + plane] = tile32[(7 - row) * 4 + plane]
    return bytes(out)


# ---------------------------------------------------------------------------
# Palette Building
# ---------------------------------------------------------------------------

def build_sms_palette(nes_palette_ram: list, slot: str) -> tuple:
    """
    Build 16-entry SMS palette from NES palette RAM values.
    nes_palette_ram: 16 NES 6-bit color indices
    slot: 'bg' or 'spr'
    Returns: (palette_bytes: bytes[16], color_map: list[4×palette][4])
    """
    sms_palette = bytearray(16)
    for i, nes_color in enumerate(nes_palette_ram[:16]):
        sms_palette[i] = nes_color_to_sms(nes_color)

    # Build color_map per-palette (4 palettes × 4 colors)
    # NES BG palette layout: [backdrop, pal0c1, pal0c2, pal0c3, backdrop, pal1c1, ...]
    color_maps = []
    for pal in range(4):
        cm = [0] * 4
        for c in range(4):
            nes_idx = nes_palette_ram[pal * 4 + c] if (pal * 4 + c) < 16 else 0
            # Find nearest SMS palette slot
            sms_col = nes_color_to_sms(nes_idx)
            best = 0
            best_dist = float('inf')
            for j in range(16):
                d = rgb_distance(sms_color_to_rgb(sms_palette[j]),
                                 sms_color_to_rgb(sms_col))
                if d < best_dist:
                    best_dist = d
                    best = j
            cm[c] = best
        color_maps.append(cm)
    return bytes(sms_palette), color_maps


# ---------------------------------------------------------------------------
# Full CHR Conversion
# ---------------------------------------------------------------------------

def convert_chr_bank(chr_data: bytes, color_maps: list, flip_strategy: str):
    """
    Convert all tiles in chr_data to SMS 4bpp format.
    color_maps: list of color_map arrays (one per NES palette)
    flip_strategy: 'cache' | 'none'

    Returns:
      sms_tiles: list of 32-byte tile bytes
      flip_index: dict mapping (nes_tile_id, nes_palette, flip_mask) → sms_tile_id
      warnings: list of warning strings
    """
    n_tiles = len(chr_data) // 16
    sms_tiles = []
    tile_to_id = {}  # bytes -> id
    flip_index = {}
    warnings = []

    def get_or_add_tile(tile_bytes):
        if tile_bytes in tile_to_id:
            return tile_to_id[tile_bytes]
        new_id = len(sms_tiles)
        sms_tiles.append(tile_bytes)
        tile_to_id[tile_bytes] = new_id
        return new_id

    for tile_id in range(n_tiles):
        chr16 = chr_data[tile_id * 16:(tile_id + 1) * 16]
        for pal_id, cm in enumerate(color_maps):
            sms_tile = nes_tile_to_sms(chr16, cm)
            
            sms_id = get_or_add_tile(sms_tile)
            flip_index[(tile_id, pal_id, 0)] = sms_id  # no flip

            if flip_strategy == 'cache':
                h_tile = flip_tile_h(sms_tile)
                v_tile = flip_tile_v(sms_tile)
                hv_tile = flip_tile_v(h_tile)
                flip_index[(tile_id, pal_id, 1)] = get_or_add_tile(h_tile)
                flip_index[(tile_id, pal_id, 2)] = get_or_add_tile(v_tile)
                flip_index[(tile_id, pal_id, 3)] = get_or_add_tile(hv_tile)

    print(f"[convert-gfx] De-duped tiles: {n_tiles * len(color_maps) * (4 if flip_strategy == 'cache' else 1)} raw -> {len(sms_tiles)} unique")

    total_vram = len(sms_tiles) * 32
    if total_vram > 14336:  # $3800 - $0000 = 14 KB safe tile area
        warnings.append(
            f"VRAM WARNING: {len(sms_tiles)} tiles × 32 bytes = {total_vram} bytes "
            f"exceeds safe tile area (14 KB). Consider --no-flip-cache or tile dedup."
        )
    return sms_tiles, flip_index, warnings


# ---------------------------------------------------------------------------
# Audio: APU event extraction (static scan, heuristic)
# ---------------------------------------------------------------------------

APU_REGS = {
    0x4000: ('pulse1', 'vol_duty'),   0x4001: ('pulse1', 'sweep'),
    0x4002: ('pulse1', 'period_lo'),  0x4003: ('pulse1', 'period_hi'),
    0x4004: ('pulse2', 'vol_duty'),   0x4005: ('pulse2', 'sweep'),
    0x4006: ('pulse2', 'period_lo'),  0x4007: ('pulse2', 'period_hi'),
    0x4008: ('triangle', 'linear'),   0x400A: ('triangle', 'period_lo'),
    0x400B: ('triangle', 'period_hi'),0x400C: ('noise', 'vol'),
    0x400E: ('noise', 'period'),      0x400F: ('noise', 'length'),
    0x4010: ('dmc', 'flags'),         0x4011: ('dmc', 'direct'),
    0x4012: ('dmc', 'addr'),          0x4013: ('dmc', 'length'),
    0x4015: ('apu', 'status'),
}

NES_CLOCK_NTSC = 1789773

def period_to_hz_pulse(period: int) -> float:
    if period == 0:
        return 0.0
    return NES_CLOCK_NTSC / (16.0 * (period + 1))

def period_to_hz_triangle(period: int) -> float:
    if period == 0:
        return 0.0
    return NES_CLOCK_NTSC / (32.0 * (period + 1))

def hz_to_psg_period(hz: float) -> int:
    SMS_CLOCK = 3579545
    if hz <= 0:
        return 0
    period = round(SMS_CLOCK / (32.0 * hz))
    return max(0, min(1023, period))

def scan_apu_writes(prg_data: bytes) -> list:
    """
    Heuristic static scan for APU write patterns (STA abs addressing: $8D opcode).
    Returns list of {offset, channel, reg_name, value_context}.
    NOTE: This is a heuristic. CDL trace results are more reliable.
    """
    events = []
    i = 0
    while i < len(prg_data) - 2:
        opcode = prg_data[i]
        if opcode == 0x8D:  # STA absolute
            addr = prg_data[i+1] | (prg_data[i+2] << 8)
            if addr in APU_REGS:
                channel, reg = APU_REGS[addr]
                events.append({
                    'prg_offset': i,
                    'cpu_addr': f'${addr:04X}',
                    'channel': channel,
                    'register': reg,
                    'note': 'static_scan_heuristic',
                })
        i += 1
    return events


def build_psg_data_asm(events: list, strategy: str) -> str:
    """Generate WLA-DX PSG data stub from extracted APU events."""
    lines = [
        '; PSG audio data generated by nes2sms convert_gfx.py',
        f'; Strategy: {strategy}',
        '; Channels: Tone1=Pulse1, Tone2=Pulse2, Tone3=Triangle, Noise=Noise',
        '; DMC: DROPPED (no PSG equivalent)',
        '',
        '.section "PSGData" FREE',
        '',
        'PSG_SilenceAll:',
        '    ld   a, %10011111  ; Tone1 attenuation = 15 (silent)',
        '    out  ($7F), a',
        '    ld   a, %10111111  ; Tone2 attenuation = 15',
        '    out  ($7F), a',
        '    ld   a, %11011111  ; Tone3 attenuation = 15',
        '    out  ($7F), a',
        '    ld   a, %11111111  ; Noise attenuation = 15',
        '    out  ($7F), a',
        '    ret',
        '',
        '; TODO: Implement music driver using events.json data',
        '; Reference: references/hardware_diff.md § Audio Conversion',
        '',
    ]
    if strategy == 'stub':
        lines += [
            'PSG_Init:',
            '    call PSG_SilenceAll',
            '    ret',
            '',
            'PSG_Update:',
            '    ; TODO: port NES music driver logic here',
            '    ret',
        ]
    lines.append('')
    lines.append('.ends')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# SMS Manifest Builder
# ---------------------------------------------------------------------------

def build_sms_manifest(nes_manifest: dict, hdr: dict, vectors: dict,
                       chr_tile_count: int, warnings: list) -> dict:
    return {
        'source_manifest': nes_manifest,
        'nes_header': hdr,
        'vectors': vectors,
        'conversion_state': {
            'ingest': 'DONE',
            'analyze_mapper': 'PENDING',
            'convert_gfx': 'PENDING',
            'convert_audio': 'PENDING',
            'generate_scaffold': 'PENDING',
            'build': 'PENDING',
            'test': 'PENDING',
        },
        'sms_assets': {
            'tile_count': chr_tile_count,
            'vram_tiles_bytes': chr_tile_count * 32,
            'palette_bg': 'assets/palette_bg.bin',
            'palette_spr': 'assets/palette_spr.bin',
            'tiles': 'assets/tiles.bin',
            'tilemap': 'assets/tilemap.bin',
        },
        'warnings': warnings,
        'tool': 'nes2sms/scripts/convert_gfx.py',
    }


# ---------------------------------------------------------------------------
# CLI Subcommands
# ---------------------------------------------------------------------------

def cmd_ingest(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    nes_path = Path(args.nes)
    if not nes_path.exists():
        print(f"ERROR: {nes_path} not found.", file=sys.stderr); sys.exit(1)

    data = nes_path.read_bytes()
    hdr = parse_ines_header(data)
    prg, chr_, trainer = extract_sections(data, hdr)
    vectors = read_vectors(prg)

    (out / 'prg.bin').write_bytes(prg)
    if chr_:
        (out / 'chr.bin').write_bytes(chr_)
    if trainer:
        (out / 'trainer.bin').write_bytes(trainer)

    # Try to copy nes-disasm artifacts
    nes_manifest = {}
    if args.disasm_dir:
        d = Path(args.disasm_dir)
        for f in ['manifest.json', 'symbols.json', 'banks.json']:
            if (d / f).exists():
                shutil.copy(d / f, out / f)
        mf = d / 'manifest.json'
        if mf.exists():
            nes_manifest = json.loads(mf.read_text())

    sha = hashlib.sha256(data).hexdigest()
    sms_manifest = build_sms_manifest(nes_manifest, hdr, vectors,
                                      len(chr_) // 16 if chr_ else 0, [])
    sms_manifest['source_hash_sha256'] = sha
    (out / 'manifest_sms.json').write_text(json.dumps(sms_manifest, indent=2), encoding='utf-8')

    print(f"[ingest] OK — PRG {len(prg)//1024}KB | CHR {len(chr_)//1024}KB "
          f"| mapper {hdr['mapper']} | vectors {vectors}")
    print(f"[ingest] Wrote to {out}/")


def cmd_convert_gfx(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    chr_path = Path(args.chr)
    if not chr_path.exists():
        print(f"ERROR: {chr_path} not found.", file=sys.stderr); sys.exit(1)

    chr_data = chr_path.read_bytes()

    # Build default NES palettes (4 BG + 4 SPR, 4 colors each)
    # In absence of a trace, use default colors from the NES palette
    default_nes_bg_ram  = [0x0F, 0x01, 0x11, 0x21,
                            0x0F, 0x06, 0x16, 0x26,
                            0x0F, 0x09, 0x19, 0x29,
                            0x0F, 0x0C, 0x1C, 0x2C]
    default_nes_spr_ram = [0x0F, 0x16, 0x27, 0x38,
                            0x0F, 0x02, 0x12, 0x22,
                            0x0F, 0x05, 0x15, 0x25,
                            0x0F, 0x0A, 0x1A, 0x2A]

    palette_bg_bytes,  color_maps_bg  = build_sms_palette(default_nes_bg_ram,  'bg')
    palette_spr_bytes, color_maps_spr = build_sms_palette(default_nes_spr_ram, 'spr')

    flip_strategy = args.sprite_flip_strategy if hasattr(args, 'sprite_flip_strategy') else 'cache'
    sms_tiles, flip_index, warnings = convert_chr_bank(chr_data, color_maps_bg, flip_strategy)

    # Write outputs
    (out / 'palette_bg.bin').write_bytes(palette_bg_bytes)
    (out / 'palette_spr.bin').write_bytes(palette_spr_bytes)
    tiles_bin = b''.join(sms_tiles)
    (out / 'tiles.bin').write_bytes(tiles_bin)

    # Write flip index as JSON for stub generator
    serializable_flip = {str(k): v for k, v in flip_index.items()}
    (out / 'flip_index.json').write_text(json.dumps(serializable_flip, indent=2), encoding='utf-8')

    for w in warnings:
        print(f"[convert-gfx] WARNING: {w}")

    print(f"[convert-gfx] {len(sms_tiles)} SMS tiles | "
          f"{len(tiles_bin)//1024}KB tiles.bin | "
          f"palettes: palette_bg.bin + palette_spr.bin")
    print(f"[convert-gfx] NOTE: tilemap requires PPU trace or manual nametable dump.")


def cmd_convert_audio(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    prg_data = Path(args.prg).read_bytes()
    strategy = args.audio_strategy if hasattr(args, 'audio_strategy') else 'rearrange'

    # Try to load trace if provided
    events = []
    if hasattr(args, 'trace') and args.trace and Path(args.trace).exists():
        events = json.loads(Path(args.trace).read_text())
        print(f"[convert-audio] Loaded {len(events)} events from trace.")
    else:
        events = scan_apu_writes(prg_data)
        print(f"[convert-audio] No trace provided; heuristic scan found "
              f"{len(events)} APU write patterns (may be incomplete).")

    dmc_count = sum(1 for e in events if e.get('channel') == 'dmc')
    if dmc_count > 0:
        print(f"[convert-audio] WARNING: {dmc_count} DMC events found. "
              f"DMC will be DROPPED (strategy='{strategy}'). "
              f"See conversion_report.md for details.")

    (out / 'events.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
    psg_asm = build_psg_data_asm(events, strategy)
    (out / 'psg_data.asm').write_text(psg_asm, encoding='utf-8')

    print(f"[convert-audio] Wrote events.json ({len(events)} events) "
          f"and psg_data.asm to {out}/")


def cmd_report(args):
    manifest = json.loads(Path(args.manifest).read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    lines = [
        '# NES → SMS Conversion Report',
        '',
        f"## Source ROM",
        f"- SHA256: {manifest.get('source_hash_sha256', 'unknown')}",
        f"- Mapper: {manifest.get('nes_header', {}).get('mapper', '?')}",
        f"- PRG: {manifest.get('nes_header', {}).get('prg_size', 0) // 1024} KB",
        f"- CHR: {manifest.get('nes_header', {}).get('chr_size', 0) // 1024} KB "
              f"({'CHR-RAM' if manifest.get('nes_header', {}).get('chr_ram') else 'CHR-ROM'})",
        '',
        '## Interrupt Vectors (NES)',
        f"- NMI:   {manifest.get('vectors', {}).get('nmi', 'unknown')}",
        f"- RESET: {manifest.get('vectors', {}).get('reset', 'unknown')}",
        f"- IRQ:   {manifest.get('vectors', {}).get('irq', 'unknown')}",
        '',
        '## Conversion State',
    ]
    for step, state in manifest.get('conversion_state', {}).items():
        icon = '✓' if state == 'DONE' else ('⚠' if state == 'UNSPECIFIED' else '○')
        lines.append(f"- {icon} {step}: {state}")

    lines += ['', '## Warnings']
    for w in manifest.get('warnings', []):
        lines.append(f"- ⚠ {w}")
    if not manifest.get('warnings'):
        lines.append('- None')

    lines += [
        '',
        '## Asset Summary',
        f"- SMS tiles: {manifest.get('sms_assets', {}).get('tile_count', 0)} "
              f"({manifest.get('sms_assets', {}).get('vram_tiles_bytes', 0)} bytes)",
        '',
        '## TODO / Manual Steps Required',
        '- [ ] Port game logic routines from NES ASM stubs to Z80',
        '- [ ] Verify tilemap (requires PPU trace or nametable dump)',
        '- [ ] Port music driver to PSG (see assets/audio/psg_data.asm)',
        '- [ ] Map NES ZP variables to SMS RAM addresses',
        '- [ ] Test in Emulicious / MEKA',
    ]

    (out / 'conversion_report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f"[report] Wrote conversion_report.md to {out}/")


def cmd_analyze_mapper(args):
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found.", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    nes_hdr = manifest.get('nes_header', {})
    mapper = nes_hdr.get('mapper', -1)
    prg_size = nes_hdr.get('prg_size', 0)
    prg_banks = prg_size // 16384

    # Generate banks.json logically mapping NES PRG to SMS Sega Mapper Slots
    banks = {
        'mapper_id': mapper,
        'prg_size_kb': prg_size // 1024,
        'slots': []
    }

    if mapper == 0 or mapper == 3:  # NROM / CNROM (Fixed PRG)
        banks['strategy'] = 'linear'
        for i in range(prg_banks):
            banks['slots'].append({'sms_bank': i, 'nes_bank': i, 'fixed': True})
    elif mapper == 1:  # MMC1
        banks['strategy'] = 'sega_mapper'
        for i in range(prg_banks):
            banks['slots'].append({'sms_bank': i, 'nes_bank': i, 'fixed': (i == prg_banks - 1)})
    elif mapper == 2:  # UxROM
        banks['strategy'] = 'sega_mapper'
        for i in range(prg_banks):
            # UXRom: last bank is fixed to $C000-$FFFF, but SMS needs it at $0000-$3FFF (slot 0) along with vectors.
            # We map NES last bank (vectors) to SMS slot 0.
            # NES bank i to SMS bank i.
            banks['slots'].append({'sms_bank': i, 'nes_bank': i, 'fixed': (i == prg_banks - 1)})
    elif mapper == 4:  # MMC3
        banks['strategy'] = 'mmc3_advanced'
        for i in range(prg_banks):
            banks['slots'].append({'sms_bank': i, 'nes_bank': i, 'fixed': False})
        manifest.setdefault('warnings', []).append('MMC3 bank switching requires advanced Z80 interrupt translations.')
    else:
        banks['strategy'] = 'unsupported'
        manifest.setdefault('warnings', []).append(f'Unsupported mapper {mapper}. Generated flat export.')
        for i in range(prg_banks):
            banks['slots'].append({'sms_bank': i, 'nes_bank': i, 'fixed': False})

    (out / 'banks.json').write_text(json.dumps(banks, indent=2), encoding='utf-8')

    if 'conversion_state' in manifest:
        manifest['conversion_state']['analyze_mapper'] = 'DONE'

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    
    print(f"[analyze-mapper] Mapper {mapper} detected. Wrote {len(banks['slots'])} banks to banks.json.")

def main():
    parser = argparse.ArgumentParser(
        description='NES → SMS Graphics & Audio Conversion Pipeline')
    sub = parser.add_subparsers(dest='cmd')

    p_ingest = sub.add_parser('ingest')
    p_ingest.add_argument('--nes', required=True)
    p_ingest.add_argument('--disasm-dir', default=None)
    p_ingest.add_argument('--out', required=True)

    p_gfx = sub.add_parser('convert-gfx')
    p_gfx.add_argument('--chr', required=True)
    p_gfx.add_argument('--prg', required=True)
    p_gfx.add_argument('--palette-strategy', default='global-fit')
    p_gfx.add_argument('--sprite-flip-strategy', default='cache',
                       choices=['cache', 'none'])
    p_gfx.add_argument('--out', required=True)

    p_audio = sub.add_parser('convert-audio')
    p_audio.add_argument('--prg', required=True)
    p_audio.add_argument('--trace', default=None)
    p_audio.add_argument('--audio-strategy', default='rearrange',
                         choices=['rearrange', 'simplified', 'stub'])
    p_audio.add_argument('--out', required=True)

    p_am = sub.add_parser('analyze-mapper')
    p_am.add_argument('--manifest', required=True)
    p_am.add_argument('--out', required=True)

    p_rpt = sub.add_parser('report')
    p_rpt.add_argument('--manifest', required=True)
    p_rpt.add_argument('--out', required=True)

    args = parser.parse_args()
    if args.cmd == 'ingest':
        cmd_ingest(args)
    elif args.cmd == 'convert-gfx':
        cmd_convert_gfx(args)
    elif args.cmd == 'convert-audio':
        cmd_convert_audio(args)
    elif args.cmd == 'analyze-mapper':
        cmd_analyze_mapper(args)
    elif args.cmd == 'report':
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
