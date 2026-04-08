"""
Agent 8 — Superviseur (SupervisorAgent)
Chef de chantier du systeme multi-agents : supervise la sante, la coherence
et la performance de l'ensemble du pipeline de trading.

Responsabilites :
  - Monitoring des heartbeats de tous les agents (alerte si silence > 90s)
  - Validation croisee de la coherence du vault Obsidian (liens, orphelins)
  - Suivi du flux pipeline : signaux -> decisions -> ordres -> executions
  - Detection d'anomalies de performance (win rate, drawdown, series perdantes)
  - Reparation/suggestion de wikilinks casses dans le vault
  - Production de rapports periodiques dans vault/supervision/

Vault : vault/supervision/
Canaux ecoutes : TOUS (heartbeat, error, signals_*, decisions, orders_*, portfolio_update, market_context)
Canal de sortie : system:error (alertes superviseur)

NOTE ARCHITECTURE :
  - Le canal "supervisor" n'existe pas encore dans CHANNELS.
    Les alertes sont publiees sur le canal "error" avec type="supervisor_alert".
  - Le dossier vault/supervision/ n'est pas dans VAULT_DIRS.
    Il est cree dans setup() via mkdir(exist_ok=True).
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from core.base_agent import BaseAgent
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient
from core.performance_tracker import PerformanceTracker

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

# Seuil de silence heartbeat avant alerte (secondes)
HEARTBEAT_TIMEOUT_SEC = 90

# Seuil d'age d'un signal sans decision correspondante (secondes)
STALE_SIGNAL_SEC = 900  # 15 minutes

# Seuils d'anomalie performance
WIN_RATE_ALERT_THRESHOLD = 0.40       # Alerte si win rate < 40% sur 10 trades
DRAWDOWN_ALERT_RATIO = 0.80           # Alerte si drawdown > 80% du max autorise
CONSECUTIVE_LOSSES_ALERT = 3          # Alerte apres 3 pertes consecutives
AGENT_ERROR_RATE_THRESHOLD = 0.10     # Alerte si taux erreur agent > 10%

# Frequence des rapports (en cycles de 60s)
STATUS_REPORT_INTERVAL = 30           # Toutes les 30 minutes (reduit le spam Telegram)
COHERENCE_REPORT_INTERVAL = 1440      # Quotidien (1440 minutes)

# Taille des buffers de messages
MESSAGE_BUFFER_SIZE = 200


# ── Structures de donnees ────────────────────────────────────────────────────

@dataclass
class AgentHealthState:
    """Etat de sante d'un agent surveille."""
    name: str
    last_heartbeat: datetime | None = None
    cycle_count: int = 0
    error_count: int = 0
    total_messages: int = 0
    is_alive: bool = False
    last_error: str = ""
    last_error_time: datetime | None = None

    @property
    def error_rate(self) -> float:
        """Taux d'erreur de l'agent (erreurs / messages totaux)."""
        if self.total_messages == 0:
            return 0.0
        return self.error_count / self.total_messages

    @property
    def seconds_since_heartbeat(self) -> float:
        """Secondes ecoulees depuis le dernier heartbeat."""
        if self.last_heartbeat is None:
            return float("inf")
        delta = datetime.now(timezone.utc) - self.last_heartbeat
        return delta.total_seconds()


@dataclass
class PipelineFlowStats:
    """Statistiques de flux du pipeline de trading."""
    signals_technical: int = 0
    signals_fundamental: int = 0
    decisions: int = 0
    orders_validated: int = 0
    orders_executed: int = 0
    portfolio_updates: int = 0
    market_context: int = 0
    errors: int = 0

    # Timestamps du dernier message par canal
    last_signal_technical: datetime | None = None
    last_signal_fundamental: datetime | None = None
    last_decision: datetime | None = None
    last_order_validated: datetime | None = None
    last_order_executed: datetime | None = None

    @property
    def signal_to_decision_rate(self) -> float:
        """Taux de conversion signaux -> decisions."""
        total_signals = self.signals_technical + self.signals_fundamental
        if total_signals == 0:
            return 0.0
        return self.decisions / total_signals

    @property
    def decision_to_order_rate(self) -> float:
        """Taux de conversion decisions -> ordres valides."""
        if self.decisions == 0:
            return 0.0
        return self.orders_validated / self.decisions

    @property
    def order_to_execution_rate(self) -> float:
        """Taux de conversion ordres -> executions."""
        if self.orders_validated == 0:
            return 0.0
        return self.orders_executed / self.orders_validated


@dataclass
class CoherenceIssue:
    """Probleme de coherence detecte dans le vault."""
    severity: str          # "warning" | "error" | "info"
    category: str          # "orphelin" | "lien_casse" | "donnees_manquantes"
    file_path: str
    description: str
    suggestion: str = ""   # Suggestion de reparation


# ── SupervisorAgent ──────────────────────────────────────────────────────────

class SupervisorAgent(BaseAgent):
    """
    Agent superviseur — chef de chantier du systeme de trading.

    Surveille en continu la sante de tous les agents, la coherence du vault,
    le flux du pipeline, et la performance globale. Produit des rapports
    periodiques et des alertes en temps reel.

    Parametres specifiques :
        agents   : liste des noms d'agents a surveiller
        tracker  : PerformanceTracker pour les metriques financieres
        telegram : client Telegram pour les alertes (optionnel)
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        agents: list[str],
        tracker: PerformanceTracker,
        telegram: Any = None,
        config: dict | None = None,
    ):
        # Cycle superviseur toutes les 60 secondes
        default_config = {"cycle_interval_seconds": 60}
        if config:
            default_config.update(config)
        super().__init__("SupervisorAgent", "supervision", bus, obsidian, default_config)

        self.monitored_agents = agents
        self.tracker = tracker
        self.telegram = telegram

        # --- Etat interne ---

        # Sante par agent
        self._health: dict[str, AgentHealthState] = {
            name: AgentHealthState(name=name) for name in agents
        }

        # Flux du pipeline
        self._flow = PipelineFlowStats()

        # Buffer de messages recents par canal (pour analyse temporelle)
        self._message_log: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=MESSAGE_BUFFER_SIZE)
        )

        # Signaux en attente de decision (pour detecter les signaux stale)
        self._pending_signals: dict[str, datetime] = {}

        # Historique des alertes emises (eviter les doublons)
        self._alert_history: deque[str] = deque(maxlen=100)

        # Compteurs de cycles pour les rapports periodiques
        self._cycle_count: int = 0
        self._last_coherence_date: str = ""

        # Issues de coherence detectees
        self._coherence_issues: list[CoherenceIssue] = []

        # Historique des derniers trades pour detection de series
        self._recent_outcomes: deque[bool] = deque(maxlen=20)  # True=win, False=loss

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        """Initialise le superviseur : cree le dossier vault/supervision/."""
        supervision_dir = self.obsidian.vault_path / "supervision"
        supervision_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "[SupervisorAgent] Dossier supervision cree : %s", supervision_dir
        )
        logger.info(
            "[SupervisorAgent] Surveillance de %d agents : %s",
            len(self.monitored_agents),
            ", ".join(self.monitored_agents),
        )

    # ── Souscriptions ─────────────────────────────────────────────────────────

    def _register_subscriptions(self) -> None:
        """S'abonne a TOUS les canaux du bus pour supervision globale."""
        # Heartbeat — suivi de la sante des agents
        self.bus.subscribe(CHANNELS["heartbeat"], self._on_heartbeat)

        # Erreurs — suivi des erreurs agents
        self.bus.subscribe(CHANNELS["error"], self._on_error)

        # Signaux techniques — entree du pipeline
        self.bus.subscribe(CHANNELS["signals_technical"], self._on_signal_technical)

        # Signaux fondamentaux — entree du pipeline
        self.bus.subscribe(CHANNELS["signals_fundamental"], self._on_signal_fundamental)

        # Decisions — sortie du PredictAgent
        self.bus.subscribe(CHANNELS["decisions"], self._on_decision)

        # Ordres valides — sortie du RiskAgent
        self.bus.subscribe(CHANNELS["orders_validated"], self._on_order_validated)

        # Ordres executes — sortie de l'ExecuteAgent
        self.bus.subscribe(CHANNELS["orders_executed"], self._on_order_executed)

        # Mise a jour du portefeuille
        self.bus.subscribe(CHANNELS["portfolio_update"], self._on_portfolio_update)

        # Contexte de marche (SynthesisAgent)
        self.bus.subscribe(CHANNELS["market_context"], self._on_market_context)

        logger.info(
            "[SupervisorAgent] Abonne a %d canaux pour supervision complete",
            len(CHANNELS),
        )

    # ── Handlers de messages ─────────────────────────────────────────────────

    async def _on_heartbeat(self, data: dict) -> None:
        """Traite un heartbeat : met a jour l'etat de l'agent."""
        agent_name = data.get("agent", "")
        if agent_name in self._health:
            state = self._health[agent_name]
            state.last_heartbeat = datetime.now(timezone.utc)
            state.is_alive = True
            state.cycle_count += 1
            state.total_messages += 1

    async def _on_error(self, data: dict) -> None:
        """Traite une erreur d'un agent."""
        agent_name = data.get("agent", "")
        error_msg = data.get("error", "Erreur inconnue")

        if agent_name in self._health:
            state = self._health[agent_name]
            state.error_count += 1
            state.total_messages += 1
            state.last_error = error_msg
            state.last_error_time = datetime.now(timezone.utc)

        self._flow.errors += 1
        self._message_log["error"].append(data)

        # Verifier si le taux d'erreur depasse le seuil
        if agent_name in self._health:
            state = self._health[agent_name]
            if (
                state.total_messages >= 10
                and state.error_rate > AGENT_ERROR_RATE_THRESHOLD
            ):
                await self._emit_alert(
                    f"Taux erreur {agent_name}",
                    f"Agent {agent_name} : taux d'erreur de {state.error_rate:.1%} "
                    f"({state.error_count}/{state.total_messages}) depasse le seuil de "
                    f"{AGENT_ERROR_RATE_THRESHOLD:.0%}",
                    severity="error",
                )

    async def _on_signal_technical(self, data: dict) -> None:
        """Traite un signal technique entrant."""
        self._flow.signals_technical += 1
        self._flow.last_signal_technical = datetime.now(timezone.utc)
        self._message_log["signals_technical"].append(data)

        # Enregistrer comme signal en attente de decision
        asset = data.get("asset", "unknown")
        signal_key = f"tech_{asset}_{data.get('timeframe', '')}"
        self._pending_signals[signal_key] = datetime.now(timezone.utc)

    async def _on_signal_fundamental(self, data: dict) -> None:
        """Traite un signal fondamental entrant."""
        self._flow.signals_fundamental += 1
        self._flow.last_signal_fundamental = datetime.now(timezone.utc)
        self._message_log["signals_fundamental"].append(data)

        asset = data.get("asset", "unknown")
        signal_key = f"fund_{asset}"
        self._pending_signals[signal_key] = datetime.now(timezone.utc)

    async def _on_decision(self, data: dict) -> None:
        """Traite une decision du PredictAgent."""
        self._flow.decisions += 1
        self._flow.last_decision = datetime.now(timezone.utc)
        self._message_log["decisions"].append(data)

        # Retirer les signaux correspondants de la file d'attente
        asset = data.get("asset", "")
        keys_to_remove = [
            k for k in self._pending_signals if asset in k
        ]
        for k in keys_to_remove:
            del self._pending_signals[k]

    async def _on_order_validated(self, data: dict) -> None:
        """Traite un ordre valide par le RiskAgent."""
        self._flow.orders_validated += 1
        self._flow.last_order_validated = datetime.now(timezone.utc)
        self._message_log["orders_validated"].append(data)

    async def _on_order_executed(self, data: dict) -> None:
        """Traite un ordre execute par l'ExecuteAgent."""
        self._flow.orders_executed += 1
        self._flow.last_order_executed = datetime.now(timezone.utc)
        self._message_log["orders_executed"].append(data)

        # Ne compter que les FERMETURES de trades (pas les entrées "filled")
        status = data.get("status", "")
        if status in ("stop_loss", "take_profit", "closed"):
            is_win = data.get("is_win", False)
            pnl = data.get("pnl_usd", 0)
            self._recent_outcomes.append(bool(is_win))
            logger.info(
                "[%s] 📊 Trade clos %s : %s (P&L: $%.2f)",
                self.name, data.get("asset", "?"),
                "✅ WIN" if is_win else "❌ LOSS", pnl,
            )

    async def _on_portfolio_update(self, data: dict) -> None:
        """Traite une mise a jour du portefeuille."""
        self._flow.portfolio_updates += 1
        self._message_log["portfolio_update"].append(data)

    async def _on_market_context(self, data: dict) -> None:
        """Traite une DataSheet du SynthesisAgent."""
        self._flow.market_context += 1
        self._message_log["market_context"].append(data)

    # ── Cycle principal ──────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        """
        Cycle superviseur — execute toutes les 60 secondes.

        Etapes :
        1. Verifier les heartbeats
        2. Detecter les signaux stale dans le pipeline
        3. Verifier les anomalies de performance
        4. Ecrire le rapport periodique (toutes les 5 min)
        5. Audit de coherence du vault (quotidien)
        """
        self._cycle_count += 1
        now = datetime.now(timezone.utc)

        # 1. Verification des heartbeats
        await self._check_heartbeats(now)

        # 2. Detection des signaux stale (pipeline bloque)
        await self._check_stale_signals(now)

        # 3. Detection d'anomalies de performance
        await self._check_performance_anomalies()

        # 4. Rapport de statut periodique (toutes les 5 minutes)
        # NOTE: on envoie le health via Telegram uniquement (pas d'écriture vault — jamais relu)
        if self._cycle_count % STATUS_REPORT_INTERVAL == 0:
            await self._send_status_telegram(now)

        # 5. Audit de coherence du vault (quotidien)
        today = now.strftime("%Y-%m-%d")
        if today != self._last_coherence_date:
            await self._run_coherence_audit(now)
            self._last_coherence_date = today

        logger.debug(
            "[SupervisorAgent] Cycle %d termine | Agents actifs : %d/%d",
            self._cycle_count,
            sum(1 for s in self._health.values() if s.is_alive),
            len(self._health),
        )

    # ── 1. Monitoring des heartbeats ─────────────────────────────────────────

    async def _check_heartbeats(self, now: datetime) -> None:
        """Verifie que chaque agent a envoye un heartbeat recent."""
        for agent_name, state in self._health.items():
            seconds_silent = state.seconds_since_heartbeat

            if seconds_silent > HEARTBEAT_TIMEOUT_SEC and state.is_alive:
                # L'agent etait vivant mais ne repond plus
                state.is_alive = False
                alert_msg = (
                    f"Agent {agent_name} ne repond plus ! "
                    f"Dernier heartbeat il y a {seconds_silent:.0f}s "
                    f"(seuil : {HEARTBEAT_TIMEOUT_SEC}s)"
                )
                await self._emit_alert(
                    f"Heartbeat perdu : {agent_name}",
                    alert_msg,
                    severity="error",
                )

            elif seconds_silent <= HEARTBEAT_TIMEOUT_SEC and not state.is_alive:
                # L'agent est revenu en ligne
                state.is_alive = True
                logger.info(
                    "[SupervisorAgent] Agent %s de retour en ligne", agent_name
                )

    # ── 2. Detection des signaux stale ───────────────────────────────────────

    async def _check_stale_signals(self, now: datetime) -> None:
        """Detecte les signaux restes sans decision pendant > 15 min."""
        stale_keys = []
        for signal_key, timestamp in self._pending_signals.items():
            age_sec = (now - timestamp).total_seconds()
            if age_sec > STALE_SIGNAL_SEC:
                stale_keys.append(signal_key)
                await self._emit_alert(
                    f"Signal stale : {signal_key}",
                    f"Signal '{signal_key}' emis il y a {age_sec / 60:.1f} min "
                    f"sans decision correspondante. "
                    f"Verifier PredictAgent — possible goulot d'etranglement.",
                    severity="warning",
                )

        # Nettoyer les signaux stale (eviter alertes repetees)
        for k in stale_keys:
            del self._pending_signals[k]

    # ── 3. Anomalies de performance ──────────────────────────────────────────

    async def _check_performance_anomalies(self) -> None:
        """Detecte les anomalies de performance du systeme."""
        snap = self.tracker.snapshot()
        max_dd_config = self.config.get("max_drawdown_pct", 15.0)

        # --- Win rate trop bas sur les 10 derniers trades ---
        if len(self._recent_outcomes) >= 10:
            recent_10 = list(self._recent_outcomes)[-10:]
            recent_wr = sum(recent_10) / len(recent_10)
            if recent_wr < WIN_RATE_ALERT_THRESHOLD:
                await self._emit_alert(
                    "Win rate critique",
                    f"Win rate sur les 10 derniers trades : {recent_wr:.0%} "
                    f"(seuil : {WIN_RATE_ALERT_THRESHOLD:.0%}). "
                    f"Win rate global : {snap['win_rate']:.1%}. "
                    f"Envisager un arret temporaire du trading.",
                    severity="error",
                )

        # --- Drawdown proche du maximum autorise ---
        current_dd = snap["current_drawdown"]
        dd_threshold = max_dd_config * DRAWDOWN_ALERT_RATIO
        if current_dd > dd_threshold:
            await self._emit_alert(
                "Drawdown critique",
                f"Drawdown actuel : {current_dd:.1f}% — "
                f"seuil d'alerte : {dd_threshold:.1f}% "
                f"(= {DRAWDOWN_ALERT_RATIO:.0%} du max autorise {max_dd_config:.1f}%). "
                f"Capital : ${snap['capital']:,.2f}",
                severity="error",
            )

        # --- Series de pertes consecutives ---
        if len(self._recent_outcomes) >= CONSECUTIVE_LOSSES_ALERT:
            recent_n = list(self._recent_outcomes)[-CONSECUTIVE_LOSSES_ALERT:]
            if all(not w for w in recent_n):
                await self._emit_alert(
                    "Serie perdante",
                    f"{CONSECUTIVE_LOSSES_ALERT} pertes consecutives detectees. "
                    f"Win rate global : {snap['win_rate']:.1%}. "
                    f"Profit factor : {snap['profit_factor']:.2f}. "
                    f"Recommandation : reduire la taille des positions.",
                    severity="warning",
                )

        # --- Taux d'erreur par agent ---
        for agent_name, state in self._health.items():
            if (
                state.total_messages >= 20
                and state.error_rate > AGENT_ERROR_RATE_THRESHOLD
            ):
                await self._emit_alert(
                    f"Erreurs excessives : {agent_name}",
                    f"Agent {agent_name} : {state.error_rate:.1%} d'erreurs "
                    f"({state.error_count} sur {state.total_messages} messages). "
                    f"Derniere erreur : {state.last_error}",
                    severity="warning",
                )

    # ── 4. Audit de coherence du vault ───────────────────────────────────────

    async def _run_coherence_audit(self, now: datetime) -> None:
        """
        Audit complet de coherence du vault Obsidian.

        Verifie :
        - Decisions referencent des fichiers technique/ et fondamental/ valides
        - Executions referencent des decisions risque/ valides
        - Fichiers apprentissage ont des param_updates non vides
        - Pas de fichiers orphelins (execution sans decision correspondante)
        """
        logger.info("[SupervisorAgent] Demarrage de l'audit de coherence du vault")
        self._coherence_issues.clear()

        # --- Verifier les decisions ---
        await self._audit_decisions()

        # --- Verifier les executions ---
        await self._audit_executions()

        # --- Verifier les fichiers d'apprentissage ---
        await self._audit_apprentissage()

        # --- Detecter les fichiers orphelins ---
        await self._detect_orphans()

        # --- Ecrire le rapport de coherence ---
        await self._write_coherence_report(now)

        # --- Tenter des reparations automatiques ---
        await self._suggest_repairs()

        logger.info(
            "[SupervisorAgent] Audit termine : %d problemes detectes "
            "(%d erreurs, %d avertissements, %d infos)",
            len(self._coherence_issues),
            sum(1 for i in self._coherence_issues if i.severity == "error"),
            sum(1 for i in self._coherence_issues if i.severity == "warning"),
            sum(1 for i in self._coherence_issues if i.severity == "info"),
        )

    async def _audit_decisions(self) -> None:
        """Verifie que les decisions referencent des fichiers valides."""
        decisions_dir = self.obsidian.vault_path / "decisions"
        if not decisions_dir.exists():
            return

        technique_dir = self.obsidian.vault_path / "technique"
        fondamental_dir = self.obsidian.vault_path / "fondamental"

        # Pattern pour trouver les wikilinks [[dossier/fichier]]
        wikilink_pattern = re.compile(r"\[\[([^\]]+)\]\]")

        for filepath in decisions_dir.glob("*.md"):
            try:
                text = filepath.read_text(encoding="utf-8")
            except OSError:
                continue

            links = wikilink_pattern.findall(text)
            has_tech_link = False
            has_fund_link = False

            for link in links:
                # Verifier si le fichier reference existe
                link_path = self.obsidian.vault_path / f"{link}.md"
                if not link_path.exists():
                    self._coherence_issues.append(CoherenceIssue(
                        severity="warning",
                        category="lien_casse",
                        file_path=str(filepath.relative_to(self.obsidian.vault_path)),
                        description=f"Lien casse vers [[{link}]] — fichier inexistant",
                        suggestion=self._find_closest_match(link),
                    ))

                if link.startswith("technique/"):
                    has_tech_link = True
                elif link.startswith("fondamental/"):
                    has_fund_link = True

            # Verifier qu'il y a au moins un lien technique ou fondamental
            if not has_tech_link and not has_fund_link:
                self._coherence_issues.append(CoherenceIssue(
                    severity="info",
                    category="donnees_manquantes",
                    file_path=str(filepath.relative_to(self.obsidian.vault_path)),
                    description="Decision sans reference a des signaux technique/ ou fondamental/",
                    suggestion="Ajouter des wikilinks vers les signaux source",
                ))

    async def _audit_executions(self) -> None:
        """Verifie que les executions referencent des decisions risque/ valides."""
        execution_dir = self.obsidian.vault_path / "execution"
        if not execution_dir.exists():
            return

        risque_dir = self.obsidian.vault_path / "risque"
        wikilink_pattern = re.compile(r"\[\[([^\]]+)\]\]")

        for filepath in execution_dir.glob("*.md"):
            try:
                text = filepath.read_text(encoding="utf-8")
            except OSError:
                continue

            links = wikilink_pattern.findall(text)
            has_risk_link = any(l.startswith("risque/") for l in links)
            has_decision_link = any(l.startswith("decisions/") for l in links)

            if not has_risk_link and not has_decision_link:
                self._coherence_issues.append(CoherenceIssue(
                    severity="warning",
                    category="donnees_manquantes",
                    file_path=str(filepath.relative_to(self.obsidian.vault_path)),
                    description="Execution sans reference a une decision risque/ ou decisions/",
                    suggestion="Ajouter un wikilink vers la decision correspondante",
                ))

    async def _audit_apprentissage(self) -> None:
        """Verifie que les fichiers d'apprentissage ont des param_updates non vides."""
        apprentissage_dir = self.obsidian.vault_path / "apprentissage"
        if not apprentissage_dir.exists():
            return

        for filepath in apprentissage_dir.glob("*.md"):
            note = self.obsidian._parse(filepath)
            if note is None:
                continue

            fm = note.frontmatter
            param_updates = fm.get("param_updates", None)

            if param_updates is None or param_updates == {} or param_updates == []:
                self._coherence_issues.append(CoherenceIssue(
                    severity="warning",
                    category="donnees_manquantes",
                    file_path=str(filepath.relative_to(self.obsidian.vault_path)),
                    description="Fichier apprentissage avec param_updates vide ou manquant",
                    suggestion="Verifier le LearningEngine — les mises a jour de parametres doivent etre enregistrees",
                ))

    async def _detect_orphans(self) -> None:
        """Detecte les fichiers orphelins (execution sans decision correspondante)."""
        execution_dir = self.obsidian.vault_path / "execution"
        decisions_dir = self.obsidian.vault_path / "decisions"

        if not execution_dir.exists() or not decisions_dir.exists():
            return

        # Collecter les assets+dates des decisions existantes
        decision_keys: set[str] = set()
        for filepath in decisions_dir.glob("*.md"):
            note = self.obsidian._parse(filepath)
            if note and note.frontmatter:
                asset = note.frontmatter.get("asset", "")
                date = note.frontmatter.get("date", "")
                if asset and date:
                    # Cle simplifiee : asset + date (jour)
                    day = str(date)[:10]
                    decision_keys.add(f"{asset}_{day}")

        # Verifier les executions
        for filepath in execution_dir.glob("*.md"):
            note = self.obsidian._parse(filepath)
            if note and note.frontmatter:
                asset = note.frontmatter.get("asset", "")
                date = note.frontmatter.get("date", "")
                if asset and date:
                    day = str(date)[:10]
                    key = f"{asset}_{day}"
                    if key not in decision_keys:
                        self._coherence_issues.append(CoherenceIssue(
                            severity="error",
                            category="orphelin",
                            file_path=str(filepath.relative_to(self.obsidian.vault_path)),
                            description=(
                                f"Execution orpheline : aucune decision trouvee "
                                f"pour {asset} le {day}"
                            ),
                            suggestion=(
                                f"Verifier si la decision a ete supprimee ou si "
                                f"l'execution est incorrecte"
                            ),
                        ))

    def _find_closest_match(self, broken_link: str) -> str:
        """
        Tente de trouver un fichier similaire pour un lien casse.
        Retourne une suggestion de reparation ou une chaine vide.
        """
        parts = broken_link.split("/")
        if len(parts) != 2:
            return ""

        folder, filename = parts
        folder_path = self.obsidian.vault_path / folder
        if not folder_path.exists():
            return ""

        # Chercher un fichier avec un nom similaire
        candidates = list(folder_path.glob("*.md"))
        best_match = ""
        best_score = 0

        filename_lower = filename.lower()
        for candidate in candidates:
            stem = candidate.stem.lower()
            # Score simple : nombre de caracteres communs
            common = sum(1 for a, b in zip(filename_lower, stem) if a == b)
            score = common / max(len(filename_lower), len(stem), 1)
            if score > best_score and score > 0.5:
                best_score = score
                best_match = f"{folder}/{candidate.stem}"

        if best_match:
            return f"Peut-etre vouliez-vous [[{best_match}]] ?"
        return ""

    # ── 5. Suggestions de reparation ─────────────────────────────────────────

    async def _suggest_repairs(self) -> None:
        """
        Analyse les problemes de coherence et tente des reparations simples.
        Pour les liens casses avec suggestion, log la reparation proposee.
        """
        repairs_proposed = 0

        for issue in self._coherence_issues:
            if issue.category == "lien_casse" and issue.suggestion:
                logger.info(
                    "[SupervisorAgent] Reparation suggeree pour %s : %s",
                    issue.file_path, issue.suggestion,
                )
                repairs_proposed += 1

            elif issue.category == "orphelin":
                logger.warning(
                    "[SupervisorAgent] Fichier orphelin detecte : %s — %s",
                    issue.file_path, issue.description,
                )

        if repairs_proposed > 0:
            logger.info(
                "[SupervisorAgent] %d reparations suggerees — voir rapport de coherence",
                repairs_proposed,
            )

    # ── 6. Rapports ──────────────────────────────────────────────────────────

    async def _send_status_telegram(self, now: datetime) -> None:
        """
        Envoie le health status via Telegram toutes les 5 minutes.
        PAS d'écriture vault — ce rapport n'est jamais relu par aucun agent,
        Telegram est suffisant pour le monitoring.
        """
        snap = self.tracker.snapshot()
        flow = self._flow

        logger.info(
            "[SupervisorAgent] Cycle %d | Agents %d/%d | Capital $%.2f | DD %.1f%%",
            self._cycle_count,
            sum(1 for s in self._health.values() if s.is_alive),
            len(self._health),
            snap["capital"],
            snap["current_drawdown"],
        )

        if self.telegram:
            try:
                pipeline_stats = (
                    f"Sig tech: `{flow.signals_technical}` | "
                    f"Sig fund: `{flow.signals_fundamental}`\n"
                    f"Decisions: `{flow.decisions}` | "
                    f"Ordres: `{flow.orders_validated}` → `{flow.orders_executed}`\n"
                    f"Erreurs: `{flow.errors}`"
                )
                await self.telegram.health_status(
                    agents_alive=sum(1 for s in self._health.values() if s.is_alive),
                    agents_total=len(self._health),
                    capital=snap["capital"],
                    pnl_pct=snap["total_return_pct"],
                    win_rate=snap["win_rate"],
                    drawdown=snap["current_drawdown"],
                    sharpe=snap["sharpe_ratio"],
                    pipeline_stats=pipeline_stats,
                )
            except Exception as tg_exc:
                logger.warning(
                    "[SupervisorAgent] Erreur envoi Telegram health_status: %s", tg_exc
                )

    async def _write_coherence_report(self, now: datetime) -> None:
        """
        Ecrit le rapport d'audit de coherence quotidien dans vault/supervision/.
        """
        date_str = now.strftime("%Y-%m-%d")

        errors = [i for i in self._coherence_issues if i.severity == "error"]
        warnings = [i for i in self._coherence_issues if i.severity == "warning"]
        infos = [i for i in self._coherence_issues if i.severity == "info"]

        # Construire les sections par severite
        def format_issues(issues: list[CoherenceIssue]) -> str:
            if not issues:
                return "Aucun probleme detecte.\n"
            lines = []
            for issue in issues:
                lines.append(
                    f"- **{issue.category}** — `{issue.file_path}`\n"
                    f"  {issue.description}"
                )
                if issue.suggestion:
                    lines.append(f"  > Suggestion : {issue.suggestion}")
            return "\n".join(lines) + "\n"

        frontmatter = {
            "date": date_str,
            "agent": "SupervisorAgent",
            "type": "coherence_audit",
            "tags": ["supervision", "coherence", "audit"],
            "erreurs": len(errors),
            "avertissements": len(warnings),
            "infos": len(infos),
            "total_problemes": len(self._coherence_issues),
        }

        content = f"""## Audit de Coherence du Vault — {date_str}

### Resume
- Erreurs : **{len(errors)}**
- Avertissements : **{len(warnings)}**
- Informations : **{len(infos)}**
- Total : **{len(self._coherence_issues)}** problemes detectes

### Erreurs (action requise)
{format_issues(errors)}

### Avertissements
{format_issues(warnings)}

### Informations
{format_issues(infos)}

### Dossiers audites
| Dossier | Fichiers | Statut |
|---|---|---|
{self._count_vault_files()}

### Liens verifies
Tous les wikilinks `[[dossier/fichier]]` dans les dossiers decisions/ et execution/
ont ete valides contre les fichiers existants du vault.
"""

        # vault/supervision/ supprimé — aucun agent ne lit ces rapports.
        # Les issues de cohérence sont loggées + les alertes partent sur Telegram/bus.
        logger.info(
            "[SupervisorAgent] Audit cohérence %s : %d erreurs / %d avert. / %d infos",
            date_str, len(errors), len(warnings), len(infos),
        )

    # ── Systeme d'alertes ────────────────────────────────────────────────────

    async def _emit_alert(
        self, title: str, message: str, severity: str = "warning"
    ) -> None:
        """
        Emet une alerte :
        - Log dans le journal
        - Publie sur le canal error du bus
        - Envoie une notification Telegram si disponible
        - Ecrit un fichier alerte dans vault/supervision/
        """
        # Anti-spam : ne pas repeter la meme alerte dans les 5 dernieres minutes
        alert_key = f"{title}_{severity}"
        if alert_key in self._alert_history:
            return
        self._alert_history.append(alert_key)

        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y-%m-%d_%H%M%S")

        # 1. Logger
        log_fn = logger.error if severity == "error" else logger.warning
        log_fn("[SupervisorAgent] ALERTE [%s] %s : %s", severity.upper(), title, message)

        # 2. Publier sur le bus (canal error avec type supervisor_alert)
        try:
            await self.bus.publish(
                CHANNELS["error"],
                {
                    "type": "supervisor_alert",
                    "agent": "SupervisorAgent",
                    "severity": severity,
                    "title": title,
                    "message": message,
                },
            )
        except Exception as exc:
            logger.error(
                "[SupervisorAgent] Erreur publication alerte sur le bus : %s", exc
            )

        # 3. Notification Telegram
        if self.telegram:
            try:
                severity_emoji = {"error": "!!!", "warning": "!!", "info": "i"}
                prefix = severity_emoji.get(severity, "?")
                telegram_msg = (
                    f"[{prefix}] SUPERVISEUR — {title}\n\n{message}"
                )
                await self.telegram.send(telegram_msg)
            except Exception as exc:
                logger.error(
                    "[SupervisorAgent] Erreur envoi Telegram : %s", exc
                )

        # vault/supervision/alert_* supprimé — l'alerte est déjà dans le log,
        # publiée sur le canal error (lue par RiskAgent) et envoyée sur Telegram.

    # ── Helpers de formatage ─────────────────────────────────────────────────

    def _format_pending_signals(self, now: datetime) -> str:
        """Formate la liste des signaux en attente de decision."""
        if not self._pending_signals:
            return "Aucun signal en attente.\n"

        lines = []
        for key, ts in sorted(self._pending_signals.items(), key=lambda x: x[1]):
            age_sec = (now - ts).total_seconds()
            status = "STALE" if age_sec > STALE_SIGNAL_SEC else "ok"
            lines.append(
                f"- `{key}` — age : {age_sec / 60:.1f} min [{status}]"
            )
        return "\n".join(lines) + "\n"

    def _format_recent_outcomes(self) -> str:
        """Formate la serie des derniers trades (W/L)."""
        if not self._recent_outcomes:
            return "Aucun trade enregistre.\n"

        symbols = ["W" if w else "L" for w in self._recent_outcomes]
        series_str = " ".join(symbols)

        # Compter la serie actuelle
        current_streak = 0
        streak_type = None
        for outcome in reversed(self._recent_outcomes):
            if streak_type is None:
                streak_type = outcome
                current_streak = 1
            elif outcome == streak_type:
                current_streak += 1
            else:
                break

        streak_label = "gagnante" if streak_type else "perdante"
        return (
            f"Derniers trades : `{series_str}`\n\n"
            f"Serie actuelle : **{current_streak} {streak_label}(s)**\n"
        )

    def _count_vault_files(self) -> str:
        """Compte les fichiers .md dans chaque dossier du vault."""
        folders = [
            "technique", "fondamental", "risque", "execution",
            "decisions", "retrospectives", "config",
        ]
        rows = []
        for folder in folders:
            folder_path = self.obsidian.vault_path / folder
            if folder_path.exists():
                count = len(list(folder_path.glob("*.md")))
                status = "OK" if count > 0 else "vide"
            else:
                count = 0
                status = "absent"
            rows.append(f"| {folder}/ | {count} | {status} |")
        return "\n".join(rows)

    # ── Acces externe aux metriques ──────────────────────────────────────────

    def get_health_summary(self) -> dict[str, Any]:
        """Retourne un resume de la sante de tous les agents (pour API/debug)."""
        return {
            "cycle": self._cycle_count,
            "agents": {
                name: {
                    "alive": state.is_alive,
                    "last_heartbeat": (
                        state.last_heartbeat.isoformat()
                        if state.last_heartbeat
                        else None
                    ),
                    "cycles": state.cycle_count,
                    "errors": state.error_count,
                    "error_rate": round(state.error_rate, 3),
                }
                for name, state in self._health.items()
            },
            "pipeline": {
                "signals_technical": self._flow.signals_technical,
                "signals_fundamental": self._flow.signals_fundamental,
                "decisions": self._flow.decisions,
                "orders_validated": self._flow.orders_validated,
                "orders_executed": self._flow.orders_executed,
                "conversion_signal_decision": round(
                    self._flow.signal_to_decision_rate, 3
                ),
                "conversion_decision_order": round(
                    self._flow.decision_to_order_rate, 3
                ),
                "conversion_order_execution": round(
                    self._flow.order_to_execution_rate, 3
                ),
            },
            "pending_signals": len(self._pending_signals),
            "coherence_issues": len(self._coherence_issues),
            "alerts_emitted": len(self._alert_history),
        }

    def get_flow_stats(self) -> PipelineFlowStats:
        """Retourne les statistiques de flux du pipeline."""
        return self._flow

    def get_coherence_issues(self) -> list[CoherenceIssue]:
        """Retourne la liste des problemes de coherence detectes."""
        return list(self._coherence_issues)
