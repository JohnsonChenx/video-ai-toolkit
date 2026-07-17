# Escriba (app GUI de transcrição — Windows)

Transcrição de áudio/vídeo em pt-BR com **separação de falantes**, 100% local.

## Qualidade de áudio automática

Antes de cada transcrição, o `audio_quality.py` mede o SNR do áudio (fala vs.
piso de ruído nas pausas) e detecta voz abafada. Se precisar, aplica o melhor
tratamento sozinho — RNNoise (zero instalação, modelo baixa na 1ª vez),
DeepFilterNet ou Resemble Enhance se instalados — gerando `<nome>.limpo.wav`
**sem tocar no original**. Áudio limpo passa direto (denoise desnecessário
borra consoantes). Controle: `--denoise auto|off|forcar` no `transcrever.py`.

## Requisitos

1. Rode o instalador da suíte com a flag do Escriba: `install.ps1 -Escriba` (instala PySide6 + keyboard)
2. A pipeline pesada (WhisperX + pyannote + CUDA) é instalada pelo **agente `escriba`** do Claude Code — peça a ele: *"prepara o ambiente de transcrição"*. Ele detecta o que falta, instala o que dá sozinho e te guia no restante (conta HuggingFace + token, exigidos pelos modelos de diarização).

## Como usar

`Iniciar Escriba.bat` abre a GUI (tema escuro):

- **Arrasta e solta** um áudio/vídeo ou pasta inteira → transcrição com tags `[SPEAKER_XX]`
- **Ditado global**: segure **Ctrl+Alt+D** em qualquer programa, fale, solte — o texto aparece no cursor
- **Resumir em tópicos / Ata da reunião**: via Ollama local (grátis) ou Claude API (`ANTHROPIC_API_KEY`)

Saídas: `<nome>.txt`, `<nome>.srt`, `<nome>.json` (+ `.topicos.md` / `.ata.md` nos resumos).

## Pegadinha conhecida

No Python da Microsoft Store, `pip install PySide6` pode terminar com OSError de caminho longo — **o pacote fica funcional mesmo assim**. Teste com `python -c "from PySide6.QtWidgets import QApplication"` antes de reinstalar.
