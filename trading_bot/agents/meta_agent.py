"""
Agent 13 — MetaAgent (CEO)
Cerveau central du système — chef d'orchestre adaptatif.

Responsabilités :
1. Tracking de performance de CHAQUE agent (contribution individuelle)
2. Ajustement dynamique des poids des agents (publie meta:directive)
3. Désactivation temporaire des agents sous-performants
4. Rapport CEO quotidien (vault/reports/ + Telegram)
5. Rapport hebdomadaire complet
6. Adaptation aux recommandations du ShadowAgent
7. Meta-learning : modifie les paramètres du pipeline selon les résultats

Structure des poids :
  tech_weight  : poids du modèle technique (ScanAgent → PredictAgent)
  fund_weight  : poids du modèle fondamental (ResearchAgent → PredictAgent)
  min_conf     : seuil de confiance minimal pour trader

Vault : vault/reports/
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from core.base_agent import BaseAgent
from core.llm_client import LLMClient
from core.message_bus import MessageBus, CHANNELS
from core.narrative_memory import NarrativeMemory
from core.obsidian_client import ObsidianClient
from core.performance_tracker import PerformanceTracker

logger = logging.getLogger(__name__)


# ── Structures ────────────────────────────────────────────────────────────────

class AgentScore:
    """Score de contribution d'un agent au système."""

    def __init__(self, name: str):
        self.name         = name
        self.signals_sent = 0       # Nombre de signaux envoyés
        self.signals_win  = 0       # Signaux qui ont mené à des trades gagnants
        self.trades_linked= 0       # Trades directement liés à cet agent
        self.last_activity= ""      # ISO timestamp de dernière activité
        self.alive        = True
        self.warnings     = 0       # Avertissements accumulés

    @property
    def precision(self) -> float:
        """Précision = trades gagnants / signaux envoyés."""
        return self.signals_win / max(self.signals_sent, 1)

    @property
    def activity_score(self) -> float:
        """Score d'activité décroissant avec le temps."""
        if not self.last_activity:
            return 0.0
        try:
            last = datetime.fromisoformat(self.last_activity)
            delta_min = (datetime.now(timezone.utc) - last).total_seconds() / 60
            return max(0.0, 1.0 - delta_min / 60.0)  # Décroit sur 1h
        except Exception:
            return 0.0

    def composite_score(self) -> float:
        """Score composite = précision × activité × log(trades+1)."""
        if not self.alive:
            return 0.0
        return self.precision * self.activity_score * math.log(self.trades_linked + 1 + 1)

    def to_dict(self) -> dict:
        return {
            "name":          self.name,
            "signals_sent":  self.signals_sent,
            "precision":     round(self.precision, 3),
            "trades_linked": self.trades_linked,
            "composite":     round(self.composite_score(), 3),
            "alive":         self.alive,
            "warnings":      self.warnings,
        }


class MetaAgent(BaseAgent):
    """
    CEO de la société de trading.

    Observe toute l'activité du système, évalue chaque département (agent),
    ajuste les paramètres globaux et communique les décisions stratégiques.
    """

    # Agents dont MetaAgent suit la performance
    TRACKED_AGENTS = [
        "ScanAgent", "ResearchAgent", "PredictAgent",
        "RiskAgent", "ExecuteAgent", "CompoundAgent",
        "SynthesisAgent", "SupervisorAgent",
        "RegimeAgent", "KnowledgeAgent", "ShadowAgent", "BehaviorAgent",
    ]

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        tracker: PerformanceTracker,
        config: dict,
        telegram=None,
        llm: "LLMClient | None" = None,
        narrative_memory: "NarrativeMemory | None" = None,
    ):
        super().__init__("MetaAgent", "reports", bus, obsidian, config)
        self.tracker  = tracker
        self.telegram = telegram

        # ── Scores par agent ──────────────────────────────────────────────────
        self._scores: dict[str, AgentScore] = {
            name: AgentScore(name) for name in self.TRACKED_AGENTS
        }

        # ── Poids globaux du pipeline (ajustables) ────────────────────────────
        self._weights = {
            "tech_weight":  1.0,    # PredictAgent : poids modèle technique
            "fund_weight":  1.0,    # PredictAgent : poids modèle fondamental
            "min_confidence": 55,   # Seuil global de confiance
            "risk_multiplier": 1.0, # Multiplicateur de risque global
        }

        # ── Agents désactivés temporairement ─────────────────────────────────
        self._disabled_agents: set[str] = set()

        # ── Régimes courants par asset ────────────────────────────────────────
        self._regimes: dict[str, str] = {}

        # ── Historique des trades pour stats CEO ──────────────────────────────
        self._recent_trades: deque = deque(maxlen=100)

        # ── Shadow tracking ───────────────────────────────────────────────────
        self._best_shadow_strategy: str | None = None
        self._shadow_recommendation: dict | None = None

        # ── Rapport CEO ───────────────────────────────────────────────────────
        self._cycle_count  = 0
        self._last_ceo_report: str = ""    # date YYYY-MM-DD du dernier rapport
        self._last_weekly_report: str = "" # date YYYY-WW du dernier rapport hebdo

        # ── Adjustment history ───────────────────────────────────────────────
        self._adjustments: deque = deque(maxlen=20)

        # ── LLM (briefing + postmortem) ───────────────────────────────────────
        self._llm: LLMClient | None               = llm
        self._narrative_memory: NarrativeMemory | None = narrative_memory
        self._daily_thesis: str                   = ""
        self._last_briefing_date: str             = ""

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        (self.obsidian.vault_path / "reports").mkdir(exist_ok=True)
        (self.obsidian.vault_path / "strategies").mkdir(exist_ok=True)
        logger.info(
            "[%s] CEO actif | tracking %d agents | poids: tech=%.1f fund=%.1f conf=%d",
            self.name, len(self.TRACKED_AGENTS),
            self._weights["tech_weight"],
            self._weights["fund_weight"],
            self._weights["min_confidence"],
        )

    def _register_subscriptions(self) -> None:
        # Observer tous les canaux pour scoring des agents
        self.bus.subscribe(CHANNELS["signals_technical"],  self._on_technical_signal)
        self.bus.subscribe(CHANNELS["signals_fundamental"], self._on_fundamental_signal)
        self.bus.subscribe(CHANNELS["decisions"],           self._on_convergence)
        self.bus.subscribe(CHANNELS["portfolio_update"],    self._on_trade_closed)
        self.bus.subscribe(CHANNELS["heartbeat"],           self._on_heartbeat)
        self.bus.subscribe(CHANNELS["error"],               self._on_error)
        self.bus.subscribe(CHANNELS["regime"],              self._on_regime)
        self.bus.subscribe(CHANNELS["shadow_result"],       self._on_shadow_result)
        self.bus.subscribe(CHANNELS["behavior_alert"],      self._on_behavior)
        self.bus.subscribe("meta:daily_thesis",             self._on_daily_thesis)

    # ── Handlers bus ──────────────────────────────────────────────────────────

    async def _on_technical_signal(self, data: dict) -> None:
        agent = "ScanAgent"
        self._score_activity(agent)
        self._scores[agent].signals_sent += 1

    async def _on_fundamental_signal(self, data: dict) -> None:
        agent = "ResearchAgent"
        self._score_activity(agent)
        self._scores[agent].signals_sent += 1

    async def _on_convergence(self, data: dict) -> None:
        agent = "PredictAgent"
        self._score_activity(agent)
        self._scores[agent].signals_sent += 1
        self._scores["SynthesisAgent"].signals_sent += 1

    async def _on_trade_closed(self, data: dict) -> None:
        """Enregistre l'outcome et met à jour les scores des agents impliqués."""
        if data.get("type") != "trade_closed":
            return

        is_win = data.get("is_win", False)
        self._recent_trades.append({
            "is_win":   is_win,
            "pnl_pct":  data.get("pnl_pct", 0.0),
            "asset":    data.get("asset", "?"),
            "regime":   data.get("regime", "unknown"),
            "ts":       datetime.now(timezone.utc).isoformat(),
        })

        # Post-mortem LLM (tâche async indépendante)
        asyncio.create_task(self._run_postmortem(data))

        # Tous les agents core bénéficient du trade
        for agent_name in ["ScanAgent", "ResearchAgent", "PredictAgent",
                           "RiskAgent", "SynthesisAgent", "RegimeAgent"]:
            if agent_name in self._scores:
                self._scores[agent_name].trades_linked += 1
                if is_win:
                    self._scores[agent_name].signals_win += 1

    async def _on_heartbeat(self, data: dict) -> None:
        agent = data.get("agent", "")
        if agent in self._scores:
            self._scores[agent].alive = True
            self._score_activity(agent)

    async def _on_error(self, data: dict) -> None:
        agent = data.get("agent", "")
        if agent in self._scores:
            self._scores[agent].warnings += 1
            if self._scores[agent].warnings >= 5:
                logger.warning(
                    "[%s] ⚠️ %s a accumulé %d erreurs",
                    self.name, agent, self._scores[agent].warnings,
                )

    async def _on_regime(self, data: dict) -> None:
        asset  = data.get("asset")
        regime = data.get("regime")
        if asset and regime:
            self._regimes[asset] = regime
        self._score_activity("RegimeAgent")

    async def _on_shadow_result(self, data: dict) -> None:
        """Intègre les recommandations du ShadowAgent."""
        if data.get("type") != "shadow_ranking":
            return
        self._best_shadow_strategy  = data.get("best_strategy")
        self._shadow_recommendation = data.get("recommendation", {})
        self._score_activity("ShadowAgent")
        logger.info(
            "[%s] 🔬 Shadow recommande : %s (WR=%.0f%%, return=%+.1f%%)",
            self.name,
            self._best_shadow_strategy,
            data.get("best_win_rate", 0) * 100,
            data.get("best_return_pct", 0),
        )

    async def _on_behavior(self, data: dict) -> None:
        """Observe les alertes comportementales."""
        mode = data.get("discipline_mode", "normal")
        self._score_activity("BehaviorAgent")
        if mode in ("restricted", "paused"):
            logger.info(
                "[%s] 🧠 BehaviorAgent signal : mode=%s | ×%.2f",
                self.name, mode, data.get("risk_multiplier", 1.0),
            )

    async def _on_daily_thesis(self, data: dict) -> None:
        self._daily_thesis = data.get("thesis", "")

    # ── Cycle CEO ─────────────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        # Briefing matinal (une fois par jour, entre 7h et 9h UTC)
        now_hour = datetime.now(timezone.utc).hour
        if 7 <= now_hour <= 9:
            await self._daily_briefing()

        self._cycle_count += 1

        snap = self.tracker.snapshot()

        # ── Réévaluer et potentiellement ajuster les poids ────────────────────
        adjustments = self._evaluate_and_adjust(snap)
        if adjustments:
            await self._publish_meta_directives(adjustments)

        # ── Rapport CEO quotidien ─────────────────────────────────────────────
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_ceo_report:
            await self._send_ceo_report(snap)
            self._last_ceo_report = today

        # ── Rapport hebdomadaire ─────────────────────────────────────────────
        week = datetime.now(timezone.utc).strftime("%Y-%W")
        if week != self._last_weekly_report and datetime.now(timezone.utc).weekday() == 0:
            await self._send_weekly_report(snap)
            self._last_weekly_report = week

        # Log CEO synthèse
        ranking = self._get_agent_ranking()
        if ranking:
            top = ranking[0]
            logger.info(
                "[%s] 📊 CEO | WR=%.0f%% DD=%.1f%% Sharpe=%.2f | "
                "Agent #1: %s (score=%.2f) | Poids: tech=%.1f fund=%.1f conf=%d",
                self.name,
                snap.get("win_rate", 0) * 100,
                snap.get("current_drawdown", 0),
                snap.get("sharpe_ratio", 0),
                top["name"], top.get("composite", top.get("score", 0)),
                self._weights["tech_weight"],
                self._weights["fund_weight"],
                self._weights["min_confidence"],
            )

    # ── Briefing + Post-mortem LLM ────────────────────────────────────────────

    async def _daily_briefing(self) -> None:
        """Briefing matinal par Claude Opus — produit la thèse du jour."""
        if not self._llm:
            return

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._last_briefing_date == today:
            return

        snap = self.tracker.snapshot()

        recent_patterns = ""
        if self._narrative_memory:
            all_p = self._narrative_memory._patterns[-10:]
            recent_patterns = "\n".join(
                f"- [{p.outcome.upper()} ×{p.confirmed_count}] {p.pattern}"
                for p in all_p
            ) or "Aucun pattern enregistré."

        prompt = f"""\
Tu es le stratégiste en chef d'une trading firm. Rédige la thèse de marché du jour \
en 200 mots maximum. Sois précis, actionnable, et honnête sur les incertitudes.

Date : {today}
Assets suivis : BTC/USDT, ETH/USDT, SOL/USDT
Capital actuel : ${snap.get('capital', 0):,.0f}
Win rate récent : {snap.get('win_rate', 0)*100:.1f}%
Drawdown actuel : {snap.get('max_drawdown_pct', 0):.1f}%

Patterns récents mémorisés :
{recent_patterns}

Structure de ta réponse :
1. Contexte macro (1-2 phrases)
2. Setup technique prioritaire du jour (1-2 phrases)
3. Biais directionnel par asset (1 phrase par asset)
4. Risques à surveiller aujourd'hui (1-2 phrases)
5. Règle de conduite du jour (1 phrase)"""

        resp = await self._llm.complete("claude-opus-4-6", prompt, max_tokens=400, timeout=60.0)
        if not resp:
            logger.warning("[MetaAgent] Briefing échoué — LLM indisponible")
            return

        self._daily_thesis       = resp.text
        self._last_briefing_date = today

        await self.bus.publish("meta:daily_thesis", {
            "type":   "daily_thesis",
            "date":   today,
            "thesis": self._daily_thesis,
            "cost":   resp.cost_usd,
        })

        briefing_dir = self.obsidian.vault_path / "briefing"
        briefing_dir.mkdir(exist_ok=True)
        path = briefing_dir / f"{today}_briefing.md"
        path.write_text(
            f"---\ndate: {today}\ntype: daily_briefing\ntags: [briefing, thesis]\n---\n\n"
            f"# Thèse du Jour — {today}\n\n{self._daily_thesis}\n\n"
            f"---\n_Généré par MetaAgent (Claude Opus) | coût: ${resp.cost_usd:.4f}_\n",
            encoding="utf-8",
        )

        logger.info("[MetaAgent] Briefing matinal généré ($%.4f)", resp.cost_usd)
        if self.telegram:
            try:
                await self.telegram.send_message(
                    f"☀️ **Thèse du {today}**\n\n{self._daily_thesis}"
                )
            except Exception:
                pass

    async def _run_postmortem(self, trade_data: dict) -> None:
        """Post-mortem d'un trade clôturé par Claude Opus."""
        if not self._llm or not self._narrative_memory:
            return

        asset     = trade_data.get("asset", "INCONNU")
        pnl_pct   = trade_data.get("pnl_pct", 0.0)
        is_win    = trade_data.get("is_win", False)
        regime    = trade_data.get("regime", "unknown")
        direction = trade_data.get("direction", "UNKNOWN")
        conf      = trade_data.get("confidence", 0)

        prompt = f"""\
Tu es l'analyste post-trade d'une trading firm. Analyse ce trade clôturé \
et extrais l'enseignement le plus important en 5 lignes.

Asset: {asset}
Direction: {direction}
Confiance au signal: {conf}/100
Régime au moment du trade: {regime}
Résultat: {'GAIN' if is_win else 'PERTE'} ({pnl_pct:+.2f}%)
Thèse du jour au moment du trade: {self._daily_thesis[:300] if self._daily_thesis else 'Non disponible'}

Réponds dans ce format exact :
ATTENDU: [ce qu'on pensait qu'il allait se passer]
REEL: [ce qui s'est passé]
RATE: [ce qu'on a raté ou ignoré]
PATTERN: [1 phrase mémorisable sur ce setup dans ce régime]
REGLE: [règle concrète pour le prochain trade similaire]"""

        resp = await self._llm.complete("claude-opus-4-6", prompt, max_tokens=300, timeout=45.0)
        if not resp:
            return

        pattern_line = ""
        for line in resp.text.splitlines():
            if line.startswith("PATTERN:"):
                pattern_line = line.replace("PATTERN:", "").strip()
                break
        if not pattern_line:
            pattern_line = resp.text[:150]

        setup = f"{direction.lower()}_signal"
        self._narrative_memory.add_pattern(
            asset=asset, regime=regime, setup=setup,
            outcome="win" if is_win else "loss",
            pattern_text=pattern_line,
        )

        now = datetime.now(timezone.utc)
        pm_dir = self.obsidian.vault_path / "postmortems"
        pm_dir.mkdir(exist_ok=True)
        filename = f"{now.strftime('%Y-%m-%d_%H-%M')}_{asset.replace('/', '-')}.md"
        (pm_dir / filename).write_text(
            f"---\nasset: {asset}\noutcome: {'win' if is_win else 'loss'}\n"
            f"pnl_pct: {pnl_pct:.2f}\ndate: {now.isoformat()}\ntags: [postmortem]\n---\n\n"
            f"# Post-Mortem — {asset} {'✅' if is_win else '❌'} ({pnl_pct:+.2f}%)\n\n"
            f"{resp.text}\n\n---\n_Généré par MetaAgent (Claude Opus) | ${resp.cost_usd:.4f}_\n",
            encoding="utf-8",
        )
        logger.info("[MetaAgent] Post-mortem %s (%s) généré", asset, "WIN" if is_win else "LOSS")

    # ── Évaluation et ajustements ─────────────────────────────────────────────

    def _evaluate_and_adjust(self, snap: dict) -> dict:
        """
        Analyse les performances et décide des ajustements.
        Retourne un dict d'actions à publier sur meta:directive.
        """
        actions     = {}
        win_rate    = snap.get("win_rate", 0.5)
        drawdown    = snap.get("current_drawdown", 0.0)
        sharpe      = snap.get("sharpe_ratio", 0.0)
        total_trades= snap.get("total_trades", 0)

        if total_trades < 5:
            return {}  # Pas assez de données

        # ── Ajustement du seuil de confiance ─────────────────────────────────
        # Si WR < 45% → augmenter min_confidence (être plus sélectif)
        # Si WR > 65% → diminuer légèrement min_confidence (plus d'opportunités)
        old_conf = self._weights["min_confidence"]
        if win_rate < 0.45 and old_conf < 75:
            new_conf = min(old_conf + 3, 75)
            self._weights["min_confidence"] = new_conf
            action = {"type": "confidence_update", "min_confidence": new_conf}
            actions["confidence"] = action
            self._log_adjustment(
                f"↑ Confiance min : {old_conf} → {new_conf} (WR={win_rate:.0%} < 45%)"
            )
        elif win_rate > 0.65 and old_conf > 45:
            new_conf = max(old_conf - 2, 45)
            self._weights["min_confidence"] = new_conf
            actions["confidence"] = {"type": "confidence_update", "min_confidence": new_conf}
            self._log_adjustment(
                f"↓ Confiance min : {old_conf} → {new_conf} (WR={win_rate:.0%} > 65%)"
            )

        # ── Ajustement des poids tech/fund ────────────────────────────────────
        # Comparer la précision des signaux techniques vs fondamentaux
        tech_score = self._scores.get("ScanAgent")
        fund_score = self._scores.get("ResearchAgent")
        if tech_score and fund_score and tech_score.signals_sent > 5 and fund_score.signals_sent > 5:
            tech_precision = tech_score.precision
            fund_precision = fund_score.precision
            diff = tech_precision - fund_precision

            if diff > 0.15 and self._weights["tech_weight"] < 1.5:
                self._weights["tech_weight"] = round(
                    min(self._weights["tech_weight"] + 0.1, 1.5), 2
                )
                actions["weights"] = {
                    "type":        "weight_update",
                    "tech_weight": self._weights["tech_weight"],
                    "fund_weight": self._weights["fund_weight"],
                }
                self._log_adjustment(f"↑ Poids technique : {self._weights['tech_weight']:.1f}")
            elif diff < -0.15 and self._weights["fund_weight"] < 1.5:
                self._weights["fund_weight"] = round(
                    min(self._weights["fund_weight"] + 0.1, 1.5), 2
                )
                actions["weights"] = {
                    "type":        "weight_update",
                    "tech_weight": self._weights["tech_weight"],
                    "fund_weight": self._weights["fund_weight"],
                }
                self._log_adjustment(f"↑ Poids fondamental : {self._weights['fund_weight']:.1f}")

        # ── Intégrer la recommandation Shadow ─────────────────────────────────
        if self._shadow_recommendation and total_trades >= 20:
            rec = self._shadow_recommendation
            rec_conf = rec.get("suggested_min_confidence")
            if rec_conf and abs(rec_conf - self._weights["min_confidence"]) > 5:
                old = self._weights["min_confidence"]
                # Convergence progressive vers la recommandation shadow
                self._weights["min_confidence"] = int(
                    self._weights["min_confidence"] * 0.8 + rec_conf * 0.2
                )
                actions["shadow_adapt"] = {
                    "type":           "confidence_update",
                    "min_confidence": self._weights["min_confidence"],
                    "source":         "ShadowAgent",
                }
                self._log_adjustment(
                    f"🔬 Shadow adapt: confiance {old} → {self._weights['min_confidence']}"
                )
            self._shadow_recommendation = None  # Consommé

        # ── Ajustement du risque global selon drawdown et Sharpe ─────────────
        if drawdown > 12.0 and self._weights["risk_multiplier"] > 0.3:
            new_factor = round(max(self._weights["risk_multiplier"] - 0.15, 0.3), 2)
            self._weights["risk_multiplier"] = new_factor
            actions["risk_reduction"] = {
                "type": "confidence_update",
                "risk_factor": new_factor,
            }
            self._log_adjustment(
                f"↓ Risque global : ×{new_factor} (DD={drawdown:.1f}% > 12%)"
            )
        elif sharpe > 1.5 and drawdown < 5.0 and self._weights["risk_multiplier"] < 1.0:
            new_factor = round(min(self._weights["risk_multiplier"] + 0.1, 1.0), 2)
            self._weights["risk_multiplier"] = new_factor
            actions["risk_increase"] = {
                "type": "confidence_update",
                "risk_factor": new_factor,
            }
            self._log_adjustment(
                f"↑ Risque global : ×{new_factor} (Sharpe={sharpe:.2f}, DD={drawdown:.1f}%)"
            )

        # ── Auto-désactivation d'assets perdants ─────────────────────────────
        if total_trades >= 15:
            asset_losses = {}
            for t in self._recent_trades:
                a = t.get("asset", "?")
                asset_losses.setdefault(a, {"w": 0, "l": 0})
                if t.get("is_win"):
                    asset_losses[a]["w"] += 1
                else:
                    asset_losses[a]["l"] += 1
            for a, wl in asset_losses.items():
                total = wl["w"] + wl["l"]
                if total >= 5 and wl["w"] / max(total, 1) < 0.25:
                    actions[f"warn_asset_{a}"] = {
                        "type":    "asset_warning",
                        "asset":   a,
                        "win_rate": wl["w"] / total,
                        "reason":  f"WR={wl['w']}/{total} < 25%",
                    }
                    self._log_adjustment(f"⚠️ Asset {a} sous-performe : WR={wl['w']}/{total}")

        # ── Avertissements agents sous-performants ────────────────────────────
        for name, score in self._scores.items():
            if score.warnings >= 10 and name not in self._disabled_agents:
                self._disabled_agents.add(name)
                actions[f"disable_{name}"] = {
                    "type":    "agent_disable",
                    "agent":   name,
                    "reason":  f"{score.warnings} erreurs accumulées",
                }
                self._log_adjustment(f"⚠️ {name} désactivé ({score.warnings} erreurs)")
                logger.warning("[%s] Agent %s désactivé — trop d'erreurs", self.name, name)

        return actions

    async def _publish_meta_directives(self, actions: dict) -> None:
        """Publie les directives CEO sur meta:directive."""
        for key, action in actions.items():
            if not action:
                continue
            await self.bus.publish(CHANNELS["meta_directive"], {
                **action,
                "from": "MetaAgent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            logger.info("[%s] 📣 Directive : %s", self.name, action)

    # ── Rapports CEO ──────────────────────────────────────────────────────────

    async def _send_ceo_report(self, snap: dict) -> None:
        """Génère et envoie le rapport CEO quotidien."""
        ranking  = self._get_agent_ranking()
        regimes  = self._get_regime_summary()
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # ── Vault ──────────────────────────────────────────────────────────────
        self._write_ceo_report_note(snap, ranking, regimes, date_str)

        # ── Telegram ──────────────────────────────────────────────────────────
        if self.telegram:
            try:
                await self.telegram.ceo_report(
                    date          = date_str,
                    capital       = snap.get("capital", 0),
                    pnl_pct       = snap.get("total_return_pct", 0),
                    win_rate      = snap.get("win_rate", 0),
                    sharpe        = snap.get("sharpe_ratio", 0),
                    drawdown      = snap.get("current_drawdown", 0),
                    total_trades  = snap.get("total_trades", 0),
                    ranking       = ranking[:5],
                    regimes       = regimes,
                    weights       = self._weights,
                    adjustments   = list(self._adjustments)[-5:],
                    risk_status   = self._get_risk_status(snap),
                )
            except Exception as exc:
                logger.warning("[%s] Erreur Telegram CEO report: %s", self.name, exc)

    async def _send_weekly_report(self, snap: dict) -> None:
        """Génère et envoie le rapport hebdomadaire."""
        week      = datetime.now(timezone.utc).strftime("Semaine %W — %Y")
        date_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Stats hebdomadaires depuis les trades récents
        recent_week = [
            t for t in self._recent_trades
            if self._is_this_week(t.get("ts", ""))
        ]
        week_wins   = sum(1 for t in recent_week if t.get("is_win"))
        week_pnl    = sum(t.get("pnl_pct", 0) for t in recent_week)
        week_wr     = week_wins / max(len(recent_week), 1)

        # ── Vault ──────────────────────────────────────────────────────────────
        frontmatter = {
            "date":         date_str,
            "agent":        "MetaAgent",
            "type":         "weekly_report",
            "week":         week,
            "trades":       len(recent_week),
            "win_rate":     round(week_wr, 3),
            "pnl_pct":      round(week_pnl, 2),
            "sharpe":       round(snap.get("sharpe_ratio", 0), 2),
            "tags":         ["rapport", "hebdomadaire", "CEO"],
        }

        shadow_section = ""
        if self._best_shadow_strategy:
            shadow_section = f"""
### 🔬 Shadow R&D
Meilleure stratégie shadow : **{self._best_shadow_strategy}**
"""

        content = f"""## 📊 Rapport Hebdomadaire CEO — {week}

### Performance
| Indicateur | Semaine | Session |
|---|---|---|
| Trades | `{len(recent_week)}` | `{snap.get('total_trades', 0)}` |
| Win Rate | `{week_wr:.0%}` | `{snap.get('win_rate', 0):.0%}` |
| P&L | `{week_pnl:+.2f}%` | `{snap.get('total_return_pct', 0):+.2f}%` |
| Sharpe | `—` | `{snap.get('sharpe_ratio', 0):.2f}` |
| Max DD | `—` | `{snap.get('max_drawdown_pct', 0):.2f}%` |
| Capital | `—` | `${snap.get('capital', 0):,.2f}` |

### Poids du Pipeline
| Paramètre | Valeur |
|---|---|
| Poids technique | `×{self._weights['tech_weight']:.2f}` |
| Poids fondamental | `×{self._weights['fund_weight']:.2f}` |
| Confiance minimale | `{self._weights['min_confidence']}/100` |
{shadow_section}
### Derniers Ajustements CEO
{chr(10).join(f'- {a}' for a in list(self._adjustments)[-5:]) or '- Aucun ajustement cette semaine'}

### Liens
[[agents/MetaAgent]] | [[reports/index]]
"""
        self.obsidian.write_note("reports", f"weekly_{date_str}", frontmatter, content)

        # ── Telegram ──────────────────────────────────────────────────────────
        if self.telegram:
            try:
                await self.telegram.weekly_report(
                    week         = week,
                    trades       = len(recent_week),
                    win_rate     = week_wr,
                    pnl_pct      = week_pnl,
                    total_pnl_pct= snap.get("total_return_pct", 0),
                    sharpe       = snap.get("sharpe_ratio", 0),
                    drawdown     = snap.get("max_drawdown_pct", 0),
                    capital      = snap.get("capital", 0),
                    best_shadow  = self._best_shadow_strategy,
                    adjustments  = list(self._adjustments)[-3:],
                )
            except Exception as exc:
                logger.warning("[%s] Erreur Telegram weekly report: %s", self.name, exc)

    def _write_ceo_report_note(
        self,
        snap: dict,
        ranking: list[dict],
        regimes: dict[str, str],
        date_str: str,
    ) -> None:
        """Écrit le rapport CEO dans vault/reports/."""
        ranking_md = "\n".join(
            f"| {i+1} | {r['name']} | `{r['precision']:.0%}` | "
            f"`{r.get('trades_linked', r.get('trades', 0))}` | "
            f"`{r.get('composite', r.get('score', 0)):.2f}` | "
            f"{'🟢' if r.get('alive') else '🔴'} |"
            for i, r in enumerate(ranking[:10])
        )

        regime_md = "\n".join(
            f"| `{asset}` | `{regime.upper()}` |"
            for asset, regime in regimes.items()
        ) or "| — | — |"

        adj_md = "\n".join(
            f"- {a}" for a in list(self._adjustments)[-5:]
        ) or "- Aucun ajustement"

        frontmatter = {
            "date":          date_str,
            "agent":         "MetaAgent",
            "type":          "ceo_daily_report",
            "win_rate":      round(snap.get("win_rate", 0), 3),
            "sharpe":        round(snap.get("sharpe_ratio", 0), 2),
            "drawdown":      round(snap.get("current_drawdown", 0), 2),
            "capital":       snap.get("capital", 0),
            "tags":          ["rapport", "CEO", "quotidien"],
        }

        content = f"""## 🏢 Rapport CEO — {date_str}

### Vue d'Ensemble
| Indicateur | Valeur | Statut |
|---|---|---|
| Capital | `${snap.get('capital', 0):,.2f}` | {'✅' if snap.get('total_return_pct',0) > 0 else '⚠️'} |
| Return | `{snap.get('total_return_pct', 0):+.2f}%` | — |
| Win Rate | `{snap.get('win_rate', 0):.0%}` | {'✅' if snap.get('win_rate',0) > 0.5 else '⚠️'} |
| Sharpe | `{snap.get('sharpe_ratio', 0):.2f}` | {'✅' if snap.get('sharpe_ratio',0) > 1 else '⚠️'} |
| Drawdown courant | `{snap.get('current_drawdown', 0):.2f}%` | {'✅' if snap.get('current_drawdown',0) < 5 else '⚠️'} |
| Trades total | `{snap.get('total_trades', 0)}` | — |

### Régimes de Marché
| Asset | Régime |
|---|---|
{regime_md}

### Classement des Agents
| # | Agent | Précision | Trades | Score | Statut |
|---|---|---|---|---|---|
{ranking_md}

### Poids du Pipeline
| Paramètre | Valeur |
|---|---|
| Poids technique | `×{self._weights['tech_weight']:.2f}` |
| Poids fondamental | `×{self._weights['fund_weight']:.2f}` |
| Confiance minimale | `{self._weights['min_confidence']}/100` |

### Ajustements du Jour
{adj_md}

### Risk Status : {self._get_risk_status(snap)}

### Liens
[[agents/MetaAgent]] | [[reports/index]]
{' | '.join(f'[[agents/{n}]]' for n in self.TRACKED_AGENTS[:6])}
"""
        self.obsidian.write_note("reports", f"ceo_{date_str}", frontmatter, content)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _score_activity(self, agent_name: str) -> None:
        if agent_name in self._scores:
            self._scores[agent_name].last_activity = datetime.now(timezone.utc).isoformat()
            self._scores[agent_name].alive = True

    def _get_agent_ranking(self) -> list[dict]:
        """Retourne les agents triés par score composite décroissant."""
        return sorted(
            [s.to_dict() for s in self._scores.values()],
            key=lambda x: x.get("composite", x.get("score", 0)),
            reverse=True,
        )

    def _get_regime_summary(self) -> dict[str, str]:
        return dict(self._regimes)

    def _get_risk_status(self, snap: dict) -> str:
        dd = snap.get("current_drawdown", 0)
        wr = snap.get("win_rate", 0.5)
        if dd > 10 or wr < 0.35:
            return "🔴 ELEVATED RISK"
        if dd > 5 or wr < 0.45:
            return "⚠️ CAUTION"
        return "✅ NORMAL"

    def _log_adjustment(self, message: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M")
        self._adjustments.append(f"[{ts}] {message}")
        logger.info("[%s] ⚙️  Ajustement CEO : %s", self.name, message)

    def _is_this_week(self, ts_str: str) -> bool:
        """Vérifie si un timestamp ISO est dans la semaine courante."""
        try:
            ts   = datetime.fromisoformat(ts_str)
            now  = datetime.now(timezone.utc)
            diff = now - ts.replace(tzinfo=timezone.utc)
            return diff.days < 7
        except Exception:
            return False

    # ── API publique ──────────────────────────────────────────────────────────

    @property
    def weights(self) -> dict:
        return dict(self._weights)

    @property
    def agent_ranking(self) -> list[dict]:
        return self._get_agent_ranking()

    def get_score(self, agent_name: str) -> float:
        sc = self._scores.get(agent_name)
        return sc.composite_score() if sc else 0.0
