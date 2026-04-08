---
agent: SynthesisAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/synthese/"
channel: "market:context"
tags: [agent, trading-system]
---
# 🧠 SynthesisAgent

## Rôle
Cerveau analytique — construit la DataSheet institutionnelle de chaque asset.

## Inputs
- `signals:technical` (ScanAgent — via bus)
- `signals:fundamental` (ResearchAgent — via bus)
- `decisions:convergence` (PredictAgent — via bus)
- `portfolio:update` (RiskAgent — via bus)
- `market:regime` (RegimeAgent — via bus)
- vault/technique/ (ScanAgent — lecture directe)
- vault/fondamental/ (ResearchAgent — lecture directe)
- vault/apprentissage/ (LearningEngine — lecture directe)
- vault/retrospectives/ (RiskAgent — lecture directe)
- vault/config/CompoundAgent_state.md (lecture directe)

## Outputs
- `market:context` → PredictAgent, RiskAgent, CompoundAgent
- vault/synthese/

## Vault
`vault/synthese/`

## Canal Principal
`market:context`

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
- [[agents/CompoundAgent]]
- [[agents/KnowledgeAgent]]
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
