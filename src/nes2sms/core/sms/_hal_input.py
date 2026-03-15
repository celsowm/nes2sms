"""Input HAL section generator."""


def generate_input_routines() -> str:
    return """
.export hal_input_write
.export hal_input_read
.export hal_input_on_pause_nmi

hal_input_write:
    ; A = Value (bit0=strobe), L = Port (0 or 1)
    ; NES behavior:
    ; - $4016 bit0 controls strobe/latch for BOTH controllers.
    ; - $4017 writes are ignored by input latch logic.
    ; strobe=1: reads return current A button (no shift)
    ; strobe=0: reads shift serialized latch
    push bc
    ld   c, a
    ld   a, l
    or   a
    jr   nz, _input_write_ignore_p2

    ; Port 0 ($4016) controls shared strobe
    ld   a, (_input_strobe)
    ld   b, a                    ; previous strobe
    ld   a, c
    and  $01
    ld   (_input_strobe), a
    or   a
    jr   z, _input_write_low
    ; Strobe high: keep live A reads current for both pads.
    call _input_capture_p1
    call _input_capture_p2
    jr   _input_write_done
_input_write_low:
    ; Latch once on high->low transition.
    ld   a, b
    or   a
    jr   z, _input_write_done
    call _input_capture_p1
    call _input_capture_p2
    jr   _input_write_done
_input_write_ignore_p2:
    ; Port 1 ($4017) frame counter is not part of joypad strobe.
    jr   _input_write_done
_input_write_done:
    pop  bc
    ret

hal_input_on_pause_nmi:
    ; SMS PAUSE/NMI maps to NES Start pulse for next P1 latch.
    ld   a, $01
    ld   (_input_start_p1_pending), a
    ret

_input_capture_p1:
    call _input_read_sms_p1
    call _map_sms_to_nes
    ld   b, a
    ld   a, (_input_start_p1_pending)
    or   a
    jr   z, _input_capture_p1_no_start
    ld   a, b
    set  3, a                    ; NES Start
    ld   b, a
    xor  a
    ld   (_input_start_p1_pending), a
_input_capture_p1_no_start:
    ld   a, b
    ld   (_input_live_p1), a
    ld   (_input_latch_p1), a
    ret

_input_capture_p2:
    call _input_read_sms_p2
    call _map_sms_to_nes
    ld   (_input_live_p2), a
    ld   (_input_latch_p2), a
    ret

_input_read_sms_p1:
    in   a, ($DC)
    cpl
    and  $3F
    ret

_input_read_sms_p2:
    ; P2 on SMS is split across ports:
    ; - $DC bit6=Up, bit7=Down
    ; - $DD bit0=Left, bit1=Right, bit2=Button1, bit3=Button2
    ; Output A normalized to SMS internal format:
    ;   Up=b0,Down=b1,Left=b2,Right=b3,Btn1=b4,Btn2=b5
    push bc
    in   a, ($DC)
    cpl
    and  $C0
    ld   b, a
    in   a, ($DD)
    cpl
    and  $0F
    ld   c, a
    xor  a
    bit  6, b
    jr   z, +
    set  0, a
+:  bit  7, b
    jr   z, +
    set  1, a
+:  bit  0, c
    jr   z, +
    set  2, a
+:  bit  1, c
    jr   z, +
    set  3, a
+:  bit  2, c
    jr   z, +
    set  4, a
+:  bit  3, c
    jr   z, +
    set  5, a
+:  pop  bc
    ret

_map_sms_to_nes:
    ; Input A: SMS format (Up=b0,Down=b1,Left=b2,Right=b3,Btn1=b4,Btn2=b5)
    ; Output A: NES serial order (A=b0,B=b1,Sel=b2,Start=b3,Up=b4,Down=b5,Left=b6,Right=b7)
    push bc
    ld   b, a
    xor  a
    bit  4, b
    jr   z, +
    set  0, a
+:  bit  5, b
    jr   z, +
    set  1, a
+:  bit  4, b
    jr   z, +
    bit  5, b
    jr   z, +
    set  2, a                    ; Select = BTN1+BTN2
+:  bit  0, b
    jr   z, +
    set  4, a
+:  bit  1, b
    jr   z, +
    set  5, a
+:  bit  2, b
    jr   z, +
    set  6, a
+:  bit  3, b
    jr   z, +
    set  7, a
+:  pop  bc
    ret

hal_input_read:
    ; L = Port (0 or 1)
    ; Returns bit 0 = current button state (NES serial style)
    ; strobe=1: returns current A (no shift)
    ; strobe=0: shifts latch right, filling bit 7 with 1
    push bc
    ld   a, l
    or   a
    jr   nz, _read_p2
    ld   a, (_input_strobe)
    or   a
    jr   z, _read_p1_shift
    call _input_capture_p1
    ld   a, (_input_live_p1)
    and  $01
    jr   _input_read_done
_read_p1_shift:
    ld   a, (_input_latch_p1)
    ld   b, a
    srl  a
    set  7, a
    ld   (_input_latch_p1), a
    ld   a, b
    and  $01
    jr   _input_read_done
_read_p2:
    ld   a, (_input_strobe)
    or   a
    jr   z, _read_p2_shift
    call _input_capture_p2
    ld   a, (_input_live_p2)
    and  $01
    jr   _input_read_done
_read_p2_shift:
    ld   a, (_input_latch_p2)
    ld   b, a
    srl  a
    set  7, a
    ld   (_input_latch_p2), a
    ld   a, b
    and  $01
_input_read_done:
    pop  bc
    ret

; Input state variables are absolute WRAM labels from memory.inc (.ENUM $DF00)
"""
