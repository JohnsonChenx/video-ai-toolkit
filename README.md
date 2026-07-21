# 🎬 Video AI Toolkit

**Dê ao seu agente de IA o poder completo sobre vídeos: baixar, assistir e transcrever — tudo local, tudo grátis.**

> *EN: A one-command toolkit that lets Claude (or any AI agent) download videos (yt-dlp), actually watch them (claude-real-video) and transcribe them with speaker diarization (WhisperX) — fully local, pt-BR first. Install: run `install.ps1` (Windows) or `install.sh` (macOS/Linux).*

📖 **[Manual completo (HTML)](docs/manual.html)** — funcionalidades detalhadas, fluxos de decisão, frases prontas e solução de problemas. Abra no navegador ou via [htmlpreview](https://htmlpreview.github.io/?https://github.com/JohnsonChenx/video-ai-toolkit/blob/main/docs/manual.html).

## O que vem dentro

| Peça | O que faz | Como usar |
|---|---|---|
| **Skill `youtube`** | Baixa vídeo (sempre MP4) ou só o áudio (sempre MP3) do YouTube e centenas de sites; se autoinstala | "baixa esse vídeo: \<url\>" |
| **Skill `claude-real-video`** | O Claude "assiste" o vídeo: keyframes por detecção de cena + transcrição + grids 3×3 | "resume esse vídeo: \<url\>" |
| **Agente `escriba`** | Transcrição pt-BR com separação de falantes (WhisperX + pyannote + CUDA); instala a própria pipeline; **analisa a qualidade do áudio e aplica denoise automaticamente** quando necessário; entrega Resumo Estruturado ou Ata de Reunião | "transcreve essa reunião" (Windows) |
| **Agente `editor`** | Edição de vídeo por conversa: método das 3 passadas (erros → silêncio real → redundância), comando de voz embutido ("pato preto"), plano de cortes para aprovação, render ffmpeg/NVENC, cortes 9:16 com legenda karaokê, split-screen, motion graphics (Remotion/Motion Canvas) e verificação com nota 0-100 | "edita esse bruto, corta os erros" (Windows) |
| **Skill `invest`** | Estilo de edição "notícia dinâmica": legendas bloco-CAPS, cartões de dados para números, manchetes reais como prova, flash de ênfase, ritmo denso — aplicado pelo agente editor | "edita no estilo invest" |
| **Skill `instalar`** | Instala, verifica e **repara** o toolkit conduzindo passo a passo; diagnostica e corrige as falhas conhecidas automaticamente | "instala o video-ai-toolkit" |
| **App Baixador** (`apps/baixador/`) | Interface web local de download com seletor de pasta e barra de progresso | dois cliques em `ABRIR.bat` |
| **App Escriba** (`apps/escriba/`) | GUI de transcrição: arrasta-e-solta, ditado global Ctrl+Alt+D, resumo/ata por IA | `Iniciar Escriba.bat` (Windows) |

## Instalação

**Pré-requisito:** Python 3.10+ ([Microsoft Store](https://apps.microsoft.com/search?query=python) no Windows, `brew`/`apt` no resto) e `git`.

### Comando único (clone + instalação)

Cole **uma linha** no terminal:

```powershell
# Windows (PowerShell)
git clone https://github.com/JohnsonChenx/video-ai-toolkit; cd video-ai-toolkit; powershell -ExecutionPolicy Bypass -File install.ps1
```

```bash
# macOS / Linux
git clone https://github.com/JohnsonChenx/video-ai-toolkit && cd video-ai-toolkit && bash install.sh
```

Depois disso, abra o Claude Code na pasta `video-ai-toolkit` e já pode conversar com as ferramentas.

### Passo a passo (se preferir ver cada etapa)

```powershell
# Windows (PowerShell)
git clone https://github.com/JohnsonChenx/video-ai-toolkit
cd video-ai-toolkit
powershell -ExecutionPolicy Bypass -File install.ps1           # stack de vídeo
powershell -ExecutionPolicy Bypass -File install.ps1 -Escriba  # + GUI do Escriba
```

```bash
# macOS / Linux
git clone https://github.com/JohnsonChenx/video-ai-toolkit
cd video-ai-toolkit
bash install.sh
```

O instalador cuida de: **yt-dlp**, **ffmpeg** (fonte oficial via winget/brew/apt), **Deno** (runtime JS que o YouTube exige desde 2026, incluindo o registro no config do yt-dlp), **claude-real-video**, **faster-whisper**, a variável `PYTHONUTF8` no Windows, e a cópia das skills e agentes para `~/.claude/`.

### Instalação guiada pelo agente

Prefere deixar o Claude conduzir? São **3 passos**:

1. Tenha o **Claude Code** instalado
2. `git clone https://github.com/JohnsonChenx/video-ai-toolkit` e abra o Claude Code nessa pasta
3. Peça: **"instala o video-ai-toolkit"**

A skill `instalar` faz um check-up do que já existe, roda o instalador certo para o seu sistema e — o pulo do gato — **diagnostica e corrige as falhas conhecidas na hora** (Deno fora do PATH, `PYTHONUTF8`, SSL do antivírus, repos gated do HuggingFace…) em vez de te deixar sozinho com um erro. Também serve para **reparar** uma instalação que parou de funcionar: "conserta a instalação" / "o crv parou de funcionar".

> Por que o clone (passo 2) é necessário: a skill `instalar` vive dentro do repositório, então o agente só sabe que ela existe depois que os arquivos estão na sua máquina.

Não usa Claude Code? As skills funcionam em qualquer agente que leia `SKILL.md` (Codex, OpenCode, Gemini CLI…) — copie as pastas de `skills/` para o diretório de skills do seu agente.

## Por que esta suíte (e não instalar cada peça na mão)

Além de juntar tudo num comando, ela embute as correções de pegadinhas reais que custam horas de quem instala por conta:

- **YouTube sem runtime JS** oculta os melhores formatos → o instalador configura o Deno no `%APPDATA%\yt-dlp\config` (o winget o instala fora do PATH — quase ninguém descobre isso sozinho)
- **Console Windows em cp1252** quebra o crv no "✓" final e os grids nunca são gerados → `PYTHONUTF8=1` permanente
- **Antivírus interceptando HTTPS** (Avast e afins) derruba pip e winget → fonte winget forçada + receita do `pip-system-certs`
- **Formatos garantidos**: vídeo sempre sai MP4 (H.264+AAC com remux), áudio sempre MP3 — sem surpresa de `.webm` que não abre na TV

## Exemplos de uso (no Claude Code)

```
Você: baixa só o áudio disso: https://youtube.com/watch?v=...
Claude: [skill youtube] → musica.mp3 salvo, 4.2 MB

Você: o que acontece nesse vídeo? https://youtube.com/watch?v=...
Claude: [skill claude-real-video] → extrai 17 keyframes + transcrição,
        lê os grids e responde citando timestamps

Você: transcreve a reunião de ontem (reuniao.m4a) e identifica quem falou
Claude: [agente escriba] → reuniao.txt/.srt/.json com tags [SPEAKER_00]...
```

## Privacidade

Todo o processamento (download, extração de frames, transcrição, diarização) roda **na sua máquina**. Nada é enviado a nuvem alguma pelas ferramentas — se você colar o resultado num LLM em nuvem, aí a escolha (e o dado) é sua.

## Créditos e licenças

| Componente | Autor | Licença |
|---|---|---|
| [claude-real-video](https://github.com/HUANGCHIHHUNGLeo/claude-real-video) | HUANGCHIHHUNGLeo | MIT (usado via PyPI; skill adaptada com atribuição) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | yt-dlp team | Unlicense |
| [WhisperX](https://github.com/m-bain/whisperX) / [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | m-bain / SYSTRAN | BSD-2 / MIT |
| [ffmpeg](https://ffmpeg.org) | FFmpeg team | LGPL/GPL — **não redistribuído aqui**; o instalador baixa das fontes oficiais |
| Skills, agente Escriba, apps e instaladores | este repositório | MIT |

⚠️ **Use com responsabilidade:** baixe e transcreva apenas conteúdo que você tem direito de usar.
