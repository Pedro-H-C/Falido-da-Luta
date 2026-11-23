@echo off
rem Gera dist\FalidoDaLuta.zip para mandar para os amigos (dois cliques aqui).
cd /d "%~dp0"
python tools\gerar_jogo.py
pause
