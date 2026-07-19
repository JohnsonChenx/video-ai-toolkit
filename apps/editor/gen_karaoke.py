import json, sys

src = sys.argv[1]
out = sys.argv[2]
# margem inferior (pixels a partir da base) e tamanho de fonte
marginv = int(sys.argv[3]) if len(sys.argv) > 3 else 300
fontsize = int(sys.argv[4]) if len(sys.argv) > 4 else 64
# cor de PINTAR (a palavra acesa) — argv[5]: nome pt-BR ou &H BGR ASS.
# Karaokê = palavra começa branca e é pintada por esta cor conforme a fala.
cor_arg = sys.argv[5] if len(sys.argv) > 5 else "amarelo"

# ASS usa &H00BBGGRR (BGR, não RGB). Paleta em pt-BR:
_CORES = {
    "amarelo": "&H0020C0FF",  # padrão da casa
    "azul": "&H00FF6820",     # azul vivo
    "ciano": "&H00FFFF00",
    "verde": "&H0000E000",
    "vermelho": "&H004040FF",
    "laranja": "&H000090FF",
    "rosa": "&H00B060FF",
    "roxo": "&H00E040A0",
    "branco": "&H00FFFFFF",
}


def _resolver_cor(v):
    v = v.strip().lower()
    if v.startswith("&h"):            # já é ASS BGR
        return v.upper().replace("&H", "&H", 1)
    if v in _CORES:
        return _CORES[v]
    m = v.lstrip("#")
    if len(m) == 6 and all(c in "0123456789abcdef" for c in m):  # RGB hex → ASS BGR
        r, g, b = m[0:2], m[2:4], m[4:6]
        return f"&H00{b}{g}{r}".upper()
    return _CORES["amarelo"]          # desconhecida → padrão da casa


primary = _resolver_cor(cor_arg)      # cor acesa (pintada)

data = json.load(open(src, encoding="utf-8"))
words = []
for seg in data["segments"]:
    for w in seg.get("words", []):
        if "start" in w and "end" in w:
            words.append([w["start"], w["end"], w["word"].strip()])

# preenche palavras sem timestamp (raras) interpolando
for i, w in enumerate(words):
    if w[0] is None:
        w[0] = words[i-1][1] if i else 0.0
    if w[1] is None:
        w[1] = w[0] + 0.3

# agrupa em blocos de no maximo N palavras / ate uma pausa grande / apos pontuacao
MAX_WORDS = 5
GAP = 0.7
blocks, cur = [], []
for i, w in enumerate(words):
    prev_punct = cur and cur[-1][2].rstrip().endswith((",", ".", "?", "!", "…", ";", ":"))
    if cur and (len(cur) >= MAX_WORDS or w[0] - cur[-1][1] > GAP or (prev_punct and len(cur) >= 2)):
        blocks.append(cur); cur = []
    cur.append(w)
if cur:
    blocks.append(cur)

def cs(t):  # centiseconds ASS time
    h = int(t // 3600); t -= h*3600
    m = int(t // 60); t -= m*60
    s = int(t); c = int(round((t - s) * 100))
    if c == 100:
        c = 0; s += 1
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"

header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kar,Arial,{fontsize},{primary},&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,{marginv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, Effect, Text
"""

# PADRAO: SecondaryColour (antes de acender) = branco; PrimaryColour (aceso) = amarelo
# => a palavra comeca branca e vai sendo PINTADA pela cor conforme a fala
# usamos \k: a palavra comeca na SecondaryColour e vira PrimaryColour no seu tempo
lines = []
for blk in blocks:
    start = blk[0][0]
    end = blk[-1][1]
    text = ""
    prev_end = start
    # remove so pontuacao ORFA no inicio do bloco (a do meio/fim fica)
    blk[0][2] = blk[0][2].lstrip(",.;:!?…-— ")
    blk[:] = [w for w in blk if w[2]]
    for s, e, tok in blk:
        # gap antes da palavra vira \k parado (mantem apagado)
        gap = int(round((s - prev_end) * 100))
        if gap > 0:
            text += f"{{\\k{gap}}}"
        dur = max(1, int(round((e - s) * 100)))
        text += f"{{\\kf{dur}}}{tok} "
        prev_end = e
    # Formato: Layer,Start,End,Style,Name,MarginL,MarginR,Effect,Text (9 campos)
    # campos: 0(Layer) start end Kar(Style) ''(Name) 0(MarginL) 0(MarginR) ''(Effect) text
    lines.append(f"Dialogue: 0,{cs(start)},{cs(end)},Kar,,0,0,,{text.strip()}")

open(out, "w", encoding="utf-8").write(header + "\n".join(lines) + "\n")
print(f"{len(blocks)} blocos, {len(words)} palavras -> {out}")
