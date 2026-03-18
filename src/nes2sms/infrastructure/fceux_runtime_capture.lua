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
local ppudata_write_count = 0
local ppudata_nt_writes = 0

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

local function on_ppustatus(addr, size, value)
    -- Reading $2002 resets the address latch toggle
    addr_toggle = 0
    scroll_toggle = 0
end

local function advance_ppu_addr()
    -- PPUCTRL bit 2: 0 = increment 1, 1 = increment 32
    local inc = 1
    if (ppuctrl % 8) >= 4 then
        inc = 32
    end
    current_addr = (current_addr + inc) % 0x4000
end

local function on_ppudata_exec()
    -- Fired when CPU executes STA/STX/STY $2007.
    -- At this point the A/X/Y register still holds the value to be stored.
    ppudata_write_count = ppudata_write_count + 1

    -- Read the opcode at PC to determine which register is being stored
    local pc = memory.getregister("pc")
    local opcode = memory.readbyte(pc)
    local value
    if opcode == 0x8D then
        value = memory.getregister("a")
    elseif opcode == 0x8E then
        value = memory.getregister("x")
    elseif opcode == 0x8C then
        value = memory.getregister("y")
    else
        value = memory.getregister("a")
    end
    if value == nil then value = 0 end

    local ppu_addr = current_addr % 0x4000

    if ppu_addr >= 0x3F00 then
        -- Palette write
        local _, pal_idx = normalize_ppu_addr(ppu_addr)
        if pal_idx ~= nil then
            palette_ram[pal_idx] = value % 64
        end
    elseif ppu_addr >= 0x2000 and ppu_addr < 0x3000 then
        -- Nametable write (including attribute tables)
        local offset = ppu_addr - 0x2000
        ppu_vram[offset] = value % 256
        ppudata_nt_writes = ppudata_nt_writes + 1
    elseif ppu_addr >= 0x3000 and ppu_addr < 0x3F00 then
        -- Nametable mirror ($3000-$3EFF mirrors $2000-$2EFF)
        local offset = (ppu_addr - 0x1000) - 0x2000
        ppu_vram[offset] = value % 256
    end

    advance_ppu_addr()
end

local function on_oam_dma(addr, size, value)
    local base = (value % 256) * 256
    for i = 0, 255 do
        oam[i] = memory.readbyte(base + i)
    end
end

local function refresh_ppu_snapshot()
    -- Nametable data is already captured via $2007 write interception.
    -- Only refresh palette from ppu.readbyte (which works for $3F00+).
    for i = 0, 31 do
        local normalized, palette_index = normalize_ppu_addr(0x3F00 + i)
        if palette_index ~= nil then
            local ppu_val = ppu.readbyte(normalized)
            if ppu_val ~= 0 then
                palette_ram[palette_index] = ppu_val % 64
            end
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
    out_file:write('  "_debug_ppudata_writes": ' .. tostring(ppudata_write_count) .. ',\n')
    out_file:write('  "_debug_ppudata_nt_writes": ' .. tostring(ppudata_nt_writes) .. ',\n')
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
memory.registerread(0x2002, 1, on_ppustatus)
memory.registerwrite(0x2005, 1, on_ppuscroll)
memory.registerwrite(0x2006, 1, on_ppuaddr)
memory.registerwrite(0x4014, 1, on_oam_dma)

FCEU.speedmode("maximum")
FCEU.poweron()
FCEU.frameadvance() -- Ensure memory is fully initialized

-- Scan ROM for all STA/STX/STY $2007 instructions and register exec hooks.
-- memory.registerwrite(0x2007) passes stale values for PPU data port writes.
local ppudata_hook_count = 0
for scan_addr = 0x8000, 0xFFFD do
    local opcode = memory.readbyte(scan_addr)
    -- STA abs = 0x8D, STX abs = 0x8E, STY abs = 0x8C (all 3-byte instructions)
    if opcode == 0x8D or opcode == 0x8E or opcode == 0x8C then
        local lo = memory.readbyte(scan_addr + 1)
        local hi = memory.readbyte(scan_addr + 2)
        if lo == 0x07 and hi == 0x20 then
            memory.registerexec(scan_addr, on_ppudata_exec)
            ppudata_hook_count = ppudata_hook_count + 1
        end
    end
end

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
