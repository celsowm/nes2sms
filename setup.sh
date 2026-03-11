#!/usr/bin/env bash
# ============================================================================
# nes2sms Setup Script for Linux/macOS
# ============================================================================
# Installs all required dependencies:
#   - Python dependencies (nes2sms)
#   - WLA-DX toolchain (assembler + linker)
#   - cc65 toolchain (da65 disassembler for 6502 -> Z80 translation)
# ============================================================================

set -e

echo "============================================================================"
echo "nes2sms Setup - Linux/macOS"
echo "============================================================================"
echo ""

# Check Python
echo "[1/6] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found. Please install Python 3.10+"
    exit 1
fi
python3 --version
echo ""

# Upgrade pip
echo "[2/6] Upgrading pip..."
python3 -m pip install --upgrade pip --quiet || echo "WARNING: Failed to upgrade pip"
echo ""

# Install nes2sms
echo "[3/6] Installing nes2sms..."
pip3 install -e . || {
    echo "ERROR: Failed to install nes2sms"
    exit 1
}
echo ""

# Install WLA-DX
echo "[4/6] Installing WLA-DX toolchain..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$SCRIPT_DIR/tools"
WLA_DIR="$TOOLS_DIR/wla-dx"
WLA_VERSION="v10.6"

mkdir -p "$WLA_DIR"
cd "$WLA_DIR"

if [[ -f "wla-z80" && -f "wlalink" ]]; then
    echo "WLA-DX already downloaded"
else
    echo "Downloading WLA-DX $WLA_VERSION..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        URL="https://github.com/vhelin/wla-dx/releases/download/$WLA_VERSION/wla_dx_${WLA_VERSION}_Linux64.tar.gz"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        URL="https://github.com/vhelin/wla-dx/releases/download/$WLA_VERSION/wla_dx_${WLA_VERSION}_macOS.tar.gz"
    else
        URL="https://github.com/vhelin/wla-dx/releases/download/$WLA_VERSION/wla_dx_${WLA_VERSION}_Linux64.tar.gz"
    fi
    
    curl -L -o wla-dx.tar.gz "$URL" || {
        echo "WARNING: Failed to download WLA-DX"
    }
    
    if [[ -f "wla-dx.tar.gz" ]]; then
        tar -xzf wla-dx.tar.gz --strip-components=1
        rm wla-dx.tar.gz
        chmod +x wla-z80 wlalink 2>/dev/null || true
        echo "WLA-DX downloaded and extracted"
    fi
fi

echo ""

# Install cc65
echo "[5/6] Installing cc65 toolchain (da65 disassembler)..."

CC65_DIR="$TOOLS_DIR/cc65"

if [[ -f "$CC65_DIR/bin/da65" ]]; then
    echo "cc65 already installed"
else
    echo "Downloading cc65..."
    mkdir -p "$CC65_DIR"
    cd "$CC65_DIR"
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        CC65_URL="https://github.com/cc65/cc65/releases/download/V2.19/cc65-2.19-linux.zip"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        CC65_URL="https://github.com/cc65/cc65/releases/download/V2.19/cc65-2.19-macos.zip"
    else
        CC65_URL="https://github.com/cc65/cc65/releases/download/V2.19/cc65-2.19-linux.zip"
    fi
    
    if command -v curl &> /dev/null; then
        curl -L -o cc65.zip "$CC65_URL" || echo "WARNING: Failed to download cc65"
    elif command -v wget &> /dev/null; then
        wget -O cc65.zip "$CC65_URL" || echo "WARNING: Failed to download cc65"
    fi
    
    if [[ -f "cc65.zip" ]]; then
        unzip -o cc65.zip
        rm cc65.zip
        chmod +x bin/* 2>/dev/null || true
        echo "cc65 downloaded and extracted"
    else
        echo "WARNING: Failed to download cc65"
        echo "Install manually from: https://github.com/cc65/cc65/releases"
    fi
fi

echo ""

# Verify installations
echo "[6/6] Verifying installation..."
echo ""

# Check WLA-DX
if command -v wla-z80 &> /dev/null; then
    wla-z80 --version || true
    echo "WLA-DX is available in PATH"
else
    echo "WLA-DX: $WLA_DIR/wla-z80"
fi

# Check da65
if command -v da65 &> /dev/null; then
    da65 --version || true
    echo "da65 is available in PATH"
else
    if [[ -f "$CC65_DIR/bin/da65" ]]; then
        echo "da65: $CC65_DIR/bin/da65"
    else
        echo "da65: NOT FOUND (translation will use stubs only)"
    fi
fi

echo ""
# Verify nes2sms
if command -v nes2sms &> /dev/null; then
    nes2sms --version || true
fi

echo ""
echo "============================================================================"
echo "Setup complete!"
echo "============================================================================"
echo ""
echo "To convert and run a NES ROM:"
echo "  nes2sms convert --nes game.nes --out output_dir --build --run"
echo ""
echo "Notes:"
echo "  - da65 enables automatic 6502 -> Z80 translation"
echo "  - Without da65, you'll get stubs that need manual porting"
echo ""
echo "Add tools to PATH (optional):"
echo "  export PATH=\"$WLA_DIR:$CC65_DIR/bin:\$PATH\""
echo ""
