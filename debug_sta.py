prg = open('out/pong_sms/work/prg.bin', 'rb').read()
sta_count = 0
stx_count = 0
sty_count = 0
for i in range(len(prg) - 2):
    lo = prg[i + 1]
    hi = prg[i + 2]
    addr = lo | (hi << 8)
    if addr == 0x2007:
        if prg[i] == 0x8D:
            sta_count += 1
            print(f"  STA $2007 at PRG offset ${i:04X} (addr ${0x8000+i:04X})")
        if prg[i] == 0x8E:
            stx_count += 1
            print(f"  STX $2007 at PRG offset ${i:04X} (addr ${0x8000+i:04X})")
        if prg[i] == 0x8C:
            sty_count += 1
            print(f"  STY $2007 at PRG offset ${i:04X} (addr ${0x8000+i:04X})")
print(f"STA $2007: {sta_count}")
print(f"STX $2007: {stx_count}")
print(f"STY $2007: {sty_count}")
