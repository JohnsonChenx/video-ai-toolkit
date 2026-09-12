#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assets.py - Busca e baixa imagens/videos LICENCIADOS para dark videos,
registrando a atribuicao de cada item em CREDITOS.md (obrigatorio).

Fontes:
  wikimedia  imagens do Wikimedia Commons (SEM chave; CC/dominio publico)
  nasa       imagens da NASA (SEM chave; dominio publico)
  pexels     fotos e videos do Pexels (chave gratis: PEXELS_API_KEY)
  pixabay    fotos e videos do Pixabay (chave gratis: PIXABAY_API_KEY)
  clipe      trecho de video do YouTube — SO baixa se a licenca for
             Creative Commons (checagem dura, sem override)

Exemplos:
  python assets.py wikimedia "green anaconda" --n 6 --dir C:\\DarkVideos\\sucuri\\assets
  python assets.py nasa "amazon river" --n 3 --dir ...\\assets
  python assets.py pexels "anaconda snake" --video --n 4 --dir ...\\assets
  python assets.py clipe https://youtu.be/XXXX --ini 92 --fim 118 --dir ...\\assets

Chaves gratis (2 min): https://www.pexels.com/api/  |  https://pixabay.com/api/docs/
Registrar com: setx PEXELS_API_KEY "..."  (idem PIXABAY_API_KEY)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

try:
    import requests
except ImportError:
    print("[assets] ERRO: pip install requests", file=sys.stderr)
    sys.exit(1)

UA = {"User-Agent": "Documentarista/1.0 (agente local de producao de video)"}


def _slug(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_-]+", "-", s)[:maxlen] or "asset"


def _sufixo(url: str, padrao: str = ".jpg") -> str:
    """Extensao segura a partir de URL (ignora query string e lixo)."""
    ext = Path(url.split("?")[0].split("&")[0]).suffix.lower()
    return ext if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif",
                          ".mp4", ".webm"} else padrao


def _sem_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _creditar(pasta: Path, arquivo: str, fonte: str, autor: str,
              licenca: str, url: str) -> None:
    """Toda peca baixada entra no CREDITOS.md — sem excecao."""
    cred = pasta / "CREDITOS.md"
    if not cred.exists():
        cred.write_text("# Créditos e licenças dos assets\n\n"
                        "| Arquivo | Fonte | Autor | Licença | Origem |\n"
                        "|---------|-------|-------|---------|--------|\n",
                        encoding="utf-8")
    with cred.open("a", encoding="utf-8") as f:
        f.write(f"| {arquivo} | {fonte} | {autor or '?'} | {licenca or '?'} "
                f"| {url} |\n")


def _baixar(url: str, destino: Path) -> bool:
    for tentativa in (1, 2):
        r = requests.get(url, headers=UA, timeout=120, stream=True)
        if r.status_code == 429 and tentativa == 1:
            time.sleep(6)  # rate-limit (Wikimedia limita rajadas): espera e tenta 1x
            continue
        if r.status_code != 200:
            print(f"[assets]   pulei ({r.status_code}): {url[:80]}")
            return False
        with destino.open("wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        time.sleep(1.5)  # cortesia entre downloads — evita o proximo 429
        return True
    return False


# ---------------------------------------------------------------- wikimedia
def cmd_wikimedia(a) -> int:
    api = "https://commons.wikimedia.org/w/api.php"
    # bitmap = so imagem (sem svg/pdf/audio)
    params = {"action": "query", "format": "json", "generator": "search",
              "gsrsearch": f"filetype:bitmap {a.busca}", "gsrnamespace": 6,
              "gsrlimit": a.n * 2, "prop": "imageinfo",
              "iiprop": "url|extmetadata", "iiurlwidth": 1920}
    pages = requests.get(api, params=params, headers=UA, timeout=60)\
        .json().get("query", {}).get("pages", {})
    baixados = 0
    for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
        if baixados >= a.n:
            break
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "?")
        url = ii.get("thumburl") or ii.get("url")
        if not url:
            continue
        nome = f"wm-{_slug(a.busca)}-{baixados+1:02d}{_sufixo(url)}"
        if _baixar(url, a.dir / nome):
            _creditar(a.dir, nome, "Wikimedia Commons",
                      _sem_html(meta.get("Artist", {}).get("value", "")),
                      lic, ii.get("descriptionurl", url))
            baixados += 1
            print(f"[assets] ok: {nome}  [{lic}]")
    print(f"[assets] wikimedia: {baixados} imagens em {a.dir}")
    return 0 if baixados else 2


# --------------------------------------------------------------------- nasa
def cmd_nasa(a) -> int:
    r = requests.get("https://images-api.nasa.gov/search",
                     params={"q": a.busca, "media_type": "image"},
                     headers=UA, timeout=60).json()
    itens = r.get("collection", {}).get("items", [])[:a.n]
    baixados = 0
    for i, item in enumerate(itens, 1):
        d = (item.get("data") or [{}])[0]
        # o manifesto lista os tamanhos; pegar o maior nao-original (~large)
        try:
            tamanhos = requests.get(item["href"], headers=UA, timeout=60).json()
        except Exception:
            continue
        url = next((u for u in tamanhos if "~large" in u),
                   next((u for u in tamanhos if u.lower().endswith(
                       (".jpg", ".png"))), None))
        if not url:
            continue
        nome = f"nasa-{_slug(a.busca)}-{i:02d}{_sufixo(url)}"
        if _baixar(url, a.dir / nome):
            _creditar(a.dir, nome, "NASA", d.get("center", "NASA"),
                      "Domínio público (NASA)",
                      f"https://images.nasa.gov/details/{d.get('nasa_id', '')}")
            baixados += 1
            print(f"[assets] ok: {nome}")
    print(f"[assets] nasa: {baixados} imagens em {a.dir}")
    return 0 if baixados else 2


# ------------------------------------------------------------------- pexels
def cmd_pexels(a) -> int:
    chave = os.environ.get("PEXELS_API_KEY")
    if not chave:
        print("[assets] ERRO: falta PEXELS_API_KEY (gratis em pexels.com/api; "
              'depois: setx PEXELS_API_KEY "sua-chave")', file=sys.stderr)
        return 3
    h = {**UA, "Authorization": chave}
    if a.video:
        r = requests.get("https://api.pexels.com/videos/search", headers=h,
                         params={"query": a.busca, "per_page": a.n,
                                 "orientation": "landscape"}, timeout=60).json()
        baixados = 0
        for i, v in enumerate(r.get("videos", []), 1):
            arqs = sorted(v.get("video_files", []),
                          key=lambda f: f.get("width") or 0, reverse=True)
            arq = next((f for f in arqs if (f.get("width") or 0) <= 1920), arqs[0] if arqs else None)
            if not arq:
                continue
            nome = f"px-{_slug(a.busca)}-{i:02d}.mp4"
            if _baixar(arq["link"], a.dir / nome):
                _creditar(a.dir, nome, "Pexels",
                          v.get("user", {}).get("name", "?"),
                          "Pexels License (uso livre)", v.get("url", ""))
                baixados += 1
                print(f"[assets] ok: {nome} ({arq.get('width')}x{arq.get('height')})")
    else:
        r = requests.get("https://api.pexels.com/v1/search", headers=h,
                         params={"query": a.busca, "per_page": a.n,
                                 "orientation": "landscape"}, timeout=60).json()
        baixados = 0
        for i, p in enumerate(r.get("photos", []), 1):
            nome = f"px-{_slug(a.busca)}-{i:02d}.jpg"
            if _baixar(p["src"]["large2x"], a.dir / nome):
                _creditar(a.dir, nome, "Pexels", p.get("photographer", "?"),
                          "Pexels License (uso livre)", p.get("url", ""))
                baixados += 1
                print(f"[assets] ok: {nome}")
    print(f"[assets] pexels: {baixados} itens em {a.dir}")
    return 0 if baixados else 2


# ------------------------------------------------------------------ pixabay
def cmd_pixabay(a) -> int:
    chave = os.environ.get("PIXABAY_API_KEY")
    if not chave:
        print("[assets] ERRO: falta PIXABAY_API_KEY (gratis em pixabay.com/api/docs; "
              'depois: setx PIXABAY_API_KEY "sua-chave")', file=sys.stderr)
        return 3
    base = "https://pixabay.com/api/videos/" if a.video else "https://pixabay.com/api/"
    r = requests.get(base, params={"key": chave, "q": a.busca,
                                   "per_page": max(a.n, 3), "safesearch": "true"},
                     headers=UA, timeout=60).json()
    baixados = 0
    for i, h in enumerate(r.get("hits", [])[:a.n], 1):
        if a.video:
            v = h.get("videos", {}).get("large") or h.get("videos", {}).get("medium")
            url, nome = v.get("url"), f"pb-{_slug(a.busca)}-{i:02d}.mp4"
        else:
            url, nome = h.get("largeImageURL"), f"pb-{_slug(a.busca)}-{i:02d}.jpg"
        if url and _baixar(url, a.dir / nome):
            _creditar(a.dir, nome, "Pixabay", h.get("user", "?"),
                      "Pixabay License (uso livre)", h.get("pageURL", ""))
            baixados += 1
            print(f"[assets] ok: {nome}")
    print(f"[assets] pixabay: {baixados} itens em {a.dir}")
    return 0 if baixados else 2


# -------------------------------------------------------------------- clipe
def cmd_clipe(a) -> int:
    """Baixa um TRECHO de video do YouTube. So licenca Creative Commons."""
    meta = subprocess.run(["yt-dlp", "--no-warnings", "--skip-download",
                           "--dump-json", a.url],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=90)
    if not meta.stdout.strip():
        print(f"[assets] ERRO: nao li metadados: {meta.stderr[:300]}",
              file=sys.stderr)
        return 2
    d = json.loads(meta.stdout.splitlines()[0])
    lic = d.get("license") or "Padrao do YouTube"
    if "creative commons" not in lic.lower():
        print(f"[assets] BLOQUEADO: licenca do video e '{lic}', nao Creative "
              "Commons. Reuso de trecho violaria direitos autorais — escolha "
              "outro video (o ranking do hype.py marca os CC) ou use stock.",
              file=sys.stderr)
        return 4
    nome = f"cc-{_slug(d.get('title', 'clipe'))}-{int(a.ini)}s.mp4"
    r = subprocess.run(
        ["yt-dlp", "--no-warnings", "-f",
         "bv*[vcodec^=avc1][height<=1080]+ba[acodec^=mp4a]/bv*+ba/b",
         "--merge-output-format", "mp4", "--no-playlist",
         "--download-sections", f"*{a.ini}-{a.fim}",
         "-o", str(a.dir / nome), a.url],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    if not (a.dir / nome).exists():
        print(f"[assets] ERRO no download: {r.stderr[-400:]}", file=sys.stderr)
        return 2
    _creditar(a.dir, nome, "YouTube (Creative Commons)",
              d.get("channel") or d.get("uploader", "?"), lic,
              d.get("webpage_url", a.url))
    print(f"[assets] ok: {nome}  [{lic}] — atribuicao registrada")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("wikimedia", "nasa", "pexels", "pixabay"):
        s = sub.add_parser(nome)
        s.add_argument("busca")
        s.add_argument("--n", type=int, default=5)
        s.add_argument("--dir", type=Path, required=True)
        if nome in ("pexels", "pixabay"):
            s.add_argument("--video", action="store_true",
                           help="buscar videos em vez de fotos")
    c = sub.add_parser("clipe")
    c.add_argument("url")
    c.add_argument("--ini", type=float, required=True, help="inicio em segundos")
    c.add_argument("--fim", type=float, required=True, help="fim em segundos")
    c.add_argument("--dir", type=Path, required=True)
    a = ap.parse_args()
    a.dir.mkdir(parents=True, exist_ok=True)
    return {"wikimedia": cmd_wikimedia, "nasa": cmd_nasa, "pexels": cmd_pexels,
            "pixabay": cmd_pixabay, "clipe": cmd_clipe}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
