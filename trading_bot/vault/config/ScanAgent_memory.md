---
agent: ScanAgent
version: 7
total_trades: 6
total_wins: 0
win_rate: 0.0
total_pnl_usd: -396.72
sharpe_approx: -1.451
last_updated: '2026-03-31T09:20:24.921497+00:00'
tags:
- config
- ml
- memory
- scanagent
total_pnl_pct: -6.7208
best_trade_pct: 0.0
worst_trade_pct: -1.5444
current_streak: -2
---

## Mémoire Apprise — ScanAgent

### Paramètres Adaptatifs
```json
{
  "sl_atr_multiplier": 1.54,
  "tp_rr_ratio": 2.5,
  "confidence_floor": 55.0,
  "tech_weight": 0.6,
  "fund_weight": 0.4,
  "learning_rate": 0.1,
  "regime_sensitivity": 0.5
}
```

### Poids des Indicateurs
```json
{
  "rsi:1h:EUR/USD": 1.1,
  "macd:1h:EUR/USD": 0.93,
  "bb:1h:EUR/USD": 1.1,
  "volume:1h:EUR/USD": 0.93,
  "rsi:1h:BTC/USDT": 1.02,
  "macd:1h:BTC/USDT": 0.867,
  "bb:1h:BTC/USDT": 1.19,
  "volume:1h:BTC/USDT": 0.867,
  "rsi:1h:ETH/USDT": 1.02,
  "macd:1h:ETH/USDT": 0.867,
  "bb:1h:ETH/USDT": 1.19,
  "volume:1h:ETH/USDT": 0.867,
  "rsi:1h:SOL/USDT": 1.1,
  "macd:1h:SOL/USDT": 0.93,
  "bb:1h:SOL/USDT": 1.1,
  "volume:1h:SOL/USDT": 0.93
}
```

### Statistiques par Indicateur
```json
{
  "rsi:EUR/USD": {
    "total": 1,
    "wins": 1,
    "avg_pnl": -0.017385997035487412
  },
  "macd:EUR/USD": {
    "total": 1,
    "wins": 0,
    "avg_pnl": -0.017385997035487412
  },
  "bb:EUR/USD": {
    "total": 1,
    "wins": 1,
    "avg_pnl": -0.017385997035487412
  },
  "volume:EUR/USD": {
    "total": 1,
    "wins": 0,
    "avg_pnl": -0.017385997035487412
  },
  "rsi:BTC/USDT": {
    "total": 2,
    "wins": 1,
    "avg_pnl": -0.1996087985757773
  },
  "macd:BTC/USDT": {
    "total": 2,
    "wins": 0,
    "avg_pnl": -0.1996087985757773
  },
  "bb:BTC/USDT": {
    "total": 2,
    "wins": 2,
    "avg_pnl": -0.1996087985757773
  },
  "volume:BTC/USDT": {
    "total": 2,
    "wins": 0,
    "avg_pnl": -0.1996087985757773
  },
  "rsi:ETH/USDT": {
    "total": 2,
    "wins": 1,
    "avg_pnl": -0.2836912753641471
  },
  "macd:ETH/USDT": {
    "total": 2,
    "wins": 0,
    "avg_pnl": -0.2836912753641471
  },
  "bb:ETH/USDT": {
    "total": 2,
    "wins": 2,
    "avg_pnl": -0.2836912753641471
  },
  "volume:ETH/USDT": {
    "total": 2,
    "wins": 0,
    "avg_pnl": -0.2836912753641471
  },
  "rsi:SOL/USDT": {
    "total": 1,
    "wins": 1,
    "avg_pnl": -0.1470234515935053
  },
  "macd:SOL/USDT": {
    "total": 1,
    "wins": 0,
    "avg_pnl": -0.1470234515935053
  },
  "bb:SOL/USDT": {
    "total": 1,
    "wins": 1,
    "avg_pnl": -0.1470234515935053
  },
  "volume:SOL/USDT": {
    "total": 1,
    "wins": 0,
    "avg_pnl": -0.1470234515935053
  }
}
```

### Statistiques par Asset
```json
{
  "EUR/USD": {
    "total": 1,
    "wins": 0,
    "pnl_pct": -0.017385997035487412
  },
  "BTC/USDT": {
    "total": 2,
    "wins": 0,
    "pnl_pct": -0.1996087985757773
  },
  "ETH/USDT": {
    "total": 2,
    "wins": 0,
    "pnl_pct": -0.2836912753641471
  },
  "SOL/USDT": {
    "total": 1,
    "wins": 0,
    "pnl_pct": -0.1470234515935053
  }
}
```

### Historique d'Apprentissage
- Total trades : **6**
- Win rate : **0.0%**
- P&L total : **$-396.72** (`-6.72%`)
- Meilleur trade : **+0.00%**
- Pire trade : **-1.54%**
- Série en cours : **-2**
