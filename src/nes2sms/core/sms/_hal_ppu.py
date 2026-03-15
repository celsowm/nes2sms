"""PPU HAL section generator."""


def generate_ppu_routines() -> str:
    return """
.export hal_ppu_write
.export hal_ppu_read

hal_ppu_write:
    ; A = Value to write
    ; L = Register offset (0-7)
    ld   h, $00
    add  hl, hl  ; hl = offset * 2
    ld   de, _ppu_jump_table
    add  hl, de
    ld   e, (hl)
    inc  hl
    ld   d, (hl)
    push de
    ret

_ppu_jump_table:
    .dw _ppu_2000, _ppu_2001, _ppu_2002, _ppu_2003
    .dw _ppu_2004, _ppu_2005, _ppu_2006, _ppu_2007

_ppu_2000: ; PPUCTRL
    ld   (_ppu_ctrl_shadow), a
    ; Bit 7 = NES NMI enable → SMS VDP reg 1 bit 5 (frame IRQ enable)
    push bc
    ld   b, a
    ld   a, (_vdp_reg1_shadow)
    bit  7, b
    jr   nz, _ppu_2000_nmi_on
    res  5, a
    jr   _ppu_2000_done
_ppu_2000_nmi_on:
    set  5, a
_ppu_2000_done:
    ld   (_vdp_reg1_shadow), a
    ld   b, a
    ld   a, 1
    call VDP_WriteReg
    pop  bc
    ret

_ppu_2005: ; PPUSCROLL
    ; PPUSCROLL uses the same first/second write latch as PPUADDR.
    ; 1st write = X scroll, 2nd write = Y scroll.
    push bc
    ld   b, a
    ld   a, (_ppu_addr_toggle)
    or   a
    jr   nz, _ppu_2005_y
    ; First write: X scroll (invert to match SMS horizontal direction)
    ld   a, b
    ld   (_ppu_scroll_x), a
    cpl
    inc  a
    ld   b, a
    ld   a, 8
    call VDP_WriteReg
    ld   a, $01
    ld   (_ppu_addr_toggle), a
    pop  bc
    ret
_ppu_2005_y:
    ; Second write: Y scroll
    ld   a, b
    ld   (_ppu_scroll_y), a
    ld   b, a
    ld   a, 9
    call VDP_WriteReg
    xor  a
    ld   (_ppu_addr_toggle), a
    pop  bc
    ret

_ppu_2006: ; PPUADDR
    push bc
    ld   b, a
    ld   a, (_ppu_addr_toggle)
    or   a
    jr   nz, _ppu_2006_lo
    ; First write: high byte
    ld   a, b
    ld   (_ppu_addr_hi), a
    ; Enter neutral mode until low byte resolves target range.
    xor  a
    ld   (_ppu_write_mode), a
    ld   a, $01
    ld   (_ppu_addr_toggle), a
    pop  bc
    ret
_ppu_2006_lo:
    ; Second write: low byte
    ld   a, b
    ld   (_ppu_addr_lo), a
    xor  a
    ld   (_ppu_addr_toggle), a
    ; Set up VDP write address based on NES PPU address range
    ld   a, (_ppu_addr_hi)
    cp   $3F
    jr   z, _ppu_2006_palette
    cp   $20
    jr   c, _ppu_2006_chr
    ; Attribute table ranges ($23C0/$27C0/$2BC0/$2FC0) are translated to
    ; SMS name table attribute bytes by _ppu_2007_attribute.
    ld   a, (_ppu_addr_hi)
    and  $03
    cp   $03
    jr   nz, _ppu_2006_nametable
    ld   a, (_ppu_addr_lo)
    cp   $C0
    jr   nc, _ppu_2006_attribute
_ppu_2006_nametable:
    ; Ensure VDP auto-increment = 2 so each tile write advances one SMS cell.
    ld   a, $02
    call _ppu_set_vdp_increment

    ; Nametable range $20xx-$2Fxx -> SMS $3800 + offset
    ; NES addr = ($2000 + offset), SMS addr = ($3800 + offset*2)
    ; For simplicity, set VDP address for nametable writes
    sub  $20
    ld   d, a
    ld   a, (_ppu_addr_lo)
    ld   e, a
    ; DE = NES nametable offset (from $2000)
    ; SMS nametable at $3800, each entry = 2 bytes
    ; SMS addr = $3800 + (DE * 2)
    sla  e
    rl   d
    ld   a, d
    add  a, $38
    ld   d, a
    ; Set VDP write address
    ld   a, e
    out  ($BF), a
    ld   a, d
    or   $40
    out  ($BF), a
    ld   a, $01
    ld   (_ppu_write_mode), a  ; nametable mode
    pop  bc
    ret
_ppu_2006_attribute:
    ld   a, $01
    call _ppu_set_vdp_increment
    ld   a, $03
    ld   (_ppu_write_mode), a  ; attribute table mode
    pop  bc
    ret
_ppu_2006_palette:
    ; Palette writes use byte-wise VDP increment.
    ld   a, $01
    call _ppu_set_vdp_increment
    ; Palette $3F00-$3F1F -> SMS CRAM
    ld   a, (_ppu_addr_lo)
    and  $1F
    ld   e, a
    ld   d, $00
    ; SMS CRAM address = $C000 + offset
    ld   a, e
    out  ($BF), a
    ld   a, $C0
    out  ($BF), a
    ld   a, $02
    ld   (_ppu_write_mode), a  ; palette mode
    pop  bc
    ret
_ppu_2006_chr:
    ; CHR/pattern range $0000-$1FFF
    ; Handle runtime CHR-RAM writes by mapping NES bitplanes to SMS tile planes 0/1.
    ld   a, $01
    call _ppu_set_vdp_increment
    ld   a, $04
    ld   (_ppu_write_mode), a
    pop  bc
    ret

_ppu_2007: ; PPUDATA
    push bc
    push de
    push hl
    ld   b, a
    ld   a, (_ppu_write_mode)
    cp   $02
    jp   z, _ppu_2007_palette
    cp   $03
    jp   z, _ppu_2007_attribute
    cp   $04
    jp   z, _ppu_2007_chr
    cp   $01
    jp   z, _ppu_2007_nametable
    ; Unsupported mode: ignore
    call _ppu_advance_vram_addr
    pop  hl
    pop  de
    pop  bc
    ret
_ppu_2007_palette:
    ; A(saved in B) = NES palette index (0-63)
    ; Convert to SMS color via lookup table
    ld   a, b
    and  $3F
    ld   e, a
    ld   d, $00
    ld   hl, _nes_to_sms_color
    add  hl, de
    ld   a, (hl)
    out  ($BE), a
    call _ppu_advance_vram_addr
    pop  hl
    pop  de
    pop  bc
    ret
_ppu_2007_nametable:
    ; With VDP increment=2, writing only the tile byte updates one SMS cell.
    ; Attribute bytes remain zero (set during clear/init).
    ld   a, b
    out  ($BE), a
    call _ppu_advance_vram_addr
    pop  hl
    pop  de
    pop  bc
    ret
_ppu_2007_attribute:
    ; Expand NES attribute byte into SMS palette bit (entry bit 3) for each 2x2 tile block.
    ; Mapping policy: NES palettes 0/1 -> SMS palette 0, NES palettes 2/3 -> SMS palette 1.
    ld   a, b
    ld   (_ppu_attr_value), a
    ; Compute base nametable entry index from current PPU attribute address.
    ; nametable index (0..3)
    ld   a, (_ppu_addr_hi)
    sub  $20
    and  $0C
    rrca
    rrca
    ld   h, a
    ; attribute index inside table (0..63)
    ld   a, (_ppu_addr_lo)
    and  $3F
    ld   l, a

    ; DE = attr_y*128
    ld   a, l
    and  $38
    ld   e, a
    ld   d, $00
    sla  e
    rl   d
    sla  e
    rl   d
    sla  e
    rl   d
    sla  e
    rl   d
    ; + attr_x*4
    ld   a, l
    and  $07
    add  a, a
    add  a, a
    add  a, e
    ld   e, a
    jr   nc, _ppu_attr_no_xy_carry
    inc  d
_ppu_attr_no_xy_carry:
    ; + nametable*0x400
    ld   a, h
    ld   c, a
    ld   b, $00
    sla  c
    rl   b
    sla  c
    rl   b
    sla  c
    rl   b
    sla  c
    rl   b
    sla  c
    rl   b
    sla  c
    rl   b
    sla  c
    rl   b
    sla  c
    rl   b
    sla  c
    rl   b
    sla  c
    rl   b
    ld   a, e
    add  a, c
    ld   e, a
    ld   a, d
    adc  a, b
    ld   d, a
    ; Convert entry index to VRAM address of attribute byte:
    ; $3800 + entry*2 + 1
    sla  e
    rl   d
    ld   a, e
    add  a, $01
    ld   e, a
    ld   a, d
    adc  a, $38
    ld   d, a
    ; Keep top-left base in HL for quadrant offsets.
    ld   h, d
    ld   l, e

    ; Top-left quadrant (bits 1:0 -> use bit 1 as SMS palette selector)
    ld   a, (_ppu_attr_value)
    and  $02
    sla  a
    sla  a
    call _ppu_attr_write_2x2

    ; Top-right quadrant (bits 3:2 -> use bit 3)
    ld   bc, $0004
    add  hl, bc
    ld   d, h
    ld   e, l
    ld   a, (_ppu_attr_value)
    and  $08
    call _ppu_attr_write_2x2

    ; Bottom-left quadrant (bits 5:4 -> use bit 5)
    ld   bc, $007C
    add  hl, bc
    ld   d, h
    ld   e, l
    ld   a, (_ppu_attr_value)
    and  $20
    srl  a
    srl  a
    call _ppu_attr_write_2x2

    ; Bottom-right quadrant (bits 7:6 -> use bit 7)
    ld   bc, $0004
    add  hl, bc
    ld   d, h
    ld   e, l
    ld   a, (_ppu_attr_value)
    and  $80
    srl  a
    srl  a
    srl  a
    srl  a
    call _ppu_attr_write_2x2

    call _ppu_advance_vram_addr
    pop  hl
    pop  de
    pop  bc
    ret
_ppu_2007_chr:
    ; Runtime CHR write: map NES tile bitplanes directly into SMS tile plane bytes.
    ; NES byte offset inside tile determines destination row/plane.
    ld   a, b
    ld   (_ppu_chr_data), a

    ; DE = current NES PPU address (13-bit in $0000-$1FFF)
    ld   a, (_ppu_addr_hi)
    and  $1F
    ld   d, a
    ld   a, (_ppu_addr_lo)
    ld   e, a

    ; C = byte offset inside tile (0..15)
    ld   a, e
    and  $0F
    ld   c, a

    ; DE = tile index (address >> 4)
    srl  d
    rr   e
    srl  d
    rr   e
    srl  d
    rr   e
    srl  d
    rr   e

    ; B = destination plane (0 or 1), C = row (0..7)
    ld   a, c
    cp   $08
    jr   c, _ppu_chr_plane0
    sub  $08
    ld   c, a
    ld   b, $01
    jr   _ppu_chr_plane_done
_ppu_chr_plane0:
    ld   c, a
    ld   b, $00
_ppu_chr_plane_done:
    ; DE = tile_index * 32
    sla  e
    rl   d
    sla  e
    rl   d
    sla  e
    rl   d
    sla  e
    rl   d
    sla  e
    rl   d

    ; + row * 4
    ld   a, c
    add  a, a
    add  a, a
    add  a, e
    ld   e, a
    jr   nc, _ppu_chr_no_row_carry
    inc  d
_ppu_chr_no_row_carry:
    ; + plane
    ld   a, e
    add  a, b
    ld   e, a
    jr   nc, _ppu_chr_no_plane_carry
    inc  d
_ppu_chr_no_plane_carry:
    ; Write one byte to computed SMS VRAM address
    ld   a, e
    out  ($BF), a
    ld   a, d
    or   $40
    out  ($BF), a
    ld   a, (_ppu_chr_data)
    out  ($BE), a

    call _ppu_advance_vram_addr
    pop  hl
    pop  de
    pop  bc
    ret

_ppu_2001: ; PPUMASK
    ; Bits 3,4 = show BG, show sprites
    ; Map to VDP register 1 bit 6 (display enable)
    push bc
    ld   b, a
    ld   a, (_vdp_reg1_shadow)
    bit  3, b
    jr   nz, _ppu_2001_on
    bit  4, b
    jr   nz, _ppu_2001_on
    ; Display off
    res  6, a
    jr   _ppu_2001_write
_ppu_2001_on:
    set  6, a
_ppu_2001_write:
    ld   (_vdp_reg1_shadow), a
    ld   b, a
    ld   a, 1
    call VDP_WriteReg
    pop  bc
    ret

_ppu_2002: ; PPUSTATUS
_ppu_2003: ; OAMADDR
_ppu_2004: ; OAMDATA
    ret

hal_ppu_read:
    ; L = register offset
    ld   a, l
    cp   2
    jr   z, _ppu_read_status
    xor  a
    ret
_ppu_read_status:
    ; Reading $2002 resets the address latch toggle
    xor  a
    ld   (_ppu_addr_toggle), a
    ; Return VDP status (bit 7 = vblank)
    in   a, ($BF)
    ret

; PPU state variables are absolute WRAM labels from memory.inc (.ENUM $DF00)

_ppu_advance_vram_addr:
    ; Emulate NES internal VRAM increment after each PPUDATA write.
    ; PPUCTRL bit 2 selects increment of 1 (clear) or 32 (set).
    ld   a, (_ppu_ctrl_shadow)
    and  $04
    jr   z, _ppu_addr_inc1
    ld   a, (_ppu_addr_lo)
    add  a, $20
    ld   (_ppu_addr_lo), a
    ret  nc
    ld   a, (_ppu_addr_hi)
    adc  a, $00
    ld   (_ppu_addr_hi), a
    ret
_ppu_addr_inc1:
    ld   a, (_ppu_addr_lo)
    inc  a
    ld   (_ppu_addr_lo), a
    ret  nz
    ld   a, (_ppu_addr_hi)
    inc  a
    ld   (_ppu_addr_hi), a
    ret

_ppu_attr_write_2x2:
    ; A = attribute byte to write (bit3 palette select)
    ; DE = top-left attribute byte address for 2x2 tiles
    ld   b, a
    ld   a, b
    call _ppu_attr_write_cell
    inc  de
    inc  de
    ld   a, b
    call _ppu_attr_write_cell
    ld   h, d
    ld   l, e
    ld   bc, $003E
    add  hl, bc
    ld   d, h
    ld   e, l
    ld   a, b
    call _ppu_attr_write_cell
    inc  de
    inc  de
    ld   a, b
    call _ppu_attr_write_cell
    ret

_ppu_attr_write_cell:
    push af
    ld   a, e
    out  ($BF), a
    ld   a, d
    or   $40
    out  ($BF), a
    pop  af
    out  ($BE), a
    ret

_ppu_set_vdp_increment:
    ; A = desired increment value for VDP register 15.
    ld   c, a
    ld   a, (_vdp_reg15_shadow)
    cp   c
    ret  z
    ld   a, c
    ld   (_vdp_reg15_shadow), a
    push bc
    ld   b, a
    ld   a, 15
    call VDP_WriteReg
    pop  bc
    ret

; NES palette index (0-63) -> SMS color (--BBGGRR)
_nes_to_sms_color:
    ;      0     1     2     3     4     5     6     7     8     9     A     B     C     D     E     F
    .db $15, $02, $06, $0A, $09, $08, $08, $04, $14, $10, $10, $11, $15, $00, $00, $00  ; $00-$0F
    .db $3F, $07, $0B, $2E, $2D, $0D, $1C, $2C, $28, $24, $20, $21, $25, $00, $00, $00  ; $10-$1F
    .db $3F, $0B, $0F, $2F, $2F, $1F, $3D, $3D, $3C, $38, $34, $35, $3A, $15, $00, $00  ; $20-$2F
    .db $3F, $2F, $2F, $3F, $3F, $2B, $3F, $3F, $3E, $3D, $39, $3A, $3F, $2A, $00, $00  ; $30-$3F
"""
