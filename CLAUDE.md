# ORACLE v2 — World-Modeling Trading System

## What This Project Is

ORACLE v2 is NOT a simple trading bot.
It is a world-modeling reasoning system that builds a living representation
of macroeconomic reality and deduces where prices MUST go — before they get there.
It combines short-term algorithmic crypto trading with long-term macro investing,
governed by a parliament of 8 specialized AI agents that debate every decision.

-----

## My Profile

- **Location**: French Polynesia, Tahiti (UTC-10)
- **Markets**: Crypto pairs on Binance (BTC, ETH, and majors)
- **Style**: Swing trading + day trading + long-term allocation
- **Level**: Advanced — familiar with XGBoost, SHAP, multi-timeframe
  signal cascades, dynamic leverage, backtesting pipelines
- **Timezone edge**: I see US close + Asia open simultaneously.
  Nikkei open is particularly relevant. Map inefficiencies at UTC-10.

-----

## Primary Exchange & APIs

- **Exchange**: Binance (python-binance SDK)
- **Broker fallback**: Capital.com (CFD — Nikkei, Gold)
- **Macro data**: FRED API (free) — M2, CPI, yield curve, ISM
- **Market data**: yfinance (free fallback), Binance WebSocket (live)
- **Sentiment**: Reddit API (PRAW), RSS feeds (Reuters, Bloomberg)
- **Onchain**: Glassnode free tier, CryptoQuant free tier
- **LLM**: Claude API — model: claude-sonnet-4-20250514
- **Agents**: LangGraph (multi-agent parliament)

-----

## Architecture — 11 Strates (implement one at a time)

### Status Tracker (update [ ] → [x] as completed)

- [ ] Strate 0  — Epistemological Engine (signal vs noise, Shannon entropy)
- [ ] Strate 1  — World Model Engine (macro simulation, Monte Carlo)
- [ ] Strate 2  — Minsky Cycle Detector (5-phase fragility model)
- [ ] Strate 3  — Narrative Epidemiology (Shiller + SIR model)
- [ ] Strate 4  — Reflexivity Map (Soros — self-reinforcing loops)
- [ ] Strate 5  — Behavioral Bias Arbitrage (Kahneman)
- [ ] Strate 6  — Multi-Agent Parliament (8 LangGraph agents)
- [ ] Strate 7  — Fractal Risk Engine (Mandelbrot — fat tails)
- [ ] Strate 8  — Temporal Causal Graph (Granger causality)
- [ ] Strate 9  — Personal Alpha Engine (UTC-10 edge + cognitive profile)
- [ ] Strate 10 — Antifragile Portfolio (Taleb + Kelly Criterion)
- [ ] Strate 11 — Meta-Cognitive Loop (agent thinks about its own thinking)

-----

## Theoretical Foundations (always reference these)

- **Soros**: Reflexivity — markets participate in creating reality
- **Minsky**: Stability is destabilizing — measure fragility build-up
- **Shiller**: Narratives cause economic cycles — model like epidemics (SIR)
- **Mandelbrot**: Markets have fat tails — use Pareto-Lévy, never Gaussian
- **Kahneman**: Exploit predictable and recurring cognitive biases
- **Taleb**: Build antifragility — construct portfolio that benefits from chaos
- **Granger**: Causality between assets has measurable and exploitable time delays
- **Kelly**: Optimal sizing = f(edge × odds × conviction × minsky_phase_risk)
- **W. Brian Arthur**: Economies are complex adaptive systems, not equilibria
- **Fischer Black**: 90%+ of price moves are pure noise — measure signal/noise first

-----

## Non-Negotiable Integration Rules

1. **Never break existing bot functionality** — wrap and extend, never replace
1. **Each strate is a new layer** on top of existing signals
1. **Existing XGBoost signals = one voice** in the parliament, not the final word
1. **Every decision must log**: timestamp, full reasoning, confidence score, agent votes
1. **Human validation required** before any change to live execution logic
1. **All API keys in .env** — never hardcoded anywhere in the codebase
1. **One strate at a time** — wait for explicit validation before moving to the next
1. **Backtest before live** — every new strate must be backtestable independently

-----

## Target File Structure

```
oracle_v2/
├── core/
│   ├── strate_0_epistemic.py        # Shannon entropy, signal/noise
│   ├── strate_1_world_model.py      # Macro simulation, Monte Carlo
│   ├── strate_2_minsky.py           # Fragility cycle detector
│   ├── strate_3_narrative.py        # SIR epidemiology on narratives
│   ├── strate_4_reflexivity.py      # Soros loop graph (NetworkX)
│   ├── strate_5_behavioral.py       # Bias detectors + strategies
│   ├── strate_6_parliament.py       # 8 LangGraph agents + arbitrator
│   ├── strate_7_fractal_risk.py     # Mandelbrot, Hurst, CVaR
│   ├── strate_8_causal_graph.py     # Granger tests, lead-lag
│   ├── strate_9_personal_alpha.py   # UTC-10 edge, cognitive profile
│   ├── strate_10_antifragile.py     # Taleb barbell, Kelly sizing
│   └── strate_11_metacognition.py   # Weekly introspection report
├── data/
│   ├── macro/                       # FRED, yfinance cached data
│   ├── narratives/                  # Reddit, RSS scraped data
│   ├── onchain/                     # Glassnode, CryptoQuant data
│   └── trades/                      # Historical trade logs
├── db/
│   ├── trades.db                    # Short-term trade journal
│   ├── positions_lt.db              # Long-term position tracker
│   ├── theses.db                    # Investment thesis storage
│   └── debates.db                   # Full parliament debate logs
├── agents/
│   ├── agent_macro.py
│   ├── agent_technical.py
│   ├── agent_behavioral.py
│   ├── agent_onchain.py
│   ├── agent_geopolitical.py
│   ├── agent_quantitative.py
│   ├── agent_contrarian.py
│   └── agent_arbitrator.py
├── dashboard/                       # React frontend
│   ├── src/
│   └── package.json
├── reports/                         # Auto-generated weekly PDFs
├── tests/                           # One test file per strate
│   ├── test_strate_0.py
│   ├── test_strate_1.py
│   └── ...
├── config.py                        # All constants and thresholds
├── .env                             # ALL API keys (never commit)
├── .env.example                     # Template with key names only
├── requirements.txt
├── CLAUDE.md                        # This file
└── main.py                          # Entry point + scheduler
```

-----

## Coding Standards (enforce always)

- Python 3.11+ with full type hints everywhere
- Every function has a docstring explaining WHAT and WHY
- Every trade decision logs: `{timestamp, pair, direction, size, reasoning, confidence, agent_votes}`
- Every strate exposes: `analyze() → dict` and `backtest(df) → BacktestResult`
- No magic numbers — all thresholds in `config.py`
- Async where possible (Binance WebSocket, parallel agent calls)
- Error handling: never let one strate crash the whole system

-----

## Scheduler (APScheduler — Tahiti time UTC-10)

- **07:00 daily** → Morning macro briefing (Strate 1 + Strate 3)
- **08:00 daily** → Parliament convenes for daily bias assessment
- **Real-time** → Signal engine on 15m/30m/1h candles via Binance WebSocket
- **Sunday 09:00** → Weekly meta-cognitive introspection report (Strate 11)
- **1st of month** → Thesis review + long-term portfolio rebalance (Strate 10)

-----

## Dashboard Requirements (React)

Must display in real-time:

- World Model state (Strate 1) — current macro regime
- Active narratives + R0 score (Strate 3)
- Minsky phase indicator with historical timeline (Strate 2)
- Parliament debate log — last 10 decisions with full reasoning (Strate 6)
- Portfolio antifragility score (Strate 10)
- Personal alpha metrics — UTC-10 performance heatmap (Strate 9)
- Live P&L: short-term vs long-term vs hedges

-----

## Alerts (Telegram Bot)

Send alerts for:

- Parliament decision with conviction score > 70
- Minsky phase change detected
- Narrative R0 crossing key thresholds (>2.0 or <1.0)
- Reflexivity loop breaking point approaching
- Black swan detector triggered
- Weekly PDF report delivery

-----

## Response Style (always follow)

- Explain WHY before HOW — theory first, code second
- Show ASCII architecture diagram before writing any code
- Implement exactly ONE strate per session — stop and wait for validation
- Flag any risk to existing code BEFORE touching it
- I am an advanced user — skip basics, go deep
- If something in my existing code conflicts with ORACLE v2 principles, tell me explicitly

```

```