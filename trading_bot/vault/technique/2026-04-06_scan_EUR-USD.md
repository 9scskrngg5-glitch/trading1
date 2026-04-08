---
date: 2026-04-06 11:40:45 UTC
agent: ScanAgent
asset: EUR/USD
signal: neutral
confiance: 10
tags:
- trading
- crypto
- 1d
timeframe: 1d
rsi: 38.29
macd_hist: 0.000459
bb_position: 0.4
atr: 0.005271
entry_price: 1.1523
sl_atr_mult: 1.54
---

## Scan de Marché — EUR/USD `1d`

> Source données : 🟢 Binance WS+REST

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `38.29` | ⚪ Neutre | `1.00` | 100% (1 signaux) |
| MACD Histogram | `0.000459` | 📈 | `1.00` | 0% (1 signaux) |
| Bollinger Band | `40.0%` | — | `1.00` | 100% (1 signaux) |
| Volume | `0.19x` | 📊 Normal | adaptatif | — |
| ATR (14) | `0.005271` | — | — | — |
| Prix | `1.1523` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `0.083` | ⚪ Neutre |
| VWAP Distance | `+0.04%` | ↑ Dessus VWAP |
| Trend Slope (1m×20) | `+0.00111%/candle` | 📈 |

### Signal Adaptatif
> **NEUTRAL** — Confiance : **10/100**
> Seuil minimum appris : `55.0/100`

### Performance Historique sur EUR/USD
| Métrique | Valeur |
|---|---|
| Trades analysés | `1` |
| Win Rate | `0.0%` |
| P&L moyen EMA | `-0.017%` |

### Paramètres ML Courants
| Paramètre | Valeur Apprise |
|---|---|
| SL multiplier | `1.54×ATR` |
| TP ratio | `1:2.50` |
| Confidence floor | `55.0/100` |

### Liens
[[decisions/2026-04-06_114045_predict_EUR-USD]]
[[config/ScanAgent_memory]]
