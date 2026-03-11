@echo off
REM ============================================================================
REM nes2sms Setup Script for Windows
REM ============================================================================
REM Installs all required dependencies:
REM   - Python dependencies (nes2sms, wla-dx if available via pip)
REM   - WLA-DX toolchain (assembler + linker)
REM   - cc65 toolchain (da65 disassembler for 6502 -> Z80 translation)
REM   - Optional: Emulator download
REM ============================================================================

setlocal EnableDelayedExpansion
echo ============================================================================
echo nes2sms Setup - Windows
echo ============================================================================
echo.

REM Check Python
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+ from https://python.org
    goto error
)
python --version
echo.

REM Upgrade pip
echo [2/6] Upgrading pip...
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo WARNING: Failed to upgrade pip, continuing anyway...
)
echo.

REM Install nes2sms
echo [3/6] Installing nes2sms...
pip install -e .
if errorlevel 1 (
    echo ERROR: Failed to install nes2sms
    goto error
)
echo.

REM Install WLA-DX
echo [4/6] Installing WLA-DX toolchain...

REM Try pip first (if available)
pip install wla-dx >nul 2>&1
if not errorlevel 1 (
    echo WLA-DX installed via pip
    goto wla_done
)

REM Download pre-built binaries
echo Pip package not available, downloading pre-built binaries...
set "TOOLS_DIR=%~dp0tools"
set "WLA_DIR=%TOOLS_DIR%\wla-dx"
set "WLA_VERSION=v10.6"

if not exist "%WLA_DIR%" (
    mkdir "%WLA_DIR%" 2>nul
)

cd /d "%WLA_DIR%"

REM Check if already downloaded
if exist "wla-z80.exe" if exist "wlalink.exe" (
    echo WLA-DX already downloaded
    goto wla_done
)

echo Downloading WLA-DX %WLA_VERSION%...
powershell -Command "& { ^
    $ProgressPreference = 'SilentlyContinue'; ^
    $url = 'https://github.com/vhelin/wla-dx/releases/download/%WLA_VERSION%/wla_dx_%WLA_VERSION%_Win64.zip'; ^
    $out = 'wla.zip'; ^
    if (Test-Path $out) { Remove-Item $out -Force }; ^
    Invoke-WebRequest -Uri $url -OutFile $out; ^
    Expand-Archive -Path $out -DestinationPath '.' -Force; ^
    Remove-Item $out -Force ^
}"

if errorlevel 1 (
    echo ERROR: Failed to download WLA-DX
    echo Please download manually from: https://github.com/vhelin/wla-dx/releases
    goto error
)

echo WLA-DX downloaded and extracted
:wla_done
echo.

REM Install cc65 (da65 disassembler)
echo [5/6] Installing cc65 toolchain (da65 disassembler)...

set "CC65_DIR=%TOOLS_DIR%\cc65"

if exist "%CC65_DIR%\bin\da65.exe" (
    echo cc65 already installed
    goto cc65_done
)

echo Downloading cc65...
if not exist "%CC65_DIR%" (
    mkdir "%CC65_DIR%" 2>nul
)

cd /d "%CC65_DIR%"

powershell -Command "& { ^
    $ProgressPreference = 'SilentlyContinue'; ^
    $url = 'https://github.com/cc65/cc65/releases/download/V2.19/cc65-2.19-win64.zip'; ^
    $out = 'cc65.zip'; ^
    if (Test-Path $out) { Remove-Item $out -Force }; ^
    Invoke-WebRequest -Uri $url -OutFile $out; ^
    Expand-Archive -Path $out -DestinationPath '.' -Force; ^
    Remove-Item $out -Force ^
}"

if errorlevel 1 (
    echo WARNING: Failed to download cc65
    echo 6502 -> Z80 translation will use stubs only
    echo Install manually from: https://github.com/cc65/cc65/releases
    goto cc65_done
)

echo cc65 downloaded and extracted
:cc65_done
echo.

REM Verify installations
echo [6/6] Verifying installation...
echo.

REM Check WLA-DX
where wla-z80 >nul 2>&1
if not errorlevel 1 (
    wla-z80 --version
    echo WLA-DX is available in PATH
) else (
    echo WLA-DX: %WLA_DIR%\wla-z80.exe
)

REM Check da65
where da65 >nul 2>&1
if not errorlevel 1 (
    da65 --version
    echo da65 is available in PATH
) else (
    if exist "%CC65_DIR%\bin\da65.exe" (
        echo da65: %CC65_DIR%\bin\da65.exe
    ) else (
        echo da65: NOT FOUND (translation will use stubs only)
    )
)

echo.
REM Verify nes2sms
nes2sms --version >nul 2>&1
if not errorlevel 1 (
    nes2sms --version
)

echo.
echo ============================================================================
echo Setup complete!
echo ============================================================================
echo.
echo To convert and run a NES ROM:
echo   nes2sms convert --nes game.nes --out output_dir --build --run
echo.
echo Notes:
echo   - da65 enables automatic 6502 -> Z80 translation
echo   - Without da65, you'll get stubs that need manual porting
echo.
echo Add tools to PATH (optional):
echo   set PATH=%WLA_DIR%;%CC65_DIR%\bin;%%PATH%%
echo.
endlocal
exit /b 0

:error
endlocal
exit /b 1
