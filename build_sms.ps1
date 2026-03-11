param (
    [string]$ProjectName = "pong_sms",
    [switch]$Run
)

$ErrorActionPreference = "Stop"

Write-Host "=== NES2SMS Build Setup ===" -ForegroundColor Cyan

# 1. Checar e instalar 'make'
if (!(Get-Command make -ErrorAction SilentlyContinue)) {
    Write-Host "[1/3] 'make' não encontrado. Tentando instalar via winget..." -ForegroundColor Yellow
    winget install ezwinports.make --silent --accept-package-agreements --accept-source-agreements
    
    # Atualiza o PATH da sessão atual do PowerShell após a instalação
    $env:PATH = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    if (!(Get-Command make -ErrorAction SilentlyContinue)) {
        Write-Host "Falha ao encontrar o 'make' após instalação. Pode ser necessário reiniciar o terminal ou instalar manualmente." -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "[1/3] 'make' já está instalado." -ForegroundColor Green
}

# 2. Baixar e configurar 'wla-dx' localmente na pasta do projeto
$wlaDxDir = "$PSScriptRoot\tools\wla-dx"
if (!(Test-Path "$wlaDxDir\wla-z80.exe")) {
    Write-Host "[2/3] Baixando WLA-DX v10.6 (Windows 64-bit)..." -ForegroundColor Yellow
    $wlaUrl = "https://github.com/vhelin/wla-dx/releases/download/v10.6/wla_dx_v10.6_Win64.zip"
    $zipPath = "$PSScriptRoot\wla-dx.zip"
    
    New-Item -ItemType Directory -Force -Path $wlaDxDir | Out-Null
    Invoke-WebRequest -Uri $wlaUrl -OutFile $zipPath
    
    Write-Host "Extraindo WLA-DX..." -ForegroundColor Yellow
    Expand-Archive -Path $zipPath -DestinationPath $wlaDxDir -Force
    Move-Item -Path "$wlaDxDir\wla_dx_v10.6_Win64\*" -Destination $wlaDxDir -Force
    Remove-Item -Path "$wlaDxDir\wla_dx_v10.6_Win64" -Recurse
    Remove-Item -Path $zipPath
    Write-Host "WLA-DX configurado em $wlaDxDir" -ForegroundColor Green
}
else {
    Write-Host "[2/3] 'wla-dx' já está configurado na pasta tools." -ForegroundColor Green
}

# Adiciona o diretório do wla-dx ao PATH apenas nesta sessão do terminal
if ($env:PATH -notmatch [regex]::Escape($wlaDxDir)) {
    $env:PATH += ";$wlaDxDir"
}

# 3. Compilar o projeto
$buildDir = "$PSScriptRoot\out\$ProjectName\build"
Write-Host "[3/3] Iniciando compilação do projeto '$ProjectName'..." -ForegroundColor Cyan

if (Test-Path "$buildDir\Makefile") {
    Push-Location $buildDir
    try {
        make
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
            Write-Host "Sucesso! O arquivo .sms deve estar dentro de: $buildDir" -ForegroundColor Green
            
            if ($Run) {
                $emulatorPath = "$PSScriptRoot\emulators\blastem\blastem.exe"
                $romPath = "$buildDir\game.sms"
                if (Test-Path $emulatorPath) {
                    if (Test-Path $romPath) {
                        Write-Host "[Run] Iniciando $romPath no BlastEm..." -ForegroundColor Cyan
                        Start-Process $emulatorPath -ArgumentList "`"$romPath`""
                    }
                    else {
                        Write-Host "ERRO: ROM não encontrada em $romPath" -ForegroundColor Red
                    }
                }
                else {
                    Write-Host "AVISO: Emulator não encontrado em $emulatorPath. Por favor, rode .\download_emulator.ps1 primeiro." -ForegroundColor Yellow
                }
            }
        }
        else {
            Write-Host "A compilação falhou com o código de saída $LASTEXITCODE." -ForegroundColor Red
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "Makefile não encontrado em $buildDir." -ForegroundColor Red
    Write-Host "Por favor, rode o script python nes2sms.py primeiro para gerar o projeto antes de rodar este script." -ForegroundColor Yellow
}
