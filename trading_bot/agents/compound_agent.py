"""
Agent 6 — Gestionnaire de Croissance (Compound)
Gère le réinvestissement des profits, le scaling des positions gagnantes,
et la stratégie de capitalisation à long terme.
Vault : vault/compound/
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np

from core.base_agent import BaseAgent
from core.learning_engine import LearningEngine
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient
from core.performance_tracker import PerformanceTracker
from models.learning import AgentMemory

logger = logging.getLogger(__name__)


class CompoundAgent(BaseAgent):
    """
    Agent de capitalisation — le 6ème maillon du pipeline.

    Stratégie de compounding :
    1. Si win rate > 55% sur 20 derniers trades → augmenter risk_per_trade de 0.1%
    2. Si Sharpe > 1.5 et drawdown < 5% → activer le scaling (pyramiding sur positions gagnantes)
    3. Si drawdown > 10% → réduire la taille et passer en mode "capital preservation"
    4. Reinvestissement automatique des profits : nouveau capital = capital × (1 + return)

    Apprend : le timing optimal de reinvestissement selon le régime de marché.
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        learning: LearningEngine,
        tracker: PerformanceTracker,
        config: dict,
        telegram=None,
    ):
        super().__init__("CompoundAgent", "compound", bus, obsidian, config)
        self.learning = learning
        self.tracker  = tracker
        self.telegram = telegram
        self.memory: AgentMemory = None

        self.base_risk_pct    = config.get("risk_per_trade_pct", 2.0)
        self.current_risk_pct = self.base_risk_pct
        self.compound_enabled = config.get("compound_enabled", True)

        # DataSheet buffer — contexte marché global pour décisions de compounding
        self._market_ctx: dict[str, dict] = {}

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        (self.obsidian.vault_path / "compound").mkdir(exist_ok=True)
        self.memory = self.learning.load_memory("CompoundAgent")

        # ── Restaurer l'état depuis la mémoire persistée ──────────────────────
        # Évite de recommencer à 0 à chaque redémarrage du bot
        saved_risk = self.memory.adaptive_params.get("current_risk_pct")
        if saved_risk and 0.5 <= saved_risk <= self.base_risk_pct * 3:
            self.current_risk_pct = round(float(saved_risk), 2)
            logger.info(
                "[%s] Risque restauré depuis mémoire : %.2f%%",
                self.name, self.current_risk_pct,
            )

        # Mettre à jour le fichier vault/config/CompoundAgent_memory.md
        # (lu par SynthesisAgent pour construire son MemoryContext)
        self._persist_mode_to_vault("startup")

        logger.info(
            "[%s] Compounding actif : risque de base %.1f%% | risque courant %.2f%%",
            self.name, self.base_risk_pct, self.current_risk_pct,
        )

    def _register_subscriptions(self) -> None:
        """S'abonne aux trade_closed pour évaluer le compounding en temps réel."""
        self.bus.subscribe(CHANNELS["portfolio_update"], self._on_trade_closed)
        self.bus.subscribe(CHANNELS["market_context"],   self._on_market_context)
        self.bus.subscribe(CHANNELS["meta_directive"],   self._on_meta_directive)

    async def _on_market_context(self, data: dict) -> None:
        """Reçoit les DataSheets du SynthesisAgent — stocke le dernier contexte par asset."""
        asset = data.get("asset")
        if asset:
            self._market_ctx[asset] = data

    async def _on_meta_directive(self, data: dict) -> None:
        """Reçoit les directives du MetaAgent (CEO) — peut forcer un reset de risque."""
        dtype = data.get("type")
        if dtype == "confidence_update":
            # Le CEO peut demander une réduction conservatrice du risque composé
            risk_factor = data.get("risk_factor")
            if isinstance(risk_factor, (int, float)) and 0.1 <= risk_factor <= 1.0:
                new_risk = round(self.current_risk_pct * risk_factor, 2)
                new_risk = max(new_risk, self.base_risk_pct * 0.5)
                if new_risk != self.current_risk_pct:
                    logger.info(
                        "[%s] 📋 CEO directive → risk composé %.2f%% → %.2f%%",
                        self.name, self.current_risk_pct, new_risk,
                    )
                    self.current_risk_pct = new_risk
        elif dtype == "agent_disable":
            # Reset du risque au niveau de base si un agent clé est désactivé
            if data.get("agent") in ("PredictAgent", "RiskAgent"):
                logger.warning(
                    "[%s] 📋 CEO désactive %s → reset risque à %.2f%%",
                    self.name, data.get("agent"), self.base_risk_pct,
                )
                self.current_risk_pct = self.base_risk_pct

    # ── Handler temps réel (déclenché par chaque trade clôturé) ──────────────

    async def _on_trade_closed(self, data: dict) -> None:
        """Reçoit chaque trade_closed de RiskAgent et ajuste le risque si nécessaire."""
        if data.get("type") != "trade_closed":
            return

        # ── Mise à jour du streak mémorisé ────────────────────────────────────
        is_win = data.get("is_win", False)
        if is_win:
            self.memory.current_streak = max(0, self.memory.current_streak) + 1
        else:
            self.memory.current_streak = min(0, self.memory.current_streak) - 1

        snap = self.tracker.snapshot()
        n = snap["total_trades"]
        if n < 3:
            logger.debug("[%s] En attente (%d/3 trades min)", self.name, n)
            return
        action = self._evaluate_compounding(snap)
        if action:
            logger.info(
                "[%s] %s %s après trade #%d — nouveau risque : %.2f%% | streak:%+d",
                self.name, action["icon"], action["mode"], n,
                action["new_risk"], self.memory.current_streak,
            )
            await self._broadcast_risk_update(action)

            # Notification Telegram du changement de mode
            if self.telegram:
                await self.telegram.compound_mode_change(
                    mode=action["mode"],
                    new_risk=action["new_risk"],
                    reason=action["reason"],
                    icon=action["icon"],
                )

    # ── Cycle principal (fallback toutes les 60s) ─────────────────────────────

    async def run_cycle(self) -> None:
        snap = self.tracker.snapshot()
        if snap["total_trades"] < 3:
            return
        action = self._evaluate_compounding(snap)
        if action:
            await self._broadcast_risk_update(action)

    # ── Logique de compounding ────────────────────────────────────────────────

    def _evaluate_compounding(self, snap: dict) -> dict | None:
        """
        Évalue si et comment ajuster le risque par trade.

        La mémoire (self.memory) est consultée AVANT de décider :
        - streak négatif → seuils plus stricts pour le scaling
        - recovery_rate mémorisé → indique si les remontées après préservation fonctionnent
        - last_mode → évite les allers-retours trop rapides entre modes

        Retourne un dict d'action ou None si rien à faire.
        """
        wr     = snap["win_rate"]
        sharpe = snap["sharpe_ratio"]
        dd     = snap["current_drawdown"]
        ret    = snap["total_return_pct"]
        trades = snap["total_trades"]

        # ── Lecture de la mémoire pour ajuster les seuils ─────────────────────
        streak      = self.memory.current_streak         # >0 wins, <0 losses
        last_mode   = self.memory.adaptive_params.get("last_mode", "normal")
        recovery_rate = float(self.memory.adaptive_params.get("recovery_rate", 0.5))

        # Seuils de WR ajustés par la série courante
        # Si on est sur une série négative (streak < -3), on exige plus pour scaler
        streak_penalty = max(0, -streak - 3) * 0.02   # +2% WR requis par lose > 3
        wr_scale_threshold = 0.60 + streak_penalty
        wr_compound_threshold = 0.55 + streak_penalty * 0.5

        # ── Ajustement DataSheet : VIX élevé ou biais extrême → bloquer le scaling ──
        ctx_block_scaling = False
        for asset, ctx in self._market_ctx.items():
            vix_data = ctx.get("vix", {})
            if isinstance(vix_data, dict):
                rv = vix_data.get("realized_vol", 0)
                if isinstance(rv, (int, float)) and rv > 80:
                    ctx_block_scaling = True
                    logger.info(
                        "[%s] 📋 VIX élevé (%.0f) sur %s — scaling bloqué",
                        self.name, rv, asset,
                    )
                    break
            bias = ctx.get("bias", {})
            if isinstance(bias, dict):
                long_pct = bias.get("long_pct", 0.5)
                if isinstance(long_pct, (int, float)) and (long_pct > 0.80 or long_pct < 0.20):
                    ctx_block_scaling = True
                    logger.info(
                        "[%s] 📋 Biais extrême (%.0f%% long) sur %s — scaling bloqué",
                        self.name, long_pct * 100, asset,
                    )
                    break

        # ── Mode Capital Preservation ──────────────────────────────
        if dd > 10.0:
            new_risk = max(self.current_risk_pct * 0.6, 0.5)
            if new_risk != self.current_risk_pct:
                self.current_risk_pct = round(new_risk, 2)
                self._update_memory_mode("capital_preservation", new_risk, snap)
                return {
                    "mode":     "capital_preservation",
                    "action":   "réduction_risque",
                    "new_risk": self.current_risk_pct,
                    "reason":   f"Drawdown {dd:.1f}% > 10% — protection du capital",
                    "icon":     "🛡️",
                }

        # ── Sortie du mode preservation si conditions favorables ──────────────
        # Ne pas rester en preservation si on a récupéré (évite d'être trop conservateur)
        if last_mode == "capital_preservation" and dd < 5.0 and wr > 0.50 and trades >= 5:
            recovery_bonus = recovery_rate * 0.5   # si la mémoire dit que les récup marchent bien
            if wr > 0.50 + recovery_bonus:
                self.current_risk_pct = round(self.base_risk_pct, 2)
                self._update_memory_mode("recovery", self.current_risk_pct, snap)
                return {
                    "mode":     "recovery",
                    "action":   "retour_base_après_préservation",
                    "new_risk": self.current_risk_pct,
                    "reason":   f"Récupération confirmée — WR {wr:.0%} > seuil | DD {dd:.1f}%",
                    "icon":     "🟢",
                }

        # ── Mode Scaling agressif (bloqué si contexte défavorable) ──
        if sharpe > 1.5 and wr > wr_scale_threshold and dd < 5.0 and trades >= 20 and not ctx_block_scaling:
            new_risk = min(self.current_risk_pct + 0.25, self.base_risk_pct * 2.0)
            if new_risk > self.current_risk_pct + 0.1:
                self.current_risk_pct = round(new_risk, 2)
                self._update_memory_mode("aggressive_scaling", new_risk, snap)
                return {
                    "mode":     "aggressive_scaling",
                    "action":   "augmentation_risque",
                    "new_risk": self.current_risk_pct,
                    "reason":   (
                        f"Sharpe {sharpe:.2f} > 1.5 & WR {wr:.0%} > {wr_scale_threshold:.0%} "
                        f"(streak={streak:+d}) — scaling activé"
                    ),
                    "icon":     "🚀",
                }

        # ── Compounding progressif (bloqué si contexte défavorable) ──
        if wr > wr_compound_threshold and dd < 8.0 and trades >= 15 and not ctx_block_scaling:
            new_risk = min(self.current_risk_pct + 0.10, self.base_risk_pct * 1.5)
            if new_risk > self.current_risk_pct + 0.05:
                self.current_risk_pct = round(new_risk, 2)
                self._update_memory_mode("progressive_compound", new_risk, snap)
                return {
                    "mode":     "progressive_compound",
                    "action":   "augmentation_légère",
                    "new_risk": self.current_risk_pct,
                    "reason":   f"WR {wr:.0%} > {wr_compound_threshold:.0%} stable — compounding progressif",
                    "icon":     "📈",
                }

        # ── Recalibrage vers la base ────────────────────────────────
        if wr < 0.45 and trades >= 20:
            if self.current_risk_pct > self.base_risk_pct:
                self.current_risk_pct = round(self.base_risk_pct, 2)
                self._update_memory_mode("recalibration", self.current_risk_pct, snap)
                return {
                    "mode":     "recalibration",
                    "action":   "retour_base",
                    "new_risk": self.current_risk_pct,
                    "reason":   f"WR {wr:.0%} < 45% — retour au risque de base",
                    "icon":     "🔄",
                }

        return None

    def _update_memory_mode(self, mode: str, risk_pct: float, snap: dict) -> None:
        """
        Met à jour la mémoire après chaque décision de compounding.
        Sauvegarde : mode actuel, risk_pct, recovery_rate, streak.
        Persiste aussi dans vault/config/ pour que SynthesisAgent puisse le lire.
        """
        # Mise à jour du streak (mémorisé dans adaptive_params)
        wr = snap.get("win_rate", 0.5)
        # Calculer le recovery_rate (wr après sortie de preservation)
        if mode == "recovery":
            past_recovery = float(self.memory.adaptive_params.get("recovery_rate", 0.5))
            new_recovery  = past_recovery * 0.8 + wr * 0.2   # EMA
            self.memory.adaptive_params["recovery_rate"] = round(new_recovery, 3)

        # Sauvegarder le mode et le risque courant
        self.memory.adaptive_params["last_mode"]        = mode
        self.memory.adaptive_params["current_risk_pct"] = risk_pct
        self.memory.adaptive_params["last_dd"]          = round(snap.get("current_drawdown", 0), 2)
        self.memory.last_updated = datetime.now(timezone.utc).isoformat()

        # Sauvegarder la mémoire dans le vault
        self.learning.save_memory(self.memory)

        # Persister aussi un fichier de config dédié pour SynthesisAgent
        self._persist_mode_to_vault(mode)

    def _persist_mode_to_vault(self, mode: str) -> None:
        """
        Écrit vault/config/CompoundAgent_memory.md avec le mode actuel.
        Utilisé par SynthesisAgent._load_active_memory() pour construire le MemoryContext.
        """
        frontmatter = {
            "agent":           "CompoundAgent",
            "type":            "memory_config",
            "current_mode":    mode,
            "current_risk_pct": self.current_risk_pct,
            "base_risk_pct":   self.base_risk_pct,
            "last_updated":    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "tags":            ["config", "compound", "memory"],
        }
        content = f"""## CompoundAgent — État Courant

| Paramètre | Valeur |
|---|---|
| Mode actuel | `{mode.upper()}` |
| Risque/trade | `{self.current_risk_pct:.2f}%` |
| Risque de base | `{self.base_risk_pct:.2f}%` |
| Streak actuel | `{self.memory.current_streak:+d}` |
| Win rate total | `{self.memory.win_rate:.1%}` |
"""
        self.obsidian.write_note("config", "CompoundAgent_state", frontmatter, content)

    async def _broadcast_risk_update(self, action: dict) -> None:
        """Publie la nouvelle config de risque vers RiskAgent via portfolio_update."""
        await self.bus.publish(CHANNELS["portfolio_update"], {
            "type":         "risk_config",
            "agent":        self.name,
            "new_risk_pct": action["new_risk"],
            "mode":         action["mode"],
            "reason":       action["reason"],
        })
        logger.info(
            "[%s] %s Mode %s → risque/trade : %.2f%% (%s)",
            self.name, action["icon"], action["mode"],
            action["new_risk"], action["reason"],
        )

    # ── Métriques de compounding ──────────────────────────────────────────────

    def _cagr(self, snap: dict) -> float:
        """Taux de croissance annuel composé (approximation)."""
        if snap["total_trades"] == 0:
            return 0.0
        years = max(snap["total_trades"] / 200, 1/12)  # ~200 trades/an
        return ((self.tracker.capital / self.tracker.initial_capital) ** (1 / years) - 1) * 100

    def _kelly_fraction(self, snap: dict) -> float:
        """Fraction de Kelly pour sizing optimal : f* = (bp - q) / b"""
        wr  = snap["win_rate"]
        pf  = snap["profit_factor"]
        if pf <= 0 or wr <= 0:
            return 0.01
        b   = pf     # ratio gain/perte moyen
        p   = wr
        q   = 1 - wr
        kelly = (b * p - q) / b
        return max(0.01, min(kelly * 0.25, 0.05))  # demi-Kelly plafonné à 5%

    # ── Vault Obsidian ────────────────────────────────────────────────────────
    # _write_compound_note() supprimé — vault/compound/*.md n'était jamais relu par aucun agent.
    # L'état actif du CompoundAgent est persisté dans vault/config/CompoundAgent_state.md
    # via _persist_mode_to_vault(), qui est lu par SynthesisAgent._load_active_memory().
