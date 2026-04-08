---
agent: PredictAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/decisions/"
channel: "decisions:convergence"
tags: [agent, trading-system]
---
# 🤖 PredictAgent

## Rôle
Convergence multi-signal : technique + fondamentale + regime + knowledge.

## Inputs
- `signals:technical` (ScanAgent)
- `signals:fundamental` (ResearchAgent)
- `market:context` (SynthesisAgent)
- `market:regime` (RegimeAgent)
- `knowledge:result` (KnowledgeAgent)
- `meta:directive` (MetaAgent — poids adaptatifs)

## Outputs
- Signal convergé (direction, confiance 0-100)
- `decisions:convergence`

## Vault
`vault/decisions/`

## Canal Principal
`decisions:convergence`

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
- [[agents/RegimeAgent]]
- [[agents/KnowledgeAgent]]
- [[agents/SynthesisAgent]]
- [[agents/RiskAgent]]
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
