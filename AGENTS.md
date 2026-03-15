# AGENTS.md

Guia curto para agentes que trabalham neste repositório. O objetivo é reduzir tempo perdido com exploração desnecessária.

## Objetivo do projeto

`nes2sms` converte ROMs NES para um projeto/ROM Sega Master System.

Fluxo alto nível:

1. carregar ROM NES
2. extrair/disassemblar símbolos
3. converter gráficos/paletas/OAM
4. traduzir 6502 para Z80
5. gerar projeto WLA-DX
6. montar ROM SMS e opcionalmente abrir no emulador

## Onde olhar primeiro

### Entradas principais

- CLI: [src/nes2sms/cli/main.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/cli/main.py)
- comando de conversão completo: [src/nes2sms/cli/commands/convert.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/cli/commands/convert.py)
- pipeline PowerShell para reprodução rápida: [pipeline.ps1](/C:/Users/celso/Documents/projetos/nes2sms/pipeline.ps1)

### Tradução 6502 -> Z80

- tradutor principal: [src/nes2sms/core/assembly/instruction_translator.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/assembly/instruction_translator.py)
- estratégias por instrução: [src/nes2sms/core/assembly/strategies.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/assembly/strategies.py)
- tradutor com fluxo: [src/nes2sms/core/assembly/flow_aware_translator.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/assembly/flow_aware_translator.py)
- interceptação de hardware NES: [src/nes2sms/core/assembly/hardware_interceptor.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/assembly/hardware_interceptor.py)

### HAL / SMS / geração de assembly

- HAL gerado para PPU/APU/input/OAM: [src/nes2sms/core/sms/hal_generator.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/sms/hal_generator.py)
- templates WLA-DX: [src/nes2sms/infrastructure/wla_dx/templates.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/infrastructure/wla_dx/templates.py)
- scaffold do projeto WLA-DX: [src/nes2sms/infrastructure/wla_dx/project_generator.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/infrastructure/wla_dx/project_generator.py)
- geração de stubs/game logic: [src/nes2sms/infrastructure/wla_dx/stub_generator.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/infrastructure/wla_dx/stub_generator.py)

### Gráficos

- tiles: [src/nes2sms/core/graphics/tile_converter.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/graphics/tile_converter.py)
- paletas: [src/nes2sms/core/graphics/palette_mapper.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/graphics/palette_mapper.py)
- OAM/sprites: [src/nes2sms/core/graphics/oam_extractor.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/graphics/oam_extractor.py)

### Infra básica

- loader de ROM: [src/nes2sms/infrastructure/rom_loader.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/infrastructure/rom_loader.py)
- extractor de símbolos: [src/nes2sms/infrastructure/symbol_extractor.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/infrastructure/symbol_extractor.py)
- disassembler nativo/da65: [src/nes2sms/infrastructure/disassembler](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/infrastructure/disassembler)

## Regra importante: não conserte artefato gerado

Se o problema aparece em `out/.../build/*.asm`, quase sempre a correção real deve ser feita em `src/...`.

Exemplos:

- `out/.../build/hal/support.asm` vem de `translator.get_support_code(...)` -> `HALGenerator`
- `out/.../build/main.asm`, `memory.inc`, `init.asm` vêm de `templates.py`
- `out/.../build/stubs/game_logic.asm` vem do `StubGenerator` e do tradutor

Edite `out/` só para inspeção rápida. Não trate isso como fonte de verdade.

## Comandos que resolvem a maioria dos casos

### Reproduzir Pong

```powershell
powershell -ExecutionPolicy Bypass -File pipeline.ps1 -CleanOut
```

Isso converte `homebrews/pong.nes`, gera `out/pong_sms`, compila e valida se a ROM foi criada.

### Rodar a ROM gerada

```powershell
powershell -ExecutionPolicy Bypass -File run_sms.ps1 out/pong_sms
```

Ou o atalho:

```powershell
powershell -ExecutionPolicy Bypass -File run_pong.ps1
```

Se o teclado não responder no BlastEm, apertar `Right Ctrl` para capturar/liberar input.

### Conversão manual via CLI

```powershell
python -m nes2sms.cli.main convert --nes homebrews/pong.nes --out out/pong_sms --build
```

### Testes

```powershell
pytest
```

Para um alvo específico:

```powershell
pytest tests/core/assembly/test_hal_generator.py
pytest tests/infrastructure/test_wla_dx_generation.py
```

## Fluxo recomendado de diagnóstico

### Se o bug é no input/controles

Olhar nesta ordem:

1. [src/nes2sms/core/assembly/hardware_interceptor.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/assembly/hardware_interceptor.py)
2. [src/nes2sms/core/assembly/strategies.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/assembly/strategies.py)
3. [src/nes2sms/core/sms/hal_generator.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/sms/hal_generator.py)
4. `out/<game>/build/hal/support.asm` só para confirmar o código final gerado

Perguntas úteis:

- leitura/escrita de `$4016/$4017` foi interceptada?
- o HAL preserva registradores que o tradutor usa para X/Y?
- o estado mutável do HAL está em RAM, não em ROM?
- o problema está no mapeamento NES serial -> SMS ou na lógica do jogo traduzido?

### Se o bug é em PPU/nametable/paleta

Olhar nesta ordem:

1. [src/nes2sms/core/sms/hal_generator.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/sms/hal_generator.py)
2. [src/nes2sms/infrastructure/wla_dx/templates.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/infrastructure/wla_dx/templates.py)
3. [src/nes2sms/core/graphics/palette_mapper.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/graphics/palette_mapper.py)
4. `out/<game>/build/assets.asm` e `out/<game>/build/hal/support.asm`

### Se o bug é na tradução de instrução 6502

Olhar nesta ordem:

1. [src/nes2sms/core/assembly/parser.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/assembly/parser.py)
2. [src/nes2sms/core/assembly/strategies.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/assembly/strategies.py)
3. [src/nes2sms/core/assembly/flow_aware_translator.py](/C:/Users/celso/Documents/projetos/nes2sms/src/nes2sms/core/assembly/flow_aware_translator.py)
4. `out/<game>/build/stubs/game_logic.asm`

Perguntas úteis:

- carry/borrow foi invertido corretamente entre 6502 e Z80?
- branch target relativo foi resolvido para o label certo?
- acesso a RAM NES foi relocado para `$C000+`?

## Artefatos e diretórios

- `homebrews/`: ROMs de entrada de teste
- `out/`: saídas geradas; pode ser apagado e regenerado
- `emulators/blastem/`: emulador SMS local esperado pelos scripts
- `tools/wla-dx/`: assembler/linker usados pelo build
- `docs/`, `smspower/`, `skills/`: referência, não pipeline principal

## Gotchas deste repositório

- `python -m nes2sms` não é o entrypoint; use `python -m nes2sms.cli.main`.
- `pipeline.ps1` é o caminho mais rápido para reproduzir e validar Pong.
- muitos problemas “em runtime” aparecem primeiro no assembly gerado em `out/.../build`.
- se a ROM compila mas o comportamento está errado, compare `src/...` com `out/.../build/...` para verificar se o gerador certo foi alterado.
- WLA-DX está em `tools/wla-dx`; não assuma que existe no PATH.
- BlastEm pode abrir sem capturar teclado; `Right Ctrl` resolve isso.

## Quando mexer em testes

Mude testes quando a fonte geradora muda de contrato observável.

Exemplos:

- se uma variável deixa de ser `.db` inline e passa a ser símbolo em WRAM, atualize testes que buscavam o texto antigo
- se o reset passa a chamar uma init nova, cubra isso em template/HAL tests

## Resultado esperado ao fechar uma tarefa

Sempre que possível:

1. corrigir em `src/`
2. regenerar com `pipeline.ps1 -CleanOut`
3. confirmar que `out/.../build/game.sms` existe
4. se for bug de runtime, abrir no BlastEm com `run_sms.ps1`
