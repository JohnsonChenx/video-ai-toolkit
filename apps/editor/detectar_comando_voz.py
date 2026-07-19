# -*- coding: utf-8 -*-
"""
detectar_comando_voz.py — engrenagem 0 do agente editor.

Lê o .json da transcrição do bruto (WhisperX, timestamps por palavra) e procura
a PALAVRA-CHAVE de comando de voz ("pato preto"). Tudo que o usuário falar
DEPOIS da palavra-chave é o briefing de edição; tudo ANTES é o conteúdo do vídeo.

Escolha da palavra-chave (validado em teste real 2026-07-18): "pato preto" usa
plosivas fortes (P, P, T) — os fonemas mais estáveis para STT. A escolha anterior
"vaca amarela" era transcrita como "faca amarela" (V→F, fricativa frágil). "preto"
não colide com "amarelo/vermelho" (palavra de erro do editor) → zero ambiguidade.

Saída (JSON no stdout):
  {
    "encontrou": true,
    "corte_em": 272.4,          # segundos: onde cortar o vídeo (fim do conteúdo)
    "keyword_inicio": 272.9,    # onde a palavra-chave começou a ser falada
    "silencio_usado": true,     # recuou até o silêncio anterior?
    "comando": "quero um corte para stories ...",  # o briefing falado
    "confianca": "alta|media",
    "cancelado": false
  }

Regras (decisões do usuário, 2026-07-18):
- palavra-chave FIXA "pato preto"
- ao detectar, recua automaticamente até o silêncio anterior e corta ali (default)
- matching FUZZY (WhisperX erra: "baca amarela", "vaca amarella", junta/separa)
- se depois da chave vier "cancela"/"cancelar"/"esquece" logo em seguida → cancelado

Uso:
  python detectar_comando_voz.py <transcricao.json> [--silencios silencio.txt] [--recuo 0.4]

O arquivo de silêncios é a saída do ffmpeg silencedetect (linhas silence_start/silence_end).
Se não for passado, o recuo é fixo (--recuo, default 0.4s antes da palavra-chave).
"""
import json
import sys
import re
import unicodedata
import argparse


PALAVRAS_CHAVE = ["pato", "preto"]  # sequência a casar (fuzzy, palavra a palavra)
CANCELADORES = {"cancela", "cancelar", "esquece", "esqueca", "ignora", "ignorar"}


def normalizar(txt):
    """minúsculas, sem acento, só letras — robusto a erro de transcrição."""
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.lower()
    return re.sub(r"[^a-z]", "", txt)


def distancia(a, b):
    """Levenshtein simples (sem libs externas) — tolerância a 1-2 chars de OCR/STT."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def parece(palavra_falada, alvo):
    """palavra falada casa com o alvo? exato ou 1 erro (2 se alvo for longo)."""
    p = normalizar(palavra_falada)
    a = normalizar(alvo)
    if not p:
        return False
    tol = 1 if len(a) <= 5 else 2
    return distancia(p, a) <= tol


def carregar_palavras(caminho_json):
    """Achata o .json do WhisperX numa lista [ (inicio, fim, texto) ] em ordem."""
    data = json.load(open(caminho_json, encoding="utf-8"))
    palavras = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []):
            ini = w.get("start")
            fim = w.get("end")
            tok = (w.get("word") or "").strip()
            if tok:
                palavras.append((ini, fim, tok))
    # preenche timestamps ausentes (raros) por interpolação
    for i, (ini, fim, tok) in enumerate(palavras):
        if ini is None:
            ini = palavras[i - 1][1] if i and palavras[i - 1][1] is not None else 0.0
        if fim is None:
            fim = (ini or 0.0) + 0.3
        palavras[i] = (ini, fim, tok)
    return palavras


def achar_keyword(palavras):
    """Procura a sequência 'vaca amarela' (fuzzy). Retorna o índice da 1ª palavra
    da sequência, ou None. Varre de trás pra frente: o comando fica no FIM do
    vídeo, então a última ocorrência é a que vale (evita falso positivo no meio)."""
    n_chave = len(PALAVRAS_CHAVE)
    for i in range(len(palavras) - n_chave, -1, -1):
        if all(parece(palavras[i + k][2], PALAVRAS_CHAVE[k]) for k in range(n_chave)):
            return i
    return None


def silencio_anterior(caminho_silencios, tempo):
    """Dado o arquivo do silencedetect, retorna o silence_start mais próximo ANTES
    de `tempo` (o começo da pausa que antecede a palavra-chave). None se não achar."""
    if not caminho_silencios:
        return None
    melhor = None
    try:
        txt = open(caminho_silencios, encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    for m in re.finditer(r"silence_start:\s*([\d.]+)", txt):
        t = float(m.group(1))
        if t < tempo and (melhor is None or t > melhor):
            melhor = t
    return melhor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcricao")
    ap.add_argument("--silencios", default=None,
                    help="saída do ffmpeg silencedetect (recua até o silêncio anterior)")
    ap.add_argument("--recuo", type=float, default=0.4,
                    help="recuo fixo (s) antes da palavra-chave se não houver silêncios")
    args = ap.parse_args()

    palavras = carregar_palavras(args.transcricao)
    idx = achar_keyword(palavras)

    if idx is None:
        print(json.dumps({"encontrou": False}, ensure_ascii=False))
        return

    kw_inicio = palavras[idx][0]
    n_chave = len(PALAVRAS_CHAVE)
    resto = palavras[idx + n_chave:]

    # cancelamento: primeira palavra útil após a chave é um cancelador?
    cancelado = False
    for _, _, tok in resto:
        if normalizar(tok):
            cancelado = normalizar(tok) in {normalizar(c) for c in CANCELADORES}
            break

    comando = " ".join(tok for _, _, tok in resto).strip()
    comando = re.sub(r"\s+([,.;:!?…])", r"\1", comando)  # cola pontuação solta

    # ponto de corte: silêncio anterior (preferido) ou recuo fixo
    sil = silencio_anterior(args.silencios, kw_inicio)
    if sil is not None:
        corte_em = round(sil, 3)
        silencio_usado = True
    else:
        corte_em = round(max(0.0, kw_inicio - args.recuo), 3)
        silencio_usado = False

    # confiança: alta se as duas palavras casaram exatas; média se houve fuzzy
    exatas = all(normalizar(palavras[idx + k][2]) == normalizar(PALAVRAS_CHAVE[k])
                 for k in range(n_chave))

    print(json.dumps({
        "encontrou": True,
        "cancelado": cancelado,
        "corte_em": corte_em,
        "keyword_inicio": round(kw_inicio, 3),
        "silencio_usado": silencio_usado,
        "comando": "" if cancelado else comando,
        "confianca": "alta" if exatas else "media",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
