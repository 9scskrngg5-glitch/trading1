"""
VaultInitializer — Crée et maintient la structure complète du vault Obsidian.

Structure créée :
  vault/agents/         ← Pages de chaque agent avec wikilinks croisés
  vault/trades/         ← Notes de trades avec liens agents + régime
  vault/patterns/       ← Patterns détectés par KnowledgeAgent
  vault/market_conditions/ ← Changements de régime (RegimeAgent)
  vault/strategies/     ← Documentation des stratégies (MetaAgent)
  vault/reports/        ← Rapports CEO + hebdo (MetaAgent)
  vault/experiments/    ← Expériences shadow (ShadowAgent)
  vault/risk/           ← Événements de risque critiques
  vault/behavior/       ← Logs discipline (BehaviorAgent)
  vault/technique/      ← Analyses techniques (ScanAgent) — existant
  vault/fondamental/    ← Analyses fondamentales (ResearchAgent) — existant
  vault/apprentissage/  ← Rétros ML (LearningEngine) — existant
  vault/retrospectives/ ← Rétros trades (RiskAgent) — existant
  vault/synthese/       ← DataSheets (SynthesisAgent) — existant
  vault/config/         ← Mémoires agents — existant
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Dossiers vault complets ───────────────────────────────────────────────────
VAULT_FOLDERS = [
    # ── Agents core ──
    "technique",         # ScanAgent
    "fondamental",       # ResearchAgent
    "decisions",         # PredictAgent
    "risque",            # RiskAgent — décisions de risque
    "execution",         # ExecuteAgent
    "retrospectives",    # RiskAgent — post-trade
    "synthese",          # SynthesisAgent
    # ── Agents avancés ──
    "market_conditions", # RegimeAgent
    "patterns",          # KnowledgeAgent
    "experiments",       # ShadowAgent
    "behavior",          # BehaviorAgent
    "reports",           # MetaAgent
    "supervision",       # SupervisorAgent
    # ── Infrastructure ──
    "apprentissage",     # LearningEngine
    "config",            # Mémoires agents + état
    # ── LLM Intelligence ──
    "briefing",          # MetaAgent — thèses quotidiennes (Claude Opus)
    "council",           # Council — threads de délibération par trade
    "postmortems",       # MetaAgent — post-mortems par trade
    "memory",            # NarrativeMemory — narrative_patterns.jsonl
    "llm_logs",          # LLMClient — coûts et logs des appels
    "agents",            # Pages agents
]

# ── Définitions des agents pour les pages Obsidian ───────────────────────────
AGENT_DEFINITIONS = {
    "ScanAgent": {
        "emoji":    "🔭",
        "role":     "Ingestion des données de marché et détection des signaux techniques.",
        "inputs":   ["Données OHLCV Binance (1m, 1h, 4h)", "MarketDataManager (WS + REST)", "Volume"],
        "outputs":  ["Signaux techniques (RSI, MACD, BB, ATR)", "Publication `signals:technical`"],
        "vault":    "vault/technique/",
        "reads":    [],
        "writes":   ["technique/"],
        "links":    ["PredictAgent", "RegimeAgent", "SynthesisAgent", "KnowledgeAgent", "MetaAgent"],
        "channel":  "signals:technical",
    },
    "ResearchAgent": {
        "emoji":    "📰",
        "role":     "Analyse macro, sentiment de marché et actualités financières.",
        "inputs":   ["CryptoPanic API", "NewsAPI", "Binance 24hr ticker", "Swarmode (simulation)"],
        "outputs":  ["Score de sentiment (-100/+100)", "Publication `signals:fundamental`"],
        "vault":    "vault/fondamental/",
        "reads":    [],
        "writes":   ["fondamental/"],
        "links":    ["PredictAgent", "SynthesisAgent", "MetaAgent"],
        "channel":  "signals:fundamental",
    },
    "PredictAgent": {
        "emoji":    "🤖",
        "role":     "Convergence multi-signal : technique + fondamentale + regime + knowledge.",
        "inputs":   [
            "`signals:technical` (ScanAgent)",
            "`signals:fundamental` (ResearchAgent)",
            "`market:context` (SynthesisAgent)",
            "`market:regime` (RegimeAgent)",
            "`knowledge:result` (KnowledgeAgent)",
            "`meta:directive` (MetaAgent — poids adaptatifs)",
        ],
        "outputs":  ["Signal convergé (direction, confiance 0-100)", "`decisions:convergence`"],
        "vault":    "vault/decisions/",
        "reads":    [],
        "writes":   ["decisions/"],
        "links":    ["ScanAgent", "ResearchAgent", "RegimeAgent", "KnowledgeAgent",
                     "SynthesisAgent", "RiskAgent", "MetaAgent"],
        "channel":  "decisions:convergence",
    },
    "RiskAgent": {
        "emoji":    "🛡️",
        "role":     "Autorité finale. Valide, size et gère toutes les positions.",
        "inputs":   [
            "`decisions:convergence` (PredictAgent)",
            "`orders:executed` (ExecuteAgent)",
            "`market:context` (SynthesisAgent)",
            "`system:behavior` (BehaviorAgent)",
            "`system:error` (SupervisorAgent)",
            "`meta:directive` (MetaAgent)",
        ],
        "outputs":  [
            "`orders:validated` → ExecuteAgent",
            "`portfolio:update` → CompoundAgent, BehaviorAgent, ShadowAgent, KnowledgeAgent, MetaAgent",
        ],
        "vault":    "vault/risque/ + vault/retrospectives/",
        "reads":    [],
        "writes":   ["risque/", "retrospectives/"],
        "links":    ["PredictAgent", "ExecuteAgent", "CompoundAgent", "BehaviorAgent",
                     "SynthesisAgent", "MetaAgent"],
        "channel":  "orders:validated + portfolio:update",
    },
    "ExecuteAgent": {
        "emoji":    "⚡",
        "role":     "Simulation réaliste de l'exécution (slippage, spread, latence).",
        "inputs":   ["`orders:validated` (RiskAgent)", "MarketDataManager (prix temps réel)"],
        "outputs":  ["`orders:executed` → RiskAgent", "Modèle de slippage interne"],
        "vault":    "vault/execution/",
        "reads":    [],
        "writes":   ["execution/"],
        "links":    ["RiskAgent", "SupervisorAgent", "MetaAgent"],
        "channel":  "orders:executed",
    },
    "CompoundAgent": {
        "emoji":    "📈",
        "role":     "Gestion de la croissance du capital et du sizing dynamique.",
        "inputs":   [
            "`portfolio:update` (RiskAgent — trades clôturés)",
            "`market:context` (SynthesisAgent)",
            "`meta:directive` (MetaAgent)",
        ],
        "outputs":  ["`portfolio:update` (risk_config — nouveau sizing)", "vault/config/CompoundAgent_state.md"],
        "vault":    "vault/config/CompoundAgent_state.md",
        "reads":    [],
        "writes":   ["config/CompoundAgent_state.md"],
        "links":    ["RiskAgent", "SynthesisAgent", "MetaAgent"],
        "channel":  "portfolio:update",
    },
    "SynthesisAgent": {
        "emoji":    "🧠",
        "role":     "Cerveau analytique — construit la DataSheet institutionnelle de chaque asset.",
        "inputs":   [
            "`signals:technical` (ScanAgent — via bus)",
            "`signals:fundamental` (ResearchAgent — via bus)",
            "`decisions:convergence` (PredictAgent — via bus)",
            "`portfolio:update` (RiskAgent — via bus)",
            "`market:regime` (RegimeAgent — via bus)",
            "vault/technique/ (ScanAgent — lecture directe)",
            "vault/fondamental/ (ResearchAgent — lecture directe)",
            "vault/apprentissage/ (LearningEngine — lecture directe)",
            "vault/retrospectives/ (RiskAgent — lecture directe)",
            "vault/config/CompoundAgent_state.md (lecture directe)",
        ],
        "outputs":  ["`market:context` → PredictAgent, RiskAgent, CompoundAgent", "vault/synthese/"],
        "vault":    "vault/synthese/",
        "reads":    ["technique/", "fondamental/", "apprentissage/", "retrospectives/", "config/"],
        "writes":   ["synthese/"],
        "links":    ["ScanAgent", "ResearchAgent", "PredictAgent", "RiskAgent",
                     "CompoundAgent", "KnowledgeAgent", "MetaAgent"],
        "channel":  "market:context",
    },
    "RegimeAgent": {
        "emoji":    "🌊",
        "role":     "Détecte le régime de marché (trending/ranging/volatile) via ADX, ATR, volume.",
        "inputs":   ["MarketDataManager (OHLCV)", "`signals:technical` (ScanAgent)"],
        "outputs":  [
            "`market:regime` → PredictAgent, SynthesisAgent, KnowledgeAgent, ShadowAgent, MetaAgent",
            "Alertes Telegram (changement de régime)",
        ],
        "vault":    "vault/market_conditions/",
        "reads":    [],
        "writes":   ["market_conditions/"],
        "links":    ["ScanAgent", "PredictAgent", "SynthesisAgent", "KnowledgeAgent",
                     "ShadowAgent", "MetaAgent"],
        "channel":  "market:regime",
    },
    "KnowledgeAgent": {
        "emoji":    "📚",
        "role":     "Financial Wikipedia — base de connaissances vectorielle (FAISS/numpy).",
        "inputs":   [
            "`portfolio:update` (trades clôturés)",
            "`market:regime` (régimes)",
            "`signals:technical` (patterns haute confiance)",
            "`knowledge:query` (requêtes PredictAgent)",
        ],
        "outputs":  ["`knowledge:result` → PredictAgent", "vault/patterns/", "data/knowledge_db.json"],
        "vault":    "vault/patterns/ + data/knowledge_db.json",
        "reads":    [],
        "writes":   ["patterns/"],
        "links":    ["PredictAgent", "ScanAgent", "RegimeAgent", "ShadowAgent", "MetaAgent"],
        "channel":  "knowledge:query / knowledge:result",
    },
    "ShadowAgent": {
        "emoji":    "🔬",
        "role":     "R&D — teste 3 stratégies alternatives en parallèle (shadow trading).",
        "inputs":   [
            "`decisions:convergence` (PredictAgent — mêmes signaux)",
            "`portfolio:update` (RiskAgent — clôtures réelles)",
            "`market:regime` (RegimeAgent — filtre régime)",
        ],
        "outputs":  ["`shadow:result` → MetaAgent (ranking stratégies)", "vault/experiments/"],
        "vault":    "vault/experiments/",
        "reads":    [],
        "writes":   ["experiments/"],
        "links":    ["PredictAgent", "RiskAgent", "RegimeAgent", "KnowledgeAgent", "MetaAgent"],
        "channel":  "shadow:result",
    },
    "BehaviorAgent": {
        "emoji":    "🧘",
        "role":     "Contrôleur de discipline — prévient le surtrading et les biais comportementaux.",
        "inputs":   [
            "`portfolio:update` (RiskAgent — streak tracking)",
            "`orders:validated` (RiskAgent — comptage trades/heure)",
        ],
        "outputs":  ["`system:behavior` → RiskAgent (multiplicateur risque)", "vault/behavior/"],
        "vault":    "vault/behavior/",
        "reads":    [],
        "writes":   ["behavior/"],
        "links":    ["RiskAgent", "MetaAgent"],
        "channel":  "system:behavior",
    },
    "MetaAgent": {
        "emoji":    "👑",
        "role":     "CEO — cerveau central. Orchestre, pondère et optimise le système entier.",
        "inputs":   [
            "`signals:technical` (ScanAgent — scoring)",
            "`signals:fundamental` (ResearchAgent — scoring)",
            "`decisions:convergence` (PredictAgent — scoring)",
            "`portfolio:update` (RiskAgent — résultats trades)",
            "`system:heartbeat` (tous les agents — liveness)",
            "`system:error` (SupervisorAgent — erreurs)",
            "`market:regime` (RegimeAgent)",
            "`shadow:result` (ShadowAgent — recommandations R&D)",
            "`system:behavior` (BehaviorAgent — état discipline)",
        ],
        "outputs":  [
            "`meta:directive` → PredictAgent, RiskAgent, CompoundAgent (poids, kill switch)",
            "Rapport CEO quotidien (vault/reports/ + Telegram)",
            "Rapport hebdomadaire (vault/reports/ + Telegram)",
        ],
        "vault":    "vault/reports/",
        "reads":    [],
        "writes":   ["reports/"],
        "links":    [
            "ScanAgent", "ResearchAgent", "PredictAgent", "RiskAgent",
            "ExecuteAgent", "CompoundAgent", "SynthesisAgent", "SupervisorAgent",
            "RegimeAgent", "KnowledgeAgent", "ShadowAgent", "BehaviorAgent",
        ],
        "channel":  "meta:directive",
    },
    "SupervisorAgent": {
        "emoji":    "👁️",
        "role":     "Surveillance globale du système, cohérence et alertes opérationnelles.",
        "inputs":   [
            "`system:heartbeat` (tous les agents — liveness)",
            "`system:error` (erreurs agents)",
            "`signals:technical` + `signals:fundamental` (pipeline flow)",
            "`decisions:convergence` (pipeline flow)",
            "`orders:validated` + `orders:executed` (pipeline flow)",
            "`portfolio:update` + `market:context` (pipeline flow)",
        ],
        "outputs":  ["`system:error` (supervisor_alert)", "Rapport santé Telegram"],
        "vault":    "vault/supervision/",
        "reads":    [],
        "writes":   ["supervision/"],
        "links":    ["MetaAgent", "RiskAgent", "BehaviorAgent"],
        "channel":  "system:error",
    },
}


class VaultInitializer:
    """
    Initialise la structure complète du vault Obsidian.
    À appeler une fois au démarrage du système.
    """

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path

    def initialize(self) -> None:
        """Crée tous les dossiers et les pages agents."""
        self._create_folders()
        self._create_agent_pages()
        self._create_index_pages()
        logger.info(
            "[VaultInitializer] Vault initialisé : %d dossiers | %d pages agents",
            len(VAULT_FOLDERS), len(AGENT_DEFINITIONS),
        )

    def _create_folders(self) -> None:
        for folder in VAULT_FOLDERS:
            (self.vault_path / folder).mkdir(parents=True, exist_ok=True)

    def _create_agent_pages(self) -> None:
        """Crée/met à jour les pages agents dans vault/agents/."""
        agents_dir = self.vault_path / "agents"
        agents_dir.mkdir(exist_ok=True)

        for name, defn in AGENT_DEFINITIONS.items():
            page_path = agents_dir / f"{name}.md"
            content   = self._build_agent_page(name, defn)
            page_path.write_text(content, encoding="utf-8")

    def _build_agent_page(self, name: str, d: dict) -> str:
        """Génère le contenu d'une page agent Obsidian avec frontmatter YAML."""
        now      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        links    = d.get("links", [])
        links_md = "\n".join(f"- [[agents/{lnk}]]" for lnk in links)

        inputs_md  = "\n".join(f"- {i}" for i in d.get("inputs",  []))
        outputs_md = "\n".join(f"- {o}" for o in d.get("outputs", []))

        frontmatter = (
            f"---\n"
            f"agent: {name}\n"
            f"type: agent_profile\n"
            f"last_updated: \"{now}\"\n"
            f"vault_folder: \"{d.get('vault', '')}\"\n"
            f"channel: \"{d.get('channel', '')}\"\n"
            f"tags: [agent, trading-system]\n"
            f"---\n"
        )

        body = f"""# {d['emoji']} {name}

## Rôle
{d['role']}

## Inputs
{inputs_md}

## Outputs
{outputs_md}

## Vault
`{d.get('vault', 'N/A')}`

## Canal Principal
`{d.get('channel', 'N/A')}`

## Performance Metrics
_Mis à jour automatiquement par MetaAgent._
| Métrique | Valeur |
|---|---|
| Signaux envoyés | — |
| Précision | — |
| Score composite | — |
| Statut | 🟢 Actif |

## Connexions (Liens Obsidian)
{links_md}

---
_Généré par VaultInitializer | {now}_
"""
        return frontmatter + body

    def _create_index_pages(self) -> None:
        """Crée les pages index pour chaque section principale."""
        indexes = {
            "agents/index": self._build_agents_index(),
            "reports/index": self._build_reports_index(),
            "patterns/index": self._build_patterns_index(),
        }
        for path_key, content in indexes.items():
            parts = path_key.split("/")
            p     = self.vault_path
            for part in parts[:-1]:
                p = p / part
            p.mkdir(parents=True, exist_ok=True)
            (p / (parts[-1] + ".md")).write_text(content, encoding="utf-8")

    def _build_agents_index(self) -> str:
        now  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = "\n".join(
            f"| {d['emoji']} [[agents/{name}\\|{name}]] | {d['role'][:60]}... |"
            for name, d in AGENT_DEFINITIONS.items()
        )
        return f"""---
type: index
tags: [index, agents]
---
# 🏢 Organigramme — AI Trading Company

> Système multi-agents de trading autonome | {now}

## Agents

| Agent | Rôle |
|---|---|
{rows}

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
"""

    def _build_reports_index(self) -> str:
        return """---
type: index
tags: [index, reports]
---
# 📊 Rapports CEO

Les rapports sont générés automatiquement par [[agents/MetaAgent]].

## Types de Rapports
- **CEO Quotidien** : performance, régimes, classement agents, ajustements
- **Hebdomadaire** : synthèse semaine, comparaison shadow, P&L

## Liens Utiles
[[agents/MetaAgent]] | [[agents/SupervisorAgent]] | [[agents/index]]
"""

    def _build_patterns_index(self) -> str:
        return """---
type: index
tags: [index, patterns]
---
# 📚 Base de Connaissances — Patterns

Les patterns sont détectés automatiquement par [[agents/KnowledgeAgent]].

## Liens
[[agents/KnowledgeAgent]] | [[agents/PredictAgent]] | [[agents/MetaAgent]]
"""
