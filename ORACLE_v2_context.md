# ORACLE v2 — World-Modeling Trading System

## Contexte réel du projet

ORACLE v2 est un système de trading cognitif multi-agents
déjà en cours de construction. Ce n'est PAS un bot simple.

Base de code existante :

- trading_bot/ — architecture complète
- 13 agents spécialisés déjà écrits (behavior, compound,
  execute, knowledge, meta, predict, regime, research,
  risk, scan, shadow, supervisor, synthesis)
- Infrastructure core complète : council, learning_engine,
  circuit_breaker, dynamic_sizer, narrative_memory,
  obsidian_client, telegram_notifier, backtester

Strates implémentées :

- [x] Strate 0 — Epistemological Engine (Shannon entropy,
  SNR gate — Fischer Black)
- [x] Strate 1 — World Model Engine (macro simulation,
  Monte Carlo)
- [x] Strate 2 — Minsky Cycle Detector (5 phases Kindleberger)
- [ ] Strate 3 à 11 — à implémenter

## Profil trader

- Localisation : Polynésie française, Tahiti (UTC-10)
- Marchés : Crypto sur Binance (BTC, ETH, majors)
- Style : Swing + day trading + allocation long terme
- Niveau : Avancé — XGBoost, SHAP, multi-timeframe,
  backtesting, LangGraph
- Edge UTC-10 : voit US close + Asia open simultanément

## Stack technique

- Python 3.11+ avec type hints complets
- LangGraph (multi-agent parliament)
- Claude API — claude-sonnet-4-20250514
- Binance API (python-binance SDK)
- Capital.com fallback (CFD — Nikkei, Gold)
- FRED API (macro : M2, CPI, yield curve, ISM)
- yfinance (fallback), Binance WebSocket (live)
- Reddit PRAW + RSS (sentiment)
- Glassnode + CryptoQuant free tier (onchain)
- SQLite (trades.db, positions_lt.db, theses.db, debates.db)
- Obsidian (vault journaling)
- Telegram (alertes)
- APScheduler (UTC-10 schedule)

## Fondations théoriques

- Fischer Black → Signal vs bruit (Strate 0 ✅)
- Minsky/Kindleberger → Fragilité cyclique (Strate 2 ✅)
- W. Brian Arthur → World Model complexe (Strate 1 ✅)
- Shiller → Épidémiologie des narratives SIR (Strate 3)
- Soros → Réflexivité, boucles prix/réalité (Strate 4)
- Kahneman → Biais comportementaux exploitables (Strate 5)
- LangGraph agents → Parlement de débat (Strate 6)
- Mandelbrot → Distributions fractales, vraie VaR (Strate 7)
- Granger → Causalité temporelle entre actifs (Strate 8)
- Edge personnel → UTC-10 + profil cognitif (Strate 9)
- Taleb + Kelly → Antifragilité + sizing optimal (Strate 10)
- Popper/Kuhn → Méta-cognition, introspection (Strate 11)

## Nouvelles théories à intégrer (session d'aujourd'hui)

- Sornette LPPL → Prédiction mathématique des crashes
- Hélène Rey → Global Financial Cycle tracker
- René Girard → Intensité mimétique, crise sacrificielle
- Douglass North → Dégradation institutionnelle
- Georgescu-Roegen → Limites thermodynamiques
- AEGIS → Gestion patrimoniale évolutive (ETFs/métaux)

## Règles non-négociables

1. Ne jamais casser le code existant — wrapper, ne pas remplacer
1. Chaque strate est une nouvelle couche sur les signaux existants
1. Chaque décision log : timestamp, raisonnement, confidence,
   votes agents
1. Validation humaine avant tout changement à l'exécution live
1. Toutes les API keys dans .env — jamais dans le code
1. Une strate à la fois — attendre validation avant la suivante
1. Backtest avant live — chaque strate testable indépendamment
1. Être honnête avant d'être agréable — contredire si nécessaire

## Standards de code

- Type hints complets partout
- Docstring sur chaque fonction (QUOI et POURQUOI)
- Chaque strate expose : analyze() → dict
  et backtest(df) → BacktestResult
- Pas de magic numbers — tout dans config.py
- Async où possible
- Error handling : une strate ne crashe jamais le système entier

## Vision philosophique

ORACLE n'est pas un outil. C'est une symbiose entre
une intelligence artificielle et un trader humain.
Le système doit contredire, questionner, corriger —
pas flatter ni confirmer. La relation est celle de deux
intelligences différentes qui pensent les marchés ensemble.
La vérité sur les marchés prime sur tout le reste.

## Ce que j'attends

- Lire le code existant AVANT de proposer quoi que ce soit
- Expliquer POURQUOI avant HOW — théorie d'abord, code ensuite
- Implémenter exactement UNE strate par session
- Signaler tout conflit avec le code existant
- Ne pas amplifier les idées — les évaluer honnêtement
- Niveau avancé — pas d'explications de base
