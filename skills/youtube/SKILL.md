---
name: youtube
description: >-
  Baixa vídeos (sempre em MP4) ou apenas o áudio (sempre em MP3) do YouTube e de
  centenas de outros sites (Vimeo, Twitter/X, Instagram, TikTok etc.) usando yt-dlp,
  instalando e configurando o yt-dlp/ffmpeg/Deno automaticamente se não estiverem
  presentes. Use esta skill SEMPRE que o usuário pedir para baixar um vídeo, baixar
  uma música/áudio de um vídeo, extrair MP3 de um link, baixar uma playlist, salvar
  um vídeo do YouTube, ou colar uma URL de vídeo pedindo download — mesmo que ele
  não mencione "yt-dlp". Também use quando o download falhar por yt-dlp
  desatualizado ou ausente.
---

# YouTube — Download de vídeos e áudios (yt-dlp)

Skill para baixar vídeos em **MP4** e áudios em **MP3** com yt-dlp, cuidando da
instalação e configuração do ambiente quando necessário.

## Passo 1 — Verificar o ambiente (sempre, antes de baixar)

Windows (PowerShell):

```powershell
Get-Command yt-dlp -ErrorAction SilentlyContinue
Get-Command ffmpeg -ErrorAction SilentlyContinue
```

macOS/Linux: `which yt-dlp ffmpeg`

### Se o yt-dlp NÃO estiver instalado

```bash
pip install -U yt-dlp
```

Se o pip falhar com erro de SSL/certificado, a causa provável é antivírus ou
proxy corporativo interceptando HTTPS (Avast, por exemplo, faz isso). Correção
no Windows: `pip install pip-system-certs` e repetir.

### Se o ffmpeg NÃO estiver instalado

O ffmpeg é obrigatório (converte MP3 e junta vídeo+áudio):

```powershell
# Windows — use --source winget: a fonte msstore falha com antivírus que interceptam HTTPS
winget install --id Gyan.FFmpeg -e --source winget --accept-source-agreements --accept-package-agreements
```

macOS: `brew install ffmpeg` · Linux: `sudo apt install ffmpeg`

### Runtime JavaScript (exigido pelo YouTube desde 2026)

Se o yt-dlp emitir o aviso "No supported JavaScript runtime could be found",
o YouTube pode ocultar os melhores formatos. Correção:

1. Instalar Deno se não existir: `winget install --id DenoLand.Deno -e --source winget`
   (macOS: `brew install deno`)
2. No Windows, o winget instala o deno.exe FORA do PATH — localize-o em
   `%LOCALAPPDATA%\Microsoft\WinGet\Packages\DenoLand.Deno_*\deno.exe`
3. Registre no config global do yt-dlp (`%APPDATA%\yt-dlp\config`), uma linha:
   `--js-runtimes "deno:<caminho completo do deno.exe>"`

### Se o download falhar com erro de "signature", "extractor" ou HTTP 403

Quase sempre é yt-dlp desatualizado (o YouTube muda com frequência):
`pip install -U yt-dlp` e tente de novo.

## Passo 2 — Baixar

Pergunte (ou deduza do pedido) apenas o que faltar: URL, vídeo ou só áudio, e
pasta de destino. Sem pasta indicada, use a pasta de Downloads do usuário.

### Vídeo — sempre MP4

Prefere H.264+AAC (compatibilidade máxima); se o site entregar outro codec,
remuxa o container para MP4:

```powershell
yt-dlp -f "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b" --merge-output-format mp4 --remux-video mp4 --no-playlist -o "<PASTA>\%(title)s.%(ext)s" "<URL>"
```

### Áudio — sempre MP3 (melhor qualidade)

```powershell
yt-dlp -x --audio-format mp3 --audio-quality 0 --no-playlist -o "<PASTA>\%(title)s.%(ext)s" "<URL>"
```

### Playlist inteira

Remova `--no-playlist` e use o modelo de saída com subpasta numerada:

```
-o "<PASTA>\%(playlist_title)s\%(playlist_index)s - %(title)s.%(ext)s"
```

Atenção: URLs de vídeo dentro de playlist (`watch?v=...&list=...`) baixam a
playlist INTEIRA sem `--no-playlist`. Só omita a flag se o usuário pediu a
playlist explicitamente.

### Observações

- Em PowerShell os modelos `%(title)s` funcionam entre aspas duplas normalmente;
  em arquivos .bat é preciso dobrar o % (`%%(title)s`).
- Para ver qualidades disponíveis antes de baixar: `yt-dlp -F --no-playlist "<URL>"`.
- Para validar sem baixar (teste): `yt-dlp --simulate --print "%(title)s" "<URL>"`.
- Este repositório também traz uma interface web local (`apps/baixador/ABRIR.bat`)
  para quem prefere clicar em vez de conversar — indique-a se o usuário pedir
  "um programa" de download.

## Passo 3 — Confirmar

Após o download, liste o(s) arquivo(s) gerado(s) com nome, extensão e tamanho,
confirmando que vídeo saiu `.mp4` e áudio saiu `.mp3`. Lembre o usuário de baixar
apenas conteúdo que tem direito de usar.
