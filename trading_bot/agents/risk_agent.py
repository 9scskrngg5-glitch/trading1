"""
Agent 4 — Gestionnaire de Risque (Risk)
Reçoit les prédictions de PredictAgent, valide et size les ordres.
Intègre le LearningEngine pour l'analyse contrefactuelle des trades échoués.
Vault : vault/risque/ — journal de risque quotidien + métriques financières.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.base_agent import BaseAgent
from core.council import Council, CouncilVerdict
from core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from core.dynamic_sizer import DynamicSizer
from core.learning_engine import LearningEngine
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient
from core.performance_tracker import PerformanceTracker
from models.learning import AgentMemory, TradeOutcome, ExitReason
from models.orders import ValidatedOrder, ExecutionReport, OrderSide, OrderStatus
from models.signals import SignalType

logger = logging.getLogger(__name__)

MAX_POSITIONS = 5
CONF_FLOOR    = 55      # Seuil minimum de confiance (optimise par backtest 90j)


class RiskAgent(BaseAgent):
    """
    Gestionnaire de risque avec apprentissage contrefactuel.

    Innovation ML :
    - À chaque trade perdant : LearningEngine calcule "qu'est-ce qui aurait marché ?"
    - Les SL/TP multipliers sont adaptés automatiquement
    - Drawdown surveillé en continu avec alerte progressive (80% du max)
    - Métriques Sharpe/Sortino calculées et écrites dans le vault
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        learning: LearningEngine,
        tracker: PerformanceTracker,
        telegram=None,
        config: dict = None,
        council: "Council | None" = None,
        daily_thesis_ref: "list | None" = None,
    ):
        super().__init__("RiskAgent", "risque", bus, obsidian, config or {})
        self.learning = learning
        self.tracker  = tracker
        self.telegram = telegram
        self.memory: AgentMemory = None

        self.capital_usd        = (config or {}).get("capital_usd", 10_000)
        self.risk_per_trade_pct = (config or {}).get("risk_per_trade_pct", 2.0)
        self.max_drawdown_pct   = (config or {}).get("max_drawdown_pct", 15.0)

        # Circuit Breaker — protection automatique du capital
        cb_config = CircuitBreakerConfig(
            max_consecutive_losses=(config or {}).get("cb_max_losses", 5),
            half_open_losses=(config or {}).get("cb_half_losses", 3),
            max_drawdown_pct=self.max_drawdown_pct,
            warning_drawdown_pct=self.max_drawdown_pct * 0.65,
            max_daily_drawdown_pct=(config or {}).get("cb_daily_dd", 5.0),
            max_daily_loss_usd=(config or {}).get("cb_daily_loss", 500.0),
            cooldown_minutes=(config or {}).get("cb_cooldown_min", 30),
        )
        self.circuit_breaker = CircuitBreaker(config=cb_config, telegram=telegram)

        # Dynamic Sizer — Kelly Criterion adaptatif
        self.sizer = DynamicSizer(
            method=(config or {}).get("sizing_method", "adaptive"),
            base_risk_pct=self.risk_per_trade_pct,
            min_risk_pct=0.5,
            max_risk_pct=(config or {}).get("max_risk_pct", 5.0),
        )

        self._open_positions: dict[str, dict]          = {}
        self._open_trade_data: dict[str, dict]         = {}
        self._execution_log:  list[dict]               = []

        # DataSheet buffer : contexte de marché SynthesisAgent
        self._market_ctx: dict[str, dict] = {}
        # Health status : agents morts détectés par SupervisorAgent
        self._agents_alive_ratio: float = 1.0
        # BehaviorAgent : multiplicateur de risque comportemental (0.0–1.0)
        self._behavior_multiplier: float = 1.0

        # ── LLM Council ───────────────────────────────────────────────────────
        self._council = council
        self._daily_thesis_ref: list = daily_thesis_ref or []

        # Persistance des trades ouverts pour survivre aux redémarrages
        self._trade_data_path = Path(
            (config or {}).get("vault_path", "vault")
        ) / "config" / "risk_open_trades.json"

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        self.memory = self.learning.load_memory("RiskAgent")

        # Forcer une re-sauvegarde pour nettoyer les blocs JSON corrompus
        self.learning.save_memory(self.memory)
        logger.info("[%s] Mémoire rechargée et nettoyée (v%d, %d trades)",
                    self.name, self.memory.version, self.memory.total_trades)

        # Recharger les trades ouverts depuis le disque (survie aux redémarrages)
        self._load_open_trade_data()

        logger.info(
            "[%s] Capital : $%.2f | Risk/trade : %.1f%% | DD max : %.1f%%",
            self.name, self.tracker.capital,
            self.risk_per_trade_pct, self.max_drawdown_pct,
        )
        if self._open_trade_data:
            logger.info(
                "[%s] 🔄 %d trade(s) ouvert(s) restauré(s) : %s",
                self.name, len(self._open_trade_data), list(self._open_trade_data.keys()),
            )

    # ── Persistance des trades ouverts ────────────────────────────────────────

    def _load_open_trade_data(self) -> None:
        if not self._trade_data_path.exists():
            return
        try:
            data = json.loads(self._trade_data_path.read_text(encoding="utf-8"))
            self._open_trade_data = data.get("trade_data", {})
            self._open_positions = data.get("positions", {})
        except Exception as exc:
            logger.warning("[%s] Erreur chargement risk_open_trades.json: %s", self.name, exc)

    def _save_open_trade_data(self) -> None:
        try:
            self._trade_data_path.parent.mkdir(parents=True, exist_ok=True)
            self._trade_data_path.write_text(json.dumps({
                "trade_data": self._open_trade_data,
                "positions": self._open_positions,
            }, indent=2, default=str), encoding="utf-8")
        except Exception as exc:
            logger.warning("[%s] Erreur sauvegarde risk_open_trades.json: %s", self.name, exc)

    def _register_subscriptions(self) -> None:
        self.bus.subscribe(CHANNELS["decisions"],        self._on_prediction)
        self.bus.subscribe(CHANNELS["orders_executed"],  self._on_execution)
        self.bus.subscribe(CHANNELS["portfolio_update"], self._on_portfolio_update)
        self.bus.subscribe(CHANNELS["market_context"],   self._on_market_context)
        self.bus.subscribe(CHANNELS["error"],            self._on_system_error)
        self.bus.subscribe(CHANNELS["behavior_alert"],   self._on_behavior)
        self.bus.subscribe(CHANNELS["meta_directive"],   self._on_meta_directive)
        self.bus.subscribe("meta:daily_thesis", self._on_daily_thesis)

    # ── Cycle principal ───────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        # PerformanceTracker persiste déjà toutes les métriques dans trade_history.json
        # _write_risk_journal() écrivait dans vault/risque/ sans jamais être relu — supprimé
        self.tracker.write_performance_note()

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _on_prediction(self, data: dict) -> None:
        asset      = data.get("asset")
        direction  = data.get("direction")
        confidence = data.get("confidence", 0)

        # ── Circuit Breaker ──
        if not self.circuit_breaker.can_trade():
            cb = self.circuit_breaker.snapshot()
            logger.warning(
                "[%s] 🚨 CIRCUIT BREAKER %s — %s (cooldown: %.0f min)",
                self.name, cb["state"], cb["trip_reason"], cb["cooldown_remaining"],
            )
            return

        # ── Garde-fous drawdown (backup du circuit breaker) ──
        dd = self.tracker.current_drawdown
        if dd >= self.max_drawdown_pct:
            logger.warning("[%s] 🚨 DRAWDOWN LIMITE (%.1f%%) — aucun nouvel ordre", self.name, dd)
            return

        # ── Garde-fou DataSheet : manipulation détectée → BLOQUER le trade ──
        ctx = self._market_ctx.get(asset, {})
        manipulation = ctx.get("manipulation", {})
        if isinstance(manipulation, dict):
            manip_alerts = manipulation.get("alerts", [])
            if manip_alerts:
                logger.warning(
                    "[%s] 🚨 MANIPULATION détectée sur %s (%d alertes) — trade BLOQUÉ",
                    self.name, asset, len(manip_alerts),
                )
                if self.telegram:
                    try:
                        await self.telegram.risk_alert(
                            drawdown=dd,
                            capital=self.tracker.capital,
                            message=f"Trade {asset} bloqué : manipulation détectée ({len(manip_alerts)} alertes)",
                        )
                    except Exception:
                        pass
                return

        # Confidence floor : regime-specific si disponible
        pred_regime = data.get("regime", "sideways")
        regime_p = self.memory.regime_params.get(pred_regime, {})
        conf_floor = int(regime_p.get("confidence_floor",
                         self.memory.adaptive_params.get("confidence_floor", CONF_FLOOR)))
        if confidence < conf_floor:
            logger.debug("[%s] Confiance %d < seuil %d pour %s", self.name, confidence, conf_floor, asset)
            return
        if asset in self._open_positions:
            logger.debug("[%s] Position déjà ouverte sur %s", self.name, asset)
            return
        if len(self._open_positions) >= MAX_POSITIONS:
            logger.warning("[%s] Max positions (%d) atteint", self.name, MAX_POSITIONS)
            return

        # ── Sizing de la position ──
        order = self._build_order(data)
        if not order:
            return

        # ── Conseil LLM (délibération avant exécution) ────────────────────────
        if self._council:
            daily_thesis = self._daily_thesis_ref[0] if self._daily_thesis_ref else ""
            council_verdict = await self._council.convene(
                asset=asset,
                direction=str(direction),
                confidence=confidence,
                regime=data.get("regime", "unknown"),
                daily_thesis=daily_thesis,
                indicators={
                    "rsi":       data.get("rsi", 0),
                    "macd_hist": data.get("macd_hist", 0),
                    "bb_pos":    data.get("bb_position", 0),
                    "atr":       data.get("atr", 0),
                },
            )

            if council_verdict.verdict == "PASSE":
                logger.info(
                    "[%s] 🛑 CONSEIL: PASSE sur %s (conf %d→%d) — %s",
                    self.name, asset,
                    confidence, council_verdict.final_confidence,
                    council_verdict.reasoning,
                )
                return

            if council_verdict.verdict == "REDUIS_TAILLE":
                order.quantity = order.quantity * 0.5
                logger.info(
                    "[%s] ⚠️ CONSEIL: REDUIS_TAILLE sur %s — taille ÷2",
                    self.name, asset,
                )

            confidence = max(0, min(100, council_verdict.final_confidence))

        await self.bus.publish(CHANNELS["orders_validated"], order.to_dict())
        self._open_positions[asset] = order.to_dict()

        # Sauvegarder les données d'entrée pour le TradeOutcome ultérieur
        self._open_trade_data[asset] = {
            "asset":          asset,
            "order_id":       order.order_id,
            "entry_price":    order.entry_price,
            "stop_loss":      order.stop_loss,
            "take_profit":    order.take_profit,
            "side":           order.side.value,
            "quantity":       order.quantity,
            "entry_time":     datetime.now(timezone.utc).isoformat(),
            "confidence":     confidence,
            "tech_signal":    data.get("tech_signal", {}),
            "fund_signal":    data.get("fund_signal", {}),
            "regime":         data.get("regime", "sideways"),
        }
        self._save_open_trade_data()

        logger.info(
            "[%s] ✅ Ordre validé : %s %s %.6f @ %s | SL:%s TP:%s R:R=%.1f",
            self.name, order.side.value.upper(), asset,
            order.quantity, order.entry_price,
            order.stop_loss, order.take_profit, order.risk_reward_ratio,
        )
        # vault/risque/risque_decision_* supprimé — données déjà dans retrospectives/
        # (lu par SynthesisAgent) et trade_history.json. Aucun agent ne relisait ces notes.

        # Notification Telegram — trade ouvert (capital LIVE via tracker)
        if self.telegram:
            risk_usd = self.tracker.capital * self.risk_per_trade_pct / 100
            await self.telegram.trade_opened(
                asset=asset,
                direction=order.side.value,
                entry=float(order.entry_price),
                sl=float(order.stop_loss),
                tp=float(order.take_profit),
                size=float(order.quantity),
                risk_usd=risk_usd,
                capital=self.tracker.capital,
            )

    async def _on_market_context(self, data: dict) -> None:
        """Reçoit les DataSheets de SynthesisAgent — utilisées pour le sizing contextuel."""
        asset = data.get("asset")
        if asset:
            self._market_ctx[asset] = data

    async def _on_system_error(self, data: dict) -> None:
        """Reçoit les alertes du SupervisorAgent — ajuste le ratio agents vivants."""
        if data.get("type") == "supervisor_alert":
            title = data.get("title", "")
            if "ne repond plus" in title.lower() or "heartbeat" in title.lower():
                # Au moins un agent est mort — réduire l'appétit au risque
                self._agents_alive_ratio = max(self._agents_alive_ratio - 0.15, 0.3)
                logger.warning(
                    "[%s] ⚠️ Agent mort détecté — ratio agents alive: %.0f%%",
                    self.name, self._agents_alive_ratio * 100,
                )
            elif "de retour" in title.lower():
                self._agents_alive_ratio = min(self._agents_alive_ratio + 0.15, 1.0)

    async def _on_behavior(self, data: dict) -> None:
        """Reçoit les alertes comportementales de BehaviorAgent — applique le multiplicateur de risque."""
        mult = data.get("risk_multiplier")
        if isinstance(mult, (int, float)) and 0.0 <= mult <= 1.0:
            prev = self._behavior_multiplier
            self._behavior_multiplier = float(mult)
            if abs(prev - mult) >= 0.05:
                logger.info(
                    "[%s] 🧠 BehaviorAgent → risk_multiplier : %.2f → %.2f (mode=%s)",
                    self.name, prev, mult, data.get("mode", "?"),
                )

    async def _on_meta_directive(self, data: dict) -> None:
        """Reçoit les directives du MetaAgent (CEO) — ajuste les paramètres de risque."""
        dtype = data.get("type")
        if dtype == "confidence_update":
            # MetaAgent peut demander une réduction du risque global
            factor = data.get("risk_factor")
            if isinstance(factor, (int, float)) and 0.1 <= factor <= 1.0:
                self.risk_per_trade_pct = round(self.risk_per_trade_pct * factor, 2)
                logger.info("[%s] 📋 CEO directive → risk_per_trade=%.2f%%",
                            self.name, self.risk_per_trade_pct)

    async def _on_daily_thesis(self, data: dict) -> None:
        thesis = data.get("thesis", "")
        if self._daily_thesis_ref:
            self._daily_thesis_ref[0] = thesis
        else:
            self._daily_thesis_ref.append(thesis)

    async def _on_portfolio_update(self, data: dict) -> None:
        """Reçoit les ajustements de risque publiés par CompoundAgent."""
        if data.get("type") != "risk_config":
            return
        new_risk = data.get("new_risk_pct")
        if not isinstance(new_risk, (int, float)) or new_risk <= 0:
            return
        old_risk = self.risk_per_trade_pct
        self.risk_per_trade_pct = round(float(new_risk), 3)
        logger.info(
            "[%s] ⚙️  CompoundAgent → risk/trade : %.2f%% → %.2f%% (mode: %s)",
            self.name, old_risk, self.risk_per_trade_pct, data.get("mode", "?"),
        )

    async def _on_execution(self, data: dict) -> None:
        """Reçoit le rapport d'exécution et enregistre le TradeOutcome pour l'apprentissage."""
        asset    = data.get("asset")
        status   = data.get("status")
        order_id = data.get("order_id")

        self._execution_log.append(data)

        if status == OrderStatus.FILLED.value:
            # Trade ouvert — on attend la fermeture (SL ou TP)
            logger.info("[%s] 📂 Trade ouvert : %s @ %s", self.name, asset, data.get("filled_price"))

        elif status in ("stop_loss", "take_profit", "closed"):
            # Trade fermé — on calcule le P&L et on apprend
            trade_data = self._open_trade_data.pop(asset, None)
            self._open_positions.pop(asset, None)
            self._save_open_trade_data()

            if trade_data:
                await self._finalize_trade(trade_data, data)
            else:
                logger.warning(
                    "[%s] ⚠️  Trade fermé %s mais pas de données d'entrée — "
                    "trade ouvert avant dernier redémarrage? PnL non comptabilisé.",
                    self.name, asset,
                )

    # ── Sizing des positions ───────────────────────────────────────────────────

    def _build_order(self, pred: dict) -> Optional[ValidatedOrder]:
        asset     = pred.get("asset")
        direction = pred.get("direction")
        entry     = pred.get("entry_price")
        atr       = pred.get("atr")
        confidence= pred.get("confidence", 60)

        if not entry:
            return None

        # Paramètres adaptatifs depuis la mémoire ML — régime-spécifique si disponible
        regime = pred.get("regime", "sideways")
        rp = self.memory.regime_params.get(regime, {})
        sl_mult  = rp.get("sl_atr_multiplier", self.memory.adaptive_params.get("sl_atr_multiplier", 2.0))
        tp_ratio = rp.get("tp_rr_ratio", self.memory.adaptive_params.get("tp_rr_ratio", 3.0))
        leverage = rp.get("leverage", self.memory.adaptive_params.get("leverage", 1.0))

        atr_val  = atr or (entry * 0.015)
        sl_dist  = atr_val * sl_mult
        tp_dist  = sl_dist * tp_ratio

        is_buy  = (direction == "bullish")
        sl      = round(entry - sl_dist if is_buy else entry + sl_dist, 6)
        tp      = round(entry + tp_dist if is_buy else entry - tp_dist, 6)
        side    = OrderSide.BUY if is_buy else OrderSide.SELL

        # ── Dynamic Sizing (Kelly Criterion + adaptatif) ──
        snap = self.tracker.snapshot()
        avg_win  = abs(snap.get("best_trade_pct", 2.5)) if snap.get("total_trades", 0) > 0 else 2.5
        avg_loss = abs(snap.get("worst_trade_pct", 1.0)) if snap.get("total_trades", 0) > 0 else 1.0
        # Calculer avg win/loss depuis les trades réels
        wins_pnl  = [t.pnl_pct for t in self.tracker._trades if t.is_win]
        losses_pnl = [abs(t.pnl_pct) for t in self.tracker._trades if not t.is_win]
        if wins_pnl:
            avg_win = sum(wins_pnl) / len(wins_pnl)
        if losses_pnl:
            avg_loss = sum(losses_pnl) / len(losses_pnl)

        atr_pct = (atr_val / entry) * 100 if entry > 0 else 1.5

        dynamic_risk_pct = self.sizer.compute(
            win_rate=snap.get("win_rate", 0.5),
            avg_win_pct=avg_win,
            avg_loss_pct=avg_loss,
            confidence=confidence,
            drawdown_pct=snap.get("current_drawdown", 0),
            max_drawdown_pct=self.max_drawdown_pct,
            atr_pct=atr_pct,
            streak=self.memory.current_streak,
            total_trades=snap.get("total_trades", 0),
        )

        # Appliquer le facteur du circuit breaker (0.5 en mode HALF)
        dynamic_risk_pct *= self.circuit_breaker.size_factor()

        # ── Facteur DataSheet : VIX élevé → réduire le sizing ──
        ctx = self._market_ctx.get(asset, {})
        vix_data = ctx.get("vix", {})
        ctx_factor = 1.0
        if isinstance(vix_data, dict):
            realized_vol = vix_data.get("realized_vol", 0)
            if isinstance(realized_vol, (int, float)) and realized_vol > 80:
                ctx_factor *= 0.7   # VIX élevé → -30% sizing
                logger.info("[%s] 📉 VIX élevé (%.0f) → sizing ×0.7", self.name, realized_vol)
            elif isinstance(realized_vol, (int, float)) and realized_vol > 60:
                ctx_factor *= 0.85  # VIX modéré → -15% sizing
        dynamic_risk_pct *= ctx_factor

        # ── Facteur agents vivants : agents morts → réduire le sizing ──
        if self._agents_alive_ratio < 0.8:
            dynamic_risk_pct *= self._agents_alive_ratio
            logger.warning(
                "[%s] ⚠️ Agents alive ratio %.0f%% → sizing réduit",
                self.name, self._agents_alive_ratio * 100,
            )

        # ── Facteur comportemental (BehaviorAgent) ──
        if self._behavior_multiplier < 1.0:
            dynamic_risk_pct *= self._behavior_multiplier
            if self._behavior_multiplier == 0.0:
                logger.warning("[%s] 🛑 BehaviorAgent KILL switch — ordre annulé", self.name)
                return None
            logger.info(
                "[%s] 🧠 Behavior multiplier ×%.2f → risk=%.2f%%",
                self.name, self._behavior_multiplier, dynamic_risk_pct,
            )

        # Appliquer le levier appris (1x en paper par défaut, augmente si Sharpe bon)
        dynamic_risk_pct *= max(leverage, 0.5)

        risk_usd = self.tracker.capital * (dynamic_risk_pct / 100)
        qty      = round(risk_usd / max(sl_dist, 1e-9), 6)

        logger.info(
            "[%s] 📐 Sizing %s : %.2f%% (Kelly adaptatif) | CB:×%.1f | Risk:$%.2f",
            self.name, asset, dynamic_risk_pct,
            self.circuit_breaker.size_factor(), risk_usd,
        )

        if qty <= 0:
            return None

        return ValidatedOrder(
            asset           = asset,
            side            = side,
            quantity        = qty,
            entry_price     = round(entry, 6),
            stop_loss       = sl,
            take_profit     = tp,
            risk_amount_usd = round(risk_usd, 2),
            risk_percent    = self.risk_per_trade_pct,
            confidence_score= confidence,
            signal_sources  = ["ScanAgent", "ResearchAgent", "PredictAgent"],
            exchange        = self.config.get("exchanges", ["binance"])[0],
        )

    # ── Enregistrement du résultat → LearningEngine ────────────────────────────

    async def _finalize_trade(self, entry_data: dict, exec_data: dict) -> None:
        """
        Construit le TradeOutcome et le transmet au LearningEngine.
        Déclenche l'analyse contrefactuelle si trade perdant.
        """
        from models.learning import MarketRegime as MR
        exit_price = exec_data.get("filled_price", entry_data["entry_price"])
        exit_reason_str = exec_data.get("exit_reason", exec_data.get("status", "unknown"))

        try:
            exit_reason = ExitReason(exit_reason_str)
        except ValueError:
            exit_reason = ExitReason.TIMEOUT

        try:
            regime = MR(entry_data.get("regime", "sideways"))
        except ValueError:
            regime = MR.SIDEWAYS

        outcome = TradeOutcome(
            order_id    = entry_data.get("order_id", "?"),
            asset       = entry_data.get("asset", exec_data.get("asset", "?")),
            side        = OrderSide(entry_data["side"]),
            entry_price = entry_data["entry_price"],
            exit_price  = exit_price,
            stop_loss   = entry_data["stop_loss"],
            take_profit = entry_data["take_profit"],
            quantity    = entry_data["quantity"],
            entry_time  = datetime.fromisoformat(entry_data["entry_time"]),
            exit_time   = datetime.now(timezone.utc),
            exit_reason = exit_reason,
            exchange    = exec_data.get("exchange", "?"),
            tech_signal = entry_data.get("tech_signal", {}),
            fund_signal = entry_data.get("fund_signal", {}),
            confidence  = entry_data.get("confidence", 0),
            regime      = regime,
        )

        # Enregistrer dans le tracker de performance
        self.tracker.record(outcome)

        # Enregistrer dans le LearningEngine (déclenche contrefactuel si LOSS)
        self.learning.record_outcome(outcome)

        # (learning_update fusionne dans trade_closed pour reduire le spam Telegram)

        # Alimenter le circuit breaker
        self.circuit_breaker.record_trade(
            pnl_usd=outcome.pnl_usd,
            capital=self.tracker.capital,
            drawdown_pct=self.tracker.current_drawdown,
        )

        logger.info(
            "[%s] 📋 Trade clôturé %s : %+.2f%% ($%+.2f) [%s]",
            self.name, outcome.asset, outcome.pnl_pct, outcome.pnl_usd,
            "✅ WIN" if outcome.is_win else "❌ LOSS",
        )

        # Publier snapshot de performance → déclenche CompoundAgent en temps réel
        snap = self.tracker.snapshot()
        await self.bus.publish(CHANNELS["portfolio_update"], {
            "type":         "trade_closed",
            "asset":        outcome.asset,
            "pnl_usd":      round(outcome.pnl_usd, 2),
            "pnl_pct":      round(outcome.pnl_pct, 4),
            "is_win":       outcome.is_win,
            "total_trades": snap["total_trades"],
            "win_rate":     snap["win_rate"],
            "sharpe":       snap["sharpe_ratio"],
            "drawdown":     snap["current_drawdown"],
            "capital":      snap["capital"],
            "risk_pct":     self.risk_per_trade_pct,
        })

        # Rétrospective détaillée → vault/retrospectives/
        try:
            self._write_retrospective(outcome, entry_data, snap)
        except Exception as retro_exc:
            logger.error(
                "[%s] Erreur écriture rétrospective %s: %s",
                self.name, outcome.asset, retro_exc, exc_info=True,
            )

        # Notification Telegram — trade fermé + ML update (fusionné en 1 message)
        if self.telegram:
            mem = self.learning.get_memory("RiskAgent")
            ml_info = (
                f"ML: SL `{mem.adaptive_params.get('sl_atr_multiplier', 2.0):.2f}x` "
                f"TP `1:{mem.adaptive_params.get('tp_rr_ratio', 3.0):.2f}` "
                f"Floor `{mem.adaptive_params.get('confidence_floor', 55):.0f}`"
            )
            await self.telegram.trade_closed(
                asset        = outcome.asset,
                pnl_usd      = outcome.pnl_usd,
                pnl_pct      = outcome.pnl_pct,
                win_rate     = snap["win_rate"],
                total_trades = snap["total_trades"],
                capital      = snap["capital"],
                drawdown     = snap["current_drawdown"],
                sharpe       = snap["sharpe_ratio"],
                ml_info      = ml_info,
            )

    # ── Rétrospective Post-Trade ───────────────────────────────────────────────

    def _write_retrospective(self, outcome, entry_data: dict, snap: dict) -> None:
        """
        Post-mortem détaillé écrit dans vault/retrospectives/ après chaque trade.
        Template Wall Street : rationale d'entrée, qualité d'exécution, leçon apprise.
        """
        (self.obsidian.vault_path / "retrospectives").mkdir(exist_ok=True)

        ts    = datetime.now(timezone.utc)
        fname = f"retro_{ts.strftime('%Y-%m-%d_%H%M')}_{outcome.asset.replace('/','_')}"
        icon  = "✅" if outcome.is_win else "❌"
        result_label = "WINNER" if outcome.is_win else "LOSER"

        # Analyse de la qualité du signal d'entrée
        tech   = entry_data.get("tech_signal", {})
        fund   = entry_data.get("fund_signal", {})
        regime = entry_data.get("regime", "sideways")

        rsi_at_entry  = tech.get("rsi", "?")
        macd_at_entry = tech.get("macd_hist", "?")
        bb_at_entry   = tech.get("bb_position", "?")
        vol_at_entry  = tech.get("volume_ratio", "?")
        ob_imbalance  = tech.get("ob_imbalance", "?")
        vwap_dist     = tech.get("vwap_dist_pct", "?")
        fund_sent     = fund.get("sentiment_score", "?")
        fund_conf     = fund.get("confidence", "?")

        # Calcul de la durée du trade
        entry_dt = datetime.fromisoformat(entry_data["entry_time"])
        duration_min = int((ts - entry_dt).total_seconds() / 60)

        # Distance réelle de l'exit par rapport au TP/SL
        entry_p = entry_data["entry_price"]
        exit_p  = outcome.exit_price
        sl_p    = entry_data["stop_loss"]
        tp_p    = entry_data["take_profit"]
        sl_dist = abs(entry_p - sl_p)
        tp_dist = abs(entry_p - tp_p)
        actual_move = abs(exit_p - entry_p)

        # Efficacité d'entrée (0% = pire point, 100% = meilleur point)
        # Pour un trade LONG : efficacité = (entry - lowest) / (highest - lowest) de la session
        # Simplification : compare l'exit réel au TP théorique
        entry_efficiency = min(actual_move / tp_dist, 1.0) if tp_dist > 0 else 0.0
        entry_efficiency_pct = entry_efficiency * 100 if outcome.is_win else 0.0

        # Diagnostic
        if outcome.is_win:
            if entry_data["confidence"] >= 70:
                signal_quality = "🟢 FORT — confiance élevée + résultat positif"
            else:
                signal_quality = "🟡 CORRECT — confiance modérée, résultat positif"
        else:
            if entry_data["confidence"] >= 70:
                signal_quality = "🔴 FAUX POSITIF — confiance élevée mais trade perdant (overfitting ?)"
            elif ob_imbalance != "?" and isinstance(ob_imbalance, float) and abs(ob_imbalance) > 0.2:
                signal_quality = "🟠 ORDER BOOK contre-signal ignoré — revoir le filtre OB"
            else:
                signal_quality = "🟡 SIGNAL FAIBLE — confiance insuffisante pour ce setup"

        # Leçon apprise
        if outcome.is_win and outcome.pnl_pct > 1.0:
            lesson = "✅ Setup validé — augmenter légèrement le sizing sur ce régime"
        elif outcome.is_win:
            lesson = "✅ Petit win — setup correct, continuer à filtrer"
        elif abs(outcome.pnl_pct) < 0.5:
            lesson = "⚠️ Stop trop serré ? Vérifier ATR multiplier pour ce marché"
        elif entry_data.get("regime") == "volatile":
            lesson = "🔴 Éviter ce setup en régime VOLATILE — réduire fund_weight"
        else:
            lesson = "🔴 Revoir l'alignement multi-timeframe — signal probablement isolé"

        frontmatter = {
            "date":         ts.strftime("%Y-%m-%d"),
            "asset":        outcome.asset,
            "result":       result_label,
            "pnl_pct":      round(outcome.pnl_pct, 4),
            "pnl_usd":      round(outcome.pnl_usd, 2),
            "confidence":   entry_data.get("confidence", 0),
            "regime":       regime,
            "exit_reason":  outcome.exit_reason.value,
            "duration_min": duration_min,
            "tags":         ["retrospective", "trade", regime, result_label.lower()],
        }

        content = f"""## {icon} Rétrospective — {outcome.asset} | {result_label}

> **P&L : {outcome.pnl_pct:+.3f}% (${outcome.pnl_usd:+.2f})**
> Durée : {duration_min} minutes | Exit : `{outcome.exit_reason.value}` | Régime : `{regime}`

---

### 1. Rationale d'Entrée
| Paramètre | Valeur | Évaluation |
|---|---|---|
| Confiance globale | `{entry_data.get('confidence', 0)}/100` | {signal_quality} |
| Signal technique | `{entry_data.get('side','?').upper()}` | RSI:{rsi_at_entry} MACD:{macd_at_entry} BB:{bb_at_entry} |
| Signal fondamental | sentiment `{fund_sent}` | conf. `{fund_conf}/100` |
| Volume ratio | `{vol_at_entry}x` | {'🔥 Fort' if isinstance(vol_at_entry, (int, float)) and vol_at_entry > 1.5 else '📊 Normal'} |
| Order Book Imbalance | `{ob_imbalance}` | {'pression acheteuse' if isinstance(ob_imbalance, float) and ob_imbalance > 0.1 else ('pression vendeuse' if isinstance(ob_imbalance, float) and ob_imbalance < -0.1 else 'neutre')} |
| Distance VWAP | `{vwap_dist}%` | contexte intraday |
| Régime de marché | `{regime}` | poids tech/fund ajustés |

### 2. Exécution
| Niveau | Prix | Distance Entrée |
|---|---|---|
| Entrée | `{entry_p:.6f}` | — |
| Stop-Loss | `{sl_p:.6f}` | `{sl_dist/entry_p*100:.2f}%` |
| Take-Profit | `{tp_p:.6f}` | `{tp_dist/entry_p*100:.2f}%` |
| Exit réel | `{exit_p:.6f}` | `{actual_move/entry_p*100:.2f}%` |
| Efficacité | — | `{entry_efficiency_pct:.0f}%` du TP théorique |

### 3. P&L et Impact Portefeuille
| Métrique | Valeur |
|---|---|
| P&L brut | `{outcome.pnl_pct:+.4f}%` |
| P&L USD | `${outcome.pnl_usd:+.2f}` |
| Capital après | `${snap['capital']:,.2f}` |
| Win rate session | `{snap['win_rate']:.1%}` ({snap['total_trades']} trades) |
| Drawdown courant | `{snap['current_drawdown']:.2f}%` |

### 4. Diagnostic Signal
{signal_quality}

**Indicateurs au moment de l'entrée :**
- RSI : `{rsi_at_entry}` {'→ zone haussière' if isinstance(rsi_at_entry, (int, float)) and rsi_at_entry > 55 else ('→ zone baissière' if isinstance(rsi_at_entry, (int, float)) and rsi_at_entry < 45 else '→ neutre')}
- MACD hist : `{macd_at_entry}` {'→ haussier' if isinstance(macd_at_entry, (int, float)) and macd_at_entry > 0 else '→ baissier'}
- BB Position : `{bb_at_entry}` {'→ proche bas bande (rebond ?)' if isinstance(bb_at_entry, (int, float)) and bb_at_entry < 0.25 else ('→ proche haut bande (résistance ?)' if isinstance(bb_at_entry, (int, float)) and bb_at_entry > 0.75 else '→ milieu bande')}
- OB Imbalance : `{ob_imbalance}` (confirmation institutionnelle)

### 5. Leçon Apprise
> {lesson}

**Paramètres ML avant ce trade :**
- SL multiplier : `{self.memory.adaptive_params.get('sl_atr_multiplier', 1.5):.2f}×ATR`
- TP ratio : `1:{self.memory.adaptive_params.get('tp_rr_ratio', 2.5):.2f}`
- Confidence floor : `{self.memory.adaptive_params.get('confidence_floor', 30)}/100`

Le LearningEngine a mis à jour ces paramètres après ce trade.

### Liens
{self.obsidian.wikilink('risque', self.obsidian.timestamp_filename('risque_decision', outcome.asset))}
{self.obsidian.wikilink('config', 'RiskAgent_memory')}
"""
        self.obsidian.write_note("retrospectives", fname, frontmatter, content)
        logger.info(
            "[%s] 📝 Rétrospective écrite : %s %s (%+.2f%%) — %s",
            self.name, icon, outcome.asset, outcome.pnl_pct, lesson[:60],
        )

    # ── Vault Obsidian ────────────────────────────────────────────────────────

    def _write_decision_note(self, order: ValidatedOrder, pred: dict) -> None:
        filename = self.obsidian.timestamp_filename("risque_decision", order.asset)
        snap     = self.tracker.snapshot()

        frontmatter = self._build_frontmatter(
            asset=order.asset, signal_type=order.side.value,
            confidence=order.confidence_score,
            extra={"order_id": order.order_id, "rr": order.risk_reward_ratio},
        )

        content = f"""## Décision de Risque — {order.asset}

### Validation de l'Ordre
| Paramètre | Valeur |
|---|---|
| Ordre ID | `{order.order_id}` |
| Direction | **{order.side.value.upper()}** |
| Quantité | `{order.quantity}` |
| Entrée | `{order.entry_price}` |
| Stop-Loss | `{order.stop_loss}` (−{abs(order.entry_price - order.stop_loss)/order.entry_price:.2%}) |
| Take-Profit | `{order.take_profit}` (+{abs(order.take_profit - order.entry_price)/order.entry_price:.2%}) |
| R:R | `1:{order.risk_reward_ratio}` |
| Capital risqué | `${order.risk_amount_usd}` ({order.risk_percent}%) |
| Régime détecté | `{pred.get('regime', '?')}` |

### État du Portefeuille au Moment de la Décision
| Métrique | Valeur |
|---|---|
| Capital | `${snap['capital']:,.2f}` |
| Drawdown courant | `{snap['current_drawdown']:.2f}%` / `{self.max_drawdown_pct}%` max |
| Positions ouvertes | `{len(self._open_positions)} / {MAX_POSITIONS}` |
| Win Rate (session) | `{snap['win_rate']:.1%}` |
| Sharpe (session) | `{snap['sharpe_ratio']:.2f}` |

### Liens
{self.obsidian.wikilink('decisions', self.obsidian.timestamp_filename('predict', order.asset))}
{self.obsidian.wikilink('config', 'RiskAgent_memory')}
"""
        self.obsidian.write_note("risque", filename, frontmatter, content)

    # _write_risk_journal() supprimé — vault/risque/journal_* n'était jamais relu par aucun agent.
    # PerformanceTracker persiste toutes les métriques dans trade_history.json (actif).
    # SupervisorAgent lit trade_history.json et envoie les stats via Telegram health_status().
