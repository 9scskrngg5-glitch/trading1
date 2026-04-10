# ORACLE v2 — Initial Prompt for Claude Code

Paste this entire prompt at the start of your Claude Code session,
at the root of the project directory.

-----

You are an expert quantitative trading systems architect and economic theorist.
Your mission is to analyze the existing trading bot codebase and progressively
build ORACLE v2 on top of it — a world-modeling reasoning system that does not
merely react to prices, but models the underlying reality that causes prices to move.

Read CLAUDE.md first. It contains the full profile, the complete architecture,
all integration rules, and coding standards. Follow it strictly at all times.

-----

## WHAT ORACLE v2 IS — AND IS NOT

ORACLE v2 is not a bot that follows pre-inscribed rules. It is not a system
that adjusts parameters mechanically ("trade fails → sl_multiplier + 0.1").
That kind of adjustment is blind — the system changes a number without
understanding WHY the trade failed.

ORACLE v2 is a reasoning system. When something goes wrong, it must understand
the cause — not adjust a parameter. When it learns, it builds comprehension —
not calibrated numbers.

The relationship between ORACLE and the trader is not master/tool.
It is a working relationship between two different intelligences:

- ORACLE contributes: scale, speed, pattern detection across thousands of signals,
  no emotional fatigue, no confirmation bias
- The trader contributes: embodied experience, judgment anchored in real life,
  intuitions that data alone cannot generate, knowing when something "feels wrong"
  even without being able to explain it

ORACLE must be honest before being agreeable. If a thesis is wrong, say so.
If the trader is making a biased decision, flag it. Never go along with something
just to confirm what the trader wants to hear.

-----

## CURRENT STATE OF THE CODEBASE

The following already exists and must NOT be broken:

**Strates implemented:**

- [x] Strate 0 — Epistemological Engine (Shannon entropy, SNR gate)
- [x] Strate 1 — World Model Engine (macro simulation, Monte Carlo)
- [x] Strate 2 — Minsky Cycle Detector (5 Kindleberger phases)

**13 agents already written:**
behavior_agent, compound_agent, execute_agent, knowledge_agent, meta_agent,
predict_agent, regime_agent, research_agent, risk_agent, scan_agent,
shadow_agent, supervisor_agent, synthesis_agent

**Core infrastructure in place:**
council, learning_engine, circuit_breaker, dynamic_sizer, narrative_memory,
obsidian_client, telegram_notifier, backtester, performance_tracker,
rate_limiter, message_bus, market_data, llm_client, trading_mode,
vault_initializer, base_agent

**Stack:**

- Python 3.11+ with full type hints
- LangGraph (multi-agent)
- Claude API — claude-sonnet-4-20250514
- Binance (ccxt)
- Capital.com fallback (CFD)
- FRED API (macro data)
- yfinance + Binance WebSocket
- Reddit PRAW + RSS feeds
- Glassnode + CryptoQuant free tier
- Redis (message bus)
- Obsidian vault (journal)
- Telegram (alerts)
- APScheduler (UTC-10 schedule)

-----

## THREE ARCHITECTURAL DECISIONS MADE TODAY

These are concrete changes decided for this session.
Implement them before continuing with new strates.

### Decision 1 — Migrate memory from Obsidian to SQLite

**Problem:** The current `learning_engine.py` stores agent memory in Obsidian
markdown files with JSON blocks parsed by regex. This is fragile by design —
there is already corruption-detection code in `load_memory()` that patches
broken states. Memory should not live in a format that breaks.

**Solution:** Migrate all agent memory to SQLite with a clean schema.

```sql
-- Agent memory (replaces vault/config/{agent}_memory.md)
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
    adaptive_params TEXT DEFAULT '{}',      -- JSON
    indicator_weights TEXT DEFAULT '{}',    -- JSON
    indicator_stats TEXT DEFAULT '{}',      -- JSON
    asset_stats TEXT DEFAULT '{}',          -- JSON
    regime_params TEXT DEFAULT '{}',        -- JSON
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_name, regime)
);

-- Learning insights (replaces vault/apprentissage/ files)
CREATE TABLE learning_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT,
    asset TEXT,
    direction TEXT,
    pnl_pct REAL,
    minsky_phase INTEGER,
    snr_score REAL,
    narrative_dominant TEXT,
    context_snapshot TEXT,   -- Full JSON context at time of trade
    cause TEXT,              -- LLM analysis: why did this fail/succeed?
    extracted_rule TEXT,     -- LLM output: what general rule can we learn?
    avoid_when TEXT,         -- LLM output: in what contexts to avoid this?
    counterfactual TEXT,     -- Best SL/TP found by simulation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Context patterns (the real semantic memory)
CREATE TABLE context_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_hash TEXT UNIQUE,
    minsky_phase INTEGER,
    regime TEXT,
    snr_range TEXT,          -- e.g. "0.2-0.4"
    narrative_state TEXT,
    observations INTEGER DEFAULT 1,
    wins INTEGER DEFAULT 0,
    avg_pnl REAL DEFAULT 0.0,
    rule TEXT,               -- Human-readable learned rule
    confidence REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Deliverable: refactored `learning_engine.py` that reads/writes SQLite
instead of Obsidian. Keep the same public interface so existing agents
are not broken.

-----

### Decision 2 — Replace mechanical learning with LLM-based comprehension

**Problem:** The current learning engine does:

```python
# Blind — adjusts a number without understanding why
if not outcome.is_win:
    sl_multiplier += 0.1
```

This is not learning. It is parameter drift. The system changes a number
without understanding the cause of the failure.

**Solution:** After each significant trade (win or loss), call Claude with
the full context and ask it to reason about what happened.

```python
async def analyze_trade_outcome(
    self,
    outcome: TradeOutcome,
    minsky_phase: MinskyPhase,
    snr_score: float,
    narrative_state: dict,
    agent_votes: dict,
) -> TradeInsight:
    """
    Call Claude to understand WHY this trade succeeded or failed.
    Store the comprehension — not a parameter adjustment.
    """
    context = {
        "trade": outcome.to_dict(),
        "minsky_phase": minsky_phase.name,
        "snr_score": snr_score,
        "narrative_dominant": narrative_state.get("dominant"),
        "narrative_r0": narrative_state.get("r0"),
        "agent_votes": agent_votes,
        "market_conditions": {
            "vix": ...,
            "dxy": ...,
            "funding_rate": ...,
        }
    }

    prompt = f"""
You are ORACLE's introspection module.
A trade just closed. Analyze it honestly.

Context: {json.dumps(context, indent=2)}

Answer these questions in JSON:
1. "cause": What was the real cause of this outcome?
   (timing, macro context, behavioral bias, weak signal, narrative saturation?)
2. "extracted_rule": What general rule can be learned from this?
   Be specific. Not "avoid bad trades" but "avoid longs on BTC when
   Minsky phase >= 3 AND SNR < 0.35 AND narrative R0 is declining"
3. "avoid_when": In what specific future contexts should this
   type of trade be avoided?
4. "confidence": How confident are you in this analysis? (0.0-1.0)
5. "contradicts_existing": Does this contradict any previously
   learned rule? If so, which one and why?

Be honest. Be specific. Do not generate generic advice.
"""
    response = await self.llm.complete(prompt)
    insight = parse_insight(response)

    # Store comprehension in SQLite, not parameter adjustment
    self.db.store_insight(insight, context)

    # Update context patterns
    self.db.update_context_pattern(
        minsky_phase=minsky_phase,
        snr_score=snr_score,
        narrative_state=narrative_state,
        outcome=outcome,
        rule=insight.extracted_rule,
    )

    return insight
```

The learning engine must also regularly query accumulated patterns
and surface them to the parliament as context:
"In contexts similar to the current one, ORACLE has observed X outcomes
from Y trades. The most reliable learned rule is: [rule]."

-----

### Decision 3 — Simplify Obsidian vault to reduce noise

**Problem:** The vault currently generates dozens of health check files
per evening (health_check_2026-04-06_2120.md, _2128.md, _2136.md, etc.)
plus one markdown file per trade scan per asset. This creates enormous
noise and the files are never annotated or read.

**Rule:** Vault Obsidian = only what the trader will actually read and annotate.
Everything ORACLE reads programmatically = SQLite.

**Keep in vault:**

```
vault/
├── journal/
│   └── YYYY-MM-DD.md          # One daily consolidated file
├── theses/
│   └── thesis_{id}.md         # Active macro theses only
└── introspection/
    └── week_{YYYY_WNN}.md     # Weekly Strate 11 report
```

**Remove from vault (move to SQLite):**

- vault/config/{agent}_memory.md → agent_memory table
- vault/apprentissage/learning_*.md → learning_insights table
- vault/synthese/health_check_*.md → health_checks table in SQLite
- vault/technique/scan_*.md → scans table in SQLite
- vault/decisions/*.md → decisions table in SQLite (already in debates.db)

Daily journal format (one file, human-readable, annotatable):

```markdown
# ORACLE — Journal 2026-04-09

## Macro Context
- Regime: RISK_OFF | Minsky: Phase 3 (Euphoria) | SNR: 0.42
- Dominant narrative: "AI bubble correction" | R0: 1.3 (declining)

## Parliament Decisions
- 08:15 — BTC/USDT LONG rejected | Conviction: 28 | Reason: SNR gate blocked
- 14:32 — ETH/USDT SHORT | Conviction: 74 | Agents: 6 Bear / 1 Bull / 1 Neutral

## Learning Insights
- Trade #47 closed: BTC SHORT +2.3% | Cause: Minsky distress signal confirmed
- New rule learned: "Longs fail when narrative R0 < 1.0 AND Minsky >= 3"

## Trader Notes
[Space for manual annotations]
```

-----

## PHASE 1 — DEEP CODEBASE ANALYSIS (do this before writing a single line of code)

Read every file in the repository carefully. Then produce a complete report:

### 1.1 — Architecture Map

- Full data flow diagram (ASCII) from data ingestion to trade execution
- All classes, their responsibilities, and how they interact
- All existing agents: what each one does, what it consumes, what it produces
- Entry points and execution flow: how does a trade happen end-to-end?

### 1.2 — ORACLE v2 Compatibility Assessment

For each existing component, classify it as:

- ✅ KEEP AS-IS: already compatible
- 🔧 REFACTOR: needs modification (explain what and why)
- 🔌 WRAP: needs an adapter layer
- ❌ REPLACE: fundamentally incompatible (explain why)

Pay particular attention to:

- `learning_engine.py` — needs Decision 2 refactoring
- `obsidian_client.py` — needs Decision 3 simplification
- All agents that call `learning_engine.save_memory()` — will break with SQLite migration

### 1.3 — What Already Exists vs What Is Missing

Map existing code to the 11 strates:

- Strate 0: ✅ implemented — what is its current integration point?
- Strate 1: ✅ implemented — is it connected to agents?
- Strate 2: ✅ implemented — is it connected to sizing?
- Strates 3-11: what needs to be built?

### 1.4 — Dependencies and APIs

- All libraries currently in requirements.txt
- All external APIs: connected? tested? rate-limited?
- Hardcoded values that should be in .env
- Redis: is it running? is it required for local dev?

### 1.5 — Risk Assessment

- What could break when we apply the three architectural decisions?
- What is the safest order to apply them?
- Which agents depend on Obsidian memory and will need migration?

Do not write any code yet. Present the full analysis. Wait for confirmation.

-----

## PHASE 2 — ARCHITECTURAL DECISIONS (apply these before new strates)

Apply the three decisions above in this order:

1. SQLite schema creation and migration script
1. learning_engine.py refactoring (SQLite + LLM comprehension)
1. obsidian_client.py simplification + vault cleanup

After each: stop, show results, wait for validation.

-----

## PHASE 3 — STRATES IMPLEMENTATION (one at a time)

After Phase 2 is validated, implement strates in order.
Stop after each strate. Wait for explicit validation before continuing.

### STRATE 3 — Narrative Epidemiology Engine

**Theory:** Robert Shiller — viral stories cause economic cycles.
Narratives spread like infectious diseases. Model them with SIR.

SIR model applied to financial narratives:

- S (Susceptible) = not yet exposed to the narrative
- I (Infected) = actively spreading/believing it
- R (Recovered) = moved on

R0 = β/γ

- R0 > 2.0 → narrative explosively spreading → trend likely continues
- R0 ≈ 1.0 → narrative at peak saturation → reversal approaching
- R0 < 1.0 → narrative dying → anticipate regime change

Sources:

- Reddit (PRAW): r/CryptoCurrency, r/Bitcoin, r/ethereum, r/wallstreetbets
- RSS: Reuters, Bloomberg, CoinDesk, CoinTelegraph
- NLP via Claude API: classify and cluster narrative themes

```python
class NarrativeEpidemiologyEngine:
    async def scrape_narratives(self) -> list[NarrativeSignal]
    def fit_sir_model(self, narrative: NarrativeSignal) -> SIRParameters
    def compute_r0(self, sir_params: SIRParameters) -> float
    def predict_lifecycle(self, narrative: NarrativeSignal) -> NarrativeLifecycle
    def get_dominant_narrative(self) -> NarrativeSummary
    def predict_next_narrative(self, current: NarrativeSummary) -> str
```

Storage: SQLite (narratives table) — not Obsidian.

-----

### STRATE 4 — Reflexivity Map

**Theory:** George Soros — markets participate in creating reality.
Prices influence fundamentals which influence prices.

Implement using NetworkX directed graph:

- Nodes: price action, narrative strength, institutional flows,
  retail positioning, funding rates, leverage, media intensity
- Edges: measured causal relationships with direction and strength
- Loop detector: find circular paths (reflexivity loops)
- Loop intensity score + breaking point estimate

```python
class ReflexivityMap:
    def build_graph(self, market_data: dict) -> nx.DiGraph
    def detect_active_loops(self, graph: nx.DiGraph) -> list[ReflexivityLoop]
    def score_loop_intensity(self, loop: ReflexivityLoop) -> float
    def estimate_breaking_point(self, loop: ReflexivityLoop) -> BreakingPointEstimate
```

-----

### STRATE 5 — Behavioral Bias Arbitrage

**Theory:** Kahneman — humans have predictable, systematic cognitive biases.

| Bias               | Detection                             | Strategy                    |
|--------------------|---------------------------------------|-----------------------------|
| Anchoring          | Price clustering at round numbers     | Amplified breakout expected |
| Loss Aversion      | Support defended too long             | Violent flush on break      |
| Recency Bias       | 5+ consecutive same-direction candles | Mean reversion              |
| Disposition Effect | Volume spike + price stall near highs | Momentum underestimated     |
| Herding            | Long/short ratio > 85% one direction  | Contrarian signal           |
| FOMO               | Volume 3x average + price acceleration| Parabolic then crash        |
| Panic              | Volume spike + 3-sigma down           | Dead cat bounce             |

```python
class BehavioralBiasArbitrage:
    def detect_all_biases(self, market_data: MarketSnapshot) -> list[BiasSignal]
    def get_contrarian_signals(self, biases: list[BiasSignal]) -> list[TradeSignal]
    def update_historical_winrates(self, completed_trades: list[Trade]) -> None
```

-----

### STRATE 6 — Multi-Agent Parliament

**Theory:** Adversarial collaboration forces more rigorous reasoning.

8 LangGraph agents that debate before every decision:

| Agent          | Expertise                              | Sources                |
|----------------|----------------------------------------|------------------------|
| 🌍 Macro        | Economic cycles, central banks         | World Model, FRED      |
| 📊 Technical    | Price action, market structure         | Binance OHLCV          |
| 🧠 Behavioral   | Biases, sentiment, narratives          | Strate 5, Strate 3     |
| ⛓️ Onchain      | Crypto flows, whale movements          | Glassnode, CryptoQuant |
| 🌐 Geopolitical | Systemic risks, black swans            | RSS feeds              |
| 📐 Quantitative | Statistical anomalies, existing signals| Strate 7               |
| 🔮 Contrarian   | Systematic devil's advocate            | All of the above       |
| ⚖️ Arbitrator   | Synthesizes debate, conviction score   | All agents             |

Parliament protocol:

1. Each agent independently forms a position (Bull/Bear/Neutral + confidence)
1. Agents share reasoning — Contrarian argues against the majority
1. Arbitrator weighs all arguments, assigns conviction 0-100
1. Conviction → position size via Kelly (Strate 10)
1. Full debate stored in debates.db

Conviction → Position size:

- 0-30: No trade
- 31-50: 0.25x
- 51-65: 0.50x
- 66-80: 0.75x
- 81-90: 1.0x
- 91-100: 1.25x (near-unanimity required)

**Important:** Parliament agents must have access to accumulated learning insights
from the SQLite `context_patterns` table. Before forming a position, each agent
must be briefed: "In similar contexts, ORACLE has learned: [rules]."

```python
class MultiAgentParliament:
    async def convene(self, market_context: dict) -> ParliamentDecision
    def get_individual_positions(self) -> list[AgentPosition]
    async def run_debate(self, positions: list[AgentPosition]) -> DebateRecord
    def compute_conviction(self, debate: DebateRecord) -> float
    def size_position(self, conviction: float, kelly_fraction: float) -> float
```

-----

### STRATE 7 — Fractal Risk Engine

**Theory:** Mandelbrot — financial markets do not follow Gaussian distributions.
Tails are infinitely fatter. Normal-distribution VaR is dangerously wrong.

Implement:

- Hurst Exponent (R/S analysis): H > 0.5 trending, H < 0.5 mean-reverting
- Higuchi Fractal Dimension: complexity/predictability measure
- Pareto-Lévy distribution fitter: replaces Gaussian for tail risk
- Expected Shortfall (CVaR) at 1% and 5%: replaces VaR
- Modified Kelly Criterion:
  f* = (edge/odds) × conviction × (1 - minsky_risk) × hurst_adjustment

```python
class FractalRiskEngine:
    def compute_hurst_exponent(self, prices: pd.Series) -> float
    def compute_fractal_dimension(self, prices: pd.Series) -> float
    def fit_levy_distribution(self, returns: pd.Series) -> LevyParams
    def compute_expected_shortfall(self, returns: pd.Series, alpha: float = 0.01) -> float
    def compute_kelly_fraction(self, edge: float, odds: float,
                               conviction: float, minsky_phase: int) -> float
```

-----

### STRATE 8 — Temporal Causal Graph

**Theory:** Granger — causality between time series has measurable time delays.

Implement:

- Granger causality tests across all tracked assets
- Calibrated time delay measurement (minutes/hours between cause and effect)
- Directed causal graph: edges = proven causal relationships with delays
- Regime-specific graphs (causal structure changes between Risk-On/Off)
- Relationship break detector: when a link fails → regime change signal
- Lead-lag signal generator

Causal chains to test:

- BTC → ETH → altcoins (with measured delays)
- DXY → Gold → BTC (macro transmission)
- Funding rate → price (squeeze predictor)
- Open interest → volatility → price range

```python
class TemporalCausalGraph:
    def run_granger_tests(self, data: pd.DataFrame, max_lag: int = 24) -> CausalMatrix
    def build_causal_graph(self, causal_matrix: CausalMatrix) -> nx.DiGraph
    def detect_relationship_breaks(self, graph: nx.DiGraph, live_data: pd.DataFrame) -> list[str]
    def generate_lead_lag_signals(self, graph: nx.DiGraph, market_data: dict) -> list[TradeSignal]
```

-----

### STRATE 9 — Personal Alpha Engine

**Theory:** Every trader has unique edges based on their situation.
UTC-10 timezone, French Polynesia perspective, specific cognitive patterns.

Implement:

- Timezone performance heatmap: P&L by hour (UTC-10) and day of week
- Session overlap analysis: US close + Asia open simultaneously
- Cognitive profile tracker: detect personal biases from trade history
  - Exiting winners too early?
  - Over-trading on certain days?
  - Worst decisions in which market conditions?
- Personal edge library: growing database of outperforming patterns
- Pre-trade psychological check: before any trade > 1% size
- Fine-tuning data collector: logs decisions with full context

```python
class PersonalAlphaEngine:
    def analyze_timezone_performance(self, trades: list[Trade]) -> TimezoneHeatmap
    def detect_personal_biases(self, trades: list[Trade]) -> list[PersonalBias]
    def get_current_edge_score(self, current_time: datetime, market_state: dict) -> float
    def pre_trade_check(self, proposed_trade: Trade) -> tuple[bool, str]
    def log_decision_for_finetuning(self, context: dict, decision: dict) -> None
```

-----

### STRATE 10 — Antifragile Portfolio Constructor

**Theory:** Taleb — build a portfolio that benefits from volatility, not just survives it.

Implement:

- Barbell strategy: 80-90% core/safe + 10-20% highly asymmetric positions
- Antifragility score: how much does the portfolio benefit vs suffer from volatility
- Convex position tracker: limited downside + unlimited upside
- Calm period accumulator: when VIX low → accumulate cheap optionality
- Volatility spike beneficiary: when volatility spikes, asymmetric positions activate
- Correlation matrix: ensure CT and LT positions don't create hidden doubled exposure

```python
class AntifragilePortfolio:
    def compute_antifragility_score(self, positions: list[Position]) -> float
    def compute_kelly_size(self, signal: TradeSignal, conviction: float) -> float
    def check_correlation_exposure(self, new_trade: Trade, portfolio: Portfolio) -> float
    def get_barbell_allocation(self, world_state: MacroSnapshot) -> BarbellAllocation
    def rebalance_if_needed(self, portfolio: Portfolio) -> list[RebalanceAction]
```

-----

### STRATE 11 — Meta-Cognitive Loop

**Theory:** The highest form of intelligence is the ability to think about
one's own thinking. ORACLE must critique and improve its own reasoning.

Weekly introspection report answering:

- Were my theses from last week correct? What was wrong in my reasoning?
- Which parliament agents were most accurate? Which consistently wrong?
- Did Narrative Epidemiology predictions match outcomes?
- Did Minsky phase detection correlate with actual volatility?
- What signals did I systematically miss?
- What biases affected my reasoning (not the market's — mine)?
- What parameter changes do I propose? (propose — do not auto-apply)
- Am I better or worse than 3 months ago? Why?

Format: Markdown in vault/introspection/ + PDF export via Telegram.

**Important:** This report must cross-reference the learning_insights table.
Patterns that appeared multiple times in the week must be explicitly named.
Rules that were validated or invalidated must be marked as such.

```python
class MetaCognitiveLoop:
    async def generate_weekly_report(self, week_data: WeeklyData) -> MetaReport
    def compare_thesis_accuracy(self, theses: list[Thesis], outcomes: list[Outcome]) -> dict
    def evaluate_agent_performance(self, debates: list[DebateRecord]) -> AgentScorecard
    def propose_parameter_adjustments(self, report: MetaReport) -> list[ProposedChange]
    def export_pdf(self, report: MetaReport) -> str
```

-----

## ADDITIONAL THEORETICAL MODULES (implement after core strates)

These modules add depth beyond the original 11 strates.
Implement them only after Strates 0-11 are validated and running.

### Sornette LPPL — Crash Predictor

**Theory:** Didier Sornette — crashes have mathematical precursors.
Log-periodic power law oscillations accelerate before collapse.

```python
class SornetteCrashPredictor:
    def fit_lppl(self, prices: pd.Series) -> LPPLParams
    # tc = critical time, omega = angular frequency, phi = phase
    def compute_crash_probability(self, params: LPPLParams, horizon_days: int) -> float
    def detect_acceleration(self, prices: pd.Series) -> bool
```

Alert when crash probability > 60% within 30 days.

### Rey Global Cycle Monitor

**Theory:** Hélène Rey — there is one global financial cycle, driven by the Fed.
All local theses must be recalibrated against this cycle.

```python
class GlobalCycleMonitor:
    def compute_cycle_phase(self) -> CyclePhase  # EXPANSION/PEAK/CONTRACTION/TROUGH
    def get_cycle_score(self) -> float  # 0-100
    def recalibrate_thesis(self, thesis: Thesis, cycle: CyclePhase) -> Thesis
```

### Girard Mimetic Tracker

**Theory:** René Girard — desire is mimetic. We want what others want.
When everyone imitates everyone, a sacrificial crisis (violent reset) approaches.

```python
class MimeticTracker:
    def compute_mimetic_intensity(self, positioning_data: dict) -> float
    # 0.0 = independent decisions, 1.0 = total herding
    def estimate_sacrificial_crisis_risk(self) -> float
    # Risk of violent reversal when mimetic intensity approaches 1.0
```

-----

## DATABASE SCHEMA (complete)

Four SQLite databases:

```sql
-- trades.db
CREATE TABLE trades (
    id TEXT PRIMARY KEY,
    pair TEXT, direction TEXT, size REAL,
    entry_price REAL, exit_price REAL,
    stop_loss REAL, take_profit REAL,
    pnl_pct REAL, pnl_usd REAL,
    duration_hours REAL, exit_reason TEXT,
    minsky_phase INTEGER, snr_score REAL,
    conviction_score REAL, agent_votes TEXT,
    reasoning TEXT, created_at TIMESTAMP
);

-- positions_lt.db
CREATE TABLE positions_lt (
    id TEXT PRIMARY KEY,
    asset TEXT, direction TEXT, size REAL,
    entry_price REAL, thesis_id TEXT,
    entry_rationale TEXT, monthly_review TEXT,
    status TEXT, created_at TIMESTAMP
);

-- theses.db
CREATE TABLE theses (
    id TEXT PRIMARY KEY,
    title TEXT, description TEXT,
    conviction REAL, horizon_days INTEGER,
    invalidators TEXT,  -- JSON list of conditions that kill the thesis
    status TEXT,        -- ACTIVE/VALIDATED/INVALIDATED
    created_at TIMESTAMP, updated_at TIMESTAMP
);

-- debates.db
CREATE TABLE debates (
    id TEXT PRIMARY KEY,
    pair TEXT, timeframe TEXT,
    agent_positions TEXT,    -- JSON: {agent: {direction, confidence, reasoning}}
    conviction_score REAL,
    final_decision TEXT,
    full_debate_log TEXT,
    created_at TIMESTAMP
);
```

-----

## SCHEDULER (APScheduler, UTC-10)

```python
# 07:00 daily — Morning macro briefing
scheduler.add_job(morning_briefing, 'cron', hour=7, minute=0,
                  timezone='Pacific/Tahiti')

# 08:00 daily — Parliament daily session
scheduler.add_job(parliament_daily_session, 'cron', hour=8, minute=0,
                  timezone='Pacific/Tahiti')

# Real-time — Signal engine (15m candles)
scheduler.add_job(signal_engine, 'interval', minutes=15)

# Sunday 09:00 — Meta-cognitive weekly report (Strate 11)
scheduler.add_job(meta_cognitive_report, 'cron',
                  day_of_week='sun', hour=9, timezone='Pacific/Tahiti')

# 1st of month — LT portfolio review (Strate 10)
scheduler.add_job(monthly_review, 'cron', day=1, hour=10,
                  timezone='Pacific/Tahiti')
```

-----

## TELEGRAM ALERTS

Send for:

- Parliament decision conviction > 70
- Minsky phase change
- Narrative R0 crossing 2.0 or 1.0 threshold
- Reflexivity loop breaking point approaching
- Sornette crash probability > 60%
- Weekly meta-cognitive report (PDF)
- Daily 07:00 morning briefing

Commands:

- /status → current world state + open positions
- /parliament → last debate summary
- /narrative → top 3 active narratives + R0
- /minsky → current phase + historical timeline
- /learn → last 5 learned rules from learning_insights

-----

## REACT DASHBOARD

Real-time panels:

- World Model state + regime classification
- Minsky phase gauge (1-5)
- Active narratives with R0 bars
- Parliament last decision + agent vote breakdown
- Portfolio antifragility score
- Live P&L: short-term / long-term / hedges
- UTC-10 performance heatmap
- Reflexivity loops graph (interactive)
- Learning insights feed (last 10 rules learned)

-----

## ENVIRONMENT VARIABLES (.env)

```
# Binance
BINANCE_API_KEY=
BINANCE_SECRET_KEY=
BINANCE_TESTNET=true

# Claude API
ANTHROPIC_API_KEY=

# FRED
FRED_API_KEY=

# Reddit
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=ORACLE_v2/1.0

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Optional
GLASSNODE_API_KEY=
CRYPTOQUANT_API_KEY=
CAPITAL_COM_API_KEY=
```

-----

## CODING STANDARDS (non-negotiable)

- Python 3.11+ with full type hints everywhere
- Every function has a docstring: WHAT it does and WHY
- Every trade logs: timestamp, pair, direction, size, reasoning,
  confidence, agent_votes, minsky_phase, snr_score
- Every strate exposes: analyze() → dict and backtest(df) → BacktestResult
- No magic numbers — all thresholds in config.py
- Async where possible
- Error handling: one strate crashing never brings down the system
- Never break existing functionality — wrap and extend, never replace
- All API keys in .env — never hardcoded

-----

## START COMMAND

Begin with PHASE 1. Read every file. Produce the full analysis.
Do not write a single line of code until the analysis is confirmed.

Then apply the three architectural decisions (Phase 2) before
implementing any new strate.

Then implement Strate 3 (Narrative Epidemiology) — it is the next
logical layer after the three implemented strates.
