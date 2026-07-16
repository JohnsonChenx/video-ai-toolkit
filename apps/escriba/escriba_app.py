r"""
Escriba — App de transcrição amigável (Windows).

Funcionalidades:
  1. Arraste um áudio (ou pasta) para transcrever com diarização (usa transcrever.py)
  2. Botões "Transcrever arquivo..." e "Transcrever pasta (lote)..."
  3. Ditado por atalho global (segurar Ctrl+Alt+D, falar, soltar) — o texto é
     colado onde o cursor estiver (Word, navegador, etc.)
  4. "Resumir em tópicos" e "Ata da reunião" — via Ollama local ou Claude API,
     identificando participantes pelas tags [SPEAKER_XX]

Requisitos: PySide6, sounddevice, keyboard, faster-whisper, requests, anthropic
Inicie com:  pythonw escriba_app.py   (ou o atalho "Iniciar Escriba.bat")
"""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np
import requests

try:
    import winsound
except ImportError:
    winsound = None

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
TRANSCREVER = APP_DIR / "transcrever.py"

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4",
              ".webm", ".opus", ".wma", ".aac", ".mkv", ".mov"}

HOTKEY_KEY = "d"          # tecla do push-to-talk (com Ctrl+Alt)
HOTKEY_LABEL = "Ctrl+Alt+D"
MAX_DICTATION_SEC = 120   # segurança: para gravação automaticamente
SAMPLE_RATE = 16000

OLLAMA_URL = "http://localhost:11434"
CLAUDE_MODEL = "claude-opus-4-8"

PROMPT_TOPICOS = (
    "Você resume transcrições de áudio em português brasileiro. "
    "Produza um resumo em tópicos (Markdown): comece com uma linha de resumo geral, "
    "depois agrupe os pontos por tema com bullets curtos. Preserve nomes, valores, "
    "datas, prazos e decisões importantes. Não invente informações."
)

PROMPT_ATA = (
    "Você redige atas de reunião em português brasileiro a partir de transcrições "
    "diarizadas, nas quais os falantes aparecem como [SPEAKER_00], [SPEAKER_01], etc. "
    "Identifique os participantes pelos nomes citados no contexto sempre que possível, "
    "associando cada SPEAKER a um nome real; quando não for possível, mantenha o rótulo "
    "SPEAKER_XX. Estruture a ata em Markdown com as seções: "
    "1) Participantes (com o mapeamento SPEAKER → nome); "
    "2) Pauta / temas discutidos; "
    "3) Principais discussões (atribuindo posições a cada participante); "
    "4) Decisões tomadas; "
    "5) Ações e pendências (com responsável e prazo quando identificáveis). "
    "Não invente informações que não estejam na transcrição."
)


def read_user_env(name: str) -> str | None:
    """Lê variável do ambiente atual OU do registro do usuário (setx)."""
    val = os.environ.get(name)
    if val:
        return val
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def beep(freq: int, ms: int) -> None:
    if winsound is not None:
        try:
            winsound.Beep(freq, ms)
        except RuntimeError:
            pass


# ----------------------------------------------------------------------------
# Ponte de sinais (threads de trabalho -> GUI)
# ----------------------------------------------------------------------------
class Bridge(QObject):
    dictation_started = Signal()
    dictation_stopped = Signal()
    dictation_text = Signal(str)
    dictation_status = Signal(str)
    summary_done = Signal(str, str)      # (tipo, texto)
    summary_error = Signal(str)
    engines_found = Signal(list)         # lista de (rotulo, tipo, modelo)


# ----------------------------------------------------------------------------
# Ditado (push-to-talk) — gravação + faster-whisper residente
# ----------------------------------------------------------------------------
class Dictation:
    def __init__(self, bridge: Bridge):
        self.bridge = bridge
        self._model = None
        self._model_name = None
        self._lock = threading.Lock()
        self._recording = False
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._start_time = 0.0
        self.model_size = "small"

    # ---- gravação (chamado pela thread do hook de teclado) ----
    def start(self) -> None:
        if self._recording:
            return
        try:
            import sounddevice as sd
            self._frames = []
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                callback=self._on_audio,
            )
            self._stream.start()
            self._recording = True
            self._start_time = time.time()
            beep(880, 120)
            self.bridge.dictation_started.emit()
        except Exception as e:
            self.bridge.dictation_status.emit(f"Erro ao abrir microfone: {e}")

    def _on_audio(self, indata, frames, t, status) -> None:
        if self._recording:
            self._frames.append(indata.copy())
            if time.time() - self._start_time > MAX_DICTATION_SEC:
                threading.Thread(target=self.stop, daemon=True).start()

    def stop(self) -> None:
        if not self._recording:
            return
        self._recording = False
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass
        beep(440, 120)
        self.bridge.dictation_stopped.emit()
        frames = self._frames
        self._frames = []
        if not frames:
            return
        audio = np.concatenate(frames).flatten()
        if len(audio) / SAMPLE_RATE < 0.3:  # muito curto, ignora
            self.bridge.dictation_status.emit("Gravação muito curta — ignorada.")
            return
        threading.Thread(target=self._transcribe, args=(audio,), daemon=True).start()

    # ---- transcrição ----
    def _get_model(self):
        with self._lock:
            if self._model is None or self._model_name != self.model_size:
                self.bridge.dictation_status.emit(
                    f"Carregando modelo de ditado ({self.model_size})... "
                    "na primeira vez pode baixar o modelo."
                )
                from faster_whisper import WhisperModel
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except Exception:
                    device = "cpu"
                compute = "float16" if device == "cuda" else "int8"
                self._model = WhisperModel(self.model_size, device=device,
                                           compute_type=compute)
                self._model_name = self.model_size
            return self._model

    def _transcribe(self, audio: np.ndarray) -> None:
        try:
            self.bridge.dictation_status.emit("Transcrevendo ditado...")
            model = self._get_model()
            segments, _info = model.transcribe(audio, language="pt", beam_size=5)
            text = " ".join(seg.text.strip() for seg in segments).strip()
            if text:
                self.bridge.dictation_text.emit(text)
                self.bridge.dictation_status.emit("Ditado concluído.")
            else:
                self.bridge.dictation_status.emit("Nada reconhecido no áudio.")
        except Exception as e:
            traceback.print_exc()
            self.bridge.dictation_status.emit(f"Erro no ditado: {e}")


def install_hotkey(dictation: Dictation, bridge: Bridge) -> str | None:
    """Registra o push-to-talk global. Retorna mensagem de erro ou None."""
    try:
        import keyboard
    except Exception as e:
        return f"Módulo 'keyboard' indisponível: {e}"

    def on_down(event):
        if keyboard.is_pressed("ctrl") and keyboard.is_pressed("alt"):
            dictation.start()

    def on_up(event):
        if dictation._recording:
            dictation.stop()

    try:
        keyboard.on_press_key(HOTKEY_KEY, on_down, suppress=False)
        keyboard.on_release_key(HOTKEY_KEY, on_up, suppress=False)
        return None
    except Exception as e:
        return f"Não foi possível registrar o atalho global: {e}"


# ----------------------------------------------------------------------------
# Motores de resumo (Ollama / Claude API)
# ----------------------------------------------------------------------------
def detect_engines(bridge: Bridge) -> None:
    """Roda em thread: descobre Ollama e Claude API disponíveis."""
    engines: list[tuple[str, str, str]] = []  # (rotulo, tipo, modelo)
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.ok:
            models = [m["name"] for m in r.json().get("models", [])]
            models.sort(key=lambda n: (0 if "llama3.1" in n else 1, n))
            for name in models:
                engines.append((f"Ollama: {name}", "ollama", name))
    except Exception:
        pass
    if read_user_env("ANTHROPIC_API_KEY"):
        engines.append((f"Claude API ({CLAUDE_MODEL})", "claude", CLAUDE_MODEL))
    bridge.engines_found.emit(engines)


def summarize(bridge: Bridge, engine: tuple[str, str, str],
              kind: str, text: str) -> None:
    """Roda em thread: chama o motor escolhido e emite o resultado."""
    system = PROMPT_ATA if kind == "ata" else PROMPT_TOPICOS
    user_msg = f"Transcrição:\n\n{text}"
    try:
        _, etype, model = engine
        if etype == "ollama":
            r = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ],
                    "stream": False,
                },
                timeout=900,
            )
            r.raise_for_status()
            result = r.json()["message"]["content"].strip()
        else:  # claude
            key = read_user_env("ANTHROPIC_API_KEY")
            if key and not os.environ.get("ANTHROPIC_API_KEY"):
                os.environ["ANTHROPIC_API_KEY"] = key
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=model,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            result = "".join(
                b.text for b in resp.content if b.type == "text"
            ).strip()
        bridge.summary_done.emit(kind, result)
    except Exception as e:
        traceback.print_exc()
        bridge.summary_error.emit(f"{type(e).__name__}: {e}")


# ----------------------------------------------------------------------------
# Zona de arrastar e soltar
# ----------------------------------------------------------------------------
class DropZone(QLabel):
    dropped = Signal(str)

    def __init__(self):
        super().__init__()
        exts = " ".join(sorted(e.lstrip('.') for e in
                               (".opus", ".ogg", ".m4a", ".mp3", ".wav", ".mp4")))
        self.setText(f"⤓  Arraste áudio ou pasta aqui\n({exts} ...)")
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)
        self.setObjectName("dropzone")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("hover", True)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("hover", False)
        self.style().polish(self)

    def dropEvent(self, event):
        self.setProperty("hover", False)
        self.style().polish(self)
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.dropped.emit(path)
                break  # um por vez


# ----------------------------------------------------------------------------
# Janela principal
# ----------------------------------------------------------------------------
class EscribaWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Escriba — Transcrição")
        self.resize(1080, 700)

        self.bridge = Bridge()
        self.dictation = Dictation(self.bridge)
        self.proc: QProcess | None = None
        self.current_audio: Path | None = None   # último arquivo transcrito
        self.engines: list[tuple[str, str, str]] = []

        self._build_ui()
        self._connect()
        self._apply_style()

        err = install_hotkey(self.dictation, self.bridge)
        if err:
            self.lbl_ditado_status.setText(f"⚠ {err}")
        threading.Thread(target=detect_engines, args=(self.bridge,),
                         daemon=True).start()
        self._check_env()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)

        # ---- coluna esquerda: drop zone + texto ----
        left = QVBoxLayout()
        self.drop = DropZone()
        left.addWidget(self.drop)

        splitter = QSplitter(Qt.Vertical)
        self.txt = QTextEdit()
        self.txt.setPlaceholderText(
            "A transcrição aparece aqui.\n\n"
            f"Arraste um áudio na zona acima, ou segure {HOTKEY_LABEL}, "
            "fale e solte."
        )
        splitter.addWidget(self.txt)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log.setPlaceholderText("Log do processamento...")
        mono = QFont("Consolas")
        mono.setPointSize(8)
        self.log.setFont(mono)
        splitter.addWidget(self.log)
        splitter.setSizes([460, 120])
        left.addWidget(splitter, 1)

        btm = QHBoxLayout()
        self.btn_copy = QPushButton("Copiar texto")
        self.btn_clear = QPushButton("Limpar")
        btm.addWidget(self.btn_copy)
        btm.addStretch(1)
        btm.addWidget(self.btn_clear)
        left.addLayout(btm)
        root.addLayout(left, 3)

        # ---- coluna direita: controles ----
        right = QVBoxLayout()

        g_arq = QGroupBox("Transcrição de arquivos")
        v = QVBoxLayout(g_arq)
        self.btn_file = QPushButton("Transcrever arquivo...")
        self.btn_folder = QPushButton("Transcrever pasta (lote)...")
        self.btn_stop = QPushButton("■ Parar")
        self.btn_stop.setEnabled(False)
        v.addWidget(self.btn_file)
        v.addWidget(self.btn_folder)
        v.addWidget(self.btn_stop)

        h = QHBoxLayout()
        h.addWidget(QLabel("Modelo:"))
        self.cmb_model = QComboBox()
        self.cmb_model.addItems(["medium", "large-v3", "small", "base", "tiny"])
        h.addWidget(self.cmb_model, 1)
        v.addLayout(h)

        h = QHBoxLayout()
        h.addWidget(QLabel("Falantes:"))
        self.spn_speakers = QSpinBox()
        self.spn_speakers.setRange(0, 20)
        self.spn_speakers.setSpecialValueText("auto")
        h.addWidget(self.spn_speakers, 1)
        v.addLayout(h)

        self.chk_force = QCheckBox("Reprocessar já transcritos (--forcar)")
        self.chk_recursive = QCheckBox("Incluir subpastas (--recursivo)")
        v.addWidget(self.chk_force)
        v.addWidget(self.chk_recursive)
        right.addWidget(g_arq)

        g_dit = QGroupBox(f"Ditado — segurar {HOTKEY_LABEL} para falar")
        v = QVBoxLayout(g_dit)
        self.chk_paste = QCheckBox("Colar texto no cursor ✓")
        self.chk_paste.setChecked(True)
        v.addWidget(self.chk_paste)
        h = QHBoxLayout()
        h.addWidget(QLabel("Modelo ditado:"))
        self.cmb_dict_model = QComboBox()
        self.cmb_dict_model.addItems(["small", "medium", "base"])
        h.addWidget(self.cmb_dict_model, 1)
        v.addLayout(h)
        self.lbl_ditado_status = QLabel("Pronto. Segure o atalho, fale e solte.")
        self.lbl_ditado_status.setWordWrap(True)
        v.addWidget(self.lbl_ditado_status)
        right.addWidget(g_dit)

        g_sum = QGroupBox("Resumo com IA")
        v = QVBoxLayout(g_sum)
        h = QHBoxLayout()
        h.addWidget(QLabel("Motor:"))
        self.cmb_engine = QComboBox()
        self.cmb_engine.addItem("Detectando motores...")
        h.addWidget(self.cmb_engine, 1)
        v.addLayout(h)
        self.btn_topics = QPushButton("Resumir em tópicos")
        self.btn_minutes = QPushButton("Ata da reunião (com participantes)")
        self.btn_topics.setEnabled(False)
        self.btn_minutes.setEnabled(False)
        v.addWidget(self.btn_topics)
        v.addWidget(self.btn_minutes)
        right.addWidget(g_sum)

        right.addStretch(1)
        self.btn_quit = QPushButton("Sair do Escriba")
        right.addWidget(self.btn_quit)

        panel = QFrame()
        panel.setLayout(right)
        panel.setFixedWidth(310)
        root.addWidget(panel)

        self.setCentralWidget(central)
        self.status = self.statusBar()

    def _connect(self):
        self.drop.dropped.connect(self.on_dropped)
        self.btn_file.clicked.connect(self.pick_file)
        self.btn_folder.clicked.connect(self.pick_folder)
        self.btn_stop.clicked.connect(self.stop_process)
        self.btn_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self.txt.toPlainText()))
        self.btn_clear.clicked.connect(self.txt.clear)
        self.btn_quit.clicked.connect(self.close)
        self.btn_topics.clicked.connect(lambda: self.run_summary("topicos"))
        self.btn_minutes.clicked.connect(lambda: self.run_summary("ata"))
        self.cmb_dict_model.currentTextChanged.connect(
            lambda t: setattr(self.dictation, "model_size", t))

        b = self.bridge
        b.dictation_started.connect(
            lambda: self.lbl_ditado_status.setText("🔴 Gravando... solte para transcrever."))
        b.dictation_stopped.connect(
            lambda: self.lbl_ditado_status.setText("Processando..."))
        b.dictation_status.connect(self.lbl_ditado_status.setText)
        b.dictation_text.connect(self.on_dictation_text)
        b.engines_found.connect(self.on_engines)
        b.summary_done.connect(self.on_summary_done)
        b.summary_error.connect(self.on_summary_error)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #1e2126; color: #e8e8e8;
                font-size: 10pt; }
            QGroupBox { border: 1px solid #3a3f47; border-radius: 8px;
                margin-top: 14px; padding-top: 10px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px;
                padding: 0 4px; color: #9fb3c8; }
            QPushButton { background: #2e343d; border: 1px solid #444b55;
                border-radius: 8px; padding: 7px 12px; }
            QPushButton:hover { background: #3a424d; }
            QPushButton:pressed { background: #262b32; }
            QPushButton:disabled { color: #6b7280; background: #262a30; }
            QTextEdit, QPlainTextEdit { background: #14161a;
                border: 1px solid #3a3f47; border-radius: 8px; padding: 6px; }
            QComboBox, QSpinBox { background: #2e343d;
                border: 1px solid #444b55; border-radius: 6px; padding: 3px 8px; }
            QComboBox QAbstractItemView { background: #2e343d; }
            QLabel#dropzone { border: 2px dashed #57606c; border-radius: 12px;
                color: #9aa5b1; background: #23272e; }
            QLabel#dropzone[hover="true"] { border-color: #7aa2f7;
                color: #c0d4ff; background: #262d3a; }
            QStatusBar { color: #9aa5b1; }
        """)

    def _check_env(self):
        if not TRANSCREVER.exists():
            self.log_line(f"AVISO: {TRANSCREVER} não encontrado — "
                          "transcrição de arquivos indisponível.")
        if not read_user_env("HF_TOKEN"):
            self.log_line("AVISO: HF_TOKEN não configurado — a diarização "
                          "(separação de falantes) vai falhar.")

    # ------------------------------------------------------- transcrição ----
    def log_line(self, text: str):
        self.log.appendPlainText(text.rstrip())
        self.log.moveCursor(QTextCursor.End)

    def on_dropped(self, path: str):
        p = Path(path)
        if p.is_file() and p.suffix.lower() in {".txt", ".srt", ".md"}:
            self.txt.setPlainText(p.read_text(encoding="utf-8", errors="replace"))
            self.current_audio = p.with_suffix("")  # base p/ salvar resumos
            self.status.showMessage(f"Texto carregado: {p.name}")
            return
        self.start_transcription(p)

    def pick_file(self):
        exts = " ".join(f"*{e}" for e in sorted(AUDIO_EXTS))
        path, _ = QFileDialog.getOpenFileName(
            self, "Escolher áudio", "", f"Áudio/Vídeo ({exts});;Todos (*.*)")
        if path:
            self.start_transcription(Path(path))

    def pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Escolher pasta com áudios")
        if path:
            self.start_transcription(Path(path))

    def start_transcription(self, target: Path):
        if self.proc is not None:
            QMessageBox.warning(self, "Escriba",
                                "Já existe uma transcrição em andamento.")
            return
        if not TRANSCREVER.exists():
            QMessageBox.critical(self, "Escriba",
                                 f"Script não encontrado:\n{TRANSCREVER}")
            return
        if target.is_file() and target.suffix.lower() not in AUDIO_EXTS:
            QMessageBox.warning(self, "Escriba",
                                f"Extensão não suportada: {target.suffix}")
            return

        args = [str(TRANSCREVER), str(target),
                "--modelo", self.cmb_model.currentText()]
        if self.spn_speakers.value() > 0:
            args += ["--falantes", str(self.spn_speakers.value())]
        if self.chk_force.isChecked():
            args.append("--forcar")
        if target.is_dir() and self.chk_recursive.isChecked():
            args.append("--recursivo")
        if self.cmb_model.currentText() == "large-v3":
            args += ["--compute-type", "int8_float16", "--batch-size", "4"]

        self.current_audio = target if target.is_file() else None

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        hf = read_user_env("HF_TOKEN")
        if hf:
            env.insert("HF_TOKEN", hf)

        self.proc = QProcess(self)
        self.proc.setProcessEnvironment(env)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._proc_output)
        self.proc.finished.connect(self._proc_finished)
        self.proc.setProgram(sys.executable)
        self.proc.setArguments(args)

        self.log.clear()
        self.log_line(f"Iniciando: {target}")
        self.status.showMessage(f"Transcrevendo {target.name}...")
        self._set_busy(True)
        self.proc.start()

    def _proc_output(self):
        data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        for line in data.splitlines():
            if line.strip():
                self.log_line(line)

    def _proc_finished(self, code: int, _status):
        self._set_busy(False)
        proc, self.proc = self.proc, None
        proc.deleteLater()
        if code == 0:
            self.status.showMessage("Transcrição concluída.")
            self.log_line("--- concluído ---")
            if self.current_audio is not None:
                txt = self.current_audio.with_suffix(".txt")
                if txt.exists():
                    self.txt.setPlainText(
                        txt.read_text(encoding="utf-8", errors="replace"))
                    self.status.showMessage(f"Concluído: {txt.name}")
        else:
            self.status.showMessage(f"Transcrição terminou com erro (código {code}).")
            self.log_line(f"--- terminou com código {code}; veja o log acima ---")

    def stop_process(self):
        if self.proc is not None:
            self.proc.kill()
            self.log_line("--- interrompido pelo usuário ---")

    def _set_busy(self, busy: bool):
        for w in (self.btn_file, self.btn_folder, self.drop):
            w.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)

    # ------------------------------------------------------------ ditado ----
    def on_dictation_text(self, text: str):
        cursor = self.txt.textCursor()
        cursor.movePosition(QTextCursor.End)
        prefix = "" if self.txt.toPlainText().endswith(("\n", "")) else " "
        cursor.insertText(prefix + text + "\n")
        if self.chk_paste.isChecked():
            QApplication.clipboard().setText(text)
            QTimer.singleShot(150, self._paste_at_cursor)

    def _paste_at_cursor(self):
        try:
            import keyboard
            keyboard.send("ctrl+v")
        except Exception as e:
            self.lbl_ditado_status.setText(f"Falha ao colar: {e}")

    # ------------------------------------------------------------ resumo ----
    def on_engines(self, engines: list):
        self.engines = [tuple(e) for e in engines]
        self.cmb_engine.clear()
        if not self.engines:
            self.cmb_engine.addItem("Nenhum motor disponível")
            tip = ("Instale o Ollama (ollama.com) e baixe um modelo "
                   "(ex.: ollama pull llama3.1), OU configure a variável "
                   "ANTHROPIC_API_KEY para usar a Claude API.")
            self.cmb_engine.setToolTip(tip)
            self.btn_topics.setToolTip(tip)
            self.btn_minutes.setToolTip(tip)
            self.log_line("Nenhum motor de resumo: " + tip)
            return
        for label, _t, _m in self.engines:
            self.cmb_engine.addItem(label)
        self.btn_topics.setEnabled(True)
        self.btn_minutes.setEnabled(True)

    def run_summary(self, kind: str):
        text = self.txt.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Escriba",
                                    "Não há texto para resumir. Transcreva um "
                                    "áudio ou cole o texto na área principal.")
            return
        if not self.engines:
            return
        idx = max(0, self.cmb_engine.currentIndex())
        engine = self.engines[min(idx, len(self.engines) - 1)]
        self.btn_topics.setEnabled(False)
        self.btn_minutes.setEnabled(False)
        rotulo = "ata da reunião" if kind == "ata" else "resumo em tópicos"
        self.status.showMessage(f"Gerando {rotulo} com {engine[0]}...")
        self.log_line(f"Gerando {rotulo} ({engine[0]})...")
        threading.Thread(target=summarize,
                         args=(self.bridge, engine, kind, text),
                         daemon=True).start()

    def on_summary_done(self, kind: str, result: str):
        self.btn_topics.setEnabled(True)
        self.btn_minutes.setEnabled(True)
        header = "ATA DA REUNIÃO" if kind == "ata" else "RESUMO EM TÓPICOS"
        self.txt.append(f"\n\n{'=' * 50}\n{header}\n{'=' * 50}\n\n{result}")
        self.status.showMessage(f"{header.capitalize()} pronto.")
        if self.current_audio is not None:
            suffix = ".ata.md" if kind == "ata" else ".topicos.md"
            out = self.current_audio.with_suffix(suffix)
            try:
                out.write_text(result, encoding="utf-8")
                self.log_line(f"Salvo em: {out}")
            except OSError as e:
                self.log_line(f"Não foi possível salvar {out}: {e}")

    def on_summary_error(self, msg: str):
        self.btn_topics.setEnabled(True)
        self.btn_minutes.setEnabled(True)
        self.status.showMessage("Erro ao gerar resumo.")
        self.log_line(f"ERRO no resumo: {msg}")
        QMessageBox.critical(self, "Escriba", f"Erro ao gerar resumo:\n{msg}")

    # ----------------------------------------------------------------------
    def closeEvent(self, event):
        if self.proc is not None:
            self.proc.kill()
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Escriba")
    win = EscribaWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
