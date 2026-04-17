# ORACLE v2 — Workflow d'implémentation

Document de travail. Lecture obligatoire avant chaque session de dev.
Compagnon de `ORACLE_V2_MASTER_PROMPT.md` (le *quoi*) — ce fichier est le *quand* et le *dans quel ordre*.

Règle d'or : **une phase à la fois, gate de validation entre chaque, jamais deux chantiers en parallèle**.

---

## Phase 0 — État des lieux (déjà fait, à garder sous les yeux)

| Élément | Statut | Fichier |
|---|---|---|
| Strates 0-5 implémentées | ✅ | `trading_bot/core/strate_*.py` |
| `DynamicSizer` (Kelly/ADAPTIVE) | ✅ | `trading_bot/core/dynamic_sizer.py` |
| `SignalAggregator` (adaptateurs + fail-safe) | ✅ | `trading_bot/core/signal_aggregator.py` |
| `BacktestRunner` (ccxt + walk-forward) | ✅ | `trading_bot/core/backtest_runner.py` |
| `CLAUDE.md` (règles projet) | ✅ | `trading/CLAUDE.md` |
| `ORACLE_V2_MASTER_PROMPT.md` (spec cible) | ✅ | `trading/ORACLE_V2_MASTER_PROMPT.md` |
| `AUDIT_REPORT.md` (Phase 1 audit) | ✅ | `trading/AUDIT_REPORT.md` |
| Skill réutilisable `oracle-audit` | ✅ | `oracle-audit/` (workspace) |

**Gate Phase 0** : trois smoke-tests passent (S0 crash → FLAT, all-skipped → FLAT, bullish convergence → LONG). Documenté dans `AUDIT_REPORT.md`.

---

## Phase 1 — Fondations architecturales (trois décisions)

**Objectif** : poser les fondations avant d'ajouter la moindre nouvelle strate. L'ordre compte.

### 1.A — Migration Obsidian → SQLite (mémoire agents)

**Pourquoi d'abord** : tout ce qui suit (parliament, learning, polymarket) écrit dans la mémoire. Si la mémoire est en markdown éparpillé, on multiplie les bugs de parsing.

**Livrables** :
- `trading_bot/memory/schema.sql` (tables `episodes`, `agent_memory`, `parliament_votes`, `polymarket_snapshots`, `twitter_signals`)
- `trading_bot/memory/store.py` (wrapper sync + async, context manager)
- Script one-shot `scripts/migrate_obsidian_to_sqlite.py` (lit `vault/`, écrit dans `oracle.db`)
- Test : round-trip write/read sur chaque table

**Gate 1.A** : `oracle.db` créé, 100 % des fichiers `vault/agents/*.md` importés, aucun orphelin.

### 1.B — Refactor LLM learning (compréhension, pas paramètres)

**Pourquoi en deuxième** : avant de nourrir la mémoire avec des votes, on doit savoir ce qu'on veut apprendre. Le principe « drift de compréhension, pas drift de paramètres » exige un schéma clair.

**Livrables** :
- `trading_bot/learning/comprehension_log.py` (ajoute `hypothesis`, `observation`, `update_rule` à chaque post-trade)
- Hook dans `signal_aggregator` qui écrit un épisode après chaque décision
- Rapport `scripts/generate_learning_report.py` qui produit un markdown hebdo

**Gate 1.B** : une trade simulée produit un épisode complet lisible.

### 1.C — Simplification du vault

**Pourquoi en dernier de la phase 1** : une fois SQLite en place, le vault ne garde que la doc humaine (markdown). On supprime les sous-dossiers devenus caduques.

**Livrables** :
- Arborescence cible : `vault/README.md`, `vault/theories/`, `vault/decisions/`, `vault/backtest/` uniquement
- Script `scripts/vault_cleanup.py` (dry-run par défaut)

**Gate Phase 1** : les trois sous-étapes validées + backup `vault.zip` sauvegardé avant suppression.

---

## Phase 2 — Architecture neuromorphique (le « cerveau »)

**Objectif** : construire `brain/` avec les modules bas-niveau (brainstem, safety_kernel, working_memory) AVANT le parliament. Sans tronc cérébral, le cortex s'excite dans le vide.

### 2.A — `brain/brainstem.py`

Instincts de survie : circuit-breaker global, coupure urgence, heartbeat.

**Gate** : tuer le process via signal ; brainstem doit déclencher un flat_all avant exit.

### 2.B — `brain/safety_kernel.py`

Limites dures (max exposure, max drawdown, max trade size). Override impossible par les strates — c'est un veto en amont.

**Gate** : safety_kernel refuse une position qui dépasse 5 % du capital même si conviction = 0.99.

### 2.C — `brain/working_memory.py`

Buffer court terme, 50 derniers signaux par strate, accessible en O(1). Pas de SQLite ici — pure RAM.

**Gate** : dump du buffer après 100 cycles = exactement 50 entrées par strate.

### 2.D — `brain/parliament.py` (LangGraph)

Huit agents adversariaux avec poids Hebbiens. Les agents lisent `working_memory` + les votes des strates, débattent, produisent un vote final.

**Gate** : un scénario bullish unanime doit converger ; un scénario litigieux doit déclencher l'Arbitrator.

### 2.E — Couches sensorielle / feature / prédictive / association

Câblage : `sensory_layer` (normalisation prices/volume/sentiment) → `feature_layer` (indicateurs) → `predictive_layer` (forecast court terme) → `association_cortex` (fusion multi-modale vers parliament).

**Gate Phase 2** : un tick de marché traverse tout le pipeline sans erreur, temps < 200 ms.

---

## Phase 3 — Strate Polymarket (spécialisée BTC 5m + 15m)

**Objectif** : première « nouvelle » strate au sens du master prompt. Restreinte volontairement à BTC court terme pour cadrer le scope.

### 3.A — Fetcher Gamma API

`trading_bot/core/polymarket_fetcher.py` : liste les markets actifs, filtre via `BTC_POLY_KEYWORDS` (DIRECT_BTC / BTC_ETF / REGULATION / MACRO_CRYPTO / INFRA).
Cache 5 min côté SQLite (`polymarket_snapshots`).

### 3.B — Strate `polymarket_btc_strate.py`

Pour chaque market retenu :
- Calcul edge = `implied_probability − model_probability`
- Conversion direction via la table du master prompt
- Sizing Kelly fractionnaire (0.5 × Kelly) avec cap à 2 % du capital
- Fenêtre de décision = 5 min et 15 min uniquement

### 3.C — Adaptateur `adapt_s_polymarket` dans `SignalAggregator`

Intégration au pipeline existant sans toucher aux adaptateurs S1-S5. Poids initial : 0.10 (prélevé proportionnellement sur S1-S5, donc renormalisation).

**Gate Phase 3** :
- Backtest walk-forward sur 90 jours BTC 5m+15m, Sharpe > 0 sur ≥ 9 folds
- Dry-run 7 jours en paper-trading
- Review humaine avant d'activer en live

---

## Phase 4 — Strate Twitter/X (actualité hors-BTC court terme)

**Objectif** : couvrir les paris hors-scope Polymarket BTC (ETH, gold, Nikkei, altcoins, events macro) via signaux news.

### 4.A — Ingestion

`trading_bot/core/twitter_fetcher.py` : listes ciblées (Fed speakers, Treasury, SEC, whale trackers, analystes crypto verified). Pull toutes les 2 min.

### 4.B — Scoring & dé-duplication

NLP léger (keyword + sentiment + urgency), clustering pour éviter 500 retweets du même event.

### 4.C — Strate `twitter_news_strate.py` + adaptateur

Routing : si asset ∈ {BTC 5m, BTC 15m} → Polymarket primaire, Twitter fallback. Sinon → Twitter primaire.

### 4.D — Fusion dans le parliament

Polymarket et Twitter votent séparément. Convergence = boost conviction. Divergence = Arbitrator.

**Gate Phase 4** : même critère que Phase 3 (walk-forward + paper-trading + revue).

---

## Phase 5 — Telegram bot

**Objectif** : pilotage humain à distance, alertes push, pas de décision automatisée via Telegram.

### Commandes à implémenter

`/status`, `/signals`, `/polymarket`, `/twitter`, `/brainstem`, `/parliament`, `/report`, `/pause`, `/resume`, `/learn`.

### Alertes push

Drawdown > seuil, safety_kernel veto, strate crashée, trade ouvert/fermé.

**Gate Phase 5** : `/pause` coupe toute nouvelle entrée en < 2 s ; `/status` répond < 1 s.

---

## Phase 6 — Terminal UI (Textual cyberpunk)

**Objectif** : tableau de bord local temps réel. Purement lecture.

### Panels

Prix live, équité, positions ouvertes, votes parliament, signaux par strate, journal des trades, mémoire court terme.

### Thème

Cyberpunk Rich/Textual — palette `#00f5ff` / `#ff00aa` / `#0a0a1a`.

**Gate Phase 6** : UI tourne 24 h sans fuite mémoire, refresh < 500 ms.

---

## Phase 7 — Scheduler + cutover live

**Objectif** : orchestrer toutes les tâches et passer en live quand tout est vert.

### 7.A — APScheduler

- Polymarket fetch : 5 min
- Twitter fetch : 2 min
- Macro snapshot (S1) : 1 h
- Narrative SIR (S3) : 6 h
- Parliament cycle : 15 min (aligné BTC 15m)
- Learning report : hebdomadaire
- Backup DB : quotidien UTC 00:00

Tout en UTC, affichage UTC-10 (Tahiti) côté UI et Telegram.

### 7.B — Cutover criteria (avant live)

Checklist bloquante :
- [ ] Toutes les strates live (S0-S5 + Polymarket + Twitter) ont un backtest walk-forward ≥ 9 folds Sharpe > 0
- [ ] Paper-trading agrégé 14 jours consécutifs sans panic
- [ ] Brainstem + safety_kernel testés avec failure injection
- [ ] Telegram `/pause` validé sous load
- [ ] Backup quotidien vérifié sur 7 jours
- [ ] Clés API en `.env` + `.env` confirmé dans `.gitignore`
- [ ] Revue humaine finale par le trader

**Gate Phase 7** : si une seule case n'est pas cochée, on reste en paper-trading.

---

## Phase 8 — Roadmap strates 6-11 (après le core)

Ordre non négociable, une à la fois :

| Strate | Théorie | Précondition |
|---|---|---|
| S6 — Parliament adversarial (LangGraph) | Déjà construite en Phase 2.D, on la raffine |
| S7 — Mandelbrot fractal risk | Hurst + Higuchi + Lévy + CVaR ; après S6 stable |
| S8 — Granger causality | Besoin d'historique propre en SQLite, donc après Phase 1 |
| S9 — Optionalité convexe | Requiert S7 pour le sizing |
| S10 — Taleb antifragile barbell | Requiert S9 |
| S11 — Méta-cognition (Opus 4.6) | Dernière : observe tout le reste |

Modules théoriques additionnels (pas des strates votantes, des observateurs) : Sornette LPPL, Rey Global Cycle, Girard Mimetic. À brancher comme « senseurs » dans `association_cortex` après S11.

---

## Règles transverses (valables à chaque phase)

1. **Jamais supprimer de code qui tourne.** Wrapper, jamais réécrire.
2. **Jamais deux strates en parallèle.** Une à la fois, avec gate.
3. **Backtest avant live.** Sharpe > 0 sur ≥ 9 folds walk-forward, minimum.
4. **Fail-safe partout.** Chaque nouvelle strate a son try/except dans l'adaptateur.
5. **Pas de look-ahead.** `iloc[:i+1]` max, décision à `i` close, exécution à `i+1` open.
6. **Type hints complets, docstrings QUOI + POURQUOI.**
7. **Clés API dans `.env` uniquement.**
8. **Chaque décision écrite dans `episodes` SQLite.**
9. **Modèles Claude : `claude-sonnet-4-6` (arbitre), `claude-opus-4-6` (méta).** Ne jamais downgrader.
10. **Honnêteté > agréabilité.** Contredire le trader si les données l'exigent.

---

## Livrables par phase — récap une ligne

| Phase | Livrable principal | Gate |
|---|---|---|
| 0 | État des lieux | Smoke-tests aggregator passent |
| 1 | SQLite + learning + vault propre | Round-trip DB OK |
| 2 | `brain/` complet | Tick traverse < 200 ms |
| 3 | Polymarket BTC 5m/15m | Walk-forward ≥ 9 folds |
| 4 | Twitter news | Walk-forward ≥ 9 folds |
| 5 | Telegram | `/pause` < 2 s |
| 6 | Textual UI | 24 h sans fuite |
| 7 | Scheduler + cutover | Checklist 7.B complète |
| 8 | S6-S11 + modules obs | Un à la fois |

---

## Comment lire ce workflow dans Claude

Quand tu ouvres une session :

1. `Read trading/WORKFLOW.md` (ce fichier)
2. `Read trading/ORACLE_V2_MASTER_PROMPT.md` (spec)
3. `Read trading/CLAUDE.md` (règles)
4. `Read trading/AUDIT_REPORT.md` (dernier état)
5. Identifier la phase en cours
6. Ne rien commencer sans valider le gate de la phase précédente

Le master prompt dit *quoi construire*. Ce workflow dit *dans quel ordre* et *quand passer à la suivante*.
