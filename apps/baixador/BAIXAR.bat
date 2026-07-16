@echo off
chcp 65001 >nul
title Baixador de Videos (yt-dlp)
setlocal EnableDelayedExpansion

:menu
cls
echo ============================================
echo        BAIXADOR DE VIDEOS  (yt-dlp)
echo ============================================
echo.
echo   [1] Baixar VIDEO (melhor qualidade MP4)
echo   [2] Baixar AUDIO (MP3)
echo   [3] Baixar VIDEO em qualidade especifica
echo   [4] Baixar PLAYLIST inteira (video)
echo   [5] Baixar PLAYLIST inteira (audio MP3)
echo   [6] Atualizar yt-dlp
echo   [0] Sair
echo.
set /p opcao="Escolha uma opcao: "

if "%opcao%"=="0" exit /b
if "%opcao%"=="6" goto atualizar
if "%opcao%"=="1" goto video
if "%opcao%"=="2" goto audio
if "%opcao%"=="3" goto qualidade
if "%opcao%"=="4" goto playlist_video
if "%opcao%"=="5" goto playlist_audio
goto menu

:video
set /p url="Cole a URL do video: "
yt-dlp -f "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b" --merge-output-format mp4 --remux-video mp4 --no-playlist -o "%~dp0Videos\%%(title)s.%%(ext)s" "%url%"
goto fim

:audio
set /p url="Cole a URL do video: "
yt-dlp -x --audio-format mp3 --audio-quality 0 --no-playlist -o "%~dp0Audios\%%(title)s.%%(ext)s" "%url%"
goto fim

:qualidade
set /p url="Cole a URL do video: "
echo.
echo Qualidades disponiveis:
yt-dlp -F --no-playlist "%url%"
echo.
set /p fmt="Digite o codigo do formato (ex: 137+140 ou 22): "
yt-dlp -f "%fmt%" --merge-output-format mp4 --remux-video mp4 --no-playlist -o "%~dp0Videos\%%(title)s.%%(ext)s" "%url%"
goto fim

:playlist_video
set /p url="Cole a URL da playlist: "
yt-dlp -f "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b" --merge-output-format mp4 --remux-video mp4 -o "%~dp0Videos\%%(playlist_title)s\%%(playlist_index)s - %%(title)s.%%(ext)s" "%url%"
goto fim

:playlist_audio
set /p url="Cole a URL da playlist: "
yt-dlp -x --audio-format mp3 --audio-quality 0 -o "%~dp0Audios\%%(playlist_title)s\%%(playlist_index)s - %%(title)s.%%(ext)s" "%url%"
goto fim

:atualizar
pip install -U yt-dlp
pause
goto menu

:fim
echo.
echo ============================================
echo  Download concluido! Arquivos em:
echo  Videos\  ou  Audios\
echo ============================================
pause
goto menu
