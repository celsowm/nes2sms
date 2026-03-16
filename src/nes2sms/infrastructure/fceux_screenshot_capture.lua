local RAW_GD_PATH = [[__RAW_GD_PATH__]]
local READY_PATH = [[__READY_PATH__]]
local CAPTURE_FRAME = __CAPTURE_FRAME__

FCEU.speedmode("maximum")
FCEU.poweron()

local frame_counter = 0
while frame_counter < CAPTURE_FRAME do
    FCEU.frameadvance()
    frame_counter = frame_counter + 1
end

local screenshot = gui.gdscreenshot()

local gd_file = assert(io.open(RAW_GD_PATH, "wb"))
gd_file:write(screenshot)
gd_file:close()

local ready_file = assert(io.open(READY_PATH, "w"))
ready_file:write("{\n")
ready_file:write('  "source": "fceux_gdscreenshot",\n')
ready_file:write('  "frame": ' .. tostring(frame_counter) .. ",\n")
ready_file:write('  "gd_bytes": ' .. tostring(string.len(screenshot)) .. "\n")
ready_file:write("}\n")
ready_file:close()

while true do
    FCEU.frameadvance()
end
