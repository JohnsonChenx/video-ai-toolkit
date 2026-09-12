#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
noticias.py - Busca noticias recentes sobre um tema, deduplica contra os
episodios ja produzidos e entrega um dossie pronto para roteirizacao.

Nao usa chave de API: le os feeds RSS publicos do Google Noticias e de
veiculos abertos. Cada item carrega a DATA e a FONTE - roteiro sem data
verificavel e roteiro que nao deveria ir ao ar.

Uso:
    python noticias.py "inteligencia artificial" --horas 48
    python noticias.py "forex" "banco central" --horas 24 --max 15
    python noticias.py "IA" --historico historico.json --saida dossie.md

Opcoes:
    --horas N       so noticias das ultimas N horas (default 48)
    --max N         maximo de itens no dossie (default 12)
    --historico F   json com o que ja foi coberto (default historico.json)
    --saida F       arquivo markdown de saida (default dossie.md)
    --idioma        pt-BR (default) ou en
    --sem-dedup     ignora o historico (util para o primeiro episodio)

O historico guarda TITULO + URL + data de cada materia ja usada. A
deduplicacao compara por URL exata e por similaridade de titulo, porque a
mesma noticia reaparece com manchete reescrita em veiculo diferente.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) noticias.py/1.0"
TIMEOUT = 20

# Google Noticias RSS: cobre milhares de veiculos, sem chave, com data.
GNEWS = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"

LOCALES = {
    "pt-BR": {"hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"},
    "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
}


def _norm(texto: str) -> str:
    """minusculas, sem acento, so letras e numeros - para comparar titulos."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def _parecidos(a: str, b: str, limiar: float = 0.82) -> bool:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio() >= limiar


# --------------------------------------------------------------------------
# Trava de tema sensivel.
#
# Existe porque o teste real mostrou que politica se infiltra sozinha: uma
# busca por "inteligencia artificial" trouxe "TSE rejeita punicao a Flavio
# Bolsonaro por video criado com IA". Ninguem pediu politica - ela veio.
#
# Isto NAO censura nada: apenas MARCA o item para que a decisao de usar ou
# nao seja consciente. Plataformas de avatar (HeyGen, Synthesia) proibem
# conteudo politico/eleitoral a criterio proprio, e a conta pode ser
# suspensa DEPOIS do video publicado.
# --------------------------------------------------------------------------
TERMOS_SENSIVEIS = {
    "politica/eleicoes": [
        "eleicao", "eleicoes", "eleitoral", "tse", "stf", "urna", "voto",
        "presidente", "presidencia", "senador", "senado", "deputado",
        "camara dos deputados", "congresso", "ministro", "ministerio",
        "governador", "prefeito", "vereador", "partido", "candidato",
        "campanha eleitoral", "impeachment", "cpi", "bolsonaro", "lula",
        "planalto", "esquerda", "direita",
    ],
    "saude publica": [
        "vacina", "vacinacao", "pandemia", "epidemia", "surto", "anvisa",
        "ministerio da saude", "contagio", "virus", "oms",
    ],
    "judicial/criminal": [
        "condenado", "condenacao", "preso", "prisao", "indiciado",
        "denunciado", "acusado", "investigado", "operacao policial",
        "homicidio", "assassinato", "atentado",
    ],
}


def classificar_risco(item: dict) -> list[str]:
    """Categorias sensiveis detectadas no titulo/resumo. Lista vazia = limpo."""
    alvo = _norm(f"{item['titulo']} {item.get('resumo', '')}")
    achadas = []
    for categoria, termos in TERMOS_SENSIVEIS.items():
        if any(re.search(rf"\b{re.escape(t)}\b", alvo) for t in termos):
            achadas.append(categoria)
    return achadas



def buscar(termo: str, idioma: str = "pt-BR") -> list[dict]:
    loc = LOCALES.get(idioma, LOCALES["pt-BR"])
    url = GNEWS.format(q=urllib.parse.quote(termo), **loc)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            xml = r.read()
    except Exception as e:
        print(f"  [aviso] falha ao buscar '{termo}': {e}", file=sys.stderr)
        return []

    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError as e:
        print(f"  [aviso] RSS invalido para '{termo}': {e}", file=sys.stderr)
        return []

    itens = []
    for it in raiz.iterfind(".//item"):
        titulo = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        fonte = it.findtext("{*}source") or it.findtext("source") or ""
        desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        desc = desc.replace("&nbsp;", " ").replace("&amp;", "&")
        desc = re.sub(r"\s+", " ", desc).strip()
        # O RSS do Google repete o titulo na descricao; nesse caso nao ha resumo.
        if _norm(desc).startswith(_norm(titulo)[:40]):
            desc = ""

        # O Google poe " - Veiculo" no fim do titulo; separa.
        if not fonte and " - " in titulo:
            titulo, _, fonte = titulo.rpartition(" - ")

        quando = None
        for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                quando = datetime.strptime(pub, fmt)
                break
            except ValueError:
                continue
        if quando and quando.tzinfo is None:
            quando = quando.replace(tzinfo=timezone.utc)

        if titulo and link:
            itens.append({
                "titulo": titulo.strip(),
                "url": link,
                "fonte": (fonte or "").strip() or "nao identificada",
                "data": quando.isoformat() if quando else None,
                "resumo": desc[:400],
                "termo": termo,
            })
    return itens


def carregar_historico(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [aviso] historico ilegivel ({e}); tratando como vazio.", file=sys.stderr)
        return []


def ja_coberto(item: dict, historico: list[dict]) -> str | None:
    """Devolve o motivo se ja foi coberto, senao None."""
    for h in historico:
        if item["url"] == h.get("url"):
            return "mesma URL"
        if _parecidos(item["titulo"], h.get("titulo", "")):
            return f"titulo ~ '{h.get('titulo', '')[:60]}'"
    return None


def dedup_interno(itens: list[dict]) -> list[dict]:
    """Remove repeticoes DENTRO da colheita (mesma noticia em 5 veiculos)."""
    saida: list[dict] = []
    for it in itens:
        if any(it["url"] == s["url"] or _parecidos(it["titulo"], s["titulo"]) for s in saida):
            continue
        saida.append(it)
    return saida


def main() -> int:
    p = argparse.ArgumentParser(
        description="Busca noticias recentes e deduplica contra episodios anteriores.")
    p.add_argument("termos", nargs="+", help="tema(s) a pesquisar")
    p.add_argument("--horas", type=int, default=48)
    p.add_argument("--max", type=int, default=12)
    p.add_argument("--historico", default="historico.json")
    p.add_argument("--saida", default="dossie.md")
    p.add_argument("--idioma", default="pt-BR", choices=list(LOCALES))
    p.add_argument("--sem-dedup", action="store_true")
    p.add_argument("--so-seguro", action="store_true",
                   help="descarta itens marcados como tema sensivel "
                        "(politica, saude publica, judicial)")
    a = p.parse_args()

    hist_path = Path(a.historico)
    historico = [] if a.sem_dedup else carregar_historico(hist_path)
    if historico:
        print(f"Historico: {len(historico)} materias ja cobertas.")

    brutos: list[dict] = []
    for termo in a.termos:
        achados = buscar(termo, a.idioma)
        print(f"  '{termo}': {len(achados)} itens")
        brutos.extend(achados)

    if not brutos:
        print("\nNenhuma noticia encontrada. Verifique o termo ou a conexao.")
        return 1

    corte = datetime.now(timezone.utc) - timedelta(hours=a.horas)
    recentes, sem_data = [], 0
    for it in brutos:
        if not it["data"]:
            sem_data += 1
            continue
        if datetime.fromisoformat(it["data"]) >= corte:
            recentes.append(it)

    recentes.sort(key=lambda x: x["data"], reverse=True)
    unicos = dedup_interno(recentes)

    novos, repetidos = [], []
    for it in unicos:
        motivo = ja_coberto(it, historico) if historico else None
        (repetidos if motivo else novos).append(
            {**it, "motivo": motivo} if motivo else it)

    for it in novos:
        it["risco"] = classificar_risco(it)

    limpos = [it for it in novos if not it["risco"]]
    sensiveis = [it for it in novos if it["risco"]]

    if a.so_seguro:
        selecao = limpos[: a.max]
    else:
        selecao = novos[: a.max]

    print(f"\n{len(brutos)} coletados -> {len(recentes)} nas ultimas {a.horas}h "
          f"-> {len(unicos)} unicos -> {len(novos)} ineditos -> {len(selecao)} no dossie")
    if sem_data:
        print(f"  ({sem_data} descartados por nao trazerem data - regra da casa)")
    if repetidos:
        print(f"  ({len(repetidos)} ja cobertos em episodios anteriores)")

    if sensiveis:
        print()
        print(f"  ATENCAO: {len(sensiveis)} item(ns) com tema sensivel:")
        for it in sensiveis[:5]:
            print(f"    [{', '.join(it['risco'])}] {it['titulo'][:70]}")
        if a.so_seguro:
            print("    -> descartados (--so-seguro ativo)")
        else:
            print("    -> mantidos no dossie e MARCADOS. Plataformas de avatar")
            print("       (HeyGen/Synthesia) proibem conteudo politico a criterio")
            print("       proprio. Decida item a item antes de produzir.")

    if not selecao:
        print("\nNada novo desde o ultimo episodio. Nao ha o que produzir.")
        return 2

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    linhas = [
        f"# Dossie de noticias - {', '.join(a.termos)}",
        "",
        f"Coletado em {agora} | janela: ultimas {a.horas}h | {len(selecao)} materias ineditas",
        "",
        "> Cada item traz data e fonte. Roteiro que afirmar algo fora daqui",
        "> precisa de verificacao propria antes de ir ao ar.",
        "",
    ]
    for i, it in enumerate(selecao, 1):
        quando = datetime.fromisoformat(it["data"]).strftime("%d/%m %H:%M")
        aviso = ""
        if it.get("risco"):
            aviso = f"> **TEMA SENSIVEL: {', '.join(it['risco'])}** - risco de moderacao em plataforma de avatar."
        linhas += [
            f"## {i}. {it['titulo']}",
            "",
        ]
        if aviso:
            linhas += [aviso, ""]
        linhas += [
            f"- **Fonte:** {it['fonte']}",
            f"- **Publicado:** {quando}",
            f"- **Link:** {it['url']}",
            "",
            it["resumo"] or "_(sem resumo no feed - abrir o link para apurar)_",
            "",
        ]

    if repetidos:
        linhas += ["---", "", "## Descartados por ja terem sido cobertos", ""]
        for it in repetidos[:10]:
            linhas.append(f"- {it['titulo']} ({it['motivo']})")
        linhas.append("")

    Path(a.saida).write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nDossie: {a.saida}")

    pend = Path(a.saida).with_suffix(".pendente.json")
    pend.write_text(json.dumps(selecao, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pendente de confirmacao: {pend}")
    print("  (o historico so e atualizado por confirmar.py, DEPOIS do video pronto)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
