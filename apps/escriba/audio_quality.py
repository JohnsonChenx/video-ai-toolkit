# -*- coding: utf-8 -*-
"""
Análise automática de qualidade de áudio + tratamento (denoise) para o pipeline Escriba.

Mede, via ffmpeg (sem dependências pesadas):
  - SNR estimado: nível de fala (percentil 95 do RMS em janelas de 0,5 s) menos
    piso de ruído (percentil 10 — as pausas da fala revelam o ruído de fundo)
  - Voz abafada: energia da banda de presença (2,5-8 kHz) muito abaixo da banda
    grave da fala (200-2500 Hz) indica gravação muffled/reverberante

Decide o tratamento:
  SNR >= 25 dB            -> nenhum (áudio limpo; denoise só borraria consoantes)
  12 <= SNR < 25 dB       -> rnnoise (leve, via ffmpeg arnndn — zero instalação)
  SNR < 12 dB             -> deepfilternet se instalado, senão rnnoise
  abafado + resemble ok   -> resemble (denoise + dereverb + reconstrução)

Uso:
    python audio_quality.py analisar "audio.m4a" [--json]
    python audio_quality.py tratar "audio.m4a" [--saida out.wav] [--forcar]

Como módulo (usado pelo transcrever.py):
    from audio_quality import preparar_audio
    limpo = preparar_audio(caminho, modo="auto")  # None = usar original
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

# Limiares (dB) — ver racional no docstring
SNR_LIMPO = 25.0
SNR_RUIM = 12.0
ABAFADO_DELTA = -30.0  # (banda 2.5-8k) - (banda 200-2.5k) abaixo disso = abafado
PISO_MINIMO = -90.0    # clamp para janelas de silêncio digital (-inf)

MODELO_RNNN_URL = ("https://raw.githubusercontent.com/GregorR/rnnoise-models/"
                   "master/conjoined-burgers-2018-08-28/cb.rnnn")


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg não encontrado no PATH")
    return exe


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def _rms_janelas(caminho: str) -> list[float]:
    """RMS (dB) por janela de 0,5 s, mono 16 kHz."""
    r = _run([_ffmpeg(), "-hide_banner", "-i", caminho, "-af",
              "aresample=16000,aformat=channel_layouts=mono,"
              "asetnsamples=n=8000,astats=metadata=1:reset=1,"
              "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level:file=-",
              "-f", "null", "-"])
    valores = []
    for m in re.finditer(r"RMS_level=(-?[\d.]+|-inf)", r.stdout or ""):
        v = m.group(1)
        valores.append(PISO_MINIMO if v == "-inf" else max(PISO_MINIMO, float(v)))
    return valores


def _volume_banda(caminho: str, f_low: int, f_high: int) -> float | None:
    """mean_volume (dB) da banda [f_low, f_high] Hz."""
    r = _run([_ffmpeg(), "-hide_banner", "-i", caminho, "-af",
              f"highpass=f={f_low},lowpass=f={f_high},volumedetect",
              "-f", "null", "-"])
    m = re.search(r"mean_volume:\s*(-?[\d.]+)", r.stderr or "")
    return float(m.group(1)) if m else None


def _percentil(valores: list[float], p: float) -> float:
    s = sorted(valores)
    if not s:
        return PISO_MINIMO
    i = min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))
    return s[i]


def _tem_modulo(nome: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(nome) is not None
    except Exception:
        return False


def analisar(caminho: str) -> dict:
    """Mede SNR estimado e abafamento; devolve métricas + recomendação."""
    caminho = str(Path(caminho).resolve())
    rms = _rms_janelas(caminho)
    if len(rms) < 4:
        return {"erro": "áudio curto demais ou ilegível", "recomendacao": "nenhum"}

    fala = _percentil(rms, 95)
    ruido = _percentil(rms, 10)
    snr = fala - ruido

    lf = _volume_banda(caminho, 200, 2500)
    hf = _volume_banda(caminho, 2500, 8000)
    abafado = (lf is not None and hf is not None and (hf - lf) < ABAFADO_DELTA)

    tem_df = _tem_modulo("df") or _tem_modulo("deepfilternet") or shutil.which("deep-filter")
    tem_resemble = _tem_modulo("resemble_enhance")

    if snr >= SNR_LIMPO and not abafado:
        rec, motivo = "nenhum", f"áudio limpo (SNR ~{snr:.0f} dB); denoise só borraria consoantes"
    elif abafado and tem_resemble:
        rec, motivo = "resemble", f"voz abafada (banda 2.5-8k {hf - lf:.0f} dB abaixo da grave); resemble faz dereverb + reconstrução"
    elif snr < SNR_RUIM:
        if tem_df:
            rec, motivo = "deepfilternet", f"muito ruído (SNR ~{snr:.0f} dB); DeepFilterNet preserva melhor as consoantes"
        else:
            rec, motivo = "rnnoise", f"muito ruído (SNR ~{snr:.0f} dB); usando RNNoise (instale deepfilternet para resultado melhor)"
    elif snr < SNR_LIMPO:
        rec, motivo = "rnnoise", f"ruído moderado (SNR ~{snr:.0f} dB); RNNoise resolve sem custo"
    else:  # limpo porém abafado, sem resemble
        rec, motivo = "nenhum", "voz abafada detectada, mas resemble-enhance não está instalado (pip install resemble-enhance)"

    return {
        "arquivo": caminho,
        "janelas": len(rms),
        "fala_db": round(fala, 1),
        "ruido_db": round(ruido, 1),
        "snr_db": round(snr, 1),
        "abafado": abafado,
        "recomendacao": rec,
        "motivo": motivo,
    }


def _garantir_modelo_rnnn() -> Path:
    """Modelo cb.rnnn ao lado deste script (baixa da fonte oficial na 1ª vez)."""
    destino = Path(__file__).parent / "models" / "cb.rnnn"
    if destino.exists() and destino.stat().st_size > 100_000:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    # ssl padrão do Python no Windows usa o repositório de certificados do sistema
    # (funciona atrás de antivírus que interceptam HTTPS, ao contrário do curl do Git Bash)
    with urllib.request.urlopen(MODELO_RNNN_URL, timeout=60) as resp, open(destino, "wb") as f:
        f.write(resp.read())
    if destino.stat().st_size < 100_000:
        destino.unlink(missing_ok=True)
        raise RuntimeError("download do modelo RNNoise veio incompleto")
    return destino


def aplicar(caminho: str, recomendacao: str, saida: str | None = None) -> str:
    """Aplica o tratamento; devolve o caminho do arquivo limpo (original intocado)."""
    origem = Path(caminho).resolve()
    # nota: with_suffix substituiria o ".limpo" — montar o nome completo de uma vez
    destino = Path(saida).resolve() if saida else origem.with_name(origem.stem + ".limpo.wav")

    if recomendacao == "rnnoise":
        modelo = _garantir_modelo_rnnn()
        # O caminho do modelo no filtro NÃO pode ser absoluto no Windows
        # (o ':' de 'C:\' quebra a sintaxe de filtros) — rodamos com cwd na pasta dele.
        r = subprocess.run([_ffmpeg(), "-y", "-i", str(origem), "-af",
                            f"arnndn=m={modelo.name}", str(destino),
                            "-hide_banner", "-loglevel", "error"],
                           cwd=str(modelo.parent), capture_output=True, text=True)
        if r.returncode != 0 or not destino.exists():
            raise RuntimeError(f"rnnoise falhou: {(r.stderr or '').strip()[-300:]}")
        return str(destino)

    if recomendacao == "deepfilternet":
        binario = shutil.which("deep-filter")
        if binario:
            tmp = destino.parent / ".dfn_tmp"
            tmp.mkdir(exist_ok=True)
            r = subprocess.run([binario, "-o", str(tmp), str(origem)],
                               capture_output=True, text=True)
            produzido = tmp / origem.name
            if r.returncode == 0 and produzido.exists():
                shutil.move(str(produzido), str(destino))
                shutil.rmtree(tmp, ignore_errors=True)
                return str(destino)
            shutil.rmtree(tmp, ignore_errors=True)
            raise RuntimeError("deep-filter (binário) falhou")
        from df.enhance import enhance, init_df, load_audio, save_audio
        model, df_state, _ = init_df()
        audio, _ = load_audio(str(origem), sr=df_state.sr())
        save_audio(str(destino), enhance(model, df_state, audio), df_state.sr())
        return str(destino)

    if recomendacao == "resemble":
        import soundfile as sf
        import torch
        from resemble_enhance.enhancer.inference import enhance
        device = "cuda" if torch.cuda.is_available() else "cpu"
        wav, sr = sf.read(str(origem))
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        out_wav, out_sr = enhance(torch.as_tensor(wav, dtype=torch.float32).to(device),
                                  sr, device=device, nfe=64, solver="midpoint",
                                  lambd=0.5, tau=0.5)
        sf.write(str(destino), out_wav.cpu().numpy(), out_sr)
        return str(destino)

    raise ValueError(f"recomendação desconhecida: {recomendacao}")


def preparar_audio(caminho: str, modo: str = "auto") -> str | None:
    """Ponto de entrada do transcrever.py.

    modo: "auto" (analisa e trata se necessário), "off" (nunca), "forcar"
    (trata mesmo com SNR bom, usando rnnoise como mínimo).
    Devolve o caminho do arquivo limpo, ou None para usar o original.
    Nunca levanta exceção — falha de análise/tratamento = seguir com o original.
    """
    if modo == "off":
        return None
    try:
        origem = Path(caminho).resolve()
        destino = origem.with_name(origem.stem + ".limpo.wav")
        if destino.exists():
            print(f"  [audio] reaproveitando tratamento anterior: {destino.name}")
            return str(destino)
        met = analisar(str(origem))
        if met.get("erro"):
            print(f"  [audio] análise inconclusiva ({met['erro']}); usando original")
            return None
        rec = met["recomendacao"]
        if rec == "nenhum" and modo == "forcar":
            rec = "rnnoise"
            met["motivo"] = "tratamento forçado pelo usuário (--denoise forcar)"
        print(f"  [audio] SNR ~{met['snr_db']} dB | ruído {met['ruido_db']} dB | "
              f"fala {met['fala_db']} dB{' | ABAFADO' if met['abafado'] else ''}")
        if rec == "nenhum":
            print(f"  [audio] {met['motivo']}")
            return None
        print(f"  [audio] aplicando {rec}: {met['motivo']}")
        limpo = aplicar(str(origem), rec)
        print(f"  [audio] áudio tratado -> {Path(limpo).name} (original intacto)")
        return limpo
    except Exception as e:
        print(f"  [audio] aviso: tratamento falhou ({type(e).__name__}: {e}); usando original")
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("analisar", help="Mede qualidade e recomenda tratamento")
    pa.add_argument("arquivo")
    pa.add_argument("--json", action="store_true")
    pt = sub.add_parser("tratar", help="Analisa e aplica o melhor tratamento")
    pt.add_argument("arquivo")
    pt.add_argument("--saida", default=None)
    pt.add_argument("--forcar", action="store_true",
                    help="Trata mesmo que a análise diga que não precisa")
    args = ap.parse_args()

    if args.cmd == "analisar":
        met = analisar(args.arquivo)
        if args.json:
            print(json.dumps(met, ensure_ascii=False, indent=2))
        else:
            for k, v in met.items():
                print(f"{k}: {v}")
        return

    met = analisar(args.arquivo)
    rec = met.get("recomendacao", "nenhum")
    if rec == "nenhum" and args.forcar:
        rec = "rnnoise"
    print(json.dumps(met, ensure_ascii=False, indent=2))
    if rec == "nenhum":
        print("Nenhum tratamento necessário.")
        return
    limpo = aplicar(args.arquivo, rec, args.saida)
    print(f"Tratado ({rec}): {limpo}")


if __name__ == "__main__":
    main()
