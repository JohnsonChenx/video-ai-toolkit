# -*- coding: utf-8 -*-
"""
Baixador de Videos — servidor local que serve a interface HTML e executa o yt-dlp.
Apenas bibliotecas padrão do Python. Inicie com ABRIR.bat ou: python servidor.py
"""
import json
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PORTA = 8765
BASE = Path(__file__).parent

# Vídeo: prefere H.264+AAC (compatibilidade máxima) e garante container MP4 no final
FORMATO_VIDEO = "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b"

estado = {"ativo": False, "linhas": [], "ok": None}
lock = threading.Lock()
proc_atual = None


def rodar_download(url: str, tipo: str, pasta: str, playlist: bool):
    global proc_atual
    modelo = ("%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s"
              if playlist else "%(title)s.%(ext)s")
    destino = str(Path(pasta) / modelo)

    if tipo == "audio":
        cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        cmd = ["yt-dlp", "-f", FORMATO_VIDEO,
               "--merge-output-format", "mp4", "--remux-video", "mp4"]

    if not playlist:
        cmd.append("--no-playlist")
    cmd += ["--newline", "--no-colors", "-o", destino, url]

    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                creationflags=flags)
    except FileNotFoundError:
        with lock:
            estado["linhas"].append("ERRO: yt-dlp não encontrado no PATH.")
            estado["ativo"] = False
            estado["ok"] = False
        return

    proc_atual = proc
    for linha in proc.stdout:
        with lock:
            estado["linhas"].append(linha.rstrip())
    proc.wait()
    with lock:
        estado["ativo"] = False
        estado["ok"] = (proc.returncode == 0)
    proc_atual = None


# O tkinter só funciona de forma confiável na thread principal de um processo.
# Como cada requisição HTTP roda em thread própria (ThreadingHTTPServer), o diálogo
# é aberto num subprocesso Python dedicado, onde ele É a thread principal.
DIALOGO_PASTA = """
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
root.update()
print(filedialog.askdirectory(title='Escolha a pasta de destino', parent=root))
"""


def escolher_pasta() -> str:
    """Abre o seletor de pastas nativo do Windows (em subprocesso próprio)."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    r = subprocess.run([sys.executable, "-c", DIALOGO_PASTA],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=flags)
    pasta = (r.stdout or "").strip()
    return pasta.replace("/", "\\") if pasta else ""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silencia o log de requisições no console
        pass

    def _json(self, dados, codigo=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        rota = urlparse(self.path).path
        if rota == "/":
            html = (BASE / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif rota == "/status":
            with lock:
                self._json(estado)
        elif rota == "/escolher-pasta":
            self._json({"pasta": escolher_pasta()})
        elif rota == "/pastas-padrao":
            self._json({"video": str(BASE / "Videos"), "audio": str(BASE / "Audios")})
        else:
            self._json({"erro": "rota desconhecida"}, 404)

    def do_POST(self):
        rota = urlparse(self.path).path
        tamanho = int(self.headers.get("Content-Length", 0))
        dados = json.loads(self.rfile.read(tamanho) or b"{}")

        if rota == "/baixar":
            with lock:
                if estado["ativo"]:
                    self._json({"erro": "Já existe um download em andamento."}, 409)
                    return
                estado.update({"ativo": True, "linhas": [], "ok": None})
            url = dados.get("url", "").strip()
            tipo = dados.get("tipo", "video")
            pasta = dados.get("pasta", "").strip() or str(
                BASE / ("Audios" if tipo == "audio" else "Videos"))
            playlist = bool(dados.get("playlist", False))
            if not url:
                with lock:
                    estado["ativo"] = False
                self._json({"erro": "Informe a URL."}, 400)
                return
            threading.Thread(target=rodar_download,
                             args=(url, tipo, pasta, playlist), daemon=True).start()
            self._json({"ok": True})
        elif rota == "/cancelar":
            if proc_atual:
                proc_atual.terminate()
                with lock:
                    estado["linhas"].append("Download cancelado pelo usuário.")
            self._json({"ok": True})
        else:
            self._json({"erro": "rota desconhecida"}, 404)


if __name__ == "__main__":
    try:
        servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    except OSError:
        print(f"ERRO: a porta {PORTA} ja esta em uso.")
        print("Provavelmente outra janela do Baixador ja esta aberta.")
        print("Feche a outra janela (ou use o navegador que ja esta aberto) e tente de novo.")
        input("Pressione Enter para sair...")
        sys.exit(1)
    print(f"Baixador de Videos rodando em http://localhost:{PORTA}")
    print("Feche esta janela para encerrar.")
    threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{PORTA}")).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
