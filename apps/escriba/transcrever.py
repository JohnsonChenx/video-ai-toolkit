r"""
Transcricao + diarizacao de audio usando WhisperX (pt-BR).
Aceita arquivo unico OU pasta inteira (modo lote).

Uso:
    # Arquivo unico
    python transcrever.py "C:\caminho\audio.mp3"

    # Pasta inteira (todos os audios suportados)
    python transcrever.py "C:\caminho\pasta"

    # Pasta + subpastas
    python transcrever.py "C:\caminho\pasta" --recursivo

    # Forcar reprocessar mesmo que .txt/.srt/.json ja existam
    python transcrever.py "C:\caminho\pasta" --forcar

    # Numero exato de falantes (resultado mais consistente)
    python transcrever.py "C:\caminho\pasta" --falantes 2

Saidas geradas no mesmo diretorio de cada audio:
    <nome>.txt   transcricao agrupada por falante
    <nome>.srt   legendas com [SPEAKER_XX]
    <nome>.json  segmentos completos com timestamps por palavra

Modo lote: modelos sao carregados UMA VEZ e reutilizados em todos os arquivos.
Arquivos ja transcritos sao pulados (a menos que --forcar).
Erro em um arquivo nao interrompe a fila.
"""
import argparse
import gc
import json
import os
import sys
import time
import traceback
from pathlib import Path

import torch
import whisperx

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4",
              ".webm", ".opus", ".wma", ".aac", ".mkv", ".mov"}


def fmt_srt_time(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def already_done(audio_path: Path) -> bool:
    base = audio_path.with_suffix("")
    return all(base.with_suffix(ext).exists() for ext in (".txt", ".srt", ".json"))


def write_outputs(audio_path: Path, result):
    out_base = audio_path.with_suffix("")
    txt_path = out_base.with_suffix(".txt")
    srt_path = out_base.with_suffix(".srt")
    json_path = out_base.with_suffix(".json")

    with open(txt_path, "w", encoding="utf-8") as f:
        last_speaker = None
        for seg in result["segments"]:
            sp = seg.get("speaker", "SPEAKER_??")
            if sp != last_speaker:
                f.write(f"\n[{sp}]\n")
                last_speaker = sp
            f.write(seg["text"].strip() + " ")

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(result["segments"], 1):
            sp = seg.get("speaker", "SPEAKER_??")
            f.write(f"{i}\n{fmt_srt_time(seg['start'])} --> {fmt_srt_time(seg['end'])}\n")
            f.write(f"[{sp}] {seg['text'].strip()}\n\n")

    with open(json_path, "w", encoding="utf-8") as f:
        clean = {"segments": result["segments"], "language": result.get("language")}
        json.dump(clean, f, ensure_ascii=False, indent=2, default=str)

    return txt_path, srt_path, json_path


def _free_vram(device):
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()


def transcribe_one(audio_path: Path, args, device, batch_size, compute_type, hf_token):
    # Análise automática de qualidade + denoise quando necessário (audio_quality.py).
    # Saídas continuam nomeadas pelo arquivo ORIGINAL; o .limpo.wav fica ao lado.
    fonte = audio_path
    if getattr(args, "denoise", "auto") != "off":
        try:
            from audio_quality import preparar_audio
            limpo = preparar_audio(str(audio_path), modo=args.denoise)
            if limpo:
                fonte = Path(limpo)
        except ImportError:
            pass  # audio_quality.py ausente: segue com o original

    audio = whisperx.load_audio(str(fonte))
    duration_sec = len(audio) / 16000
    print(f"  duracao: {duration_sec:.1f}s ({duration_sec/60:.1f} min)")

    print(f"  [1/3] transcrevendo (Whisper {args.modelo}, batch={batch_size})...")
    whisper_model = whisperx.load_model(args.modelo, device,
                                        compute_type=compute_type, language=args.idioma)
    result = whisper_model.transcribe(audio, batch_size=batch_size, language=args.idioma)
    del whisper_model
    _free_vram(device)

    print(f"  [2/3] alinhando palavras...")
    align_model, align_meta = whisperx.load_align_model(language_code=args.idioma, device=device)
    result = whisperx.align(result["segments"], align_model, align_meta, audio,
                            device, return_char_alignments=False)
    del align_model, align_meta
    _free_vram(device)

    print(f"  [3/3] diarizando...")
    diarize_model = whisperx.diarize.DiarizationPipeline(token=hf_token, device=device)
    diarize_kwargs = {}
    if args.falantes > 0:
        diarize_kwargs["min_speakers"] = args.falantes
        diarize_kwargs["max_speakers"] = args.falantes
    diarize_segments = diarize_model(audio, **diarize_kwargs)
    result = whisperx.assign_word_speakers(diarize_segments, result)
    result["language"] = args.idioma
    del diarize_model
    _free_vram(device)

    txt_path, srt_path, json_path = write_outputs(audio_path, result)
    speakers = sorted({s.get("speaker", "?") for s in result["segments"]})
    return speakers, [txt_path, srt_path, json_path]


def collect_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() not in AUDIO_EXTS:
            print(f"AVISO: extensao {path.suffix} nao reconhecida; tentando processar mesmo assim.")
        return [path]
    if not path.is_dir():
        return []
    if recursive:
        candidates = path.rglob("*")
    else:
        candidates = path.iterdir()
    return sorted([f for f in candidates
                   if f.is_file() and f.suffix.lower() in AUDIO_EXTS
                   and not f.stem.endswith(".limpo")])  # não retranscrever os tratados


def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description=__doc__)
    ap.add_argument("caminho", help="Arquivo de audio OU pasta com audios")
    ap.add_argument("--modelo", default="medium",
                    choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                    help="Modelo Whisper (default: medium)")
    ap.add_argument("--falantes", type=int, default=0,
                    help="Numero de falantes (0 = automatico)")
    ap.add_argument("--idioma", default="pt", help="Codigo do idioma (default: pt)")
    ap.add_argument("--recursivo", action="store_true",
                    help="Processar subpastas (apenas se caminho for pasta)")
    ap.add_argument("--forcar", action="store_true",
                    help="Reprocessar mesmo que .txt/.srt/.json ja existam")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--compute-type", default="float16",
                    help="float16 (GPU), int8 (CPU/baixa VRAM), float32 (CPU preciso)")
    ap.add_argument("--batch-size", type=int, default=0,
                    help="Batch do Whisper (0 = automatico: 8 GPU, 4 CPU). "
                         "Reduza para 4 ou 2 se OOM em large-v3 com VRAM <= 8GB.")
    ap.add_argument("--denoise", default="auto", choices=["auto", "off", "forcar"],
                    help="Tratamento automatico de audio antes de transcrever: "
                         "auto = analisa SNR e trata so se precisar (default); "
                         "off = nunca; forcar = trata mesmo com audio bom.")
    args = ap.parse_args()

    target = Path(args.caminho).resolve()
    if not target.exists():
        print(f"ERRO: caminho nao encontrado: {target}")
        sys.exit(1)

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("ERRO: variavel HF_TOKEN nao definida.")
        sys.exit(1)

    files = collect_files(target, args.recursivo)
    if not files:
        print(f"ERRO: nenhum arquivo de audio encontrado em {target}")
        print(f"      extensoes suportadas: {sorted(AUDIO_EXTS)}")
        sys.exit(1)

    pending, skipped = [], []
    for f in files:
        if not args.forcar and already_done(f):
            skipped.append(f)
        else:
            pending.append(f)

    print(f"Encontrados: {len(files)} | a processar: {len(pending)} | pulando (ja transcritos): {len(skipped)}")
    if not pending:
        print("Nada a fazer. Use --forcar para reprocessar.")
        return

    device = args.device
    if args.batch_size > 0:
        batch_size = args.batch_size
    else:
        batch_size = 8 if device == "cuda" else 4
    compute_type = args.compute_type if device == "cuda" else "int8"

    print(f"\nConfig: device={device}, compute={compute_type}, batch_size={batch_size}")
    print(f"Modelos sao carregados/descarregados por etapa para evitar OOM.\n")

    ok, fail = [], []
    total_start = time.time()
    for i, audio_path in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] {audio_path.name}")
        t_file = time.time()
        try:
            speakers, outs = transcribe_one(audio_path, args, device,
                                            batch_size, compute_type, hf_token)
            print(f"  OK em {time.time()-t_file:.1f}s | falantes: {speakers}")
            ok.append(audio_path)
        except Exception as e:
            print(f"  ERRO: {type(e).__name__}: {e}")
            traceback.print_exc()
            fail.append((audio_path, str(e)))
        finally:
            _free_vram(device)

    total = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"Lote concluido em {total/60:.1f} min")
    print(f"  Sucesso: {len(ok)}  |  Falha: {len(fail)}  |  Pulados: {len(skipped)}")
    if fail:
        print(f"\nFalhas:")
        for f, err in fail:
            print(f"  - {f.name}: {err}")


if __name__ == "__main__":
    main()
