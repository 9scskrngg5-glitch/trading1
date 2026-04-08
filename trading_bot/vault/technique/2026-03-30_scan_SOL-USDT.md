---
date: 2026-03-30 23:59:59 UTC
agent: ScanAgent
asset: SOL/USDT
signal: bearish
confiance: 25
tags:
- trading
- crypto
- 1d
timeframe: 1d
rsi: 27.08
macd_hist: -0.944101
bb_position: 0.144
atr: 4.392857
entry_price: 82.47
sl_atr_mult: 1.5
---

## Scan de Marché — SOL/USDT `1d`

> Source données : 🟢 Binance WS+REST

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `27.08` | 🔴 Survente | `1.00` | — |
| MACD Histogram | `-0.944101` | 📉 | `1.00` | — |
| Bollinger Band | `14.4%` | 🟢 Bas | `1.00` | — |
| Volume | `1.02x` | 📊 Normal | adaptatif | — |
| ATR (14) | `4.392857` | — | — | — |
| Prix | `82.47` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `0.091` | ⚪ Neutre |
| VWAP Distance | `-0.21%` | ↓ Dessous VWAP |
| Trend Slope (1m×20) | `+0.00229%/candle` | 📈 |

### Signal Adaptatif
> **BEARISH** — Confiance : **25/100**
> Seuil minimum appris : `55.0/100`

### Performance Historique sur SOL/USDT
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
[[decisions/2026-03-30_235959_predict_SOL-USDT]]
[[config/ScanAgent_memory]]
