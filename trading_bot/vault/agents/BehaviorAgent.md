---
agent: BehaviorAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/behavior/"
channel: "system:behavior"
tags: [agent, trading-system]
---
# 🧘 BehaviorAgent

## Rôle
Contrôleur de discipline — prévient le surtrading et les biais comportementaux.

## Inputs
- `portfolio:update` (RiskAgent — streak tracking)
- `orders:validated` (RiskAgent — comptage trades/heure)

## Outputs
- `system:behavior` → RiskAgent (multiplicateur risque)
- vault/behavior/

## Vault
`vault/behavior/`

## Canal Principal
`system:behavior`

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
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
