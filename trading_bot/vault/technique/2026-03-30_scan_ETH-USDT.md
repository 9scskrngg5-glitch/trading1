---
date: 2026-03-30 23:59:59 UTC
agent: ScanAgent
asset: ETH/USDT
signal: bearish
confiance: 32
tags:
- trading
- crypto
- 1d
timeframe: 1d
rsi: 25.05
macd_hist: -18.812125
bb_position: 0.267
atr: 104.741429
entry_price: 2024.14
sl_atr_mult: 1.5
---

## Scan de Marché — ETH/USDT `1d`

> Source données : 🟢 Binance WS+REST

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `25.05` | 🔴 Survente | `1.00` | — |
| MACD Histogram | `-18.812125` | 📉 | `1.00` | — |
| Bollinger Band | `26.7%` | — | `1.00` | — |
| Volume | `0.89x` | 📊 Normal | adaptatif | — |
| ATR (14) | `104.741429` | — | — | — |
| Prix | `2024.14` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `0.943` | 🟢 Acheteur |
| VWAP Distance | `-0.16%` | ↓ Dessous VWAP |
| Trend Slope (1m×20) | `+0.00516%/candle` | 📈 |

### Signal Adaptatif
> **BEARISH** — Confiance : **32/100**
> Seuil minimum appris : `55.0/100`

### Performance Historique sur ETH/USDT
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
[[decisions/2026-03-30_235959_predict_ETH-USDT]]
[[config/ScanAgent_memory]]
