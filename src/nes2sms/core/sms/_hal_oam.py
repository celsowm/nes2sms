"""OAM DMA HAL section generator."""


def generate_oam_dma_routine(split_y: int) -> str:
    return f"""
.export hal_oam_dma

hal_oam_dma:
    ; A = NES page number (e.g., $02 for $0200)
    ; Relocated to SMS RAM ($C0+page) automatically
    ; Uploads to SMS VDP SAT at $3F00
    push bc
    push de
    push hl

    add  a, $C0       ; Relocate NES page to SMS RAM
    ld   h, a
    ld   l, $00       ; HL = source page in SMS RAM
    xor  a
    ld   (_oam_prio_top), a
    ld   (_oam_prio_bottom), a

    ; --- First pass: write Y positions to SAT $3F00 ---
    push hl
    ld   a, $00
    out  ($BF), a
    ld   a, $7F       ; $3F00 | $40 (VDP write flag)
    out  ($BF), a

    ld   b, 64
_oam_y_loop:
    ld   a, (hl)      ; NES Y position (offset +0)
    inc  a            ; SMS Y is effectively one scanline lower
    out  ($BE), a
    inc  hl
    inc  hl
    inc  hl
    inc  hl            ; skip 4 bytes to next sprite
    djnz _oam_y_loop

    ; --- Second pass: write X/tile pairs to SAT $3F80 ---
    pop  hl
    ld   a, $80
    out  ($BF), a
    ld   a, $7F       ; $3F80 | $40 (VDP write flag)
    out  ($BF), a

    ld   b, 64
_oam_xt_loop:
    ld   a, (hl)      ; NES Y position (offset +0)
    ld   c, a
    inc  hl            ; tile offset +1
    ld   a, (hl)      ; NES tile index
    ld   d, a
    inc  hl            ; attributes offset +2
    ld   a, (hl)
    ld   e, a
    bit  5, e
    jr   z, _oam_prio_done
    ld   a, c
    cp   {split_y}
    jr   c, _oam_prio_mark_top
    ld   a, $01
    ld   (_oam_prio_bottom), a
    jr   _oam_prio_done
_oam_prio_mark_top:
    ld   a, $01
    ld   (_oam_prio_top), a
_oam_prio_done:
    inc  hl            ; X offset +3
    ld   a, (hl)      ; NES X position (offset +3)
    out  ($BE), a      ; write X
    push hl
    call _oam_map_variant_tile
    out  ($BE), a      ; write tile
    pop  hl
    inc  hl            ; advance to next sprite
    djnz _oam_xt_loop

    pop  hl
    pop  de
    pop  bc
    ret

_oam_map_variant_tile:
    ; D = base tile, E = NES attributes
    ; combo nibble: [V][H][P1][P0]
    ld   a, e
    and  $03
    ld   c, a
    bit  6, e
    jr   z, _oam_combo_h_done
    set  2, c
_oam_combo_h_done:
    bit  7, e
    jr   z, _oam_combo_ready
    set  3, c
_oam_combo_ready:
    ; HL = (D * 16) + C
    ld   a, d
    and  $0F
    add  a, a
    add  a, a
    add  a, a
    add  a, a
    ld   l, a
    ld   a, d
    and  $F0
    rrca
    rrca
    rrca
    rrca
    ld   h, a
    ld   a, l
    add  a, c
    ld   l, a
    jr   nc, _oam_lookup_ready
    inc  h
_oam_lookup_ready:
    ld   de, SpriteVariantMap
    add  hl, de
    ld   a, (hl)
    ret

; OAM state variables are absolute WRAM labels from memory.inc (.ENUM $DF00)
"""
