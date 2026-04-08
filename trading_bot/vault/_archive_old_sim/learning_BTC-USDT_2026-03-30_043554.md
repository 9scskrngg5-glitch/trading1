---
date: 2026-03-30 04:35:54 UTC
agent: LearningEngine
asset: BTC/USDT
signal: buy
confiance: 34
tags:
- apprentissage
- ml
- BTC/USDT
- retrospective
pnl_pct: -0.738
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — BTC/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `BTC/USDT` |
| Direction | BUY |
| Entrée | `89416.075908` |
| Sortie | `88755.739815` |
| P&L | `-0.738%` (`$-100.00`) |
| Durée | `0.0h` |
| Raison sortie | `stop_loss` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 34/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `88755.7398` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-0.74%` | `-0.74%` |
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
