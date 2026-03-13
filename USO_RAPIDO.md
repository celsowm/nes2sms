# nes2sms - Uso Simplificado

## Comando Único (Recomendado)

Para converter um ROM NES para SMS com um único comando:

```bash
nes2sms convert --nes game.nes --out output_dir
```

## Bootstrap Hello World NES -> SMS

Para gerar um baseline homebrew (hello world), compilar NES, converter para SMS e abrir
emuladores por padrao:

```bash
nes2sms bootstrap-hello
```

### Opcoes do `bootstrap-hello`

```bash
nes2sms bootstrap-hello [opcoes]
```

| Opcao | Descricao |
|-------|-----------|
| `--out` | Diretorio de saida (padrao: `out/hello_world`) |
| `--no-run` | Nao abre emuladores (mas continua compilando NES e SMS) |
| `--nes-emulator` | Caminho do executavel do emulador NES |
| `--sms-emulator` | Caminho do executavel do emulador SMS |

### Exemplos

```bash
# Fluxo completo (build + run NES/SMS)
nes2sms bootstrap-hello

# Fluxo sem abrir emuladores
nes2sms bootstrap-hello --no-run

# Definindo emuladores manualmente
nes2sms bootstrap-hello --nes-emulator "C:\\Emulators\\fceux.exe" --sms-emulator "C:\\Emulators\\blastem.exe"
```

> Nota: sucesso neste ciclo significa ROM NES valida + ROM SMS gerada/compilada.
> O resultado visual NES vs SMS nao e esperado ser 1:1.

### Opções do Comando `convert`

```bash
nes2sms convert --nes game.nes --out output_dir [opções]
```

| Opção | Descrição |
|-------|-----------|
| `--nes` | Path do arquivo .nes (obrigatório) |
| `--out` | Diretório de saída (obrigatório) |
| `--flip-strategy` | Estratégia de flip: `cache` (padrão) ou `none` |
| `--sat-source` | Fonte do SAT: `runtime` (padrão, via DMA `$4014`) ou `static-fallback` |
| `--split-y` | Split vertical (pixels) para política de prioridade em 2 zonas (padrão: `48`) |
| `--build` | Compila o ROM SMS após conversão |
| `--run` | Abre no emulador após conversão (requer `--build`) |
| `--emulator` | Caminho do emulador (padrão: auto-detect) |

### Exemplos

**Conversão básica:**
```bash
nes2sms convert --nes pong.nes --out out/pong_sms
```

**Conversão com build:**
```bash
nes2sms convert --nes pong.nes --out out/pong_sms --build
```

**Conversão completa e abrir no emulador:**
```bash
nes2sms convert --nes pong.nes --out out/pong_sms --build --run
```

**Com emulador específico:**
```bash
nes2sms convert --nes pong.nes --out out/pong_sms --build --run --emulator "C:\Emulators\blastem.exe"
```

## Estrutura de Saída

Após a conversão, o diretório de saída conterá:

```
output_dir/
├── assets/           # Gráficos convertidos
│   ├── tiles.bin          # Tiles SMS (4bpp)
│   ├── tile_symbols.inc   # Símbolos dos tiles para WLA-DX
│   ├── palette_bg.bin     # Paleta background
│   ├── palette_spr.bin    # Paleta sprites
│   └── flip_index.json    # Mapeamento de flips
│
├── stubs/            # Código Z80 gerado
│   ├── game_logic.asm     # Stubs das rotinas do jogo
│   └── game_stubs.asm     # Stubs adicionais
│
└── work/             # Arquivos intermediários
    ├── prg.bin            # PRG extraído
    ├── chr.bin            # CHR extraído
    ├── symbols.json       # Símbolos extraídos
    └── banks.json         # Mapeamento de banks
```

## Comandos Individuais (Avançado)

Se precisar de controle fino sobre cada etapa:

```bash
# 1. Extrair dados do ROM
nes2sms ingest --nes game.nes --out out/game

# 2. Converter gráficos
nes2sms convert-gfx --chr out/game/work/chr.bin --prg out/game/work/prg.bin --out out/game

# 3. Traduzir assembly manualmente
nes2sms translate-asm --input game_6502.asm --output game_z80.asm

# 4. Gerar stubs Z80
nes2sms generate --manifest out/game/work/manifest_sms.json --out out/game
```

## Pipeline Automático

O comando `convert` executa automaticamente:

1. **Ingest** - Extrai PRG/CHR do ROM NES
2. **Symbol Extraction** - Identifica vetores e rotinas
3. **Mapper Analysis** - Analisa mapper e gera bank map
4. **Graphics Conversion** - Converte tiles 2bpp→4bpp com paletas
5. **Stub Generation** - Gera stubs Z80 para cada rotina encontrada
6. **Build** (opcional) - Compila com WLA-DX

## Rodar ROM Gerada a Partir de uma Pasta

Use o script PowerShell abaixo passando a pasta de saida do projeto:

```powershell
.\run_sms.ps1 out/pong_sms
```

Com emulador customizado:

```powershell
.\run_sms.ps1 out/pong_sms -EmulatorPath "C:\Emulators\blastem.exe"
```

Modo debug (abre BlastEm no debugger CLI):

```powershell
.\run_sms.ps1 out/pong_sms -DebugCLI
```

Modo GDB remote stub:

```powershell
.\run_sms.ps1 out/pong_sms -GdbStub
```

> Nota: algumas versões do BlastEm não suportam `-D`. O script detecta isso e ignora a flag automaticamente.

## Coleta Automática de Artefatos de Debug (sem interação manual)

Gera artefatos estáticos e capturas automáticas do emulador (jogo, VRAM debug e CRAM debug):

```powershell
.\capture_sms_debug_artifacts.ps1 out/pong_sms
```

Com diretório de saída customizado:

```powershell
.\capture_sms_debug_artifacts.ps1 out/pong_sms -OutDir out/pong_sms/debug_artifacts/latest
```

Notas do gate determinístico:
- `summary.json` é sempre gerado e vira o artefato principal de validação.
- Dumps mandatórios: `vdp_registers.dump.txt`, `sprite_list.dump.txt`, `palette_*.hex`, `tiles_first256.hex`, `sat_y.bin`, `sat_xt.bin`.
- PNG de VRAM/CRAM é best-effort (falha desses PNGs não invalida o gate).

## Pixel Diff (<= 1.0%)

Para medir aceitação visual por cena:

```powershell
.\measure_pixel_diff.ps1 referencia.png candidato.png -ThresholdPercent 1.0 -OutJson diff_result.json
```

## Tradução 6502→Z80

Com `--translate`, o conversor gera código Z80 traduzido automaticamente:

**6502 original:**
```asm
Reset:
    SEI
    LDX #$FF
    TXS
    LDA #$00
    STA $2000
```

**Z80 traduzido:**
```asm
Reset:
    DI
    LD   B, $FF      ; LDX
    LD   SP, BC      ; TXS
    LD   A, $00      ; LDA
    LD   ($2000), A  ; STA
```

> **Nota:** A tradução é literal. Você precisará ajustar para o hardware SMS (VDP, PSG, etc.)

## Requisitos

- Python 3.10+
- WLA-DX (para build)

## Testes

```bash
pytest tests/ -v
```

65 testes cobrindo:
- Conversão de tiles
- Mapeamento de paletas
- Tradução 6502→Z80
- Extração de símbolos
