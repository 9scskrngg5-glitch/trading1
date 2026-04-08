@echo off
title Ouvrir Vault dans Obsidian
echo Ouverture du vault dans Obsidian...

:: Tenter d'ouvrir via le protocole obsidian://
set VAULT_PATH=%~dp0trading_bot\vault
start "" "obsidian://open?path=%VAULT_PATH:\=/%"

:: Si Obsidian n'est pas installe, ouvrir le dossier
timeout /t 3 /nobreak >nul
if errorlevel 1 (
    echo Obsidian non trouve.
    echo 1. Telecharge Obsidian sur https://obsidian.md
    echo 2. Ouvre ce dossier comme vault : %VAULT_PATH%
    explorer "%VAULT_PATH%"
)

echo.
echo Vault ouvert : %VAULT_PATH%
echo Notes generees par les agents :
dir /b "%VAULT_PATH%\*" 2>nul
pause
