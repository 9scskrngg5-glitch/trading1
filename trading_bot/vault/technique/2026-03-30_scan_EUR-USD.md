---
date: 2026-03-30 23:59:59 UTC
agent: ScanAgent
asset: EUR/USD
signal: neutral
confiance: 5
tags:
- trading
- crypto
- 1d
timeframe: 1d
rsi: 46.41
macd_hist: 0.000206
bb_position: 0.272
atr: 0.006993
entry_price: 1.1464
sl_atr_mult: 1.5
---

## Scan de Marché — EUR/USD `1d`

> Source données : 🟢 Binance WS+REST

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `46.41` | ⚪ Neutre | `1.00` | — |
| MACD Histogram | `0.000206` | 📈 | `1.00` | — |
| Bollinger Band | `27.2%` | — | `1.00` | — |
| Volume | `1.07x` | 📊 Normal | adaptatif | — |
| ATR (14) | `0.006993` | — | — | — |
| Prix | `1.1464` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `-0.186` | 🔴 Vendeur |
| VWAP Distance | `-0.03%` | ↓ Dessous VWAP |
| Trend Slope (1m×20) | `-0.00037%/candle` | 📉 |

### Signal Adaptatif
> **NEUTRAL** — Confiance : **5/100**
> Seuil minimum appris : `55.0/100`

### Performance Historique sur EUR/USD
| Métrique | Valeur |
|---|---|
| Trades analysés | `0` |
| Win Rate | `0.0%` |
| P&L moyen EMA | `+0.000%` |

### Paramètres ML Courants
| Paramètre | Valeur Apprise |
|---|---|
| SL multiplier | `1.50×ATR` |
| TP ratio | `1:2.50` |
| Confidence floor | `55.0/100` |

### Liens
[[decisions/2026-03-30_235959_predict_EUR-USD]]
[[config/ScanAgent_memory]]
