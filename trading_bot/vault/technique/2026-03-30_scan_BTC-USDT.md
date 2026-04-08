---
date: 2026-03-30 23:59:59 UTC
agent: ScanAgent
asset: BTC/USDT
signal: bearish
confiance: 17
tags:
- trading
- crypto
- 1d
timeframe: 1d
rsi: 27.74
macd_hist: -525.446385
bb_position: 0.164
atr: 2683.442857
entry_price: 66701.59
sl_atr_mult: 1.5
---

## Scan de Marché — BTC/USDT `1d`

> Source données : 🟢 Binance WS+REST

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `27.74` | 🔴 Survente | `1.00` | — |
| MACD Histogram | `-525.446385` | 📉 | `1.00` | — |
| Bollinger Band | `16.4%` | 🟢 Bas | `1.00` | — |
| Volume | `0.84x` | 📊 Normal | adaptatif | — |
| ATR (14) | `2683.442857` | — | — | — |
| Prix | `66701.59` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `0.250` | 🟢 Acheteur |
| VWAP Distance | `+0.09%` | ↑ Dessus VWAP |
| Trend Slope (1m×20) | `+0.00466%/candle` | 📈 |

### Signal Adaptatif
> **BEARISH** — Confiance : **17/100**
> Seuil minimum appris : `55.0/100`

### Performance Historique sur BTC/USDT
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
[[decisions/2026-03-30_235959_predict_BTC-USDT]]
[[config/ScanAgent_memory]]
