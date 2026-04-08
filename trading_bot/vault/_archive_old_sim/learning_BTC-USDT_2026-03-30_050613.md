---
date: 2026-03-30 05:06:13 UTC
agent: LearningEngine
asset: BTC/USDT
signal: sell
confiance: 35
tags:
- apprentissage
- ml
- BTC/USDT
- retrospective
pnl_pct: -0.641
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — BTC/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `BTC/USDT` |
| Direction | SELL |
| Entrée | `53039.875702` |
| Sortie | `53379.812681` |
| P&L | `-0.641%` (`$-100.00`) |
| Durée | `0.0h` |
| Raison sortie | `stop_loss` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 35/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `53379.8127` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-0.64%` | `-0.64%` |
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
[[decisions/convergence_BTC-USDT]]
