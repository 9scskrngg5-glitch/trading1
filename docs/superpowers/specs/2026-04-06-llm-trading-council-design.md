# Design — LLM Trading Council
**Date :** 2026-04-06
**Statut :** Approuvé

---

## Contexte

Le bot de trading possède une architecture multi-agents solide (13 agents, pipeline Scan→Predict→Risk→Execute, apprentissage EMA adaptatif, backtester, circuit breaker). Le problème identifié : les agents échangent des données structurées (scores numériques) sans jamais *raisonner*. La structure existe, le cerveau manque.

**Objectif :** Injecter une intelligence LLM réelle aux moments qui comptent, sans remplacer le pipeline algorithmique existant.

---

## Architecture Générale

```
Pipeline algorithmique (inchangé, rapide)
Scan → Research → Predict → Risk → [GATE CONSEIL LLM] → Execute

                                        ↑
                               Council (nouveau)
                    3 GPT-4o parallèles → Claude Sonnet arbitre

MetaAgent (Claude Opus)
    → Briefing quotidien à 8h00
    → Post-mortem après chaque trade fermé
    → Rapport CEO hebdomadaire
```

**Principe clé :** le LLM ne remplace pas le scoring algorithmique — il s'active comme une couche de validation narrative avant chaque décision de capital.

---

## Nouveaux Modules

### `core/llm_client.py`
Wrapper unifié pour Anthropic (Claude) et OpenAI (GPT-4o).

Responsabilités :
- Appels async avec retry exponentiel (max 3 tentatives)
- Tracking du coût par appel (tokens × tarif)
- Timeout configurable (défaut : 30s)
- Logging de chaque appel dans `vault/llm_logs/`
- Interface unique : `await llm.complete(model, prompt, max_tokens)`

Modèles utilisés :
- `gpt-4o` — appels rapides, parallèles, peu coûteux
- `claude-sonnet-4-6` — arbitrage Conseil
- `claude-opus-4-6` — briefing matinal, post-mortems, rapports CEO

### `core/council.py`
Le Conseil de trading — délibération LLM avant chaque ordre.

**Déclencheur :** RiskAgent valide un signal avec confiance ≥ seuil minimum (55).

**Déroulement :**
1. Récupérer contexte : `daily_thesis` + 3 patterns narratifs similaires depuis NarrativeMemory
2. Lancer 3 appels GPT-4o en parallèle (`asyncio.gather`) :
   - **Bull Analyst** : argument le plus fort POUR ce trade
   - **Bear Analyst** : argument le plus fort CONTRE ce trade
   - **Devil's Advocate** : ce qu'on ignore, biais cognitifs, tail risk
3. Claude Sonnet (`claude-sonnet-4-6`) lit les 3 avis + contexte et produit :
   - Verdict : `EXECUTE` / `PASSE` / `REDUIS_TAILLE`
   - Ajustement confiance : entier entre -20 et +10
   - Raisonnement : 3 phrases maximum
4. Confiance finale = confiance algorithmique + ajustement
5. Si confiance finale ≥ seuil → ordre transmis à ExecuteAgent
6. Thread complet sauvegardé dans `vault/council/YYYY-MM-DD_HH-MM_ASSET.md`

**Timeout :** si le Conseil ne répond pas en 20s → l'ordre passe avec la confiance algorithmique originale (fail-open).

**Canaux :** nouveau canal `council_result` sur le bus.

### `core/narrative_memory.py`
Mémoire de patterns en langage naturel.

**Structure de stockage :** `vault/memory/narrative_patterns.jsonl`
```json
{
  "ts": "2026-04-06T09:15:00Z",
  "asset": "BTC/USDT",
  "regime": "trending_bull",
  "setup": "RSI_divergence_bull + low_volume_breakout",
  "outcome": "loss",
  "pattern": "BTC fausse cassure haussière sur volume faible → reversal -3.2% dans les 4h",
  "confirmed_count": 3
}
```

**Interface :**
- `add_pattern(asset, regime, setup, outcome, pattern_text)` — appelé par MetaAgent après post-mortem
- `find_similar(asset, regime, setup, top_k=3)` — appelé par Council avant délibération (matching par mots-clés asset+regime+setup)

---

## Modifications des Agents Existants

### MetaAgent (modifications)

**Ajout 1 — Briefing Matinal (`_daily_briefing`)**
- Déclenché à 8h00 chaque jour (via timer dans `run_cycle`)
- Claude Opus lit : prix overnight (via MarketDataManager), headlines CryptoPanic, patterns narratifs récents (top 5)
- Produit une Thèse du Jour (~200 mots) publiée sur canal `daily_thesis`
- Sauvegardée dans `vault/briefing/YYYY-MM-DD_briefing.md`

**Ajout 2 — Post-Mortem (`_run_postmortem`)**
- Déclenché à réception de `orders_executed` avec statut CLOSED
- Claude Opus écrit 5 lignes : attente vs réalité, ce qu'on a raté, pattern à retenir
- Appelle `narrative_memory.add_pattern()` avec le pattern extrait
- Sauvegardé dans `vault/postmortems/YYYY-MM-DD_HH-MM_ASSET.md`

### RiskAgent (modifications)

**Ajout — Hook pre-execution**
- Après validation algorithmique (circuit breaker OK, sizing calculé)
- Avant publication sur `orders_validated`
- Appelle `Council.convene()` et attend le verdict
- Ajuste la taille de position si verdict = `REDUIS_TAILLE` (×0.5)
- Loggue le verdict dans la note vault/risque/ existante

### ScanAgent (modifications)

**Ajout — Enrichissement GPT-4o**
- Après calcul du score technique, si score ≥ MIN_CONFIDENCE
- Appelle GPT-4o avec : indicateurs calculés + régime de marché actuel
- GPT-4o répond en 2 phrases : "Ce setup est [valide/douteux] car..."
- L'enrichissement est ajouté au signal publié sur `signals_technical` (champ `llm_comment`)
- Timeout 5s — si pas de réponse, le signal part sans commentaire

---

## Nouveaux Canaux (message_bus.py)

```python
"daily_thesis":    "meta:daily_thesis",   # MetaAgent → tous les agents
"council_result":  "council:result",      # Council → RiskAgent + logs
```

---

## Nouveaux Dossiers Vault

```
vault/briefing/        ← Thèses du jour (MetaAgent)
vault/council/         ← Threads de délibération par trade
vault/postmortems/     ← Post-mortems par trade fermé
vault/memory/          ← narrative_patterns.jsonl
vault/llm_logs/        ← Coûts et logs des appels LLM
```

---

## Variables d'Environnement (.env)

```
ANTHROPIC_API_KEY=...   ← pour Claude Sonnet + Opus
OPENAI_API_KEY=...      ← pour GPT-4o
LLM_DAILY_BUDGET_USD=10 ← coupe-circuit coût (défaut : $10/jour)
```

**Coupe-circuit coût :** si le budget journalier est atteint, le Council est désactivé et les ordres passent sur la confiance algorithmique seule.

---

## Estimation des Coûts

| Composant | Modèle | Fréquence typique | Coût unitaire |
|---|---|---|---|
| Enrichissement scan | GPT-4o | ~20/heure | ~$0.01 |
| Conseil (×3 analysts) | GPT-4o | ~5/jour | ~$0.03 |
| Arbitre Conseil | Claude Sonnet | ~5/jour | ~$0.05 |
| Briefing matinal | Claude Opus | 1/jour | ~$0.30 |
| Post-mortem | Claude Opus | ~5/jour | ~$0.30 |
| **Total estimé** | | | **~$3-6/jour** |

---

## Ce qui ne change pas

- Tous les agents existants conservent leur logique algorithmique
- Le message bus (Redis/local) est inchangé sauf 2 nouveaux canaux
- La structure du vault Obsidian est préservée (5 nouveaux dossiers ajoutés)
- Le backtester, circuit breaker, dynamic sizer, performance tracker : intacts
- Le `VaultInitializer` est mis à jour pour créer les 5 nouveaux dossiers

---

## Séquence d'implémentation

1. `core/llm_client.py` — fondation de tout le reste
2. `core/narrative_memory.py` — indépendant, testable seul
3. `core/council.py` — dépend de llm_client + narrative_memory
4. Modifications MetaAgent (briefing + post-mortem) — dépend de llm_client + narrative_memory
5. Modifications RiskAgent (hook Council) — dépend de council
6. Modifications ScanAgent (enrichissement GPT-4o) — dépend de llm_client
7. Mise à jour message_bus.py (2 canaux)
8. Mise à jour VaultInitializer (5 nouveaux dossiers)
9. Mise à jour run_demo.py (injection LLMClient + NarrativeMemory)
10. Mise à jour requirements.txt (anthropic, openai)
