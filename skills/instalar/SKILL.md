---
name: instalar
description: Instala, verifica e repara o Video AI Toolkit conduzindo o usuário passo a passo. Use quando pedirem para "instalar o toolkit", "configurar o video-ai-toolkit", "conserta a instalação", "o crv/yt-dlp parou de funcionar", "faz o check-up da instalação" ou quando um comando da suíte falhar por dependência ausente/mal configurada. Orquestra os scripts install.ps1/install.sh e diagnostica/corrige as falhas conhecidas automaticamente.
---

# Instalar / reparar o Video AI Toolkit

Você conduz a instalação como um técnico faria: roda os passos, **observa cada saída** e,
quando algo falha, aplica a correção conhecida na hora — em vez de deixar o usuário sozinho
com um erro. Os scripts `install.ps1` (Windows) e `install.sh` (macOS/Linux) são a fonte da
verdade da SEQUÊNCIA; esta skill é o diagnóstico em volta deles.

Toda comunicação em português. Nunca peça `sudo` sem avisar; nunca desative antivírus.

## Antes de começar — descubra o estado

Rode um **check-up** primeiro. Nunca reinstale o que já funciona.

```powershell
# Windows
python --version                      # precisa 3.10+
Get-Command ffmpeg,yt-dlp,crv,deno -ErrorAction SilentlyContinue | Select Name,Source
[Environment]::GetEnvironmentVariable("PYTHONUTF8","User")
Test-Path "$env:APPDATA\yt-dlp\config"
Test-Path "$env:USERPROFILE\.claude\skills"
```
```bash
# macOS/Linux
python3 --version
command -v ffmpeg yt-dlp crv deno
ls ~/.claude/skills 2>/dev/null
```

Monte um quadro do que existe × falta e só then decida: **instalação nova** (quase nada
presente) ou **reparo** (a maioria presente, algo quebrado).

## Instalação nova

1. **Rode o instalador oficial** a partir da raiz do repo clonado:
   ```powershell
   powershell -ExecutionPolicy Bypass -File install.ps1            # Windows
   powershell -ExecutionPolicy Bypass -File install.ps1 -Escriba   # + GUI do Escriba
   ```
   ```bash
   bash install.sh                                                  # macOS/Linux
   ```
2. **Leia a saída inteira**, não só o código de retorno. Cada `[aviso]`/`[erro]` do script
   corresponde a uma correção na tabela abaixo — aplique e re-rode só o passo afetado.
3. **Feche os gaps que os scripts NÃO cobrem** (ver seção "Gaps conhecidos").
4. **Valide** com os testes de fumaça no fim.

## Reparo / diagnóstico

Rode o check-up, identifique o item quebrado e vá direto na correção. Não rode o instalador
inteiro para consertar uma coisa só. Os sintomas mais comuns e suas causas estão na tabela.

## Tabela de diagnóstico (o coração desta skill)

| Sintoma | Causa raiz | Correção |
|---|---|---|
| `pip` falha com erro de SSL/certificado | Antivírus intercepta HTTPS | `python -m pip install --user pip-system-certs` e re-rode o passo pip |
| yt-dlp: erro de "JS runtime" / YouTube só dá formatos ruins | Deno ausente ou fora do config | Instale Deno; registre `--js-runtimes "deno:<caminho>"` em `%APPDATA%\yt-dlp\config`. O winget instala o Deno FORA do PATH — ache o `.exe` em `%LOCALAPPDATA%\Microsoft\WinGet\Packages` |
| yt-dlp: "signature"/403 | yt-dlp desatualizado | `pip install --user -U yt-dlp` |
| crv imprime "✓ Done" mas os grids não saem | Console cp1252 quebra no print | `setx PYTHONUTF8 1` e abra um NOVO terminal |
| Acentos viram lixo / comando morre no meio | idem PYTHONUTF8 | idem |
| ffmpeg "instalado" mas comando não encontrado | winget instalou fora do PATH desta sessão | Abra um NOVO PowerShell; se persistir, confira o PATH do usuário |
| winget falha ao baixar | fonte msstore + antivírus | sempre `--source winget` (o script já usa) |
| `~/.claude` não existe | Claude Code não instalado | Instale o Claude Code; ou copie `skills/` e `agents/` manualmente para o diretório de skills do agente que a pessoa usa |
| Skill "já existe — pulando" mas você quer atualizar | proteção contra sobrescrita | re-rode com `-Force` (Windows) / `--force` (Unix) |
| PySide6: OSError de caminho longo (só `-Escriba`) | Python da Microsoft Store | O pacote costuma ficar funcional mesmo assim — valide o import antes de reinstalar (ver testes) |
| Transcrição/diarização falha (escriba) | WhisperX/pyannote/repos gated | NÃO é problema desta skill — a pipeline pesada é instalada pelo próprio agente `escriba` na 1ª transcrição ("prepara o ambiente de transcrição"); aceite os 3 repos gated do pyannote no HuggingFace |

## Gaps conhecidos que os scripts NÃO cobrem (feche-os você)

Os `install.*` de hoje deixam coisas de fora. Depois de rodá-los, verifique e complete:

1. **Agentes no Unix** — o `install.ps1` (Windows) já copia `escriba` E `editor`. Os scripts
   Unix NÃO copiam agentes (o Escriba é voltado a Windows). Se a pessoa em macOS/Linux usa um
   agente que lê `.md`, copie os arquivos de `agents/` manualmente para o diretório dele.
2. **Deps do print de site (`web-shot`)** — precisa de Node + `npm install`. Só é necessário
   se a pessoa for usar prints de notícia/logos:
   ```bash
   cd apps/editor/web-shot && npm install    # instala puppeteer-core; usa o Chrome já presente
   ```
   Sem Node: `winget install OpenJS.NodeJS.LTS --source winget` (Windows) / `brew install node`.
3. **Scripts do editor não são "instalados"** — eles rodam da própria pasta `apps/editor/` do
   repo. Garanta que a pessoa saiba que o repo clonado precisa continuar existindo (o agente
   `editor` chama esses scripts por caminho).

Ao terminar, **diga ao usuário o que ficou de fora de propósito** (ex.: "não instalei o
web-shot porque você não vai usar prints de site — se precisar, é um `npm install`").

## Testes de fumaça (sempre rode ao final)

```bash
# 1. download (não baixa nada, só resolve os formatos — valida yt-dlp + Deno)
yt-dlp --simulate --print "%(title)s" "https://www.youtube.com/watch?v=jNQXAC9IVRw"

# 2. crv responde
crv --help

# 3. ffmpeg + encoder de GPU (nvenc é opcional; ausência não é erro)
ffmpeg -hide_banner -encoders | grep -i nvenc   # findstr no Windows

# 4. (se instalou o Escriba) PySide6 importa
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
```

Reporte um resumo final: o que instalou, o que já estava OK, o que corrigiu, o que ficou
pendente de propósito, e as 3 frases de teste no Claude Code ("baixa esse vídeo: …",
"resume esse vídeo: …", "transcreve essa reunião: …").

## Regras

- **Nunca reinstale o que já funciona** — o check-up vem primeiro, sempre.
- **Leia a saída, não só o exit code** — os scripts usam `Continue`/`|| warn` e seguem mesmo
  com falha parcial; o sinal está no texto.
- **Uma correção por vez, re-rode só o passo** — não jogue o instalador inteiro de novo.
- **Windows vs. Unix**: o Escriba (transcrição pt-BR com diarização) é voltado a Windows; em
  macOS/Linux, oriente usar `crv --speakers` para diarização leve.
- **Nunca** desative antivírus nem contorne proteções; a correção de SSL é `pip-system-certs`,
  não baixar a guarda.
