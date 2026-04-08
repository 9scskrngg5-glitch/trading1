---
date: 2026-03-30 05:36:30 UTC
agent: LearningEngine
asset: BTC/USDT
signal: sell
confiance: 37
tags:
- apprentissage
- ml
- BTC/USDT
- retrospective
pnl_pct: -0.586
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — BTC/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `BTC/USDT` |
| Direction | SELL |
| Entrée | `50825.093731` |
| Sortie | `51123.030721` |
| P&L | `-0.586%` (`$-100.00`) |
| Durée | `0.0h` |
| Raison sortie | `stop_loss` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 37/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `51123.0307` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-0.59%` | `-0.59%` |
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
