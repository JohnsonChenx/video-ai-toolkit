# -*- coding: utf-8 -*-
"""
Legendas nativas primeiro — atalho do pipeline Escriba para vídeos do YouTube.

Antes de gastar GPU com WhisperX, verifica se o vídeo JÁ TEM legendas (manuais
ou automáticas, pt-BR preferido, inglês como fallback) e as converte em
transcrição pronta. Uma palestra de 2h: legenda = 2 segundos; WhisperX = ~25 min.

Quando usar WhisperX mesmo assim: quando precisar de DIARIZAÇÃO (quem falou o
quê) — legenda não separa falantes — ou quando a legenda automática for ruim.

Uso:
    python legendas.py "https://www.youtube.com/watch?v=..." [--saida PASTA]

Saídas (na pasta de destino, nomeadas pelo título do vídeo):
    <titulo>.legenda.txt   transcrição com timestamps [MM:SS]
    <titulo>.legenda.json  segmentos {start, end, text}

Parser de VTT adaptado de bradautomates/claude-video (MIT) — dedupe dos cues
rolantes que o YouTube emite em legendas automáticas.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})")
TAG_RE = re.compile(r"<[^>]+>")


def _to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    segs: list[dict] = []
    i = 0
    while i < len(lines):
        m = TS_RE.match(lines[i])
        if not m:
            i += 1
            continue
        start = _to_seconds(*m.groups()[:4])
        end = _to_seconds(*m.groups()[4:])
        i += 1
        cue: list[str] = []
        while i < len(lines) and lines[i].strip():
            t = TAG_RE.sub("", lines[i]).strip()
            if t:
                cue.append(t)
            i += 1
        text = " ".join(cue).strip()
        if text:
            segs.append({"start": round(start, 2), "end": round(end, 2), "text": text})
        i += 1
    # dedupe dos cues rolantes (cada linha aparece 2-3x nas legendas automáticas)
    out: list[dict] = []
    for seg in segs:
        if out and seg["text"] == out[-1]["text"]:
            out[-1]["end"] = seg["end"]
            continue
        if out and seg["text"].startswith(out[-1]["text"] + " "):
            out[-1]["text"] = seg["text"]
            out[-1]["end"] = seg["end"]
            continue
        out.append(seg)
    return out


def _slug(nome: str) -> str:
    s = re.sub(r"[^\w\sÀ-ÿ-]", "", nome, flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", s)[:80] or "video"


def baixar_legendas(url: str, destino: Path) -> tuple[Path | None, str, Path]:
    """Baixa legendas pt/en em VTT (sem baixar o vídeo).

    Devolve (vtt, título, pasta_tmp). O chamador DEVE apagar pasta_tmp ao final
    (regra da casa: só o entregável final permanece na máquina)."""
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp não encontrado. Instale: pip install -U yt-dlp")
    tmp = Path(tempfile.mkdtemp(prefix="legendas-"))
    subprocess.run(["yt-dlp", "--skip-download", "--write-info-json",
                    "--write-subs", "--write-auto-subs",
                    "--sub-langs", "pt.*,en.*", "--sub-format", "vtt",
                    "--convert-subs", "vtt", "--no-playlist", "--ignore-errors",
                    "-o", str(tmp / "video.%(ext)s"), "--", url],
                   stdout=sys.stderr, stderr=sys.stderr)
    titulo = "video"
    info = tmp / "video.info.json"
    if info.exists():
        try:
            titulo = _slug(json.loads(info.read_text(encoding="utf-8")).get("title") or "video")
        except Exception:
            pass
    candidatos = sorted(tmp.glob("video*.vtt"))
    # preferência: pt-BR > pt > en
    for marcadores in ((".pt-BR.", ".pt."), (".en.", ".en-US.", ".en-orig.")):
        pref = [c for c in candidatos if any(m in c.name for m in marcadores)]
        if pref:
            return pref[0], titulo, tmp
    return (candidatos[0], titulo, tmp) if candidatos else (None, titulo, tmp)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="URL do vídeo (YouTube etc.)")
    ap.add_argument("--saida", default=".", help="Pasta de destino (default: atual)")
    args = ap.parse_args()

    destino = Path(args.saida).expanduser().resolve()
    destino.mkdir(parents=True, exist_ok=True)

    vtt, titulo, tmp = baixar_legendas(args.url, destino)
    try:
        if vtt is None:
            print("SEM_LEGENDAS: o vídeo não tem legendas pt/en — use o pipeline "
                  "WhisperX (transcrever.py) sobre o áudio baixado.")
            sys.exit(3)

        segs = parse_vtt(vtt)
        if not segs:
            print("SEM_LEGENDAS: arquivo de legenda vazio/ilegível — use WhisperX.")
            sys.exit(3)

        idioma = ".pt" if ".pt" in vtt.name else (".en" if ".en" in vtt.name else "")
    finally:
        # regra da casa: nada de temporário sobrevive ao processo
        shutil.rmtree(tmp, ignore_errors=True)
    txt = destino / f"{titulo}.legenda.txt"
    with open(txt, "w", encoding="utf-8") as f:
        for s in segs:
            m, sec = divmod(int(s["start"]), 60)
            f.write(f"[{m:02d}:{sec:02d}] {s['text']}\n")
    jsn = destino / f"{titulo}.legenda.json"
    with open(jsn, "w", encoding="utf-8") as f:
        json.dump({"segments": segs, "idioma": idioma.strip("."),
                   "fonte": "legendas nativas (yt-dlp)"}, f, ensure_ascii=False, indent=1)

    print(f"OK: {len(segs)} segmentos (idioma{idioma or ' desconhecido'})")
    print(f"  {txt}")
    print(f"  {jsn}")
    print("Lembrete: legendas NÃO separam falantes — para diarização use o WhisperX.")


if __name__ == "__main__":
    main()
