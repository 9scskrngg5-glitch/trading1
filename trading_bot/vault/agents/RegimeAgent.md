---
agent: RegimeAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/market_conditions/"
channel: "market:regime"
tags: [agent, trading-system]
---
# 🌊 RegimeAgent

## Rôle
Détecte le régime de marché (trending/ranging/volatile) via ADX, ATR, volume.

## Inputs
- MarketDataManager (OHLCV)
- `signals:technical` (ScanAgent)

## Outputs
- `market:regime` → PredictAgent, SynthesisAgent, KnowledgeAgent, ShadowAgent, MetaAgent
- Alertes Telegram (changement de régime)

## Vault
`vault/market_conditions/`

## Canal Principal
`market:regime`

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
- [[agents/PredictAgent]]
- [[agents/SynthesisAgent]]
- [[agents/KnowledgeAgent]]
- [[agents/ShadowAgent]]
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
