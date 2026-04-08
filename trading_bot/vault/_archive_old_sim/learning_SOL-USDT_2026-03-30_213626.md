---
date: 2026-03-30 21:36:26 UTC
agent: LearningEngine
asset: SOL/USDT
signal: buy
confiance: 65
tags:
- apprentissage
- ml
- SOL/USDT
- retrospective
pnl_pct: -1.761
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — SOL/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `SOL/USDT` |
| Direction | BUY |
| Entrée | `82.79` |
| Sortie | `81.332` |
| P&L | `-1.761%` (`$-130.00`) |
| Durée | `0.0h` |
| Raison sortie | `stop_loss` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 65/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `81.3320` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-1.76%` | `-1.76%` |
| Amélioration possible | — | `+0.00%` |

**Leçon apprise :** Signal de marché faible. Augmenter la confiance minimale requise pour SOL/USDT.


### Mise à Jour des Paramètres
```json
{
  "sl_atr_multiplier": 1.5,
  "tp_rr_ratio": 2.5
}
```

### Liens
[[decisions/2026-03-30_213626_predict_SOL-USDT]]
