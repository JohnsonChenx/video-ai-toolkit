@echo off
chcp 65001 >nul
title Baixador de Videos - Servidor
cd /d "%~dp0"
echo Iniciando o Baixador de Videos...
echo O navegador vai abrir automaticamente.
echo.
echo *** NAO FECHE ESTA JANELA enquanto estiver usando o baixador ***
echo.
python servidor.py
pause
