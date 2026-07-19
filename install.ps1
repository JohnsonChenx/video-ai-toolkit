# install.ps1 — Video AI Toolkit (Windows)
# Instala e configura: yt-dlp, ffmpeg, Deno (runtime JS do YouTube),
# claude-real-video (crv), faster-whisper, e as skills/agente do Claude Code.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File install.ps1              # stack de video
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Escriba     # + deps do app Escriba (GUI)
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Force       # sobrescreve skills existentes
param(
    [switch]$Escriba,   # instala tambem PySide6 + keyboard (GUI do Escriba)
    [switch]$Force      # sobrescreve skills/agente ja instalados sem perguntar
)

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot

function Info($msg)  { Write-Host "[info] $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "[ok]   $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "[aviso] $msg" -ForegroundColor Yellow }
function Fail($msg)  { Write-Host "[erro] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "   Video AI Toolkit - Instalador Windows"      -ForegroundColor Magenta
Write-Host "   baixar (yt-dlp) + assistir (crv) + ouvir"   -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host ""

# --- 1. Python 3.10+ ---
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Fail "Python nao encontrado. Instale pela Microsoft Store (busque 'Python 3.12') ou python.org e rode este script de novo."
    exit 1
}
$pyver = (python --version 2>&1) -replace "Python ", ""
if ([version]($pyver.Split(" ")[0]) -lt [version]"3.10") {
    Fail "Python $pyver e antigo demais (minimo 3.10). Atualize e rode de novo."
    exit 1
}
Ok "Python $pyver"

# --- 2. ffmpeg ---
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Ok "ffmpeg ja instalado"
} else {
    Info "Instalando ffmpeg via winget (fonte oficial Gyan.FFmpeg)..."
    # --source winget: a fonte msstore falha quando antivirus intercepta HTTPS
    winget install --id Gyan.FFmpeg -e --source winget --accept-source-agreements --accept-package-agreements
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Ok "ffmpeg instalado" }
    else { Warn "ffmpeg instalado mas fora do PATH desta sessao - abra um novo PowerShell apos concluir." }
}

# --- 3. Pacotes Python ---
Info "Instalando/atualizando yt-dlp, claude-real-video e faster-whisper (pode demorar alguns minutos)..."
python -m pip install --user -U yt-dlp claude-real-video faster-whisper 2>&1 | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) {
    Warn "pip falhou. Se o erro for de SSL/certificado (antivirus interceptando HTTPS), rode:"
    Warn "  python -m pip install --user pip-system-certs"
    Warn "e execute este instalador de novo."
} else {
    Ok "Pacotes Python instalados"
}

# --- 4. Deno (runtime JS que o YouTube exige desde 2026) ---
$denoExe = $null
$denoCmd = Get-Command deno -ErrorAction SilentlyContinue
if ($denoCmd) { $denoExe = $denoCmd.Source }
if (-not $denoExe) {
    $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "deno.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $denoExe = $found.FullName }
}
if (-not $denoExe) {
    Info "Instalando Deno via winget..."
    winget install --id DenoLand.Deno -e --source winget --accept-source-agreements --accept-package-agreements
    $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "deno.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $denoExe = $found.FullName }
}
if ($denoExe) {
    # winget instala o deno fora do PATH; registramos o caminho no config global do yt-dlp
    $cfgDir = "$env:APPDATA\yt-dlp"
    $cfgFile = "$cfgDir\config"
    New-Item -ItemType Directory -Force $cfgDir | Out-Null
    $line = "--js-runtimes `"deno:$denoExe`""
    $existing = if (Test-Path $cfgFile) { Get-Content $cfgFile -Raw } else { "" }
    if ($existing -notmatch [regex]::Escape("--js-runtimes")) {
        Add-Content -Path $cfgFile -Value $line -Encoding ascii
        Ok "Deno registrado no config do yt-dlp ($cfgFile)"
    } else {
        Ok "Runtime JS ja configurado no yt-dlp"
    }
} else {
    Warn "Deno nao encontrado/instalado - o YouTube pode ocultar os melhores formatos. Instale manualmente: winget install DenoLand.Deno"
}

# --- 5. PYTHONUTF8 (sem isso o crv quebra no console cp1252 e os grids nao saem) ---
if ([Environment]::GetEnvironmentVariable("PYTHONUTF8", "User") -ne "1") {
    setx PYTHONUTF8 1 | Out-Null
    Ok "PYTHONUTF8=1 configurado (vale para novas janelas)"
} else {
    Ok "PYTHONUTF8 ja configurado"
}

# --- 6. Skills + agente do Claude Code ---
$claudeDir = "$env:USERPROFILE\.claude"
if (Test-Path $claudeDir) {
    foreach ($skill in @("youtube", "claude-real-video", "invest")) {
        $dest = "$claudeDir\skills\$skill"
        if ((Test-Path $dest) -and -not $Force) {
            Warn "Skill '$skill' ja existe em $dest - pulando (use -Force para sobrescrever)"
        } else {
            New-Item -ItemType Directory -Force $dest | Out-Null
            Copy-Item "$root\skills\$skill\SKILL.md" "$dest\SKILL.md" -Force
            Ok "Skill '$skill' instalada"
        }
    }
    $agentDest = "$claudeDir\agents\escriba.md"
    if ((Test-Path $agentDest) -and -not $Force) {
        Warn "Agente 'escriba' ja existe - pulando (use -Force para sobrescrever)"
    } else {
        New-Item -ItemType Directory -Force "$claudeDir\agents" | Out-Null
        Copy-Item "$root\agents\escriba.md" $agentDest -Force
        Ok "Agente 'escriba' instalado"
    }
} else {
    Warn "Pasta ~\.claude nao encontrada (Claude Code nao instalado?) - skills nao copiadas."
    Warn "Instale o Claude Code e rode de novo, ou copie manualmente as pastas skills/ e agents/."
}

# --- 7. Deps opcionais do app Escriba (GUI) ---
if ($Escriba) {
    Info "Instalando dependencias do app Escriba (PySide6 + keyboard)..."
    python -m pip install --user PySide6 keyboard 2>&1 | Select-Object -Last 2
    Warn "Nota: no Python da Microsoft Store, o pip do PySide6 pode terminar com OSError de caminho longo - o pacote fica funcional mesmo assim. Teste com:"
    Warn '  python -c "from PySide6.QtWidgets import QApplication; print(''PySide6 OK'')"'
    Info "A pipeline completa de transcricao (WhisperX + pyannote + CUDA) e instalada pelo proprio agente 'escriba' na primeira transcricao - peca a ele: 'prepara o ambiente de transcricao'."
}

# --- Resumo ---
Write-Host ""
Write-Host "=============================================" -ForegroundColor Magenta
Write-Host " Instalacao concluida!" -ForegroundColor Green
Write-Host ""
Write-Host " Teste rapido (abra um NOVO PowerShell):"
Write-Host '   yt-dlp --simulate --print "%(title)s" "https://www.youtube.com/watch?v=jNQXAC9IVRw"'
Write-Host '   crv --help'
Write-Host ""
Write-Host " No Claude Code, agora e so conversar:"
Write-Host '   "baixa esse video: <url>"        -> skill youtube'
Write-Host '   "resume esse video: <url>"       -> skill claude-real-video'
Write-Host '   "transcreve essa reuniao: <arq>" -> agente escriba'
Write-Host "=============================================" -ForegroundColor Magenta
