---
date: 2026-03-31 01:34:10 UTC
agent: LearningEngine
asset: SOL/USDT
signal: sell
confiance: 40
tags:
- apprentissage
- ml
- SOL/USDT
- retrospective
pnl_pct: -1.47
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — SOL/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `SOL/USDT` |
| Direction | SELL |
| Entrée | `83.15` |
| Sortie | `84.3725` |
| P&L | `-1.470%` (`$-60.00`) |
| Durée | `2.7h` |
| Raison sortie | `ExitReason.STOP_LOSS` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 40/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `84.3725` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-1.47%` | `-1.47%` |
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
[[decisions/2026-03-31_013410_predict_SOL-USDT]]
