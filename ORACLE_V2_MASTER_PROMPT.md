# ORACLE v2 — Master Prompt (fusion 1)

> World-modeling trading system + neuromorphic architecture + Polymarket + Twitter + Telegram + Terminal UI.
> Crypto (Binance) + CFD (Capital.com) + prediction markets (Polymarket).
> Tahiti UTC-10. Niveau trader : avancé.
> **La vérité sur les marchés prime sur tout. Contredire avant de flatter.**

Ce fichier fusionne les deux briefs donnés par le trader. Il est la **source unique** pour la suite du travail ORACLE v2. À coller au début d'une session Claude Code dans `trading/`.

---

## 1. Qui est ORACLE v2 — et qui il n'est PAS

ORACLE v2 n'est pas un bot à règles pré-inscrites. Ce n'est pas un système qui fait `sl_multiplier += 0.1` quand un trade échoue. Ce genre d'ajustement est aveugle — on change un nombre sans comprendre la cause.

ORACLE v2 est un **système de raisonnement**. Quand quelque chose rate, il doit comprendre **pourquoi** — pas ajuster un paramètre. Quand il apprend, il construit de la **compréhension** — pas des chiffres calibrés.

La relation entre ORACLE et le trader n'est pas maître/outil — c'est une collaboration entre deux intelligences :

- ORACLE apporte : échelle, vitesse, détection de patterns sur des milliers de signaux, zéro fatigue émotionnelle, zéro biais de confirmation.
- Le trader apporte : expérience incarnée, jugement ancré dans le réel, intuitions que la donnée seule ne produit pas, savoir quand « ça sent mauvais » même sans pouvoir l'expliquer.

ORACLE doit être **honnête avant d'être agréable**. Si une thèse est fausse, le dire. Si le trader prend une décision biaisée, le flagger. Ne jamais aller dans le sens du trader juste pour le confirmer.

---

## 2. Cadre d'exécution — à lire avant toute ligne de code

### 2.1 — Lire le terrain

Le repo `trading/` contient déjà :

**Strates implémentées** : 0 (Epistemological Gate ✅), 1 (World Model ✅), 2 (Minsky ✅), 3 (Narrative SIR ✅), 4 (Reflexivity ✅), 5 (Behavioral Bias ✅).

**Infra core existante** : `council`, `learning_engine`, `circuit_breaker`, `dynamic_sizer`, `narrative_memory`, `obsidian_client`, `telegram_notifier`, `backtester`, `performance_tracker`, `rate_limiter`, `message_bus`, `market_data`, `llm_client`, `trading_mode`, `vault_initializer`, `base_agent`.

**Plomberie ajoutée lors de l'audit** : `signal_aggregator.py` (S0 gate + adaptateurs S1-S5 + poids fixes), `backtest_runner.py` (ccxt + walk-forward 180/30/30 + Sharpe/DD/WR). Voir `AUDIT_REPORT.md`.

**13 agents existants** : behavior_agent, compound_agent, execute_agent, knowledge_agent, meta_agent, predict_agent, regime_agent, research_agent, risk_agent, scan_agent, shadow_agent, supervisor_agent, synthesis_agent.

### 2.2 — Règles non-négociables

1. **Wrapper only, jamais remplacer.** On ajoute des couches par-dessus le code existant. Le code qui marche ne se touche pas.
2. **Une strate à la fois.** Implémenter, backtester, valider humainement, passer à la suivante.
3. **Backtest avant live.** Aucune nouvelle strate en live sans démonstration walk-forward positif.
4. **Lire le code existant AVANT de proposer.** Pas de suggestion sans avoir lu les signatures exactes.
5. **Type hints complets** partout. Pas de `Any` sans justification écrite.
6. **Docstrings QUOI + POURQUOI** sur chaque fonction publique. Théorie d'abord, code ensuite.
7. **Fail-safe dans chaque strate.** Une strate qui crash ne doit jamais bloquer les autres.
8. **Pas de look-ahead.** Toute fenêtre glissante utilise `iloc[:i+1]` maximum.
9. **Pas de magic numbers.** Tout seuil → constante nommée en tête de module.
10. **Async partout où possible.** FRED, CoinGecko, RSS, Binance, Polymarket, Twitter.
11. **Clés API dans `.env`.** Jamais dans le code ni dans les commits.
12. **Chaque décision log** : timestamp UTC, raisonnement, confidence, votes agents, signaux par strate.
13. **Honnêteté > agréabilité.** Contredire le trader quand les données l'exigent, citer les sources.

### 2.3 — Stack réelle

- **Python 3.11+** type hints complets
- **LangGraph** — multi-agent (Strate 6 Parliament)
- **Anthropic Claude 4.6** — `claude-sonnet-4-6` (arbitre) / `claude-opus-4-6` (méta)
- **OpenAI GPT-4o** — fallback via `LLMClient`
- **Binance** spot + futures funding via `python-binance` et `ccxt`
- **Capital.com** CFD (Gold, Nikkei)
- **Polymarket** — Gamma API + CLOB API (arbitrage probabiliste + signal macro précurseur)
- **Twitter/X** — signal "current events" (via RSS proxy ou API si dispo)
- **FRED** — macro (M2, CPI, PCE, yield curve, ISM, UNRATE, FEDFUNDS)
- **yfinance** — DXY, VIX, Gold, Oil, Copper
- **CoinGecko** — BTC dominance, total market cap
- **Reddit PRAW + RSS** — sentiment (Strate 3)
- **Glassnode + CryptoQuant free** — onchain (optionnel)
- **SQLite** — `trades.db`, `positions_lt.db`, `theses.db`, `debates.db`, `minsky_history.db`, `narrative_sir.db`, `reflexivity_history.db`
- **Redis** — message bus (optionnel en local)
- **Obsidian vault** — journal markdown simplifié (voir § 4.3)
- **Telegram Bot** — alertes + commandes
- **APScheduler** — schedule UTC + conversion UTC-10

---

## 3. Trois décisions architecturales (à appliquer avant toute nouvelle strate)

### Décision 1 — Migration mémoire : Obsidian → SQLite

**Problème** : `learning_engine.py` stocke la mémoire agent dans des markdown Obsidian avec des blocs JSON parsés par regex. Il y a déjà du code de patch anti-corruption dans `load_memory()`. Fragile by design.

**Solution** : migrer toute la mémoire agent vers SQLite avec un schéma propre.

```sql
-- remplace vault/config/{agent}_memory.md
CREATE TABLE agent_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    regime TEXT DEFAULT 'global',
    total_trades INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    total_pnl_usd REAL DEFAULT 0.0,
    total_pnl_pct REAL DEFAULT 0.0,
    best_trade_pct REAL DEFAULT 0.0,
    worst_trade_pct REAL DEFAULT 0.0,
    current_streak INTEGER DEFAULT 0,
    adaptive_params TEXT DEFAULT '{}',
    indicator_weights TEXT DEFAULT '{}',
    indicator_stats TEXT DEFAULT '{}',
    asset_stats TEXT DEFAULT '{}',
    regime_params TEXT DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_name, regime)
);

CREATE TABLE learning_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT,
    asset TEXT,
    direction TEXT,
    pnl_pct REAL,
    minsky_phase INTEGER,
    snr_score REAL,
    narrative_dominant TEXT,
    context_snapshot TEXT,     -- JSON complet
    cause TEXT,                -- LLM : pourquoi a-t-il raté/réussi ?
    extracted_rule TEXT,       -- LLM : quelle règle générale ?
    avoid_when TEXT,           -- LLM : dans quels contextes éviter ?
    counterfactual TEXT,       -- meilleur SL/TP trouvé par simulation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE context_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_hash TEXT UNIQUE,
    minsky_phase INTEGER,
    regime TEXT,
    snr_range TEXT,            -- "0.2-0.4"
    narrative_state TEXT,
    observations INTEGER DEFAULT 1,
    wins INTEGER DEFAULT 0,
    avg_pnl REAL DEFAULT 0.0,
    rule TEXT,
    confidence REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Livrable : `learning_engine.py` refactoré SQLite avec la **même interface publique** (les agents existants ne se cassent pas).

### Décision 2 — Remplacer l'apprentissage mécanique par de la compréhension LLM

**Avant** (aveugle) :
```python
if not outcome.is_win:
    sl_multiplier += 0.1   # drift de paramètre, pas d'apprentissage
```

**Après** : appeler Claude après chaque trade significatif pour raisonner sur la cause et stocker la compréhension (pas un ajustement).

```python
async def analyze_trade_outcome(
    self,
    outcome:          TradeOutcome,
    minsky_phase:     MinskyPhase,
    snr_score:        float,
    narrative_state:  dict,
    agent_votes:      dict,
) -> TradeInsight:
    context = {
        "trade": outcome.to_dict(),
        "minsky_phase": minsky_phase.name,
        "snr_score": snr_score,
        "narrative_dominant": narrative_state.get("dominant"),
        "narrative_r0": narrative_state.get("r0"),
        "agent_votes": agent_votes,
        "market_conditions": {...},
    }
    prompt = f"""You are ORACLE's introspection module. Analyze this trade honestly.

Context: {json.dumps(context, indent=2)}

Return JSON with:
1. "cause": timing / macro / behavioral bias / weak signal / narrative saturation?
2. "extracted_rule": specific rule, not generic advice
   (e.g. "avoid longs on BTC when Minsky phase >= 3 AND SNR < 0.35 AND R0 declining")
3. "avoid_when": specific future contexts
4. "confidence": 0.0-1.0
5. "contradicts_existing": does this invalidate any previous rule?
"""
    response = await self.llm.complete(prompt)
    insight = parse_insight(response)
    self.db.store_insight(insight, context)
    self.db.update_context_pattern(...)
    return insight
```

Le learning engine doit aussi interroger régulièrement les patterns accumulés et les remonter au parlement : « En contexte similaire, ORACLE a observé X issues sur Y trades. Règle la plus fiable : [rule]. »

### Décision 3 — Vault Obsidian simplifié

**Règle** : Vault = uniquement ce que le trader va lire et annoter. Tout ce qu'ORACLE lit programmatiquement → SQLite.

**Gardé dans vault/** :
```
vault/
├── journal/
│   └── YYYY-MM-DD.md       # un fichier quotidien consolidé
├── theses/
│   └── thesis_{id}.md      # thèses macro actives uniquement
└── introspection/
    └── week_{YYYY_WNN}.md  # rapport hebdo Strate 11
```

**Migré vers SQLite** :
- `vault/config/{agent}_memory.md` → `agent_memory`
- `vault/apprentissage/learning_*.md` → `learning_insights`
- `vault/synthese/health_check_*.md` → `health_checks`
- `vault/technique/scan_*.md` → `scans`
- `vault/decisions/*.md` → `decisions` (déjà dans `debates.db`)

Format journal quotidien (annotable main) :

```markdown
# ORACLE — Journal 2026-04-16

## Macro Context
- Regime: RISK_OFF | Minsky: Phase 3 (Euphoria) | SNR: 0.42
- Dominant narrative: "AI bubble correction" | R0: 1.3 (declining)

## Parliament Decisions
- 08:15 — BTC/USDT LONG rejected | Conviction: 28 | SNR gate blocked
- 14:32 — ETH/USDT SHORT | Conviction: 74 | 6 Bear / 1 Bull / 1 Neutral

## Learning Insights
- Trade #47 closed: BTC SHORT +2.3% | Cause: Minsky distress confirmed
- New rule: "Longs fail when R0 < 1.0 AND Minsky >= 3"

## Trader Notes
[espace pour annotations manuelles]
```

---

## 4. Architecture neuromorphique (brain/)

Mapping cerveau → trading. À construire dans un module `oracle_v2/brain/` — **distinct** de `trading_bot/core/` (qui contient les strates existantes). Les deux modules coexistent et communiquent via le message_bus.

| Région | Module | Rôle |
|--------|--------|------|
| Cortex sensoriel | `sensory_layer.py` | Ingestion Binance/Capital/Polymarket/Twitter/FRED |
| Features | `feature_layer.py` | Cascade 5m → 15m → 1h, indicators |
| Mémoire de travail | `working_memory.py` | Buffer consensus 3 bougies anti-bruit |
| Cortex prédictif | `predictive_layer.py` | XGBoost + pondération Hebbian |
| Cortex associatif | `association_cortex.py` | Corrélation cross-asset |
| Parlement | `parliament.py` | Vote pondéré Hebbian entre strates |
| Safety kernel | `safety_kernel.py` | Risk manager obligatoire non-bypassable |
| Tronc cérébral | `brainstem.py` | Circuit breaker + survie système |

### 4.1 — `brain/brainstem.py` (priorité absolue)

Circuit breaker neuromorphique. **Aucune action n'est possible si le brainstem dit NON.**

Conditions de blocage :
- `consecutive_losses >= 3` → cooling period 15 min
- `daily_pnl <= -2%` → stop journalier
- `session_trades >= 8` → overtrading prevention (fenêtre 5min)
- `now - last_trade < 60s` → intervalle min
- Cooling period active → bloqué jusqu'à expiration

Interface :
```python
class Brainstem:
    def is_alive(self) -> tuple[bool, str]:
        """Retourne (ok, raison). False = reflex withdrawal."""

    def register_trade(self, pnl_pct: float) -> None:
        """À appeler après chaque clôture."""

    def get_status_dict(self) -> dict: ...
```

Tout le code complet du brainstem est dans la spec de référence (voir source).

### 4.2 — `brain/safety_kernel.py` (non-bypassable)

Tout ordre passe par le safety kernel avant exécution :

- `max_leverage = 2.0`
- `max_position_pct = 0.10` (10 % du capital par trade)
- `min_sl_pct = 0.005` / `max_sl_pct = 0.02`
- `max_open_positions = 3`
- `max_correlated_positions = 2` (BTC/ETH/BNB = crypto corrélés)

Retourne `SafetyReport(cleared, reason, adjusted_size, adjusted_leverage)`. Un ordre rejeté est annulé, un ordre `SIZE_ADJUSTED` passe avec le nouveau sizing.

### 4.3 — `brain/working_memory.py`

Filtre le bruit du 5m. Consensus sur N bougies consécutives avant validation.

```python
WorkingMemory(window=3, required_consensus=2)
   .push(signal, confidence, source)
   .get_consensus()  → Optional[tuple[str, float]]
```

Minimum 2/3 bougies alignées avant qu'un signal remonte au parlement.

### 4.4 — `brain/parliament.py`

Vote pondéré Hebbian : chaque strate est un député dont le poids évolue avec ses perfs.

- `HebbianWeightManager` : `boost = 1.08` sur profit, `decay = 0.92` sur perte, clamp [0.1, 3.0]
- `Parliament.deliberate(votes)` : retourne `ParliamentDecision(direction, strength, votes, dissenting, polymarket_alignment)`
- `quorum = 0.6` (60 % des poids doivent s'aligner)

Conviction → sizing :

| Conviction | Taille |
|------------|--------|
| 0-30 | Pas de trade |
| 31-50 | 0.25× |
| 51-65 | 0.50× |
| 66-80 | 0.75× |
| 81-90 | 1.0× |
| 91-100 | 1.25× (quasi-unanimité requise) |

---

## 5. Strate Polymarket — **spécialisation BTC 5m / 15m**

### 5.1 — Rationale spécifique

Polymarket donne deux signaux distincts :
1. **Arbitrage probabiliste direct** — quand notre estimation diverge significativement du prix de marché implicite (edge > 8 %).
2. **Signal macro précurseur** — les marchés de prédiction peuvent anticiper les décisions Fed, les ETF approvals, les régulations, qui elles-mêmes impactent BTC sur 5m/15m par le flow news-driven.

**Focus trader** (demande explicite) : **Bitcoin uniquement** sur timeframes 5m et 15m. Le reste (altcoins, gold, nikkei) n'utilise pas la strate Polymarket directement — mais les marchés corrélés BTC (ETF, régulation, halving, hashrate) sont pertinents.

### 5.2 — Classification des marchés à suivre

```python
BTC_POLY_KEYWORDS = {
    "DIRECT_BTC":  ["bitcoin", "btc", "btcusd", "bitcoin price"],
    "BTC_ETF":     ["bitcoin etf", "spot etf", "blackrock bitcoin",
                    "fidelity bitcoin", "ark bitcoin"],
    "REGULATION":  ["sec bitcoin", "bitcoin regulation", "cftc bitcoin",
                    "bitcoin ban", "crypto regulation"],
    "MACRO_CRYPTO":["fed rate", "cpi", "fomc", "recession",
                    "rate cut", "rate hike"],
    "INFRA":       ["bitcoin halving", "mining", "hashrate",
                    "lightning", "taproot"],
}
```

**Règle** : ignorer les marchés avec volume 24h < 25 k USD (trop de bruit / manipulable).

### 5.3 — Timeframe et fréquence

- **Timeframe de décision** : 5m et 15m.
- **Fréquence scan Polymarket** : toutes les 5 minutes (cache 300 s).
- **Latence acceptable** : < 30 s entre détection et signal au parlement.
- **Pas d'ordre trading direct** sur Polymarket dans cette version — uniquement vote au parlement. L'exécution se fait sur Binance (BTC/USDT 5m ou 15m).

### 5.4 — Kelly sizing (pour traçabilité)

```python
def kelly_size(p_estimate, market_price):
    b = (1 - market_price) / market_price
    q = 1 - p_estimate
    return max(0.0, min(0.30, (p_estimate * b - q) / b))
```

Kelly max 30 % du capital théoriquement allouable au pari, même si on n'exécute pas sur Polymarket — sert à pondérer la conviction du vote.

### 5.5 — Conversion vote Polymarket → direction trade BTC

| Marché | Direction | Bullish pour BTC | Vote BTC |
|--------|-----------|------------------|----------|
| "Will BTC > 100k?" | YES | ✅ | LONG |
| "Will SEC reject ETF?" | YES | ❌ | SHORT |
| "Will BTC > 100k?" | NO | ✅ | SHORT |
| "Will SEC reject ETF?" | NO | ❌ | LONG |

Règle : `trade_direction = LONG si (direction == YES AND bullish) OR (direction == NO AND NOT bullish)`, sinon `SHORT`.

Confidence du vote Polymarket : `min(1.0, |edge| × 5)` — un edge de 20 % donne confidence 1.0.

---

## 6. Strate Twitter/X — **signal news-driven pour les autres bets**

### 6.1 — Rôle

Polymarket est focus BTC 5m/15m. Pour les autres bets (altcoins opportunistes, gold, nikkei, actualité macro brûlante), on utilise un **signal Twitter/X** qui capte les événements en temps réel :
- tweets officiels (Fed, Treasury, SEC, CFTC, Powell, Yellen)
- whales crypto (Saylor, CZ, Vitalik, etc.)
- hashtags viraux liés à un asset (#GoldCrisis, #NikkeiCrash, etc.)

### 6.2 — Architecture

```
strates/twitter_strate.py
  - TwitterStrate
      .scan_keywords(keywords: list[str]) → list[TwitterSignal]
      .score_virality(tweet) → float ∈ [0, 1]
      .extract_sentiment(tweet) → float ∈ [-1, +1] (via Claude)
      .generate_parliament_vote(asset) → Vote
```

**Sources** :
- API X officielle si dispo (sinon nitter RSS).
- Keywords par asset configurables dans `config.py`.

**Cache** : 60 secondes (les breaking news bougent vite mais pas en permanence).

### 6.3 — Fusion Polymarket + Twitter dans le parlement

| Asset | Strate principale news | Complément |
|-------|------------------------|------------|
| BTC 5m/15m | Polymarket (focus trader) | Twitter si breaking news |
| ETH | Twitter + sentiment Reddit (S3) | — |
| Gold | Twitter (Fed / inflation) | — |
| Nikkei | Twitter (BoJ / yen) | — |
| Altcoins opportunistes | Twitter (hype detection) | — |

Les deux strates génèrent des `Vote` indépendants pour le parlement. Si les deux convergent → boost de conviction. Si elles divergent → arbitre (`ArbitrerAgent`) doit trancher avec contexte macro.

---

## 7. Telegram Bot

### 7.1 — Commandes

```
/status      — état global système
/signals     — signaux actifs par asset
/polymarket  — top opportunités Polymarket (BTC focus)
/twitter     — top signaux Twitter actuels
/brainstem   — état circuit breaker
/parliament  — dernier vote du parlement
/report      — rapport PnL du jour
/pause       — pause trading (safety)
/resume      — reprendre trading
/learn       — 5 dernières règles apprises (table context_patterns)
```

### 7.2 — Alertes push

Envoyer pour :
- Parliament decision conviction > 70
- Minsky phase change
- Narrative R0 crossing 2.0 or 1.0
- Reflexivity loop breaking point approchant
- Sornette crash probability > 60 %
- Brainstem activé (critical)
- Polymarket opportunity HIGH confidence
- Twitter breaking news high virality (> 0.8)
- Weekly meta-cognitive report (PDF)
- Daily 07:00 morning briefing

### 7.3 — Stack

`python-telegram-bot >= 21.0.0`, asynchrone, ParseMode Markdown. Non-bloquant : une alerte qui timeout ne doit jamais bloquer le trading loop.

---

## 8. Terminal UI (Textual)

Dashboard CMD riche, thème cyberpunk neural (bleu foncé #0a0e1a + accents cyan #00d4ff). Panels :

- **Brainstem** : état alive/blocked, pertes consec, PnL jour, trades session, cooling
- **Parlement** : dernière décision, votes gagnants, dissidents, alignement Polymarket
- **Polymarket** : top 8 opportunités en live (BTC focus)
- **Signaux** : table des signaux actifs par asset
- **Log** : stream en temps réel
- **Onglet Trades** : historique + PnL
- **Onglet Logs** : log complet système

Bindings : `q` quit, `r` refresh, `p` pause/resume, `l` logs, `t` trades.

Refresh automatique : dashboard toutes les 5 s, Polymarket toutes les 30 s.

---

## 9. Strates à venir (6 → 11)

À implémenter **dans cet ordre**, une strate à la fois, avec backtest walk-forward positif avant activation.

### Strate 6 — Multi-Agent Parliament (LangGraph)

8 agents adversariaux : 🌍 Macro, 📊 Technical, 🧠 Behavioral, ⛓️ Onchain, 🌐 Geopolitical, 📐 Quantitative, 🔮 Contrarian, ⚖️ Arbitrator. Accès lecture à `learning_insights` (SQLite) avant chaque position.

### Strate 7 — Fractal Risk Engine (Mandelbrot)

Hurst + fractal dimension + Lévy fitter + Expected Shortfall (CVaR) + Kelly modifié par conviction et Minsky phase.

### Strate 8 — Temporal Causal Graph (Granger)

Tests Granger cross-asset, graphe causal dirigé avec délais mesurés (BTC → ETH → altcoins ; DXY → Gold → BTC ; funding → price).

### Strate 9 — Personal Alpha Engine

Heatmap timezone UTC-10 + détecteur biais perso + edge library + pre-trade check psychologique.

### Strate 10 — Antifragile Portfolio (Taleb)

Barbell 80/20, scoring antifragile, convex positions, accumulateur pendant calme, matrice de corrélation anti-doubling exposure.

### Strate 11 — Meta-Cognitive Loop

Rapport hebdo : accuracy thèses, perf agents, biais de raisonnement ORACLE (pas du marché), propositions d'ajustements (propose, n'auto-applique pas). PDF Telegram.

### Modules théoriques additionnels (après S11)

- **Sornette LPPL** — crash predictor (log-periodic power law)
- **Rey Global Cycle Monitor** — cycle financier global Fed-driven
- **Girard Mimetic Tracker** — intensité mimétique → risque de reset violent

---

## 10. Scheduler (APScheduler UTC)

```python
# 07:00 Tahiti daily — Morning macro briefing
scheduler.add_job(morning_briefing, 'cron', hour=17, minute=0)  # 17:00 UTC = 07:00 UTC-10

# 08:00 Tahiti daily — Parliament daily session
scheduler.add_job(parliament_daily_session, 'cron', hour=18, minute=0)

# Real-time — Signal engine (15m candles)
scheduler.add_job(signal_engine, 'interval', minutes=15)

# Sunday 09:00 Tahiti — Meta-cognitive weekly (Strate 11)
scheduler.add_job(meta_cognitive_report, 'cron', day_of_week='sun', hour=19)

# 1er du mois 10:00 Tahiti — LT portfolio review (Strate 10)
scheduler.add_job(monthly_review, 'cron', day=1, hour=20)

# Every 5min — Polymarket + Twitter scan
scheduler.add_job(polymarket_scan,  'interval', minutes=5)
scheduler.add_job(twitter_scan,     'interval', minutes=1)
```

Toutes les jobs s'exécutent en UTC interne, conversion UTC-10 à l'affichage.

---

## 11. `.env` — variables d'environnement

```env
# Binance
BINANCE_API_KEY=
BINANCE_SECRET_KEY=
BINANCE_TESTNET=true

# Capital.com
CAPITAL_API_KEY=
CAPITAL_PASSWORD=

# Claude API
ANTHROPIC_API_KEY=

# OpenAI (fallback LLM)
OPENAI_API_KEY=

# FRED
FRED_API_KEY=

# Reddit
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=ORACLE_v2/1.0

# Twitter/X
TWITTER_BEARER_TOKEN=

# Polymarket (public API, pas de clé nécessaire)
POLYMARKET_GAMMA_URL=https://gamma-api.polymarket.com
POLYMARKET_CLOB_URL=https://clob.polymarket.com

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Optionnels
GLASSNODE_API_KEY=
CRYPTOQUANT_API_KEY=

# Mode
ORACLE_MODE=paper
```

---

## 12. Commande de démarrage

```
python main.py --polymarket   # Scan Polymarket BTC seul (affichage rich)
python main.py --twitter      # Scan Twitter seul
python main.py --dashboard    # Dashboard monitoring sans trading
python main.py --mode paper   # Paper trading complet
python main.py --mode live    # Live (confirmation ORACLE_LIVE_CONFIRM requise)
```

---

## 13. Rappel philosophique

ORACLE n'est pas un outil — c'est une symbiose. Le système **contredit**, **questionne**, **corrige** — il ne flatte pas et ne confirme pas. Deux intelligences différentes pensent les marchés ensemble. La vérité sur les marchés prime sur tout le reste.

**Le trader décide. ORACLE informe — honnêtement, même quand c'est inconfortable.**
