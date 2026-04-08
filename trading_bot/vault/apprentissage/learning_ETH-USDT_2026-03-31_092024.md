---
date: 2026-03-31 09:20:24 UTC
agent: LearningEngine
asset: ETH/USDT
signal: buy
confiance: 47
tags:
- apprentissage
- ml
- ETH/USDT
- retrospective
pnl_pct: -1.544
is_win: false
exit_reason: ExitReason.STOP_LOSS
---

## Rétrospective ML — ETH/USDT | ❌ LOSS

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `ETH/USDT` |
| Direction | BUY |
| Entrée | `2060.01` |
| Sortie | `2028.195` |
| P&L | `-1.544%` (`$-58.30`) |
| Durée | `4.2h` |
| Raison sortie | `ExitReason.STOP_LOSS` |
| Max favorable | `+0.00%` |
| Max adverse | `+0.00%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : 47/100**

### Analyse Contrefactuelle ❌

| Paramètre | Réel | Optimal trouvé |
|---|---|---|
| SL Multiplier | `2028.1950` | `1.5× ATR` |
| TP Ratio | `réel` | `1:2.5` |
| P&L résultat | `-1.54%` | `-1.54%` |
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
[[decisions/2026-03-31_092024_predict_ETH-USDT]]
