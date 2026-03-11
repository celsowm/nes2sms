from . import IHalComponent
import textwrap

class VirtualPpuWlaDx(IHalComponent):
    """
    Generates the Virtual PPU tracking state and $2000-$2007 register simulations for WLA-DX.
    """
    def get_asm(self) -> str:
        return self._ppu_ram_def() + "\n" + self._vdp_core() + "\n" + self._ppu_io() + "\n" + self._oam_dma()

    def _ppu_ram_def(self) -> str:
        return textwrap.dedent("""; Virtual PPU State Variables (RAM C000+)
        .ramsection \"PPU_STATE_RAM\" slot 2
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
        .ends
        """)

    def _vdp_core(self) -> str:
        return textwrap.dedent("""; SMS VDP Core Utils
        .section \"VDP_CORE\" FREE
        
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
        .section \"PPU_IO\" FREE
        
        ; $2000 PPUCTRL
        NES_Write2000:
            ld   (PPU_CTRL), a
            ; Extrair base do nametable e sprite size (TODO futuramente)
            ret
            
        ; $2001 PPUMASK
        NES_Write2001:
            ld   (PPU_MASK), a
            ; Controla display ON/OFF traduzindo para VDP Reg 1
            ; Simplificado: se (A & $18), liga o Reg 1
            ret
            
        ; $2002 PPUSTATUS
        NES_Read2002:
            in   a, ($BF)               ; Ler limpa interrupt do VDP nativo
            ld   b, a                   ; Fazer backup para caso precise processar bit 5 ou 6
            ld   a, (PPU_STATUS)
            
            ; Limpar W _após_ ler
            push af
            xor  a
            ld   (PPU_W_LATCH), a
            ; Limpar VBlank no status
            ld   a, (PPU_STATUS)
            and  %01111111
            ld   (PPU_STATUS), a
            
            pop  af                     ; retorna o valor COM VBlank setado (se estivesse) no A
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
            ; Inverter scroll para SMS
            ld   a, 0
            sub  b
            call VDP_SetScrollX
            pop  bc
            ret
        .second_write:
            ld   a, b
            ld   (PPU_SCROLL_Y), a
            xor  a
            ld   (PPU_W_LATCH), a
            ld   a, b
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
            ; Configurar write addr do VDP usando o H e L combinados
            ld   a, b
            out  ($BF), a
            ld   a, (PPU_ADDR_H)
            ; Necessário transladar de $2000 NES -> $3800 SMS nametable ou CHR RAM
            ; Simplifição (assume VRAM direta por enquanto)
            or   $40
            out  ($BF), a
            pop  bc
            ret
            
        ; $2007 PPUDATA
        NES_Write2007:
            out  ($BE), a
            ; Incrementar PPU_ADDR (TODO: base PPU_CTRL bit 2: +1 ou +32)
            ret
            
        ; $2007 Ler
        NES_Read2007:
            ; Delay de 1 read (TODO)
             in  a, ($BE)
             ret
             
        .ends
        """)

    def _oam_dma(self) -> str:
        return textwrap.dedent("""; OAM DMA ($4014) para VDP SAT
        .section \"OAM_DMA\" FREE
        
        ; $4014 OAMDMA
        ; Entrada: A = High byte of memory page (e.g., $02)
        NES_Write4014:
            push hl
            push de
            push bc
            push af
            
            ; 1. Set VDP write address para SAT Y Table ($3F00)
            ld   a, $00
            out  ($BF), a
            ld   a, $7F                 ; $3F | $40
            out  ($BF), a
            
            ; Preparar loop leitura página ram
            pop  af                     ; Recupera hi byte RAM
            ld   h, a
            ld   l, $00                 ; HL = $yy00 (início sprites NES)
            ld   b, 64                  ; 64 sprites
            
            ; 2. Copiar Y coordinates (cada 4 bytes do NES)
            push hl
        .loop_y:
            ld   a, (hl)                ; Ler Y NES
            inc  a                      ; SMS Y = NES Y + 1 (evita clipping)
            out  ($BE), a               ; Salva ST Y
            inc  hl
            inc  hl
            inc  hl
            inc  hl                     ; Pular Pulo Index, Attr, X
            djnz .loop_y
            
            ; 3. Copiar X e Tile Index ($3F40)
            ld   a, $40
            out  ($BF), a
            ld   a, $7F
            out  ($BF), a
            
            pop  hl                     ; Volta início ram sprites
            ld   b, 64
        .loop_xt:
            inc  hl                     ; Pula Y
            ld   a, (hl)                ; Ler Tile Index
            ld   e, a                   ; Salva em E
            inc  hl                     ; Pula Tile Index
            inc  hl                     ; Pula Attr (ignora flip/palette agora)
            ld   a, (hl)                ; Ler X
            out  ($BE), a               ; Escreve X (SMS VDP usa X dps Tile)
            ld   a, e
            out  ($BE), a               ; Escreve Tile Index nativo
            inc  hl                     ; Proximo sprite
            djnz .loop_xt
            
            pop  bc
            pop  de
            pop  hl
            ret
            
        .ends
        \"\"\")
