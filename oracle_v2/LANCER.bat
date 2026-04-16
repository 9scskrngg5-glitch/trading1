@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title ORACLE v2

:: ─────────────────────────────────────────────────────────────
::  ORACLE v2 — Launcher principal
::  Double-cliquer pour demarrer
:: ─────────────────────────────────────────────────────────────

cd /d "%~dp0"

:: Charger .env si present
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "%%A=%%B"
    )
)

goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  FONCTIONS UTILITAIRES
:: ═════════════════════════════════════════════════════════════

:header
cls
echo.
echo  +==========================================================+
echo  ^|                                                          ^|
echo  ^|         O R A C L E   v 2                                ^|
echo  ^|         Systeme de Trading Neuromorphique                ^|
echo  ^|         12 strates cognitives unifiees                   ^|
echo  ^|                                                          ^|
echo  +==========================================================+
echo.
goto :eof

:check_env
:: Verifie si .env existe et contient les cles necessaires
set ENV_OK=1
if not exist ".env" set ENV_OK=0
if "%BINANCE_API_KEY%"=="" set ENV_OK=0
goto :eof

:status_bar
echo  ----------------------------------------------------------
if exist ".env" (
    echo  .env         : [CHARGE]
) else (
    echo  .env         : [ABSENT - configuration requise]
)
if not "%BINANCE_API_KEY%"=="" (
    echo  Binance      : [CONFIGURE]
) else (
    echo  Binance      : [NON CONFIGURE]
)
if not "%ANTHROPIC_API_KEY%"=="" (
    echo  Claude AI    : [CONFIGURE]
) else (
    echo  Claude AI    : [NON CONFIGURE - narration template uniquement]
)
if not "%TELEGRAM_TOKEN%"=="" (
    echo  Telegram     : [CONFIGURE]
) else (
    echo  Telegram     : [NON CONFIGURE - alertes desactivees]
)
echo  ----------------------------------------------------------
echo.
goto :eof

:: ═════════════════════════════════════════════════════════════
::  MENU PRINCIPAL
:: ═════════════════════════════════════════════════════════════

:menu_principal
call :header
call :status_bar

echo   TRADING ALGORITHMIQUE
echo   ─────────────────────
echo   [1]  Paper Trading    (simulation — aucun fonds reel)
echo   [2]  Live Trading     (argent reel — cles Binance requises)
echo.
echo   POLYMARKET  ^&  ARBITRAGE
echo   ─────────────────────────
echo   [3]  BTC Latency Arb  (signal BTC Polymarket vs Binance live)
echo   [4]  Scan General     (toutes opportunites Polymarket live)
echo.
echo   ORACLE AI
echo   ─────────
echo   [5]  Chat avec Oracle (conversation + explications)
echo   [6]  Dashboard        (monitoring temps reel)
echo   [F]  Lancer Free-GPT4 (IA gratuite locale, port 5500)
echo.
echo   CONFIGURATION
echo   ─────────────
echo   [7]  Configurer les cles API  (Binance / Telegram / Claude)
echo   [8]  Lancer les tests (validation systeme)
echo   [Q]  Quitter
echo.
set /p choix="  Votre choix : "

if /i "%choix%"=="1" goto :trading_paper
if /i "%choix%"=="2" goto :trading_live
if /i "%choix%"=="3" goto :poly_btc
if /i "%choix%"=="4" goto :poly_general
if /i "%choix%"=="5" goto :chat
if /i "%choix%"=="6" goto :dashboard
if /i "%choix%"=="f" goto :free_gpt4
if /i "%choix%"=="7" goto :config_wizard
if /i "%choix%"=="8" goto :tests
if /i "%choix%"=="q" goto :fin
goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  TRADING — PAPER
:: ═════════════════════════════════════════════════════════════

:trading_paper
call :header
echo  PAPER TRADING
echo  =============
echo.
echo  Simulation complete sans argent reel.
echo  Les ordres sont calcules et loggues mais jamais envoyes a Binance.
echo  Parfait pour valider la strategie avant de passer en live.
echo.
echo  Paires par defaut : BTCUSDT  ETHUSDT  BNBUSDT
echo  Cycle             : 60 secondes
echo  BTC Latency Arb   : actif (scan Polymarket toutes les 30s)
echo.
echo  [Entree] Demarrer   [Q] Retour au menu
set /p conf="  > "
if /i "%conf%"=="q" goto :menu_principal

echo.
echo  Demarrage Paper Trading...
echo  (Ctrl+C pour arreter)
echo.
python main.py --mode paper
echo.
echo  Session terminee.
pause
goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  TRADING — LIVE
:: ═════════════════════════════════════════════════════════════

:trading_live
call :header
echo  LIVE TRADING  ***  ATTENTION : FONDS REELS  ***
echo  ================================================
echo.

:: Verifier les cles Binance
if "%BINANCE_API_KEY%"=="" (
    echo  [ERREUR] BINANCE_API_KEY non configure.
    echo.
    echo  Lancez d'abord l'option [7] pour configurer vos cles API.
    echo.
    pause
    goto :menu_principal
)
if "%BINANCE_SECRET%"=="" (
    echo  [ERREUR] BINANCE_SECRET non configure.
    echo.
    echo  Lancez d'abord l'option [7] pour configurer vos cles API.
    echo.
    pause
    goto :menu_principal
)

echo  Cles Binance    : detectees
echo  Compte          : REEL (fonds engages)
echo  Taille position : max 10%% du capital par trade
echo  Stop-Loss       : 0.5%% - 2%%
echo  Max drawdown    : 2%% par jour
echo  Max positions   : 3 simultanees
echo.
echo  Une confirmation supplementaire sera demandee au demarrage.
echo.
echo  [Entree] Continuer   [Q] Annuler
set /p conf="  > "
if /i "%conf%"=="q" goto :menu_principal

echo.
echo  Demarrage Live Trading...
python main.py --mode live
echo.
echo  Session terminee.
pause
goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  POLYMARKET — BTC LATENCY ARB  (toujours live)
:: ═════════════════════════════════════════════════════════════

:poly_btc
call :header
echo  BTC LATENCY ARBITRAGE  —  Polymarket Live
echo  ==========================================
echo.
echo  Modele : P(BTC ^> X) = N(d2) lognormal
echo  Source : Binance ticker public (gratuit, sans cle API)
echo  vs      Polymarket prix du marche binaire
echo.
echo  Detecte quand Polymarket sur/sous-evalue un seuil BTC.
echo  Exemple : BTC a 70 000 USD, Polymarket cote 42%%
echo            pour "BTC au-dessus de 65 000 le 30 avril"
echo            -> modele dit 67%%, edge = +25%%
echo.
echo  Ce mode est toujours LIVE — il lit les prix en temps reel.
echo  Aucun ordre n'est execute automatiquement.
echo.
echo  [Entree] Scanner maintenant   [Q] Retour
set /p conf="  > "
if /i "%conf%"=="q" goto :menu_principal

echo.
echo  Connexion Binance + Polymarket...
python main.py --btc-arb
echo.
pause
goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  POLYMARKET — SCAN GENERAL  (toujours live)
:: ═════════════════════════════════════════════════════════════

:poly_general
call :header
echo  SCAN POLYMARKET GENERAL  —  Live
echo  =================================
echo.
echo  Scanne tous les marches Polymarket correles aux actifs crypto.
echo  Detecte les divergences de prix avec les marches spot.
echo  Actifs couverts : BTC, ETH, BNB, SOL, XRP, GOLD, S^&P500...
echo.
echo  Ce scan est toujours LIVE — donnees temps reel Polymarket.
echo  Aucun ordre n'est execute automatiquement.
echo.
echo  [Entree] Scanner maintenant   [Q] Retour
set /p conf="  > "
if /i "%conf%"=="q" goto :menu_principal

echo.
echo  Scan Polymarket en cours...
python main.py --polymarket
echo.
pause
goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  CHAT ORACLE AI
:: ═════════════════════════════════════════════════════════════

:chat
call :header
echo  CHAT AVEC ORACLE
echo  ================
echo.
if "%ANTHROPIC_API_KEY%"=="" (
    echo  [INFO] ANTHROPIC_API_KEY non configure.
    echo  Oracle repond en mode template (logique simple).
    echo  Configurez la cle API Claude pour des reponses enrichies.
) else (
    echo  Mode : LLM enrichi (Claude Haiku)
)
echo.
echo  Oracle explique ses signaux, ses decisions, sa memoire.
echo  Tapez 'memoire' pour voir l'historique des pensees.
echo  Tapez 'exit' pour revenir au menu.
echo.
echo  [Entree] Demarrer   [Q] Retour
set /p conf="  > "
if /i "%conf%"=="q" goto :menu_principal

echo.
python main.py --chat
echo.
pause
goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  DASHBOARD
:: ═════════════════════════════════════════════════════════════

:dashboard
call :header
echo  DASHBOARD — Monitoring temps reel
echo  ===================================
echo.
echo  Affiche l'etat du systeme, les signaux actifs,
echo  les positions ouvertes et les performances.
echo.
echo  [Entree] Ouvrir   [Q] Retour
set /p conf="  > "
if /i "%conf%"=="q" goto :menu_principal

python main.py --dashboard
pause
goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  CONFIGURATION CLES API  (etape par etape)
:: ═════════════════════════════════════════════════════════════

:config_wizard
call :header
echo  CONFIGURATION DES CLES API
echo  ===========================
echo.
echo  Ce wizard va creer ou mettre a jour le fichier .env
echo  contenant vos cles d'acces aux services externes.
echo.
echo  Appuyez sur Entree pour laisser une valeur inchangee.
echo  Les valeurs actuelles sont affichees entre parentheses.
echo.
echo  [Entree] Continuer   [Q] Annuler
set /p conf="  > "
if /i "%conf%"=="q" goto :menu_principal

call :header
echo  ETAPE 1/4  —  Binance (trading crypto)
echo  ========================================
echo.
echo  Obtenez vos cles sur : https://www.binance.com/fr/my/settings/api-management
echo  Permissions requises : Lecture + Trading au comptant (PAS de retrait)
echo.

set BINANCE_KEY_DISPLAY=%BINANCE_API_KEY%
if "%BINANCE_KEY_DISPLAY%"=="" set BINANCE_KEY_DISPLAY=(non configure)

set BINANCE_SECRET_DISPLAY=%BINANCE_SECRET%
if "%BINANCE_SECRET_DISPLAY%"=="" set BINANCE_SECRET_DISPLAY=(non configure)

echo  Cle API actuelle    : %BINANCE_KEY_DISPLAY%
set /p NEW_BINANCE_KEY="  Nouvelle cle API    : "

echo  Secret actuel       : %BINANCE_SECRET_DISPLAY%
set /p NEW_BINANCE_SECRET="  Nouveau secret      : "

if not "%NEW_BINANCE_KEY%"=="" set BINANCE_API_KEY=%NEW_BINANCE_KEY%
if not "%NEW_BINANCE_SECRET%"=="" set BINANCE_SECRET=%NEW_BINANCE_SECRET%

echo.
echo  [OK] Binance configure.

call :header
echo  ETAPE 2/4  —  IA Narration (Free-GPT4 ou Claude)
echo  ===================================================
echo.
echo  Oracle peut parler et expliquer ses decisions via IA.
echo  Deux options (la premiere disponible sera utilisee) :
echo.
echo  Option A - Free-GPT4 local (RECOMMANDE, gratuit, sans cle)
echo    Lancez d'abord le serveur via option [F] du menu principal.
echo    URL par defaut : http://127.0.0.1:5500

set FREE_GPT4_DISPLAY=%FREE_GPT4_URL%
if "%FREE_GPT4_DISPLAY%"=="" set FREE_GPT4_DISPLAY=http://127.0.0.1:5500

echo    URL actuelle    : %FREE_GPT4_DISPLAY%
set /p NEW_GPT4_URL="    Nouvelle URL    : "
if not "%NEW_GPT4_URL%"=="" set FREE_GPT4_URL=%NEW_GPT4_URL%
if "%FREE_GPT4_URL%"=="" set FREE_GPT4_URL=http://127.0.0.1:5500

echo.
echo  Option B - Claude AI / Anthropic (payant, plus precis)
echo    Obtenez votre cle : https://console.anthropic.com/settings/keys
echo    Laissez vide si vous utilisez Free-GPT4.

set ANTHROPIC_DISPLAY=%ANTHROPIC_API_KEY%
if "%ANTHROPIC_DISPLAY%"=="" set ANTHROPIC_DISPLAY=(non configure)

echo    Cle actuelle    : %ANTHROPIC_DISPLAY%
set /p NEW_ANTHROPIC="    Nouvelle cle    : "

if not "%NEW_ANTHROPIC%"=="" set ANTHROPIC_API_KEY=%NEW_ANTHROPIC%

echo.
echo  [OK] Narration IA configuree.

call :header
echo  ETAPE 3/4  —  Telegram (alertes mobiles)
echo  ==========================================
echo.
echo  Pour creer un bot Telegram :
echo    1. Ouvrez Telegram, cherchez @BotFather
echo    2. Tapez /newbot et suivez les instructions
echo    3. Copiez le token fourni
echo    4. Pour le Chat ID : envoyez un message a votre bot,
echo       puis visitez https://api.telegram.org/bot[TOKEN]/getUpdates
echo.

set TELEGRAM_TOKEN_DISPLAY=%TELEGRAM_TOKEN%
if "%TELEGRAM_TOKEN_DISPLAY%"=="" set TELEGRAM_TOKEN_DISPLAY=(non configure)

set TELEGRAM_ID_DISPLAY=%TELEGRAM_CHAT_ID%
if "%TELEGRAM_ID_DISPLAY%"=="" set TELEGRAM_ID_DISPLAY=(non configure)

echo  Token actuel        : %TELEGRAM_TOKEN_DISPLAY%
set /p NEW_TG_TOKEN="  Nouveau token       : "

echo  Chat ID actuel      : %TELEGRAM_ID_DISPLAY%
set /p NEW_TG_ID="  Nouveau Chat ID     : "

if not "%NEW_TG_TOKEN%"=="" set TELEGRAM_TOKEN=%NEW_TG_TOKEN%
if not "%NEW_TG_ID%"=="" set TELEGRAM_CHAT_ID=%NEW_TG_ID%

echo.
echo  [OK] Telegram configure.

call :header
echo  ETAPE 4/4  —  Parametres de trading
echo  =====================================
echo.
echo  Ces parametres controlent le risque de chaque trade.
echo.

echo  Paires tradees      : BTCUSDT ETHUSDT BNBUSDT (defaut)
set /p NEW_PAIRS="  Nouvelles paires    : "

echo  Max drawdown/jour   : 2%% (defaut)
set /p NEW_DRAWDOWN="  Nouveau drawdown    : "

echo  Taille position max : 10%% du capital (defaut)
set /p NEW_SIZE="  Nouvelle taille     : "

:: Valeurs par defaut si rien entre
if "%NEW_PAIRS%"=="" set NEW_PAIRS=BTCUSDT ETHUSDT BNBUSDT
if "%NEW_DRAWDOWN%"=="" set NEW_DRAWDOWN=0.02
if "%NEW_SIZE%"=="" set NEW_SIZE=0.10

:: ─── Ecrire le fichier .env ───────────────────────────────
(
echo # ORACLE v2 — Configuration (genere par LANCER.bat)
echo # NE JAMAIS commiter ce fichier dans Git.
echo.
echo # Binance
echo BINANCE_API_KEY=%BINANCE_API_KEY%
echo BINANCE_SECRET=%BINANCE_SECRET%
echo.
echo # Telegram
echo TELEGRAM_TOKEN=%TELEGRAM_TOKEN%
echo TELEGRAM_CHAT_ID=%TELEGRAM_CHAT_ID%
echo.
echo # LLM Narration (priorite : Free-GPT4 local -^> Claude Haiku -^> template)
echo FREE_GPT4_URL=%FREE_GPT4_URL%
echo ANTHROPIC_API_KEY=%ANTHROPIC_API_KEY%
echo.
echo # Mode
echo ORACLE_MODE=paper
) > .env

call :header
echo  CONFIGURATION SAUVEGARDEE
echo  ==========================
echo.
echo  Fichier .env mis a jour avec succes.
echo.
echo  Resume de la configuration :
echo  ─────────────────────────────────────────────────────────
if not "%BINANCE_API_KEY%"=="" (
    echo   Binance      : CONFIGURE
) else (
    echo   Binance      : non configure (mode paper uniquement)
)
echo   Free-GPT4    : %FREE_GPT4_URL% (lancez [F] pour demarrer)
if not "%ANTHROPIC_API_KEY%"=="" (
    echo   Claude AI    : CONFIGURE (fallback si Free-GPT4 indisponible)
) else (
    echo   Claude AI    : non configure
)
if not "%TELEGRAM_TOKEN%"=="" (
    echo   Telegram     : CONFIGURE (alertes actives)
) else (
    echo   Telegram     : non configure
)
echo  ─────────────────────────────────────────────────────────
echo.
echo  Vous pouvez maintenant lancer le Paper Trading (option 1).
echo  Quand vous etes pret, passez en Live Trading (option 2).
echo.
pause
goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  FREE-GPT4 — Serveur IA local gratuit
:: ═════════════════════════════════════════════════════════════

:free_gpt4
call :header
echo  FREE-GPT4 — Serveur IA local (port 5500)
echo  ==========================================
echo.
echo  Ce serveur permet a Oracle de parler et s'expliquer
echo  en utilisant GPT-4 gratuitement, sans cle API.
echo.
echo  Une fois lance, Oracle l'utilisera automatiquement
echo  pour le mode chat et les narrations enrichies.
echo.
echo  Adresse : http://127.0.0.1:5500
echo.

set FREE_GPT4_DIR=C:\Users\gille\OneDrive\Bureau\bot\Free-GPT4-WEB-API

if not exist "%FREE_GPT4_DIR%\src\FreeGPT4_Server.py" (
    echo  [ERREUR] Serveur non trouve dans :
    echo  %FREE_GPT4_DIR%
    echo.
    pause
    goto :menu_principal
)

echo  [1]  Demarrer le serveur  (nouvelle fenetre)
echo  [2]  Demarrer + Interface Web GUI
echo  [Q]  Retour
echo.
set /p gpt4choix="  Votre choix : "

if /i "%gpt4choix%"=="q" goto :menu_principal

if /i "%gpt4choix%"=="1" (
    echo.
    echo  Lancement du serveur Free-GPT4 en arriere-plan...
    start "Free-GPT4 Server" cmd /k "cd /d "%FREE_GPT4_DIR%" && python src/FreeGPT4_Server.py"
    echo.
    echo  Serveur en cours de demarrage sur http://127.0.0.1:5500
    echo  Attendez 5-10 secondes puis lancez Oracle.
    echo.
    timeout /t 5 >nul
    goto :menu_principal
)

if /i "%gpt4choix%"=="2" (
    echo.
    echo  Lancement avec interface web...
    start "Free-GPT4 Server + GUI" cmd /k "cd /d "%FREE_GPT4_DIR%" && python src/FreeGPT4_Server.py --enable-gui"
    echo  Serveur demarre. Interface : http://127.0.0.1:5500/settings
    timeout /t 5 >nul
    goto :menu_principal
)

goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  TESTS
:: ═════════════════════════════════════════════════════════════

:tests
call :header
echo  VALIDATION DU SYSTEME
echo  ======================
echo.
echo  Lance la suite complete de 101 tests unitaires.
echo  Verifie toutes les strates, le parlement, les connecteurs.
echo.
echo  [Entree] Lancer   [Q] Retour
set /p conf="  > "
if /i "%conf%"=="q" goto :menu_principal

echo.
python -m pytest tests/ -v
echo.
pause
goto :menu_principal

:: ═════════════════════════════════════════════════════════════
::  FIN
:: ═════════════════════════════════════════════════════════════

:fin
cls
echo.
echo  ORACLE v2 ferme.
echo.
timeout /t 2 >nul
endlocal
exit /b 0
