@echo off
title Instalador VaultBot
color 0A

echo ================================
echo   Instalando dependencias...
echo ================================

python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ================================
echo   Iniciando bot...
echo ================================

python bot.py

pause
