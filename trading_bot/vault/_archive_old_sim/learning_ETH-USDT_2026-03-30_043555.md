---
date: 2026-03-30 04:35:55 UTC
agent: LearningEngine
asset: ETH/USDT
signal: sell
confiance: 33
tags:
- apprentissage
- ml
- ETH/USDT
- retrospective
pnl_pct: -0.516
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — ETH/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `ETH/USDT` |
| Direction | SELL |
| Entrée | `2812.38876` |
| Sortie | `2826.892899` |
| P&L | `-0.516%` (`$-100.00`) |
| Durée | `0.0h` |
| Raison sortie | `stop_loss` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 33/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `2826.8929` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-0.52%` | `-0.52%` |
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
