---
date: 2026-03-30 05:06:15 UTC
agent: LearningEngine
asset: ETH/USDT
signal: buy
confiance: 80
tags:
- apprentissage
- ml
- ETH/USDT
- retrospective
pnl_pct: -0.506
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — ETH/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `ETH/USDT` |
| Direction | BUY |
| Entrée | `4398.995533` |
| Sortie | `4376.746558` |
| P&L | `-0.506%` (`$-160.00`) |
| Durée | `0.0h` |
| Raison sortie | `stop_loss` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 80/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `4376.7466` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-0.51%` | `-0.51%` |
| Amélioration possible | — | `+0.00%` |

**Leçon apprise :** Signal de marché faible. Augmenter la confiance minimale requise pour ETH/USDT.


### Mise à Jour des Paramètres
```json
{
  "sl_atr_multiplier": 1.5,
  "tp_rr_ratio": 2.5
}
```

### Liens
[[decisions/convergence_ETH-USDT]]
