"""
ExecutionEngine — Validation et exécution des ordres ORACLE v2.

Améliorations v2.1 :
  - compute_atr_sl()    : SL/TP DYNAMIQUE adaptatif (ATR × facteur selon volatilité)
  - try_execute()       : DI explicite, Event Bus, PnL réel à la fermeture
  - Suppression capital=1000 fallback silencieux → exception explicite
  - register_trade_opened() au placement, register_trade(pnl) à la fermeture
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from oracle_system import OracleSystem

logger = logging.getLogger("ORACLE.Execution")


# ─── SL/TP Dynamique ──────────────────────────────────────────────────────────

def compute_atr_sl(
    atr: float,
    price: float,
    atr_multiplier: float = 1.5,
    tp_ratio: float = 2.5,
    hard_floor: float = 0.003,    # guard-rail absolu bas
    hard_ceiling: float = 0.05,   # guard-rail absolu haut
) -> tuple[float, float]:
    """
    Calcule (sl_pct, tp_pct) DYNAMIQUEMENT depuis l'ATR.

    Comportement :
      sl_pct = ATR × atr_multiplier / price
        → Volatilité forte : SL plus large (évite whipsaws)
        → Volatilité faible : SL plus serré (capture de profit)

    Guards-rails hard_floor / hard_ceiling : garde-fous absolus
    (plus larges que les anciennes constantes MIN_SL/MAX_SL).
    La SafetyKernel vérifie aussi ses propres bounds (plus larges).

    Returns: (sl_pct, tp_pct)
    """
    if price > 0 and atr > 0:
        sl_pct = atr * atr_multiplier / price
        sl_pct = max(hard_floor, min(hard_ceiling, sl_pct))
    else:
        sl_pct = hard_floor

    tp_pct = sl_pct * tp_ratio
    return sl_pct, tp_pct


def compute_volatility_adjusted_size(
    base_size: float,
    atr: float,
    price: float,
    target_risk_pct: float = 0.01,
) -> float:
    """
    Ajuste la taille de position selon la volatilité (position sizing R-based).
    La taille est réduite quand la volatilité est haute pour cibler un risque $ fixe.

    base_size     : taille brute (capital × position_pct × confidence)
    atr           : ATR actuel
    price         : prix courant
    target_risk_pct : risque $ visé en % du capital (1% par défaut)

    Retourne la taille ajustée (≤ base_size).
    """
    if price <= 0 or atr <= 0:
        return base_size
    atr_pct = atr / price
    if atr_pct <= 0:
        return base_size
    # Scaling : si ATR/price est 2× la normal (0.5%), diviser la taille par 2
    vol_ratio = target_risk_pct / atr_pct
    adjusted = base_size * min(1.0, vol_ratio)
    return max(adjusted, base_size * 0.2)   # jamais < 20% de la taille brute


# ─── ExecutionEngine ──────────────────────────────────────────────────────────

class ExecutionEngine:
    """
    Délégué d'exécution d'OracleSystem.

    Dépendances explicites (DI partielle) :
      system : OracleSystem — source de vérité partagée pour brainstem,
               safety_kernel, connecteurs, trade_repo, alert_queue.

    Durée de vie : identique à OracleSystem.
    """

    def __init__(self, system: "OracleSystem"):
        self._s = system

    async def try_execute(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        decision,
        feature_vector,
    ) -> None:
        """
        Tente d'exécuter un trade.

        Pipeline :
          1. Brainstem check
          2. Capital disponible (fail explicite si absent)
          3. SL/TP dynamique ATR
          4. Sizing ajusté à la volatilité
          5. SafetyKernel validation
          6. Exécution (paper ou live)
          7. register_trade_opened() (throttle seulement)
          8. PnL → Brainstem.register_trade() à la fermeture (via close_position)
          9. Event Bus emission
        """
        from brain.safety_kernel import Order
        from events import (
            get_event_bus, TradeOpenedEvent, TradeRejectedEvent,
        )

        s = self._s
        bus = get_event_bus()

        # 1. Vérification brainstem
        s.brainstem.set_signal_confidence(confidence)
        alive, reason = s.brainstem.is_alive()
        if not alive:
            logger.warning(f"Brainstem bloqué [{symbol}]: {reason}")
            await bus.emit(TradeRejectedEvent(
                symbol=symbol, reason=reason, layer="BRAINSTEM"
            ))
            if s.alert_queue:
                s.alert_queue.alert_brainstem(reason)
            return

        # 2. Capital disponible — fail explicite (pas de fallback silencieux)
        if s.binance:
            balance = await s.binance.fetch_balance()
            capital = balance.free  # BalanceInfo est un dataclass — .free toujours présent
        else:
            logger.warning(
                f"Pas de connecteur Binance — exécution impossible pour {symbol}. "
                "En mode paper sans connecteur, utilisez MockConnector."
            )
            await bus.emit(TradeRejectedEvent(
                symbol=symbol, reason="NO_CONNECTOR", layer="CAPITAL"
            ))
            return

        if capital <= 0:
            logger.warning(f"Capital insuffisant ({capital}$) — ordre annulé")
            await bus.emit(TradeRejectedEvent(
                symbol=symbol, reason=f"INSUFFICIENT_CAPITAL ({capital}$)", layer="CAPITAL"
            ))
            return

        # 3. Prix courant + ATR
        atr = getattr(feature_vector, "atr", 0) if feature_vector else 0
        current_price = 0.0
        if s.binance:
            ticker = await s.binance.fetch_ticker(symbol)
            if ticker:
                current_price = ticker.last  # Ticker est un dataclass — .last toujours présent

        # 4. SL/TP DYNAMIQUE (adaptatif ATR)
        sl_pct, tp_pct = compute_atr_sl(
            atr=atr,
            price=current_price,
            atr_multiplier=s.config.ATR_SL_MULTIPLIER,
            tp_ratio=s.config.DEFAULT_TP_RATIO,
            hard_floor=s.config.MIN_SL_PCT,
            hard_ceiling=s.config.MAX_SL_PCT,
        )

        # 5. Sizing ajusté à la volatilité (position sizing R-based)
        base_size = capital * s.config.MAX_POSITION_SIZE_PCT * confidence
        size_usdt = compute_volatility_adjusted_size(
            base_size=base_size,
            atr=atr,
            price=current_price,
            target_risk_pct=s.config.TARGET_RISK_PCT,
        )

        order = Order(
            symbol=symbol,
            direction=direction,
            size_usdt=size_usdt,
            leverage=1.0,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
            source_strate="PARLIAMENT",
            confidence=confidence,
            mode=s.mode,
        )

        # 6. Validation SafetyKernel — NON-BYPASSABLE
        report = s.safety_kernel.validate(order, capital)
        if not report.cleared:
            logger.warning(f"SafetyKernel rejet [{symbol}]: {report.reason}")
            await bus.emit(TradeRejectedEvent(
                symbol=symbol, reason=report.reason, layer="SAFETY"
            ))
            return
        if report.adjusted_size:
            order.size_usdt = report.adjusted_size

        # 7. Paper mode
        if s.mode == "paper":
            await self._execute_paper(order, symbol, direction, sl_pct, tp_pct, confidence, current_price)
            return

        # 8. Live mode
        if s.mode == "live" and s.binance:
            await self._execute_live(order, symbol, direction, sl_pct, tp_pct, confidence, current_price)

    async def _execute_paper(
        self,
        order,
        symbol: str,
        direction: str,
        sl_pct: float,
        tp_pct: float,
        confidence: float,
        entry_price: float = 0.0,
    ) -> None:
        """Exécution paper : journal DB + throttle brainstem + événements."""
        from events import get_event_bus, TradeOpenedEvent
        s = self._s
        bus = get_event_bus()

        trade_id: Optional[int] = None
        if s._trade_repo:
            trade_id = s._trade_repo.insert_trade(
                symbol=symbol, direction=direction,
                size_usdt=order.size_usdt, sl_pct=sl_pct,
                tp_pct=tp_pct, confidence=confidence,
                source_strate="PARLIAMENT", mode="paper",
            )

        logger.info(
            f"[PAPER] {direction} {symbol} {order.size_usdt:.0f}$ | "
            f"entry={entry_price:.4f} SL:{sl_pct:.1%} TP:{tp_pct:.1%} | "
            f"Conf:{confidence:.0%} | ID:{trade_id}"
        )

        # Throttle seulement (PnL inconnu au placement)
        s.brainstem.register_trade_opened()
        s.safety_kernel.register_open(order)
        s._open_positions.append({
            "symbol": symbol,
            "order": order,
            "trade_id": trade_id,
            "entry_price": entry_price,
        })

        await bus.emit(TradeOpenedEvent(
            symbol=symbol, direction=direction,
            size_usdt=order.size_usdt, leverage=order.leverage,
            sl_pct=sl_pct, tp_pct=tp_pct, confidence=confidence,
            source="PARLIAMENT", mode="paper", trade_id=trade_id,
            entry_price=entry_price,  # ← PaperPositionMonitor l'utilise pour surveiller SL/TP
        ))

        if s.narrator:
            await s.narrator.announce_trade(
                symbol=symbol, direction=direction,
                size_usdt=order.size_usdt, sl_pct=sl_pct,
                tp_pct=tp_pct, confidence=confidence, mode="paper",
            )
        if s.alert_queue:
            s.alert_queue.alert_trade_open(
                symbol=symbol, direction=direction,
                size_usdt=order.size_usdt, leverage=order.leverage,
                sl_pct=sl_pct, tp_pct=tp_pct, confidence=confidence,
                source="PARLIAMENT",
            )

    async def _execute_live(
        self,
        order,
        symbol: str,
        direction: str,
        sl_pct: float,
        tp_pct: float,
        confidence: float,
        current_price: float,
    ) -> None:
        """Exécution live : ordre réel sur Binance + enregistrement."""
        from events import get_event_bus, TradeOpenedEvent
        s = self._s
        bus = get_event_bus()

        side = "buy" if direction == "LONG" else "sell"
        qty = order.size_usdt / (current_price or 1.0)
        result = await s.binance.place_order(
            symbol=symbol, side=side,
            amount=qty, order_type="market",
        )

        if not result:
            logger.error(f"[LIVE] Ordre rejeté par l'exchange — {symbol}")
            return

        trade_id: Optional[int] = None
        if s._trade_repo:
            trade_id = s._trade_repo.insert_trade(
                symbol=symbol, direction=direction,
                size_usdt=order.size_usdt, sl_pct=sl_pct,
                tp_pct=tp_pct, confidence=confidence,
                source_strate="PARLIAMENT", mode="live",
            )

        # Throttle seulement — PnL sera enregistré à la fermeture via close_position()
        s.brainstem.register_trade_opened()
        s.safety_kernel.register_open(order)
        s._open_positions.append({
            "symbol": symbol,
            "order": order,
            "trade_id": trade_id,
        })

        await bus.emit(TradeOpenedEvent(
            symbol=symbol, direction=direction,
            size_usdt=order.size_usdt, leverage=order.leverage,
            sl_pct=sl_pct, tp_pct=tp_pct, confidence=confidence,
            source="PARLIAMENT", mode="live", trade_id=trade_id,
        ))

        logger.info(
            f"[LIVE] {direction} {symbol} {order.size_usdt:.0f}$ | "
            f"SL:{sl_pct:.1%} TP:{tp_pct:.1%} | ID:{trade_id}"
        )
        if s.alert_queue:
            s.alert_queue.alert_trade_open(
                symbol=symbol, direction=direction,
                size_usdt=order.size_usdt, leverage=order.leverage,
                sl_pct=sl_pct, tp_pct=tp_pct, confidence=confidence,
                source="PARLIAMENT",
            )

    async def close_position(
        self,
        symbol: str,
        pnl_pct: float,
        trade_id: Optional[int] = None,
    ) -> None:
        """
        Ferme une position et enregistre le PnL RÉEL.

        C'est ici que Brainstem.register_trade(pnl_réel) est appelé —
        PAS au placement. Le circuit breaker "pertes consécutives" ne
        fonctionne que si cette méthode est appelée après chaque clôture.
        """
        from events import get_event_bus, TradeClosedEvent
        s = self._s
        bus = get_event_bus()

        # Mise à jour DB
        if s._trade_repo and trade_id:
            s._trade_repo.close_trade(trade_id, pnl_pct)

        # Mise à jour brainstem avec PnL RÉEL
        s.brainstem.register_trade(pnl_pct)

        # Mise à jour métriques
        if hasattr(s, "_metrics"):
            s._metrics.record_pnl("PARLIAMENT", pnl_pct)

        # Nettoyer les positions
        s.safety_kernel.register_close(symbol)
        s._open_positions = [
            p for p in s._open_positions if p.get("symbol") != symbol
        ]

        await bus.emit(TradeClosedEvent(
            symbol=symbol,
            pnl_pct=pnl_pct,
            trade_id=trade_id,
            source_strate="PARLIAMENT",
        ))

        logger.info(f"Position fermée — {symbol} PnL:{pnl_pct:+.2%} ID:{trade_id}")
