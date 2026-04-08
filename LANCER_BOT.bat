@echo off
title Trading Bot — AI Trading Company
color 0A
echo.
echo  ======================================================
echo   AI TRADING COMPANY — 13 AGENTS + WATCHDOG
echo   Pipeline : Scan - Research - Predict - Risk - Execute
echo   + Compound - Regime - Knowledge - Shadow - Behavior
echo   + MetaAgent (CEO) - SupervisorAgent - SynthesisAgent
echo  ======================================================
echo.

:: Aller dans le bon dossier
cd /d "%~dp0trading_bot"

:: Verifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH
    pause
    exit /b 1
)

:: Verifier .env
if not exist ".env" (
    echo [ERREUR] Fichier .env introuvable dans trading_bot/
    echo Creer le fichier .env avec TELEGRAM_TOKEN et TELEGRAM_CHAT_ID
    pause
    exit /b 1
)

:: Installer les dependances
echo [1/3] Verification des dependances...
pip install python-dotenv pandas numpy pyyaml httpx websockets ccxt --quiet >nul 2>&1
echo       OK

echo [2/3] Vault Obsidian : %~dp0trading_bot\vault
echo.

:: Choix du mode
echo  Quel mode de trading ?
echo.
echo    1. SIMULATION  (donnees simulees, ordres simules)
echo    2. PAPER       (donnees Binance reelles, ordres simules)
echo    3. LIVE        (ordres reels — ARGENT REEL)
echo.
set /p MODE_CHOICE="  Choix [1/2/3] (defaut: 1) : "

if "%MODE_CHOICE%"=="3" (
    set TRADING_MODE=live
    echo.
    echo  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo  !!!  ATTENTION : MODE LIVE — ARGENT REEL        !!!
    echo  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    set /p CONFIRM="  Confirmer ? (oui/non) : "
    if /i not "%CONFIRM%"=="oui" (
        echo Annule.
        pause
        exit /b 0
    )
) else if "%MODE_CHOICE%"=="2" (
    set TRADING_MODE=paper
) else (
    set TRADING_MODE=simulation
)

echo.
echo [3/3] Lancement en mode %TRADING_MODE% avec WATCHDOG...
echo       Si le bot crash, il redemarrera automatiquement.
echo       Logs watchdog : trading_bot\watchdog.log
echo       Ctrl+C pour tout arreter.
echo.
python watchdog.py

pause
