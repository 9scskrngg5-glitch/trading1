# Claude Code Configuration — ORACLE v2

> World-Modeling Trading System. Crypto (Binance) + CFD fallback (Capital.com).
> Basé à Tahiti (UTC-10). Niveau trader : avancé.
> La vérité sur les marchés prime sur tout. Contredire avant de flatter.

## Stack réelle

- **Python 3.11+** avec type hints complets
- **LangGraph** — parlement multi-agents (Strate 6, à venir)
- **Anthropic Claude** — `claude-sonnet-4-6` (default) / `claude-opus-4-6` (méta)
- **OpenAI GPT-4o** — fallback via `LLMClient`
- **Binance** (spot + futures funding) via `python-binance` et `ccxt`
- **Capital.com** — CFD fallback (Nikkei, Gold) — optionnel
- **FRED API** — macro (M2, CPI, PCE, yield curve, ISM, UNRATE, FEDFUNDS)
- **yfinance** — DXY, VIX, Gold, Oil, Copper
- **CoinGecko** (pas de clé) — BTC dominance, total market cap
- **Reddit PRAW + RSS** — sentiment (Strate 3)
- **Glassnode + CryptoQuant free** — onchain (Strate 2, optionnel)
- **SQLite** — `trades.db`, `positions_lt.db`, `theses.db`, `debates.db`, `minsky_history.db`, `narrative_sir.db`, `reflexivity_history.db`
- **Obsidian vault** — journaling markdown (`vault/`)
- **Telegram Bot** — alertes temps réel
- **APScheduler** — schedule UTC-10 (voit US close + Asia open simultanément)

## Strates — État réel

| # | Nom | Fichier | Théorie | Statut |
|---|---|---|---|---|
| 0 | Epistemological Gate | `strate_0_epistemic.py` | Fischer Black — SNR + Shannon entropy | ✅ |
| 1 | World Model | `strate_1_world_model.py` | W. Brian Arthur — macro + Monte Carlo GBM | ✅ |
| 2 | Minsky Cycle | `strate_2_minsky.py` | Minsky / Kindleberger — 5 phases | ✅ |
| 3 | Narrative SIR | `strate_3_narrative_sir.py` | Shiller — épidémiologie R0 | ✅ |
| 4 | Reflexivity | `strate_4_reflexivity.py` | Soros — boucle prix ↔ sentiment, Hurst | ✅ |
| 5 | Behavioral Bias | `strate_5_behavioral_bias.py` | Kahneman — 7 biais contrariants | ✅ |
| 6 | Parliament | — | LangGraph Bull/Bear/Devil/Arbitre | ❌ |
| 7 | Fractal Risk | — | Mandelbrot — vraie VaR, distributions à queues lourdes | ❌ |
| 8 | Granger Causality | — | Granger — causalité temporelle entre actifs | ❌ |
| 9 | Personal Edge | — | Profil cognitif UTC-10 | ❌ |
| 10 | Antifragile Kelly | — | Taleb + Kelly — sizing optimal | ❌ |
| 11 | Meta-Cognition | — | Popper / Kuhn — introspection | ❌ |

Règle d'or : **une strate à la fois**. Ne pas sauter d'étape. Ne rien implémenter d'approximatif « en attendant ».

## Architecture des dossiers

```
trading/
├── CLAUDE.md                       # ce fichier
├── ORACLE_v2_context.md            # contexte projet (long)
├── trading_bot/
│   ├── core/                       # infrastructure + strates
│   │   ├── strate_0_epistemic.py
│   │   ├── strate_1_world_model.py
│   │   ├── strate_2_minsky.py
│   │   ├── strate_3_narrative_sir.py
│   │   ├── strate_4_reflexivity.py
│   │   ├── strate_5_behavioral_bias.py
│   │   ├── signal_aggregator.py    # agrège S0-S5 → sizing
│   │   ├── backtest_runner.py      # wrapper pipeline pour backtest
│   │   ├── council.py              # Bull/Bear/Devil/Arbitre (Claude API)
│   │   ├── dynamic_sizer.py        # Kelly / HalfKelly / ADAPTIVE
│   │   ├── backtester.py           # ancien backtester (ScanAgent direct)
│   │   ├── circuit_breaker.py      # coupe-circuit budget + erreurs
│   │   ├── learning_engine.py      # apprentissage post-trade
│   │   ├── llm_client.py           # wrapper Anthropic + OpenAI
│   │   ├── rate_limiter.py
│   │   ├── message_bus.py / message_bus_local.py
│   │   ├── narrative_memory.py
│   │   ├── obsidian_client.py
│   │   ├── telegram_notifier.py
│   │   ├── performance_tracker.py
│   │   ├── vault_initializer.py
│   │   └── market_data.py
│   ├── agents/                     # 13 agents existants (scan, risk, execute…)
│   ├── data/
│   ├── models/
│   ├── tests/
│   ├── vault/
│   │   ├── epistemic/              # gate_log.jsonl (Strate 0)
│   │   ├── world_model/            # cache.json + *.db (Strates 1-4)
│   │   └── backtest/               # sorties de backtest_runner
│   ├── requirements.txt
│   ├── run_demo.py
│   └── watchdog.py
└── docs/
```

## Règles de code — NON négociables

1. **Wrapper only, jamais remplacer.** On ajoute des couches par-dessus le code existant. Le code qui marche ne se touche pas.
2. **Une strate à la fois.** Implémenter, backtester, valider humainement, puis passer à la suivante.
3. **Backtest avant live.** Aucune nouvelle strate ne passe en live tant qu'elle n'a pas démontré son edge sur walk-forward.
4. **Lire le code existant AVANT.** Pas de proposition sans avoir lu les signatures exactes.
5. **Type hints complets** partout — pas de `Any` sauf justification écrite.
6. **Docstrings QUOI + POURQUOI** sur chaque fonction publique. La théorie d'abord, le code ensuite.
7. **Fail-safe dans chaque strate.** Une strate qui crash ne doit jamais bloquer les autres. `try/except → résultat neutre + log`.
8. **Pas de look-ahead bias.** Toute fenêtre glissante n'utilise que les barres strictement passées (`iloc[:i+1]` pour l'observation en `i`).
9. **Pas de magic numbers.** Tout seuil → constante nommée en tête de module, ou `config.py`.
10. **Async où possible.** Surtout pour les fetchers (FRED, CoinGecko, RSS, Binance).
11. **Toutes les clés API dans `.env`.** Jamais dans le code ni dans les commits.
12. **Chaque décision log** : timestamp UTC, raisonnement, confidence, votes agents, signaux par strate.
13. **Honnêteté > agréabilité.** Contredire le trader quand les données l'exigent, citer les sources.

## Interface standard des strates

Chaque strate doit exposer deux entrées compatibles avec `SignalAggregator` :

- Une méthode d'analyse live (noms variables selon la strate) retournant un `dict` ou dataclass sérialisable.
- Une méthode `backtest(df: pd.DataFrame) -> BacktestResult` rejouable sans effets de bord.

Le `SignalAggregator` connaît les adaptateurs par strate — il n'est pas requis que toutes les strates aient la même signature. Elles n'ont pas à se ressembler entre elles tant que l'aggregator sait les appeler.

## Timezone

- **Heure de référence : UTC**
- **Heure locale trader : Pacific/Tahiti (UTC-10)**
- Schedule APScheduler : toujours en UTC + conversion à l'affichage
- Edge UTC-10 : 06:00 UTC-10 = 16:00 UTC (US close) = 07:00 JST+1 (Asia open) — possibilité rare de voir les deux ensemble au réveil.

## Modèles Claude utilisés

| Usage | Modèle | Où |
|---|---|---|
| Débat courant (Bull/Bear/Devil/Arbitre) | `claude-sonnet-4-6` | `council.py` |
| Méta-cognition (Strate 11) | `claude-opus-4-6` | `agents/meta_agent.py` |
| Tarifs | cf. `llm_client.py` PRICING | `llm_client.py` |

Budget journalier par défaut : 10 USD. Coupe-circuit via `LLMClient.budget_exceeded`.

## Boot du pipeline

```python
from pathlib import Path
from trading_bot.core.strate_0_epistemic    import EpistemologicalEngine
from trading_bot.core.strate_1_world_model  import WorldModelEngine
from trading_bot.core.strate_2_minsky       import MinskyDetector
from trading_bot.core.strate_3_narrative_sir import NarrativeEpidemiologyEngine
from trading_bot.core.strate_4_reflexivity  import ReflexivityEngine
from trading_bot.core.strate_5_behavioral_bias import BehavioralBiasEngine
from trading_bot.core.signal_aggregator     import SignalAggregator
from trading_bot.core.dynamic_sizer         import DynamicSizer

vault = Path("trading_bot/vault")
aggregator = SignalAggregator(
    s0 = EpistemologicalEngine(vault_path=vault),
    s1 = WorldModelEngine(vault_path=vault),
    s2 = MinskyDetector(vault_path=vault),
    s3 = NarrativeEpidemiologyEngine(vault_path=vault),
    s4 = ReflexivityEngine(vault_path=vault),
    s5 = BehavioralBiasEngine(vault_path=vault),
    sizer = DynamicSizer(method="adaptive"),
)
```

## Rappel philosophique

ORACLE n'est pas un outil, c'est une symbiose. Le système doit **contredire**, **questionner**, **corriger** — pas flatter ni confirmer. Deux intelligences différentes pensent les marchés ensemble. La vérité sur les marchés prime sur tout le reste.
