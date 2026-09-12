#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hype.py - Ranking de hype no YouTube, multi-idioma, sem chave de API.

Recebe uma busca por idioma (as traducoes vem de quem chama), pergunta ao
YouTube via yt-dlp e ranqueia tudo por VIEWS/DIA — a metrica real de hype:
um video de 2M de views em 15 dias esta mais quente que um de 10M em 5 anos.

Duas passadas para nao demorar:
  1. busca rasa (--flat-playlist): titulo, canal, views, duracao — rapida;
  2. metadados completos (data de upload, licenca) SO dos top N por views.

Exemplos:
  python hype.py "sucuri gigante" "giant anaconda" "anaconda gigante"
  python hype.py "abelhas assassinas" "killer bees" --n 20 --top 12 -o ranking
  python hype.py "megalodon" --duracao-min 480   # so videos de 8+ min

Saida: <out>.md (tabela legivel) + <out>.json (dados completos p/ o agente).
Requer yt-dlp no PATH (skill youtube ja instala/configura).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

# Licencas que permitem reuso do VIDEO em si (recorte de trecho).
LICENCA_CC = "creative commons"


def _run_ytdlp(args: list[str], timeout: int = 300) -> str:
    cmd = ["yt-dlp", "--no-warnings", "--ignore-errors"] + args
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    # yt-dlp devolve != 0 quando ALGUM item da busca falha; o stdout que
    # veio ainda vale — so aborta se nao veio nada.
    if not r.stdout.strip():
        raise RuntimeError(f"yt-dlp sem resultado: {r.stderr.strip()[:400]}")
    return r.stdout


def busca_rasa(query: str, n: int) -> list[dict]:
    """Passada 1: busca flat — 1 requisicao, metadados parciais."""
    out = _run_ytdlp([f"ytsearch{n}:{query}", "--flat-playlist", "--dump-json"])
    itens = []
    for linha in out.splitlines():
        try:
            d = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if d.get("view_count") is None:
            continue  # lives agendadas, itens deletados
        itens.append({
            "id": d.get("id"),
            "titulo": d.get("title", ""),
            "canal": d.get("channel") or d.get("uploader") or "?",
            "views": int(d.get("view_count") or 0),
            "duracao_s": int(d.get("duration") or 0),
            "url": d.get("url") or f"https://www.youtube.com/watch?v={d.get('id')}",
            "busca": query,
        })
    return itens


def detalhar(video: dict) -> dict:
    """Passada 2: metadados completos de UM video (data, licenca)."""
    try:
        out = _run_ytdlp([video["url"], "--skip-download", "--dump-json"],
                         timeout=60)
        d = json.loads(out.splitlines()[0])
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired,
            IndexError):
        return video  # fica sem data; views/dia vira None e vai pro fim
    up = d.get("upload_date")  # AAAAMMDD
    if up:
        idade = max((date.today() - datetime.strptime(up, "%Y%m%d").date()).days, 1)
        video["upload"] = f"{up[6:8]}/{up[4:6]}/{up[:4]}"
        video["idade_dias"] = idade
        video["views_dia"] = round(video["views"] / idade)
    video["licenca"] = d.get("license") or "Padrao do YouTube"
    video["cc"] = LICENCA_CC in (d.get("license") or "").lower()
    video["views"] = int(d.get("view_count") or video["views"])
    return video


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M".replace(".", ",")
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def fmt_dur(s: int) -> str:
    return f"{s//60}:{s%60:02d}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ranking de hype (views/dia) no YouTube, multi-idioma.")
    ap.add_argument("buscas", nargs="+",
                    help="uma busca por idioma, ex.: 'sucuri gigante' 'giant anaconda'")
    ap.add_argument("--n", type=int, default=25,
                    help="resultados da busca rasa POR idioma (default 25)")
    ap.add_argument("--top", type=int, default=10,
                    help="quantos detalhar por idioma na passada 2 (default 10)")
    ap.add_argument("--duracao-min", type=int, default=120,
                    help="descartar videos mais curtos que isso, em s (default 120 — corta Shorts)")
    ap.add_argument("--saida", "-o", type=Path, default=Path("ranking"),
                    help="prefixo dos arquivos de saida (default ./ranking)")
    args = ap.parse_args()

    todos: list[dict] = []
    vistos: set[str] = set()
    for busca in args.buscas:
        print(f"[hype] buscando: {busca!r} ...", flush=True)
        itens = [v for v in busca_rasa(busca, args.n)
                 if v["duracao_s"] >= args.duracao_min]
        itens.sort(key=lambda v: v["views"], reverse=True)
        novos = [v for v in itens[:args.top] if v["id"] not in vistos]
        vistos.update(v["id"] for v in novos)
        print(f"[hype]   {len(itens)} validos, detalhando top {len(novos)} ...",
              flush=True)
        todos += [detalhar(v) for v in novos]

    todos.sort(key=lambda v: v.get("views_dia") or -1, reverse=True)

    md = args.saida.with_suffix(".md")
    js = args.saida.with_suffix(".json")
    js.write_text(json.dumps(todos, ensure_ascii=False, indent=2),
                  encoding="utf-8")

    linhas = [
        f"# Ranking de hype — {' | '.join(args.buscas)}",
        f"Gerado em {date.today():%d/%m/%Y} — ordenado por views/dia",
        "",
        "| # | Título | Canal | Views | Views/dia | Publicado | Dur | Licença | Busca |",
        "|---|--------|-------|-------|-----------|-----------|-----|---------|-------|",
    ]
    for i, v in enumerate(todos, 1):
        lic = "**CC** ✅" if v.get("cc") else "padrão"
        # '|' no titulo/canal quebraria a tabela markdown
        v["titulo"] = v["titulo"].replace("|", "–")
        v["canal"] = v["canal"].replace("|", "–")
        linhas.append(
            f"| {i} | [{v['titulo'][:60]}]({v['url']}) | {v['canal'][:25]} "
            f"| {fmt_num(v['views'])} | {fmt_num(v['views_dia']) if v.get('views_dia') else '?'} "
            f"| {v.get('upload', '?')} | {fmt_dur(v['duracao_s'])} | {lic} | {v['busca'][:20]} |")
    n_cc = sum(1 for v in todos if v.get("cc"))
    linhas += ["", f"Total: {len(todos)} vídeos · {n_cc} com licença Creative "
                   f"Commons (trechos reutilizáveis com atribuição)."]
    md.write_text("\n".join(linhas), encoding="utf-8")

    print(f"[hype] OK: {len(todos)} videos -> {md} + {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
