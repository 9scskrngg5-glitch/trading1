---
agent: CompoundAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/config/CompoundAgent_state.md"
channel: "portfolio:update"
tags: [agent, trading-system]
---
# 📈 CompoundAgent

## Rôle
Gestion de la croissance du capital et du sizing dynamique.

## Inputs
- `portfolio:update` (RiskAgent — trades clôturés)
- `market:context` (SynthesisAgent)
- `meta:directive` (MetaAgent)

## Outputs
- `portfolio:update` (risk_config — nouveau sizing)
- vault/config/CompoundAgent_state.md

## Vault
`vault/config/CompoundAgent_state.md`

## Canal Principal
`portfolio:update`

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
- [[agents/SynthesisAgent]]
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
