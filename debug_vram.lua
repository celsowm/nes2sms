-- Quick debug: read nametable and dump to console
local OUTPUT = [[C:/Users/celso/Documents/projetos/nes2sms/debug_vram.txt]]

FCEU.speedmode("maximum")
FCEU.poweron()

for f = 1, 120 do
    FCEU.frameadvance()
end

local out = io.open(OUTPUT, "w")
out:write("Frame 120 nametable dump\n\n")

-- Dump first nametable ($2000-$23BF = 960 bytes)
local nonzero = 0
for i = 0, 959 do
    local v = ppu.readbyte(0x2000 + i)
    if v ~= 0 then
        nonzero = nonzero + 1
    end
    if i % 32 == 0 then
        out:write(string.format("\nRow %2d: ", i / 32))
    end
    out:write(string.format("%02X ", v))
end

out:write(string.format("\n\nNonzero tiles in NT0: %d / 960\n", nonzero))

-- Also dump attribute table ($23C0-$23FF = 64 bytes)
out:write("\nAttribute table:\n")
for i = 0, 63 do
    out:write(string.format("%02X ", ppu.readbyte(0x23C0 + i)))
    if (i + 1) % 8 == 0 then out:write("\n") end
end

out:close()

-- Now idle
while true do
    FCEU.frameadvance()
end
