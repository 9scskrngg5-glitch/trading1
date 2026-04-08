---
agent: KnowledgeAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/patterns/ + data/knowledge_db.json"
channel: "knowledge:query / knowledge:result"
tags: [agent, trading-system]
---
# 📚 KnowledgeAgent

## Rôle
Financial Wikipedia — base de connaissances vectorielle (FAISS/numpy).

## Inputs
- `portfolio:update` (trades clôturés)
- `market:regime` (régimes)
- `signals:technical` (patterns haute confiance)
- `knowledge:query` (requêtes PredictAgent)

## Outputs
- `knowledge:result` → PredictAgent
- vault/patterns/
- data/knowledge_db.json

## Vault
`vault/patterns/ + data/knowledge_db.json`

## Canal Principal
`knowledge:query / knowledge:result`

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
- [[agents/ScanAgent]]
- [[agents/RegimeAgent]]
- [[agents/ShadowAgent]]
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
