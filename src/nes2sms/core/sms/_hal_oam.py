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

    ; --- Second pass: write X/tile/attr triplets to SAT $3F80 ---
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

    ; Build attribute byte in advance
    ; SMS format: bit7=priority, bit5=V-flip, bit4=H-flip, bits2-0=palette
    ld   a, $00        ; Start with all zeros

    ; Set palette bits (NES attributes bits 0-1)
    ld   a, e
    and  $03           ; Keep only palette bits
    ld   c, a          ; C = palette bits

    ; Set flip bits
    ld   a, $00        ; Start fresh
    bit  6, e          ; Check H-flip
    jr   z, _oam_no_hflip
    set  4, a          ; Set H-flip bit (SMS bit 4)
_oam_no_hflip:
    bit  7, e          ; Check V-flip
    jr   z, _oam_no_vflip
    set  5, a          ; Set V-flip bit (SMS bit 5)
_oam_no_vflip:
    or   c             ; Combine with palette bits
    ld   c, a          ; C = attribute byte (without priority)

    ; Determine priority bit
    ld   a, $00        ; Default: priority=0 (in front of background)
    bit  5, e          ; Check NES priority bit
    jr   z, _oam_prio_done
    ld   a, c
    cp   {split_y}
    jr   nc, _oam_prio_done
    ld   a, c
    set  7, a          ; Set priority bit (behind background)
_oam_prio_done:
    ld   c, a          ; C = complete attribute byte

    inc  hl            ; X offset +3
    ld   a, (hl)      ; NES X position (offset +3)
    out  ($BE), a      ; write X

    push hl
    call _oam_map_variant_tile
    out  ($BE), a      ; write tile

    ld   a, c          ; Get attribute byte
    out  ($BE), a      ; write attribute byte

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
