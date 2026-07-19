# apps/editor — scripts auxiliares do agente Editor

Ferramentas que o agente `editor` (ver `agents/editor.md`) usa para recursos além do
corte básico. Todos recebem caminhos por argumento — nada é hardcoded.

## Scripts

### `detectar_comando_voz.py` — comando de voz embutido no vídeo ("pato preto")
Lê a transcrição (JSON do WhisperX, com timestamps por palavra), acha a palavra-chave
**"pato preto"** (matching fuzzy, tolera erro de transcrição) e separa o conteúdo do
vídeo (antes) do briefing de edição falado (depois). Recua o corte até o silêncio
anterior. Devolve JSON com `corte_em`, `comando`, `confianca`, `cancelado`.

```bash
python detectar_comando_voz.py transcricao.json --silencios silencio.txt
```

Palavra-chave escolhida por robustez fonética: plosivas fortes (P-P-T) resistem melhor
ao STT do que fricativas (uma tentativa com "vaca" virava "faca"). "preto" não colide
com a palavra de marcação de erro ("amarelo/vermelho"), evitando ambiguidade.

### `gen_karaoke.py` — legenda karaokê colorida
Gera um `.ass` de legenda estilo karaokê (a palavra é pintada conforme a fala, efeito
`\kf`) a partir do JSON por-palavra. Aceita a cor de destaque como 5º argumento.

```bash
python gen_karaoke.py transcricao.json saida.ass 300 64 azul
# cores: amarelo(padrão) azul ciano verde vermelho laranja rosa roxo branco | #RRGGBB | &H..
```

### `split_screen.py` — layout dividido ao meio
Durante uma janela de tempo, divide a tela 9:16: metade de cima = a pessoa (zoom-out
leve, cabeça+meio corpo), metade de baixo = referência (imagem/vídeo). Fora da janela,
tela cheia. Transição por corte seco.

```bash
python split_screen.py --video in.mp4 --ref ref.png --ini 5 --fim 8 --out out.mp4 --run
```

### `web-shot/web-shot.js` — print de site/notícia
Captura screenshot de uma página usando o Chrome/Edge já instalado (via
`puppeteer-core`, não baixa Chromium). Fecha banners de cookie automaticamente.

```bash
cd web-shot && npm install        # instala puppeteer-core (uma vez)
node web-shot.js --url "https://exemplo.com" --out shot.png
```

Sites com anti-bot (captcha/paywall) podem bloquear a captura headless — nesse caso,
tente uma URL de artigo específico ou use outra fonte. Não contorne proteções.

## Requisitos
- Python 3.10+ (ffmpeg no PATH para o `split_screen.py`)
- Node 18+ para o `web-shot` (`npm install` na pasta `web-shot/`)
