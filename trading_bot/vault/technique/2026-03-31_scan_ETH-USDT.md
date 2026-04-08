---
date: 2026-03-31 16:50:57 UTC
agent: ScanAgent
asset: ETH/USDT
signal: bearish
confiance: 32
tags:
- trading
- crypto
- 1d
timeframe: 1d
rsi: 33.66
macd_hist: -13.465306
bb_position: 0.432
atr: 105.696429
entry_price: 2091.64
sl_atr_mult: 1.54
---

## Scan de Marché — ETH/USDT `1d`

> Source données : 🟢 Binance WS+REST

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `33.66` | ⚪ Neutre | `1.00` | 50% (2 signaux) |
| MACD Histogram | `-13.465306` | 📉 | `1.00` | 0% (2 signaux) |
| Bollinger Band | `43.2%` | — | `1.00` | 100% (2 signaux) |
| Volume | `0.8x` | 📊 Normal | adaptatif | — |
| ATR (14) | `105.696429` | — | — | — |
| Prix | `2091.64` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `0.994` | 🟢 Acheteur |
| VWAP Distance | `+0.88%` | ↑ Dessus VWAP |
| Trend Slope (1m×20) | `+0.10861%/candle` | 📈 |

### Signal Adaptatif
> **BEARISH** — Confiance : **32/100**
> Seuil minimum appris : `55.0/100`

### Performance Historique sur ETH/USDT
| Métrique | Valeur |
|---|---|
| Trades analysés | `2` |
| Win Rate | `0.0%` |
| P&L moyen EMA | `-0.284%` |

### Paramètres ML Courants
| Paramètre | Valeur Apprise |
|---|---|
| SL multiplier | `1.54×ATR` |
| TP ratio | `1:2.50` |
| Confidence floor | `55.0/100` |

### Liens
[[decisions/2026-03-31_165057_predict_ETH-USDT]]
[[config/ScanAgent_memory]]
