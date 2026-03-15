local OUTPUT_PATH = [[__OUTPUT_PATH__]]
local CAPTURE_FRAME = __CAPTURE_FRAME__
local MIRRORING = "__MIRRORING__"
local VISIBLE_ROWS = __VISIBLE_ROWS__
local VISIBLE_COLS = __VISIBLE_COLS__

local ppu_vram = {}
local palette_ram = {}
local oam = {}

local ppuctrl = 0
local scroll_x = 0
local scroll_y = 0
local scroll_toggle = 0
local addr_hi = 0
local addr_lo = 0
local addr_toggle = 0
local current_addr = 0

for i = 0, 0x0FFF do
    ppu_vram[i] = 0
end

for i = 0, 31 do
    palette_ram[i] = 0x0F
end

for i = 0, 255 do
    oam[i] = 0
end

local function normalize_ppu_addr(addr)
    local masked = addr % 0x4000

    if masked >= 0x3000 and masked < 0x3F00 then
        masked = masked - 0x1000
    end

    if masked >= 0x3F00 and masked < 0x4000 then
        local index = (masked - 0x3F00) % 0x20
        if index == 0x10 then index = 0x00 end
        if index == 0x14 then index = 0x04 end
        if index == 0x18 then index = 0x08 end
        if index == 0x1C then index = 0x0C end
        return masked, index
    end

    return masked, nil
end

local function on_ppuctrl(addr, size, value)
    ppuctrl = value % 256
end

local function on_ppuscroll(addr, size, value)
    if scroll_toggle == 0 then
        scroll_x = value % 256
        scroll_toggle = 1
    else
        scroll_y = value % 256
        scroll_toggle = 0
    end
end

local function on_ppuaddr(addr, size, value)
    if addr_toggle == 0 then
        addr_hi = value % 64
        addr_toggle = 1
    else
        addr_lo = value % 256
        current_addr = (addr_hi * 256) + addr_lo
        addr_toggle = 0
    end
end

local function on_oam_dma(addr, size, value)
    local base = (value % 256) * 256
    for i = 0, 255 do
        oam[i] = memory.readbyte(base + i)
    end
end

local function refresh_ppu_snapshot()
    for i = 0, 0x0FFF do
        ppu_vram[i] = ppu.readbyte(0x2000 + i)
    end

    for i = 0, 31 do
        local normalized, palette_index = normalize_ppu_addr(0x3F00 + i)
        if palette_index ~= nil then
            palette_ram[palette_index] = ppu.readbyte(normalized) % 64
        end
    end
end

local function write_array(out_file, name, array, max_index)
    out_file:write('  "' .. name .. '": [')
    for i = 0, max_index do
        if i > 0 then
            out_file:write(',')
        end
        out_file:write(tostring(array[i] or 0))
    end
    out_file:write(']')
end

local function dump_capture(frame_value)
    local out_file = assert(io.open(OUTPUT_PATH, "w"))
    out_file:write("{\n")
    out_file:write('  "source": "fceux_lua",\n')
    out_file:write('  "frame": ' .. tostring(frame_value) .. ",\n")
    out_file:write('  "scroll_x": ' .. tostring(scroll_x) .. ",\n")
    out_file:write('  "scroll_y": ' .. tostring(scroll_y) .. ",\n")
    out_file:write('  "ppuctrl": ' .. tostring(ppuctrl) .. ",\n")
    out_file:write('  "mirroring": "' .. MIRRORING .. '",\n')
    out_file:write('  "visible_rows": ' .. tostring(VISIBLE_ROWS) .. ",\n")
    out_file:write('  "visible_cols": ' .. tostring(VISIBLE_COLS) .. ",\n")
    write_array(out_file, "palette_ram", palette_ram, 31)
    out_file:write(",\n")
    write_array(out_file, "ppu_vram", ppu_vram, 0x0FFF)
    out_file:write(",\n")
    write_array(out_file, "oam", oam, 255)
    out_file:write("\n}\n")
    out_file:close()
end

memory.registerwrite(0x2000, 1, on_ppuctrl)
memory.registerwrite(0x2005, 1, on_ppuscroll)
memory.registerwrite(0x2006, 1, on_ppuaddr)
memory.registerwrite(0x4014, 1, on_oam_dma)

FCEU.speedmode("maximum")
FCEU.poweron()

local frame_counter = 0
while frame_counter < CAPTURE_FRAME do
    FCEU.frameadvance()
    frame_counter = frame_counter + 1
end

refresh_ppu_snapshot()
dump_capture(frame_counter)

while true do
    FCEU.frameadvance()
end
