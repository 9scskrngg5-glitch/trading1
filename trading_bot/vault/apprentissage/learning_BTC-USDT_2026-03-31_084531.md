---
date: 2026-03-31 08:45:31 UTC
agent: LearningEngine
asset: BTC/USDT
signal: buy
confiance: 73
tags:
- apprentissage
- ml
- BTC/USDT
- retrospective
pnl_pct: -1.095
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — BTC/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `BTC/USDT` |
| Direction | BUY |
| Entrée | `67530.65` |
| Sortie | `66791.071785` |
| P&L | `-1.095%` (`$-87.60`) |
| Durée | `3.6h` |
| Raison sortie | `ExitReason.STOP_LOSS` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 73/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `66791.0718` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-1.10%` | `-1.10%` |
| Amélioration possible | — | `+0.00%` |

**Leçon apprise :** Signal de marché faible. Augmenter la confiance minimale requise pour BTC/USDT.


### Mise à Jour des Paramètres
```json
{
  "sl_atr_multiplier": 1.5,
  "tp_rr_ratio": 2.5
}
```

### Liens
[[decisions/2026-03-31_084531_predict_BTC-USDT]]
