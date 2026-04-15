@echo off
chcp 65001 > nul
title ORACLE v2 — Setup Wizard
cls

echo.
echo  +======================================+
echo  ^|        ORACLE v2 ^| SETUP WIZARD     ^|
echo  +======================================+
echo.

:: Check Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Python introuvable. Installe Python 3.10+ depuis python.org
    pause
    exit /b 1
)

:: Activate venv if present (oracle_v2/venv or root venv)
if exist "%~dp0oracle_v2\venv\Scripts\activate.bat" (
    call "%~dp0oracle_v2\venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

:: Run wizard from oracle_v2 directory (imports are relative to oracle_v2/)
cd /d "%~dp0oracle_v2"
python -m ui.setup_wizard
if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] Le wizard a plante. Lance manuellement :
    echo   cd oracle_v2 ^&^& python -m ui.setup_wizard
    pause
)
