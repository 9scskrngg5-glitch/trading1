---
agent: SupervisorAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/supervision/"
channel: "system:error"
tags: [agent, trading-system]
---
# 👁️ SupervisorAgent

## Rôle
Surveillance globale du système, cohérence et alertes opérationnelles.

## Inputs
- `system:heartbeat` (tous les agents — liveness)
- `system:error` (erreurs agents)
- `signals:technical` + `signals:fundamental` (pipeline flow)
- `decisions:convergence` (pipeline flow)
- `orders:validated` + `orders:executed` (pipeline flow)
- `portfolio:update` + `market:context` (pipeline flow)

## Outputs
- `system:error` (supervisor_alert)
- Rapport santé Telegram

## Vault
`vault/supervision/`

## Canal Principal
`system:error`

## Performance Metrics
_Mis à jour automatiquement par MetaAgent._
| Métrique | Valeur |
|---|---|
| Signaux envoyés | — |
| Précision | — |
| Score composite | — |
| Statut | 🟢 Actif |

## Connexions (Liens Obsidian)
- [[agents/MetaAgent]]
- [[agents/RiskAgent]]
- [[agents/BehaviorAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
