"""Hello-world NES bootstrap assets and ROM helpers."""


HELLO_WORLD_WLA_6502_ASM = """; Hello, World! for NES (WLA-6502 variant)
; Adapted from Thomas Wesley Scott (2023):
; https://github.com/thomaslantern/nes-hello-world
; This template keeps the same spirit while using WLA-6502 syntax.

.ROMBANKMAP
  BANKSTOTAL 1
  BANKSIZE $4000
  BANKS 1
.ENDRO

.MEMORYMAP
  DEFAULTSLOT 0
  SLOT 0 $8000 $4000
.ENDME

.BANK 0 SLOT 0
.ORG $0000

nmihandler:
  lda #$02
  sta $4014
  rti

irqhandler:
  rti

startgame:
  sei
  cld

  ldx #$ff
  txs
  inx
  stx $2000
  stx $2001
  stx $4015
  stx $4010
  lda #$40
  sta $4017
  lda #$00

waitvblank:
  bit $2002
  bpl waitvblank

  lda #$00
clearmemory:
  sta $0000,x
  sta $0100,x
  sta $0300,x
  sta $0400,x
  sta $0500,x
  sta $0600,x
  sta $0700,x
  lda #$ff
  sta $0200,x
  lda #$00
  inx
  cpx #$00
  bne clearmemory

waitvblank2:
  bit $2002
  bpl waitvblank2

  lda $2002
  ldx #$3f
  stx $2006
  ldx #$00
  stx $2006
  ldx #$00
copypalloop:
  lda initial_palette.W,x
  sta $2007
  inx
  cpx #$04
  bne copypalloop

  lda #$02
  sta $4014

  ldx #$00
spriteload:
  lda hello.W,x
  sta $0200,x
  inx
  cpx #$2c
  bne spriteload

  lda #%10010000
  sta $2000
  lda #%00011110
  sta $2001

forever:
  jmp forever

initial_palette:
  .DB $1f,$21,$33,$30

hello:
  .DB $6c,$00,$00,$3d
  .DB $6c,$01,$00,$46
  .DB $6c,$02,$00,$4f
  .DB $6c,$02,$00,$58
  .DB $6c,$03,$00,$61

  .DB $75,$04,$00,$3d
  .DB $75,$03,$00,$46
  .DB $75,$05,$00,$4f
  .DB $75,$02,$00,$58
  .DB $75,$06,$00,$62
  .DB $75,$07,$00,$6b

.ORG $3ffa
  .DW nmihandler
  .DW startgame
  .DW irqhandler
"""


def build_ines_header(
    prg_banks: int,
    chr_banks: int,
    mapper: int = 0,
    *,
    vertical_mirroring: bool = False,
    has_battery: bool = False,
    has_trainer: bool = False,
    four_screen: bool = False,
) -> bytes:
    """Build a 16-byte iNES header."""
    if not 0 <= prg_banks <= 0xFF:
        raise ValueError("prg_banks must fit in one byte")
    if not 0 <= chr_banks <= 0xFF:
        raise ValueError("chr_banks must fit in one byte")
    if not 0 <= mapper <= 0xFF:
        raise ValueError("mapper must fit in one byte")

    flags6 = ((mapper & 0x0F) << 4) & 0xF0
    if vertical_mirroring:
        flags6 |= 0x01
    if has_battery:
        flags6 |= 0x02
    if has_trainer:
        flags6 |= 0x04
    if four_screen:
        flags6 |= 0x08

    flags7 = mapper & 0xF0
    return bytes(
        [
            0x4E,
            0x45,
            0x53,
            0x1A,
            prg_banks & 0xFF,
            chr_banks & 0xFF,
            flags6,
            flags7,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        ]
    )


def build_hello_world_chr() -> bytes:
    """Build a single 8KB CHR-ROM page from local tile data."""
    tiles = [
        [0xC3, 0xC3, 0xC3, 0xFF, 0xFF, 0xC3, 0xC3, 0xC3, 0, 0, 0, 0, 0, 0, 0, 0],
        [0xFF, 0xFF, 0xC0, 0xFC, 0xFC, 0xC0, 0xFF, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0],
        [0xC0, 0xC0, 0xC0, 0xC0, 0xC0, 0xC0, 0xFF, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0],
        [0x7E, 0xE7, 0xC3, 0xC3, 0xC3, 0xC3, 0xE7, 0x7E, 0, 0, 0, 0, 0, 0, 0, 0],
        [0xC3, 0xC3, 0xC3, 0xC3, 0xDB, 0xDB, 0xE7, 0x42, 0, 0, 0, 0, 0, 0, 0, 0],
        [0x7E, 0xE7, 0xC3, 0xC3, 0xFC, 0xCC, 0xC6, 0xC3, 0, 0, 0, 0, 0, 0, 0, 0],
        [0xF0, 0xCE, 0xC2, 0xC3, 0xC3, 0xC2, 0xCE, 0xF0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0x18, 0x18, 0x18, 0x18, 0x18, 0x00, 0x18, 0x18, 0, 0, 0, 0, 0, 0, 0, 0],
    ]

    chr_data = bytearray()
    for tile in tiles:
        chr_data.extend(tile)
    if len(chr_data) > 8192:
        raise RuntimeError("CHR data overflow")
    chr_data.extend(b"\x00" * (8192 - len(chr_data)))
    return bytes(chr_data)
