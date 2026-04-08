---
agent: RiskAgent
version: 27
total_trades: 6
total_wins: 0
win_rate: 0.0
total_pnl_usd: -396.72
sharpe_approx: -1.451
last_updated: '2026-04-07T04:58:13.497510+00:00'
tags:
- config
- ml
- memory
- riskagent
total_pnl_pct: -6.7208
best_trade_pct: 0.0
worst_trade_pct: -1.5444
current_streak: 0
---

## Mémoire Apprise — RiskAgent

### Paramètres Adaptatifs
```json
{
  "sl_atr_multiplier": 1.54,
  "tp_rr_ratio": 2.5,
  "confidence_floor": 30.0,
  "tech_weight": 0.6,
  "fund_weight": 0.4,
  "learning_rate": 0.1,
  "regime_sensitivity": 0.5
}
```

### Poids des Indicateurs
```json
{}
```

### Statistiques par Indicateur
```json
{}
```

### Statistiques par Asset
```json
{
  "BTC/USDT": {
    "total": 1,
    "wins": 0,
    "pnl_pct": -0.10951741394463128
  },
  "ETH/USDT": {
    "total": 1,
    "wins": 0,
    "pnl_pct": -0.15444099785923504
  }
}
```

### Paramètres par Régime
```json
{
  "bull": {
    "sl_atr_multiplier": 2.0,
    "tp_rr_ratio": 3.5,
    "confidence_floor": 50.0,
    "leverage": 1.5
  },
  "bear": {
    "sl_atr_multiplier": 1.5,
    "tp_rr_ratio": 2.5,
    "confidence_floor": 65.0,
    "leverage": 1.0
  },
  "sideways": {
    "sl_atr_multiplier": 2.0,
    "tp_rr_ratio": 3.0,
    "confidence_floor": 55.0,
    "leverage": 1.0
  },
  "volatile": {
    "sl_atr_multiplier": 2.5,
    "tp_rr_ratio": 2.0,
    "confidence_floor": 70.0,
    "leverage": 0.5
  }
}
```

### Historique d'Apprentissage
- Total trades : **6**
- Win rate : **0.0%**
- P&L total : **$-396.72** (`-6.72%`)
- Meilleur trade : **+0.00%**
- Pire trade : **-1.54%**
- Série en cours : **+0**
