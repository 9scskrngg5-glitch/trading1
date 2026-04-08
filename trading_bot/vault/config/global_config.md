---
type: config
version: "1.0"
last_updated: "2024-01-01"
tags: [config, trading]
---

# Configuration Globale du Vault

## Paires Suivies

### Crypto (Binance)
- BTC/USDT
- ETH/USDT
- SOL/USDT

### Forex (OANDA)
- EUR/USD
- GBP/USD

## Timeframes Actifs
- `1h` — court terme (scalping / day trading)
- `4h` — moyen terme (swing trading)
- `1d` — long terme (confirmation de tendance)

## Paramètres de Risque
| Paramètre | Valeur |
|---|---|
| Risque par trade | 2% du capital |
| Drawdown max | 15% |
| R:R minimum | 1:2.5 |
| Confiance min (signal) | 55/100 |
| Positions max simultanées | 5 |

## Poids de Combinaison des Signaux
| Agent | Poids |
|---|---|
| Agent 1 — Technique | 60% |
| Agent 2 — Fondamental | 40% |

## Structure du Vault
- `vault/technique/`     ← Agent 1 écrit, tous lisent
- `vault/fondamental/`   ← Agent 2 écrit, tous lisent
- `vault/risque/`        ← Agent 3 écrit, tous lisent
- `vault/execution/`     ← Agent 4 écrit, Agent 3 lit
- `vault/decisions/`     ← Notes de synthèse (convergence ≥ 2 agents)
- `vault/retrospectives/`← Post-mortem automatique de chaque trade
- `vault/config/`        ← Ce fichier et les paramètres globaux
