---
date: 2026-03-30 05:37:32 UTC
agent: LearningEngine
asset: SOL/USDT
signal: buy
confiance: 54
tags:
- apprentissage
- ml
- SOL/USDT
- retrospective
pnl_pct: -0.445
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — SOL/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `SOL/USDT` |
| Direction | BUY |
| Entrée | `201.136706` |
| Sortie | `200.240768` |
| P&L | `-0.445%` (`$-105.13`) |
| Durée | `0.0h` |
| Raison sortie | `stop_loss` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 54/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `200.2408` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-0.45%` | `-0.45%` |
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
[[decisions/convergence_SOL-USDT]]
