---
date: 2026-04-06 23:31:13 UTC
agent: ScanAgent
asset: BTC/USDT
signal: bullish
confiance: 50
tags:
- trading
- crypto
- 1d
timeframe: 1d
rsi: 44.28
macd_hist: 67.589263
bb_position: 0.625
atr: 2150.345
entry_price: 69458.31
sl_atr_mult: 1.54
---

## Scan de Marché — BTC/USDT `1d`

> Source données : 🟢 Binance WS+REST

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `44.28` | ⚪ Neutre | `1.00` | 50% (2 signaux) |
| MACD Histogram | `67.589263` | 📈 | `1.00` | 0% (2 signaux) |
| Bollinger Band | `62.5%` | — | `1.00` | 100% (2 signaux) |
| Volume | `1.03x` | 📊 Normal | adaptatif | — |
| ATR (14) | `2150.345` | — | — | — |
| Prix | `69458.31` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `0.543` | 🟢 Acheteur |
| VWAP Distance | `-0.43%` | ↓ Dessous VWAP |
| Trend Slope (1m×20) | `-0.00955%/candle` | 📉 |

### Signal Adaptatif
> **BULLISH** — Confiance : **50/100**
> Seuil minimum appris : `55.0/100`

### Performance Historique sur BTC/USDT
| Métrique | Valeur |
|---|---|
| Trades analysés | `2` |
| Win Rate | `0.0%` |
| P&L moyen EMA | `-0.200%` |

### Paramètres ML Courants
| Paramètre | Valeur Apprise |
|---|---|
| SL multiplier | `1.54×ATR` |
| TP ratio | `1:2.50` |
| Confidence floor | `55.0/100` |

### Liens
[[decisions/2026-04-06_233113_predict_BTC-USDT]]
[[config/ScanAgent_memory]]
