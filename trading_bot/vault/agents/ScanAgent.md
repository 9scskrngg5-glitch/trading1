---
agent: ScanAgent
type: agent_profile
last_updated: "2026-04-07 04:58 UTC"
vault_folder: "vault/technique/"
channel: "signals:technical"
tags: [agent, trading-system]
---
# 🔭 ScanAgent

## Rôle
Ingestion des données de marché et détection des signaux techniques.

## Inputs
- Données OHLCV Binance (1m, 1h, 4h)
- MarketDataManager (WS + REST)
- Volume

## Outputs
- Signaux techniques (RSI, MACD, BB, ATR)
- Publication `signals:technical`

## Vault
`vault/technique/`

## Canal Principal
`signals:technical`

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
- [[agents/RegimeAgent]]
- [[agents/SynthesisAgent]]
- [[agents/KnowledgeAgent]]
- [[agents/MetaAgent]]

---
_Généré par VaultInitializer | 2026-04-07 04:58 UTC_
