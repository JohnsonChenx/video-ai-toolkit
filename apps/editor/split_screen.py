# -*- coding: utf-8 -*-
"""
split_screen.py — layout dividido para vídeo 9:16 (recurso do agente editor).

Durante uma janela de tempo, divide a tela ao meio: metade de CIMA = você (com
zoom-out leve, cabeça + meio corpo visível), metade de BAIXO = referência
(imagem/animação/vídeo). Fora da janela, volta ao vídeo em tela cheia.
Transição: corte seco (entra/sai instantâneo) — default do usuário (2026-07-19).

Gera o comando ffmpeg (filtergraph). Uso via --emit para imprimir o filtro, ou
--run para executar direto.

Uso:
  python split_screen.py --video IN.mp4 --ref REF.(png|mp4) --ini 5.0 --fim 8.0 \
      --out OUT.mp4 [--zoom 1.0] [--foco-y 0.45] [--run]

Parâmetros (defaults validados em teste real 2026-07-19 — cabeça+meio corpo visível):
  --zoom    quanto da largura do vídeo a faixa de cima usa (1.0 = largura cheia,
            mostra cabeça aos ombros/peito; <1 dá zoom-in no rosto)
  --foco-y  centro vertical do recorte (0=topo, 1=base). 0.45 ≈ cabeça+meio corpo
            para selfie com rosto no terço superior.

Saída 9:16 fixa 1080x1920 (metade = 1080x960).
"""
import argparse
import subprocess
import os

W, H = 1080, 1920
HALF = H // 2  # 960


def build_filter(ini, fim, zoom, foco_y, ref_is_video):
    """
    Monta o filtergraph.

    - [base] = vídeo 9:16 tela cheia (fora da janela mostra isso).
    - [top]  = recorte cabeça+meio corpo do vídeo, escalado p/ 1080x960.
    - [bot]  = referência escalada/cropada p/ 1080x960 (cover).
    - [split]= vstack de top+bot.
    - overlay do [split] sobre [base] só entre ini..fim (corte seco via enable).

    Valores de crop são PRÉ-CALCULADOS em Python (o vídeo é sempre 1080x1920) para
    evitar clip()/min()/max() no filtergraph — vírgulas dentro de função quebram o
    parser do ffmpeg ("No such filter: '0'"). Lição do teste 2026-07-19.
    """
    crop_w = round(zoom * W)
    crop_h = round(crop_w * HALF / W)           # mesma proporção do slot de cima (1080:960)
    crop_x = round((W - crop_w) / 2)            # centralizado horizontalmente
    # centro vertical em foco_y, limitado às bordas [0, H-crop_h]
    crop_y = round(H * foco_y - crop_h / 2)
    crop_y = max(0, min(crop_y, H - crop_h))

    top = (
        f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={W}:{HALF},setsar=1[top]"
    )

    ref_in = "[1:v]"
    # referência: cobre 1080x960 sem distorcer (scale cover + crop central)
    bot = (
        f"{ref_in}scale={W}:{HALF}:force_original_aspect_ratio=increase,"
        f"crop={W}:{HALF},setsar=1[bot]"
    )

    stack = "[top][bot]vstack=inputs=2[split]"
    # base = vídeo cheio; overlay do split só na janela (corte seco)
    over = (
        f"[0:v]scale={W}:{H},setsar=1[base];"
        f"[base][split]overlay=0:0:enable='between(t,{ini},{fim})'[outv]"
    )
    return ";".join([top, bot, stack, over])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--ref", required=True, help="imagem (png/jpg) ou vídeo (mp4)")
    ap.add_argument("--ini", type=float, required=True)
    ap.add_argument("--fim", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--foco-y", type=float, default=0.45, dest="foco_y")
    ap.add_argument("--emit", action="store_true", help="só imprime o filtergraph")
    ap.add_argument("--run", action="store_true", help="executa o ffmpeg")
    args = ap.parse_args()

    ref_is_video = os.path.splitext(args.ref)[1].lower() in (".mp4", ".mov", ".webm", ".mkv")
    fg = build_filter(args.ini, args.fim, args.zoom, args.foco_y, ref_is_video)

    if args.emit and not args.run:
        print(fg)
        return

    # imagem estática precisa de -loop 1 -t (senão trava) ; vídeo entra normal
    ref_input = ["-i", args.ref] if ref_is_video else ["-loop", "1", "-t", str(args.fim - args.ini + 1), "-i", args.ref]

    cmd = [
        "ffmpeg", "-y",
        "-i", args.video,
        *ref_input,
        "-filter_complex", fg,
        "-map", "[outv]", "-map", "0:a?",
        "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "23",
        "-c:a", "copy",
        args.out,
    ]
    print("RUN:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ERRO ffmpeg:\n", r.stderr[-1500:])
        raise SystemExit(1)
    print("OK ->", args.out)


if __name__ == "__main__":
    main()
