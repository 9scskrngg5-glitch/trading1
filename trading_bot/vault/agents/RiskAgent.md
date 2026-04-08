---
agent: RiskAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/risque/ + vault/retrospectives/"
channel: "orders:validated + portfolio:update"
tags: [agent, trading-system]
---
# 🛡️ RiskAgent

## Rôle
Autorité finale. Valide, size et gère toutes les positions.

## Inputs
- `decisions:convergence` (PredictAgent)
- `orders:executed` (ExecuteAgent)
- `market:context` (SynthesisAgent)
- `system:behavior` (BehaviorAgent)
- `system:error` (SupervisorAgent)
- `meta:directive` (MetaAgent)

## Outputs
- `orders:validated` → ExecuteAgent
- `portfolio:update` → CompoundAgent, BehaviorAgent, ShadowAgent, KnowledgeAgent, MetaAgent

## Vault
`vault/risque/ + vault/retrospectives/`

## Canal Principal
`orders:validated + portfolio:update`

## Performance Metrics
_Mis à jour automatiquement par MetaAgent._
| Métrique | Valeur |
|---|---|
| Signaux envoyés | — |
| Précision | — |
| Score composite | — |
| Statut | 🟢 Actif |

## Connexions (Liens Obsidian)
- [[agents/PredictAgent]]
- [[agents/ExecuteAgent]]
- [[agents/CompoundAgent]]
- [[agents/BehaviorAgent]]
- [[agents/SynthesisAgent]]
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
