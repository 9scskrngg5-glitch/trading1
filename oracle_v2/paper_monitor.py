"""
PaperPositionMonitor — Surveillance SL/TP en mode paper.

Problème corrigé : avant ce module, les positions paper ouvertes n'avaient
aucun mécanisme pour déclencher une clôture quand le prix atteignait SL ou TP.
Conséquence : Brainstem.register_trade() n'était jamais appelé → le circuit
breaker "pertes consécutives" ne fonctionnait pas en paper mode.

Architecture :
  1. S'abonne à TradeOpenedEvent via le bus global (dans oracle_system._init_engines)
  2. Stocke entry_price + SL/TP pour chaque position paper ouverte
  3. check_positions() est appelé à chaque cycle par CycleManager
  4. Si le prix atteint SL → close avec PnL = -sl_pct (perte réalisée)
  5. Si le prix atteint TP → close avec PnL = +tp_pct (gain réalisé)
  6. ExecutionEngine.close_position() propage ensuite vers Brainstem + bus

Règles :
  - En SHORT : SL = prix DESSUS l'entrée, TP = prix DESSOUS l'entrée
  - En LONG  : SL = prix DESSOUS l'entrée, TP = prix DESSUS l'entrée
  - Un seul symbole par position (pas de multi-lot)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from execution_engine import ExecutionEngine

logger = logging.getLogger("ORACLE.PaperMonitor")


@dataclass
class _PaperPos:
    """Snapshot d'une position paper ouverte — suffisant pour évaluer SL/TP."""
    symbol: str
    direction: str      # "LONG" | "SHORT"
    entry_price: float
    sl_pct: float
    tp_pct: float
    trade_id: Optional[int]
    slippage_pct: float = 0.0005  # 0.05% par défaut — représente le coût d'exécution réel


class PaperPositionMonitor:
    """
    Surveille les positions paper et déclenche les clôtures SL/TP automatiquement.

    Usage :
        monitor = PaperPositionMonitor(slippage_pct=0.0005)
        bus.subscribe(EventType.TRADE_OPENED, monitor.register)

        # Dans CycleManager.run_cycle(), à chaque cycle :
        await monitor.check_positions(binance, execution_engine)

    slippage_pct :
        Surcoût ajouté au PnL négatif lors d'un SL hit pour simuler le slippage
        réel (écart bid/ask + impact marché). 0.05% par défaut (≈ Binance Futures
        taker fee). Mettre à 0 pour un backtesting idéal sans friction.
    """

    def __init__(self, slippage_pct: float = 0.0005) -> None:
        self._positions: dict[str, _PaperPos] = {}  # symbol → position
        self._slippage_pct = slippage_pct

    # ─── Abonnement événement ─────────────────────────────────────────

    def register(self, event) -> None:
        """
        Handler abonné à TradeOpenedEvent.
        Enregistre la position pour surveillance uniquement si :
          - mode == "paper"
          - entry_price > 0 (champ ajouté dans TradeOpenedEvent)
        """
        if getattr(event, "mode", "") != "paper":
            return

        entry_price = getattr(event, "entry_price", 0.0)
        if entry_price <= 0:
            logger.debug(
                f"PaperMonitor: entry_price absent pour {event.symbol} — "
                "surveillance SL/TP ignorée (assure-toi que entry_price est "
                "fourni dans TradeOpenedEvent)"
            )
            return

        pos = _PaperPos(
            symbol=event.symbol,
            direction=event.direction,
            entry_price=entry_price,
            sl_pct=event.sl_pct,
            tp_pct=event.tp_pct,
            trade_id=event.trade_id,
            slippage_pct=self._slippage_pct,
        )
        self._positions[event.symbol] = pos

        # Log les prix cibles pour debug
        if event.direction == "LONG":
            sl_price = entry_price * (1 - event.sl_pct)
            tp_price = entry_price * (1 + event.tp_pct)
        else:
            sl_price = entry_price * (1 + event.sl_pct)
            tp_price = entry_price * (1 - event.tp_pct)

        logger.info(
            f"[PaperMonitor] 👁 {event.symbol} {event.direction} | "
            f"Entrée={entry_price:.4f} SL={sl_price:.4f} TP={tp_price:.4f}"
        )

    # ─── Vérification cyclique ────────────────────────────────────────

    async def check_positions(
        self,
        binance,
        execution_engine: "ExecutionEngine",
    ) -> None:
        """
        Appelé à chaque cycle par CycleManager.
        Vérifie si SL ou TP est atteint pour chaque position paper surveillée.

        Les positions déclenchées sont retirées avant d'appeler close_position()
        pour éviter un double-close si l'événement reboucle.
        """
        if not self._positions or not binance:
            return

        # Snapshot des positions courantes pour itération sûre
        snapshot = dict(self._positions)
        to_close: list[tuple[str, float, Optional[int], str]] = []

        for symbol, pos in snapshot.items():
            try:
                ticker = await binance.fetch_ticker(symbol)
                if ticker is None:
                    continue
                current_price: float = ticker.last  # Ticker est un dataclass — .last toujours présent
                if not current_price:
                    continue

                trigger = self._evaluate(pos, current_price)
                if trigger:
                    hit_type, pnl_pct = trigger
                    to_close.append((symbol, pnl_pct, pos.trade_id, hit_type))

            except Exception as exc:
                logger.warning(f"PaperMonitor: erreur fetch {symbol}: {exc}")

        for symbol, pnl_pct, trade_id, hit_type in to_close:
            # Retirer AVANT d'appeler close_position (évite re-entrée)
            self._positions.pop(symbol, None)
            logger.info(
                f"[PaperMonitor] 🔔 {hit_type} atteint — {symbol} "
                f"PnL simulé={pnl_pct:+.2%}"
            )
            await execution_engine.close_position(symbol, pnl_pct, trade_id)

    # ─── Utilitaires ──────────────────────────────────────────────────

    def _evaluate(
        self,
        pos: _PaperPos,
        current_price: float,
    ) -> Optional[tuple[str, float]]:
        """
        Retourne ("SL", pnl) ou ("TP", pnl) si le niveau est atteint, sinon None.

        SL : PnL = -(sl_pct + slippage_pct) — slippage aggrave la perte,
             comme sur un marché réel où l'ordre se remplit sous le SL.
        TP : PnL = +tp_pct — pas de slippage (ordre limit passif ou proche du cours).
        """
        if pos.direction == "LONG":
            if current_price <= pos.entry_price * (1 - pos.sl_pct):
                return ("SL", -(pos.sl_pct + pos.slippage_pct))
            if current_price >= pos.entry_price * (1 + pos.tp_pct):
                return ("TP", pos.tp_pct)
        else:  # SHORT
            if current_price >= pos.entry_price * (1 + pos.sl_pct):
                return ("SL", -(pos.sl_pct + pos.slippage_pct))
            if current_price <= pos.entry_price * (1 - pos.tp_pct):
                return ("TP", pos.tp_pct)
        return None

    def remove(self, symbol: str) -> None:
        """Retire une position (appelé si close_position est déclenché ailleurs)."""
        self._positions.pop(symbol, None)

    @property
    def watched_count(self) -> int:
        """Nombre de positions paper actuellement surveillées."""
        return len(self._positions)

    @property
    def watched_symbols(self) -> list[str]:
        """Liste des symboles surveillés."""
        return list(self._positions.keys())
