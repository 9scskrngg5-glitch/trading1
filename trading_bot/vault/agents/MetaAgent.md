---
agent: MetaAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/reports/"
channel: "meta:directive"
tags: [agent, trading-system]
---
# 👑 MetaAgent

## Rôle
CEO — cerveau central. Orchestre, pondère et optimise le système entier.

## Inputs
- `signals:technical` (ScanAgent — scoring)
- `signals:fundamental` (ResearchAgent — scoring)
- `decisions:convergence` (PredictAgent — scoring)
- `portfolio:update` (RiskAgent — résultats trades)
- `system:heartbeat` (tous les agents — liveness)
- `system:error` (SupervisorAgent — erreurs)
- `market:regime` (RegimeAgent)
- `shadow:result` (ShadowAgent — recommandations R&D)
- `system:behavior` (BehaviorAgent — état discipline)

## Outputs
- `meta:directive` → PredictAgent, RiskAgent, CompoundAgent (poids, kill switch)
- Rapport CEO quotidien (vault/reports/ + Telegram)
- Rapport hebdomadaire (vault/reports/ + Telegram)

## Vault
`vault/reports/`

## Canal Principal
`meta:directive`

## Performance Metrics
_Mis à jour automatiquement par MetaAgent._
| Métrique | Valeur |
|---|---|
| Signaux envoyés | — |
| Précision | — |
| Score composite | — |
| Statut | 🟢 Actif |

## Connexions (Liens Obsidian)
- [[agents/ScanAgent]]
- [[agents/ResearchAgent]]
- [[agents/PredictAgent]]
- [[agents/RiskAgent]]
- [[agents/ExecuteAgent]]
- [[agents/CompoundAgent]]
- [[agents/SynthesisAgent]]
- [[agents/SupervisorAgent]]
- [[agents/RegimeAgent]]
- [[agents/KnowledgeAgent]]
- [[agents/ShadowAgent]]
- [[agents/BehaviorAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
