---
date: 2026-03-30 04:37:54 UTC
agent: LearningEngine
asset: BTC/USDT
signal: buy
confiance: 37
tags:
- apprentissage
- ml
- BTC/USDT
- retrospective
pnl_pct: -0.748
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
| Sortie | `88746.935334` |
| P&L | `-0.748%` (`$-113.38`) |
| Durée | `0.0h` |
| Raison sortie | `stop_loss` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 37/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `88746.9353` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-0.75%` | `-0.75%` |
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
