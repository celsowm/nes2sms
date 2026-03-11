"""WLA-DX HAL components."""

import textwrap
from abc import ABC, abstractmethod


class IHalComponent(ABC):
    """Base interface for HAL components."""

    @abstractmethod
    def get_asm(self) -> str:
        """Return the assembly code for the component."""
        pass


class VirtualPpuWlaDx(IHalComponent):
    """Generates Virtual PPU and $2000-$2007 register simulations."""

    def get_asm(self) -> str:
        return (
            self._ppu_ram_def()
            + "\n"
            + self._vdp_core()
            + "\n"
            + self._ppu_io()
            + "\n"
            + self._oam_dma()
        )

    def _ppu_ram_def(self) -> str:
        return textwrap.dedent("""; Virtual PPU State Variables (RAM C000+)
        .ramsection "PPU_STATE_RAM" slot 3
            PPU_CTRL      db    ; $2000 emulation
            PPU_MASK      db    ; $2001 emulation
            PPU_STATUS    db    ; $2002 emulation (bit 7 = VBlank)
            PPU_W_LATCH   db    ; 0 = first write (X or High ADDR), 1 = second write
            PPU_SCROLL_X  db    ; $2005 first write
            PPU_SCROLL_Y  db    ; $2005 second write
            PPU_ADDR_H    db    ; $2006 high byte
            PPU_ADDR_L    db    ; $2006 low byte
            PPU_DATA_BUF  db    ; dummy buffer for $2007 reads
            OAM_ADD       db    ; $2003 addr
            PPU_V_OFFSET  db    ; Vertical letterbox offset (default 24 for centering)
        .ends
        """)

    def _vdp_core(self) -> str:
        return textwrap.dedent("""; SMS VDP Core Utils
        .section "VDP_CORE" FREE
        
        VDP_SetRegister:
            push af
            ld   c, $BF
            out  (c), b                 ; value byte first
            pop  af
            or   $80                    ; register command bit
            out  (c), a                 ; register select
            ret
            
        VDP_WriteReg:
            push af
            ld   c, $BF
            out  (c), b                 ; value byte
            pop  af
            or   $80                    ; register command bit
            out  (c), a                 ; register select
            ret
            
        VDP_Init:
            ld   a, 24
            ld   (PPU_V_OFFSET), a      ; Default 24 centers 192px viewport in 240px
            
            ld   b, VDP_INIT_TABLE_END - VDP_INIT_TABLE
            ld   hl, VDP_INIT_TABLE
            ld   e, 0                   ; register index
        .vdp_init_loop:
            ld   a, (hl)
            ld   c, $BF
            out  (c), a                 ; data byte
            ld   a, $80
            or   e
            out  (c), a                 ; register number
            inc  hl
            inc  e
            djnz .vdp_init_loop
            ret
            
        VDP_INIT_TABLE:
            .db %00100110               ; Reg 0: Mode 4 ON (bit 2), no extra features
            .db %10100000               ; Reg 1: display OFF, VBlank IRQ OFF initially
            .db $FF                     ; Reg 2: name table at $3800
            .db $FF                     ; Reg 3: (ignored in Mode 4, must be $FF)
            .db $FF                     ; Reg 4: (ignored in Mode 4, must be $FF)
            .db $FF                     ; Reg 5: SAT at $3F00
            .db $FB                     ; Reg 6: sprite tiles from $0000
            .db $00                     ; Reg 7: border color index 0
            .db $00                     ; Reg 8: X scroll = 0
            .db $00                     ; Reg 9: Y scroll = 0
            .db $FF                     ; Reg 10: line counter (disabled)
        VDP_INIT_TABLE_END:
            
        ClearVRAM:
            ld   a, $00
            out  ($BF), a
            ld   a, $40
            out  ($BF), a
            ld   hl, $4000
        .clear_loop:
            xor  a
            out  ($BE), a
            dec  hl
            ld   a, h
            or   l
            jr   nz, .clear_loop
            ret
            
        .ends
        """)

    def _ppu_io(self) -> str:
        return textwrap.dedent("""; Emulated NES PPU I/O ($2000 - $2007)
        .section "PPU_IO" FREE
        
        ; $2000 PPUCTRL
        NES_Write2000:
            ld   (PPU_CTRL), a
            ret
            
        ; $2001 PPUMASK
        NES_Write2001:
            ld   (PPU_MASK), a
            ret
            
        ; $2002 PPUSTATUS
        NES_Read2002:
            in   a, ($BF)               ; Read clears native VDP interrupt
            ld   b, a
            ld   a, (PPU_STATUS)
            
            push af
            xor  a
            ld   (PPU_W_LATCH), a
            ld   a, (PPU_STATUS)
            and  %01111111
            ld   (PPU_STATUS), a
            pop  af
            ret
            
        ; $2005 PPUSCROLL
        NES_Write2005:
            push bc
            ld   b, a
            ld   a, (PPU_W_LATCH)
            or   a
            jr   nz, .second_write
        .first_write:
            ld   a, b
            ld   (PPU_SCROLL_X), a
            ld   a, 1
            ld   (PPU_W_LATCH), a
            ; Invert scroll for SMS: SMS_X = 256 - NES_X
            ld   a, 0
            sub  b
            call VDP_SetScrollX
            pop  bc
            ret
        .second_write:
            xor  a
            ld   (PPU_W_LATCH), a
            
            ; SMS_Y = (NES_Y - PPU_V_OFFSET) % 224
            ld   a, b
            ld   c, a
            ld   a, (PPU_V_OFFSET)
            ld   b, a
            ld   a, c
            sub  b
            
            ; TODO: Ensure modulo 224 for stable wrap if needed
            call VDP_SetScrollY
            pop  bc
            ret
            
        VDP_SetScrollX:
            ld   b, a
            ld   a, 8
            call VDP_WriteReg
            ret
        VDP_SetScrollY:
            ld   b, a
            ld   a, 9
            call VDP_WriteReg
            ret
            
        ; $2006 PPUADDR
        NES_Write2006:
            push bc
            ld   b, a
            ld   a, (PPU_W_LATCH)
            or   a
            jr   nz, .second_write
        .first_write:
            ld   a, b
            ld   (PPU_ADDR_H), a
            ld   a, 1
            ld   (PPU_W_LATCH), a
            pop  bc
            ret
        .second_write:
            ld   a, b
            ld   (PPU_ADDR_L), a
            xor  a
            ld   (PPU_W_LATCH), a
            ld   a, b
            out  ($BF), a
            ld   a, (PPU_ADDR_H)
            or   $40
            out  ($BF), a
            pop  bc
            ret
            
        ; $2007 PPUDATA
        NES_Write2007:
            out  ($BE), a
            ret
            
        NES_Read2007:
             in  a, ($BE)
             ret
             
        .ends
        """)

    def _oam_dma(self) -> str:
        return textwrap.dedent("""; OAM DMA ($4014) for VDP SAT
        .section "OAM_DMA" FREE
        
        NES_Write4014:
            push hl
            push de
            push bc
            push af
            
            ld   a, $00
            out  ($BF), a
            ld   a, $7F
            out  ($BF), a
            
            pop  af
            ld   h, a
            ld   l, $00
            ld   b, 64
            
            push hl
        .loop_y:
            ld   a, (hl)
            inc  a
            out  ($BE), a
            inc  hl
            inc  hl
            inc  hl
            inc  hl
            djnz .loop_y
            
            ld   a, $40
            out  ($BF), a
            ld   a, $7F
            out  ($BF), a
            
            pop  hl
            ld   b, 64
        .loop_xt:
            inc  hl
            ld   a, (hl)
            ld   e, a
            inc  hl
            inc  hl
            ld   a, (hl)
            out  ($BE), a
            ld   a, e
            out  ($BE), a
            inc  hl
            djnz .loop_xt
            
            pop  bc
            pop  de
            pop  hl
            ret
            
        .ends
        """)


class WlaDxInputHal(IHalComponent):
    """Generates SMS Input HAL."""

    def get_asm(self) -> str:
        return textwrap.dedent("""; SMS Input HAL
        .section "Input_HAL" FREE
        
        Input_ReadJoypad1:
            in   a, ($DC)
            cpl
            and  $3F
            ret
            
        .define INPUT_UP    %00000001
        .define INPUT_DOWN  %00000010
        .define INPUT_LEFT  %00000100
        .define INPUT_RIGHT %00001000
        .define INPUT_BTN1  %00010000
        .define INPUT_BTN2  %00100000
        
        .ends
        """)


class WlaDxPsgHal(IHalComponent):
    """Generates SMS PSG HAL."""

    def get_asm(self) -> str:
        return textwrap.dedent("""; SMS PSG (SN76489) HAL
        .section "PSG_HAL" FREE
        
        PSG_PORT .equ $7F
        
        PSG_Init:
            ld   a, %10011111
            out  (PSG_PORT), a
            ld   a, %10111111
            out  (PSG_PORT), a
            ld   a, %11011111
            out  (PSG_PORT), a
            ld   a, %11111111
            out  (PSG_PORT), a
            ret
            
        PSG_SetTone:
            ld   a, h
            and  $03
            ld   a, l
            and  $0F
            ld   b, a
            ld   a, d
            rlca \ rlca \ rlca \ rlca \ rlca
            or   %10000000
            or   b
            out  (PSG_PORT), a
            ld   a, l
            rlca \ rlca \ rlca \ rlca
            or   h
            and  $3F
            out  (PSG_PORT), a
            ret
            
        PSG_SetVolume:
            ld   a, d
            rlca \ rlca \ rlca \ rlca \ rlca
            or   %10010000
            ld   b, a
            ld   a, e
            and  $0F
            or   b
            out  (PSG_PORT), a
            ret
            
        .ends
        """)


class WlaDxMapperHal(IHalComponent):
    """Generates SMS Sega Mapper HAL."""

    def get_asm(self) -> str:
        return textwrap.dedent("""; SMS Sega Mapper HAL
        .section "Mapper_HAL" FREE
        
        Mapper_Init:
            ld   a, 0
            ld   ($FFFD), a
            ld   a, 1
            ld   ($FFFE), a
            ld   a, 2
            ld   ($FFFF), a
            ret
            
        Mapper_SetSlot1:
            ld   ($FFFE), a
            ret
            
        Mapper_SetSlot2:
            ld   ($FFFF), a
            ret
            
        .ends
        """)
