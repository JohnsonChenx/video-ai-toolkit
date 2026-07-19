# -*- coding: utf-8 -*-
"""
gen_bloco_caps.py — legenda em BLOCO-CAPS (estilo InvestNews) para o agente editor.

Diferente do gen_karaoke.py (palavra pintada com \\kf), aqui o bloco inteiro entra
de uma vez, TODO EM MAIÚSCULAS, branco com contorno escuro, posicionado na ALTURA
DO PEITO (não no rodapé). Blocos curtos (2-6 palavras) que trocam rápido.

Uso:
  python gen_bloco_caps.py <transcricao.json> <saida.ass> [marginv] [fontsize]

  marginv  distância da BASE em px (PlayResY=1920). Default 560 ≈ altura do peito.
  fontsize default 66.

O .json é o do WhisperX (segments[].words[] com start/end/word).
Queimar com: ffmpeg -i video.mp4 -vf "ass=saida.ass" ...
"""
import json
import sys

src = sys.argv[1]
out = sys.argv[2]
marginv = int(sys.argv[3]) if len(sys.argv) > 3 else 560
fontsize = int(sys.argv[4]) if len(sys.argv) > 4 else 66

data = json.load(open(src, encoding="utf-8"))
words = []
for seg in data["segments"]:
    for w in seg.get("words", []):
        if w.get("word", "").strip():
            words.append([w.get("start"), w.get("end"), w["word"].strip()])

# preenche timestamps ausentes por interpolação (mesma lógica do gen_karaoke)
for i, w in enumerate(words):
    if w[0] is None:
        w[0] = words[i - 1][1] if i else 0.0
    if w[1] is None:
        w[1] = w[0] + 0.3

# agrupa em blocos: máx 5 palavras / pausa > 0.6s / após pontuação forte
MAX_WORDS = 5
GAP = 0.6
blocks, cur = [], []
for w in words:
    prev_punct = cur and cur[-1][2].rstrip().endswith((".", "?", "!", "…", ";", ":"))
    if cur and (len(cur) >= MAX_WORDS or w[0] - cur[-1][1] > GAP or (prev_punct and len(cur) >= 2)):
        blocks.append(cur)
        cur = []
    cur.append(w)
if cur:
    blocks.append(cur)


def ts(t):
    h = int(t // 3600); t -= h * 3600
    m = int(t // 60); t -= m * 60
    s = int(t); c = int(round((t - s) * 100))
    if c == 100:
        c = 0; s += 1
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caps,Arial,{fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,3,1,2,60,60,{marginv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, Effect, Text
"""

lines = []
for blk in blocks:
    start, end = blk[0][0], blk[-1][1]
    # bloco seguinte cola no fim deste (sem buraco visual entre blocos contíguos)
    texto = " ".join(w[2] for w in blk).strip()
    texto = texto.upper()
    # Dialogue: EXATAMENTE 9 campos (vírgula extra = vírgula fantasma no texto)
    lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Caps,,0,0,,{texto}")

open(out, "w", encoding="utf-8").write(header + "\n".join(lines) + "\n")
print(f"{len(blocks)} blocos CAPS, {len(words)} palavras -> {out}")
