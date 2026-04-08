---
date: 2026-03-31 01:20:55 UTC
agent: LearningEngine
asset: BTC/USDT
signal: sell
confiance: 42
tags:
- apprentissage
- ml
- BTC/USDT
- retrospective
pnl_pct: -1.001
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — BTC/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `BTC/USDT` |
| Direction | SELL |
| Entrée | `66761.39` |
| Sortie | `67429.681785` |
| P&L | `-1.001%` (`$-60.00`) |
| Durée | `2.5h` |
| Raison sortie | `ExitReason.STOP_LOSS` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 42/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `67429.6818` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-1.00%` | `-1.00%` |
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
[[decisions/2026-03-31_012055_predict_BTC-USDT]]
