#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
confirmar.py - Grava no historico as materias que VIRARAM VIDEO.

Por que existe um passo separado: se o noticias.py marcasse tudo como
"coberto" no momento da busca, uma pauta abandonada no meio do caminho
(video que nao foi produzido, roteiro reprovado) nunca mais reapareceria.
O historico deve refletir o que FOI AO AR, nao o que foi pesquisado.

Uso:
    python confirmar.py dossie.pendente.json
    python confirmar.py dossie.pendente.json --itens 1,3,5
    python confirmar.py --listar

Opcoes:
    --itens 1,3,5   confirma so esses numeros do dossie (default: todos)
    --historico F   arquivo de historico (default historico.json)
    --episodio X    rotulo do episodio (default: data de hoje)
    --listar        mostra o historico e sai
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="Registra no historico o que virou video.")
    p.add_argument("pendente", nargs="?", help="arquivo .pendente.json do dossie")
    p.add_argument("--itens", help="numeros a confirmar, ex: 1,3,5")
    p.add_argument("--historico", default="historico.json")
    p.add_argument("--episodio")
    p.add_argument("--listar", action="store_true")
    a = p.parse_args()

    hist_path = Path(a.historico)
    historico = []
    if hist_path.exists():
        historico = json.loads(hist_path.read_text(encoding="utf-8"))

    if a.listar:
        if not historico:
            print("Historico vazio.")
            return 0
        print(f"{len(historico)} materias ja cobertas:\n")
        for h in historico:
            ep = h.get("episodio", "?")
            print(f"  [{ep}] {h.get('titulo', '')[:78]}")
        return 0

    if not a.pendente:
        p.error("informe o arquivo .pendente.json (ou use --listar)")

    pend_path = Path(a.pendente)
    if not pend_path.exists():
        print(f"Arquivo nao encontrado: {pend_path}", file=sys.stderr)
        return 1

    itens = json.loads(pend_path.read_text(encoding="utf-8"))
    if not itens:
        print("Nada pendente nesse arquivo.")
        return 0

    if a.itens:
        try:
            escolhidos = {int(n.strip()) for n in a.itens.split(",") if n.strip()}
        except ValueError:
            print("--itens aceita numeros separados por virgula, ex: 1,3,5", file=sys.stderr)
            return 1
        fora = escolhidos - set(range(1, len(itens) + 1))
        if fora:
            print(f"Fora do intervalo 1..{len(itens)}: {sorted(fora)}", file=sys.stderr)
            return 1
        itens = [it for i, it in enumerate(itens, 1) if i in escolhidos]

    episodio = a.episodio or datetime.now().strftime("%Y-%m-%d")
    quando = datetime.now().isoformat(timespec="seconds")

    urls = {h.get("url") for h in historico}
    novos = 0
    for it in itens:
        if it.get("url") in urls:
            continue
        historico.append({
            "titulo": it.get("titulo", ""),
            "url": it.get("url", ""),
            "fonte": it.get("fonte", ""),
            "data_materia": it.get("data"),
            "episodio": episodio,
            "confirmado_em": quando,
        })
        novos += 1

    hist_path.write_text(
        json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Episodio '{episodio}': {novos} materia(s) registrada(s).")
    if novos < len(itens):
        print(f"  ({len(itens) - novos} ja estavam no historico)")
    print(f"Historico: {hist_path} ({len(historico)} no total)")
    print("  As proximas buscas nao vao repetir esses assuntos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
