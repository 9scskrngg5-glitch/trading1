---
date: 2026-03-31 01:32:23 UTC
agent: LearningEngine
asset: ETH/USDT
signal: sell
confiance: 41
tags:
- apprentissage
- ml
- ETH/USDT
- retrospective
pnl_pct: -1.436
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — ETH/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `ETH/USDT` |
| Direction | SELL |
| Entrée | `2036.0` |
| Sortie | `2065.239285` |
| P&L | `-1.436%` (`$-60.00`) |
| Durée | `2.6h` |
| Raison sortie | `ExitReason.STOP_LOSS` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 41/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `2065.2393` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-1.44%` | `-1.44%` |
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
[[decisions/2026-03-31_013223_predict_ETH-USDT]]
