@echo off
title Ouvrir dans VS Code
echo Ouverture du projet dans VS Code...
code "%~dp0trading_bot"
if errorlevel 1 (
    echo VS Code non trouve. Ouvre manuellement le dossier :
    echo %~dp0trading_bot
    explorer "%~dp0trading_bot"
)
