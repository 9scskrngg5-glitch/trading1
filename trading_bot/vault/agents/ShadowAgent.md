---
agent: ShadowAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/experiments/"
channel: "shadow:result"
tags: [agent, trading-system]
---
# 🔬 ShadowAgent

## Rôle
R&D — teste 3 stratégies alternatives en parallèle (shadow trading).

## Inputs
- `decisions:convergence` (PredictAgent — mêmes signaux)
- `portfolio:update` (RiskAgent — clôtures réelles)
- `market:regime` (RegimeAgent — filtre régime)

## Outputs
- `shadow:result` → MetaAgent (ranking stratégies)
- vault/experiments/

## Vault
`vault/experiments/`

## Canal Principal
`shadow:result`

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
- [[agents/RiskAgent]]
- [[agents/RegimeAgent]]
- [[agents/KnowledgeAgent]]
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
