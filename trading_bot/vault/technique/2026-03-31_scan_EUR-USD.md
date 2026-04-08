---
date: 2026-03-31 16:50:57 UTC
agent: ScanAgent
asset: EUR/USD
signal: bullish
confiance: 25
tags:
- trading
- crypto
- 1d
timeframe: 1d
rsi: 51.13
macd_hist: 0.000484
bb_position: 0.6
atr: 0.007243
entry_price: 1.1543
sl_atr_mult: 1.54
---

## Scan de Marché — EUR/USD `1d`

> Source données : 🟢 Binance WS+REST

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `51.13` | ⚪ Neutre | `1.00` | 100% (1 signaux) |
| MACD Histogram | `0.000484` | 📈 | `1.00` | 0% (1 signaux) |
| Bollinger Band | `60.0%` | — | `1.00` | 100% (1 signaux) |
| Volume | `0.89x` | 📊 Normal | adaptatif | — |
| ATR (14) | `0.007243` | — | — | — |
| Prix | `1.1543` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `0.002` | ⚪ Neutre |
| VWAP Distance | `+0.13%` | ↑ Dessus VWAP |
| Trend Slope (1m×20) | `+0.00973%/candle` | 📈 |

### Signal Adaptatif
> **BULLISH** — Confiance : **25/100**
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
[[decisions/2026-03-31_165057_predict_EUR-USD]]
[[config/ScanAgent_memory]]
