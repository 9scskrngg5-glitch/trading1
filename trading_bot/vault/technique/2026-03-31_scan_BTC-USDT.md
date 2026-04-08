---
date: 2026-03-31 16:50:56 UTC
agent: ScanAgent
asset: BTC/USDT
signal: bearish
confiance: 48
tags:
- trading
- crypto
- 1d
timeframe: 1d
rsi: 32.71
macd_hist: -443.580935
bb_position: 0.271
atr: 2669.836429
entry_price: 67585.35
sl_atr_mult: 1.54
---

## Scan de Marché — BTC/USDT `1d`

> Source données : 🟢 Binance WS+REST

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `32.71` | ⚪ Neutre | `1.00` | 50% (2 signaux) |
| MACD Histogram | `-443.580935` | 📉 | `1.00` | 0% (2 signaux) |
| Bollinger Band | `27.1%` | — | `1.00` | 100% (2 signaux) |
| Volume | `0.79x` | 📊 Normal | adaptatif | — |
| ATR (14) | `2669.836429` | — | — | — |
| Prix | `67585.35` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `-0.767` | 🔴 Vendeur |
| VWAP Distance | `+0.78%` | ↑ Dessus VWAP |
| Trend Slope (1m×20) | `+0.07194%/candle` | 📈 |

### Signal Adaptatif
> **BEARISH** — Confiance : **48/100**
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
[[decisions/2026-03-31_165056_predict_BTC-USDT]]
[[config/ScanAgent_memory]]
