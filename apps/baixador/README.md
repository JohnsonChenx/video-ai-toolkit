# Baixador de Vídeos (interface web local)

Interface amigável para baixar vídeos (MP4) e áudios (MP3) com yt-dlp, sem linha de comando.

## Requisitos

Python 3.10+, yt-dlp e ffmpeg — o `install.ps1` da suíte instala tudo.

## Como usar

Dois cliques em **`ABRIR.bat`** (Windows). O navegador abre em `http://localhost:8765` com:

- Campo de link + escolha **Vídeo (MP4)** ou **Áudio (MP3)**
- **Seletor de pasta de destino** nativo do Windows (botão "📁 Procurar…")
- Opção de baixar a **playlist inteira**
- **Barra de progresso** em tempo real, log técnico e botão de cancelar

Mantenha a janela preta (servidor) aberta enquanto usa. Alternativas de linha de comando: `BAIXAR.bat` (menu interativo) e `baixar.ps1` (CLI com flags `-Audio` e `-Playlist`).

## Formatos garantidos

- Vídeo → sempre **MP4** (prefere H.264+AAC; remux automático de outros codecs)
- Áudio → sempre **MP3** na melhor qualidade
