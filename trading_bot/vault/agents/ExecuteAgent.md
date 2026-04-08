---
agent: ExecuteAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/execution/"
channel: "orders:executed"
tags: [agent, trading-system]
---
# ⚡ ExecuteAgent

## Rôle
Simulation réaliste de l'exécution (slippage, spread, latence).

## Inputs
- `orders:validated` (RiskAgent)
- MarketDataManager (prix temps réel)

## Outputs
- `orders:executed` → RiskAgent
- Modèle de slippage interne

## Vault
`vault/execution/`

## Canal Principal
`orders:executed`

## Performance Metrics
_Mis à jour automatiquement par MetaAgent._
| Métrique | Valeur |
|---|---|
| Signaux envoyés | — |
| Précision | — |
| Score composite | — |
| Statut | 🟢 Actif |

## Connexions (Liens Obsidian)
- [[agents/RiskAgent]]
- [[agents/SupervisorAgent]]
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
