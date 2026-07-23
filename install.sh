#!/usr/bin/env bash
# install.sh — Video AI Toolkit (macOS / Linux)
# Instala: yt-dlp, ffmpeg, Deno, claude-real-video (crv), faster-whisper
# e as skills do Claude Code.
# Nota: o agente Escriba (transcricao pt-BR com diarizacao) e voltado a Windows;
# em macOS/Linux use o crv com --speakers para diarizacao leve.
#
# Uso: bash install.sh [--force]
set -uo pipefail

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

ROOT="$(cd "$(dirname "$0")" && pwd)"
info() { echo -e "\033[0;36m[info]\033[0m $*"; }
ok()   { echo -e "\033[0;32m[ok]\033[0m   $*"; }
warn() { echo -e "\033[1;33m[aviso]\033[0m $*"; }
err()  { echo -e "\033[0;31m[erro]\033[0m $*" >&2; }

echo ""
echo "============================================="
echo "   Video AI Toolkit — Instalador Unix"
echo "   baixar (yt-dlp) + assistir (crv)"
echo "============================================="
echo ""

# --- 1. Python 3.10+ ---
if ! command -v python3 >/dev/null; then
    err "python3 nao encontrado. Instale (brew install python / apt install python3) e rode de novo."
    exit 1
fi
ok "Python $(python3 --version 2>&1 | cut -d' ' -f2)"

# --- 2. Gerenciador de pacotes ---
PKG=""
if command -v brew >/dev/null; then PKG="brew"
elif command -v apt-get >/dev/null; then PKG="apt"
fi

# --- 3. ffmpeg ---
if command -v ffmpeg >/dev/null; then
    ok "ffmpeg ja instalado"
else
    case "$PKG" in
        brew) info "Instalando ffmpeg via brew..."; brew install ffmpeg ;;
        apt)  info "Instalando ffmpeg via apt (pode pedir sudo)..."; sudo apt-get install -y ffmpeg ;;
        *)    warn "Nenhum gerenciador detectado — instale o ffmpeg manualmente: https://ffmpeg.org/download.html" ;;
    esac
fi

# --- 4. Deno (runtime JS que o YouTube exige desde 2026) ---
if command -v deno >/dev/null; then
    ok "Deno ja instalado"
else
    case "$PKG" in
        brew) info "Instalando Deno via brew..."; brew install deno ;;
        apt)  warn "Deno nao esta no apt padrao. Instale via snap (sudo snap install deno) ou https://deno.land — sem ele o YouTube pode ocultar os melhores formatos." ;;
        *)    warn "Instale o Deno manualmente: https://deno.land" ;;
    esac
fi

# --- 5. Pacotes Python ---
info "Instalando/atualizando yt-dlp, claude-real-video e faster-whisper..."
python3 -m pip install --user -U yt-dlp claude-real-video faster-whisper && ok "Pacotes Python instalados" \
    || warn "pip falhou — verifique a saida acima (proxy/SSL sao as causas comuns)."

# --- 5b. agent-browser CLI (automacao de browser p/ o agente editor) ---
if command -v npm >/dev/null; then
    if command -v agent-browser >/dev/null && agent-browser --version >/dev/null 2>&1; then
        ok "agent-browser ja instalado"
    else
        info "Instalando agent-browser (CLI de automacao de browser) via npm..."
        npm install -g agent-browser 2>&1 | tail -3
        # o npm 10+ pode bloquear o postinstall; roda ele a mao se o comando nao responder
        if ! agent-browser --version >/dev/null 2>&1; then
            ab_dir="$(npm root -g 2>/dev/null)/agent-browser"
            if [[ -f "$ab_dir/scripts/postinstall.js" ]]; then
                info "Rodando postinstall do agent-browser (baixa o binario nativo do release oficial)..."
                ( cd "$ab_dir" && node scripts/postinstall.js 2>&1 | tail -3 )
            fi
        fi
        agent-browser --version >/dev/null 2>&1 && ok "agent-browser instalado" \
            || warn "agent-browser instalado mas fora do PATH desta sessao - abra um novo terminal."
    fi
else
    warn "npm nao encontrado - pulando agent-browser (opcional, usado pelo agente editor). Instale o Node.js e rode de novo."
fi

# --- 6. Skills do Claude Code ---
CLAUDE_DIR="$HOME/.claude"
if [[ -d "$CLAUDE_DIR" ]]; then
    for skill in youtube claude-real-video invest instalar; do
        dest="$CLAUDE_DIR/skills/$skill"
        if [[ -e "$dest" && $FORCE -eq 0 ]]; then
            warn "Skill '$skill' ja existe — pulando (use --force para sobrescrever)"
        else
            mkdir -p "$dest"
            cp "$ROOT/skills/$skill/SKILL.md" "$dest/SKILL.md"
            ok "Skill '$skill' instalada"
        fi
    done
    # agent-browser tem subpastas (references/, templates/) — copia recursiva
    ab_dest="$CLAUDE_DIR/skills/agent-browser"
    if [[ -e "$ab_dest" && $FORCE -eq 0 ]]; then
        warn "Skill 'agent-browser' ja existe — pulando (use --force para sobrescrever)"
    else
        mkdir -p "$ab_dest"
        cp -R "$ROOT/skills/agent-browser/." "$ab_dest/"
        ok "Skill 'agent-browser' instalada"
    fi
else
    warn "~/.claude nao encontrado (Claude Code nao instalado?) — copie skills/ manualmente depois."
fi

echo ""
echo "============================================="
echo " Instalacao concluida!"
echo ""
echo " Teste rapido:"
echo '   yt-dlp --simulate --print "%(title)s" "https://www.youtube.com/watch?v=jNQXAC9IVRw"'
echo "   crv --help"
echo ""
echo " No Claude Code, agora e so conversar:"
echo '   "baixa esse video: <url>"   -> skill youtube'
echo '   "resume esse video: <url>"  -> skill claude-real-video'
echo "============================================="
