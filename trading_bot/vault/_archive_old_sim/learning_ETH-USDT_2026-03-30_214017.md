---
date: 2026-03-30 21:40:17 UTC
agent: LearningEngine
asset: ETH/USDT
signal: sell
confiance: 35
tags:
- apprentissage
- ml
- ETH/USDT
- retrospective
pnl_pct: -1.736
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — ETH/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `ETH/USDT` |
| Direction | SELL |
| Entrée | `2043.44` |
| Sortie | `2078.917` |
| P&L | `-1.736%` (`$-90.21`) |
| Durée | `0.0h` |
| Raison sortie | `stop_loss` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 35/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `2078.9170` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-1.74%` | `-1.74%` |
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
[[decisions/2026-03-30_214017_predict_ETH-USDT]]
