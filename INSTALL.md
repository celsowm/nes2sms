# nes2sms Installation Guide

## Quick Setup

### Windows

```powershell
# Run the setup script
.\setup.bat

# Or manually:
pip install -e .
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/vhelin/wla-dx/releases/download/v10.6.0/wla-dx-v10.6.0-windows.zip' -OutFile wla.zip; Expand-Archive wla.zip -DestinationPath tools\wla-dx; Remove-Item wla.zip"
```

### Linux/macOS

```bash
# Run the setup script
chmod +x setup.sh
./setup.sh

# Or manually:
pip install -e .
# Install WLA-DX via your package manager:
#   Ubuntu/Debian: sudo apt-get install wla-dx
#   Fedora: sudo dnf install wla-dx
#   macOS: brew install wla-dx
```

## Manual Installation

### 1. Install Python Dependencies

```bash
pip install -e .
```

### 2. Install WLA-DX Toolchain

WLA-DX is required to build SMS ROMs from the generated Z80 assembly.

#### Option A: Package Manager

| OS | Command |
|----|---------|
| Ubuntu/Debian | `sudo apt-get install wla-dx` |
| Fedora | `sudo dnf install wla-dx` |
| macOS (Homebrew) | `brew install wla-dx` |
| Arch Linux | `sudo pacman -S wla-dx` |

#### Option B: Pre-built Binaries

Download from [GitHub Releases](https://github.com/vhelin/wla-dx/releases):

```bash
# Windows (PowerShell)
$url = "https://github.com/vhelin/wla-dx/releases/download/v10.6.0/wla-dx-v10.6.0-windows.zip"
Invoke-WebRequest -Uri $url -OutFile wla.zip
Expand-Archive wla.zip -DestinationPath tools\wla-dx
Remove-Item wla.zip

# Linux
wget https://github.com/vhelin/wla-dx/releases/download/v10.6.0/wla-dx-v10.6.0-linux.tar.gz
tar -xzf wla-dx-v10.6.0-linux.tar.gz -C tools/wla-dx --strip-components=1

# macOS
wget https://github.com/vhelin/wla-dx/releases/download/v10.6.0/wla-dx-v10.6.0-macos.tar.gz
tar -xzf wla-dx-v10.6.0-macos.tar.gz -C tools/wla-dx --strip-components=1
```

#### Option C: Build from Source

```bash
git clone https://github.com/vhelin/wla-dx
cd wla-dx
mkdir build && cd build
cmake ..
cmake --build . --config Release
cmake -P cmake_install.cmake  # Optional: install to system
```

### 3. Add WLA-DX to PATH (if not installed system-wide)

```bash
# Windows (PowerShell)
$env:PATH = ".\tools\wla-dx;$env:PATH"

# Linux/macOS
export PATH="$PWD/tools/wla-dx:$PATH"
```

## Verify Installation

```bash
# Check nes2sms
nes2sms --version

# Check WLA-DX
wla-z80 --version
wlalink --version
```

## Usage

```bash
# Convert NES to SMS and run in emulator
nes2sms convert --nes game.nes --out output_dir --build --run --emulator path/to/emulator.exe

# Convert only (no build)
nes2sms convert --nes game.nes --out output_dir

# Build manually
cd output_dir/build
make  # or run build.bat on Windows
```

## Troubleshooting

### "wla-dx not found"

- Ensure `wla-z80` and `wlalink` are in your PATH
- Run `where wla-z80` (Windows) or `which wla-z80` (Linux/macOS)
- Add the WLA-DX directory to your PATH

### Build fails with "file not found"

- On Windows, ensure you're using the correct path separators in Makefile
- Try running `build.bat` instead of `make`

### Emulator shows black screen

- Verify the build completed successfully (check for `.sms` or `.bin` output)
- Ensure the ROM file is >1KB (invalid builds create tiny files)
- Check emulator compatibility with homebrew ROMs

## Next Steps

- See `USO_RAPIDO.md` for quick start guide
- Check `docs/` for detailed documentation
- Run `nes2sms --help` for all available commands
