---
type: index
tags: [index, agents]
---
# 🏢 Organigramme — AI Trading Company

> Système multi-agents de trading autonome | 2026-04-07

## Agents

| Agent | Rôle |
|---|---|
| 🔭 [[agents/ScanAgent\|ScanAgent]] | Ingestion des données de marché et détection des signaux tec... |
| 📰 [[agents/ResearchAgent\|ResearchAgent]] | Analyse macro, sentiment de marché et actualités financières... |
| 🤖 [[agents/PredictAgent\|PredictAgent]] | Convergence multi-signal : technique + fondamentale + regime... |
| 🛡️ [[agents/RiskAgent\|RiskAgent]] | Autorité finale. Valide, size et gère toutes les positions.... |
| ⚡ [[agents/ExecuteAgent\|ExecuteAgent]] | Simulation réaliste de l'exécution (slippage, spread, latenc... |
| 📈 [[agents/CompoundAgent\|CompoundAgent]] | Gestion de la croissance du capital et du sizing dynamique.... |
| 🧠 [[agents/SynthesisAgent\|SynthesisAgent]] | Cerveau analytique — construit la DataSheet institutionnelle... |
| 🌊 [[agents/RegimeAgent\|RegimeAgent]] | Détecte le régime de marché (trending/ranging/volatile) via ... |
| 📚 [[agents/KnowledgeAgent\|KnowledgeAgent]] | Financial Wikipedia — base de connaissances vectorielle (FAI... |
| 🔬 [[agents/ShadowAgent\|ShadowAgent]] | R&D — teste 3 stratégies alternatives en parallèle (shadow t... |
| 🧘 [[agents/BehaviorAgent\|BehaviorAgent]] | Contrôleur de discipline — prévient le surtrading et les bia... |
| 👑 [[agents/MetaAgent\|MetaAgent]] | CEO — cerveau central. Orchestre, pondère et optimise le sys... |
| 👁️ [[agents/SupervisorAgent\|SupervisorAgent]] | Surveillance globale du système, cohérence et alertes opérat... |

## Philosophie
Chaque agent = un département de l'entreprise.
MetaAgent = CEO. RiskAgent = autorité finale.
Obsidian = mémoire centrale et graphe de connaissances.
Telegram = canal de communication exécutif.

## Architecture
```
ScanAgent + ResearchAgent
        ↓
    PredictAgent ← RegimeAgent ← KnowledgeAgent
        ↓
   SynthesisAgent
        ↓
    RiskAgent ← BehaviorAgent
        ↓
   ExecuteAgent
        ↓
   CompoundAgent
        ↓
   SupervisorAgent + MetaAgent (CEO) + ShadowAgent (R&D)
```
