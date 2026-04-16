"""
Safety Kernel — Non-bypassable.
TOUT ordre passe ici avant exécution.
Inspiré de rio_roue : "not a feature I added later. It's part of the architecture."

Améliorations v2.1 :
  - Persistance DB des positions ouvertes (survit aux redémarrages)
  - Plafonnement du notionnel global (somme positions × leverage)
  - SL/TP bounds désormais informatives — compute_atr_sl() est la source de vérité
  - Réconciliation au démarrage depuis l'exchange réel
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger("ORACLE.SafetyKernel")


@dataclass
class Order:
    symbol: str
    direction: str        # "LONG" / "SHORT"
    size_usdt: float
    leverage: float
    sl_pct: float         # Stop Loss en %
    tp_pct: float         # Take Profit en %
    source_strate: str
    confidence: float
    mode: str = "paper"


@dataclass
class SafetyReport:
    cleared: bool
    reason: str
    adjusted_size: Optional[float] = None
    adjusted_leverage: Optional[float] = None


class SafetyKernel:
    """
    Superviseur de sécurité obligatoire.

    Vérifie (dans l'ordre) :
      1. Leverage individuel
      2. Stop Loss bounds (garde-fous larges — compute_atr_sl gère le dynamisme)
      3. Position size (ajustement automatique si dépassé)
      4. Nombre de positions ouvertes
      5. Corrélation BTC/ETH/BNB
      6. [NOUVEAU] Notionnel global total (somme expositions × leverage)

    Persistance DB :
      - open_positions chargé depuis SQLite au __init__ (survit aux redémarrages)
      - Chaque register_open/register_close sync la DB en temps réel
    """

    def __init__(
        self,
        max_leverage: float = 2.0,
        max_position_pct: float = 0.10,
        min_sl_pct: float = 0.003,           # Guard-rail large — compute_atr_sl gère le fin
        max_sl_pct: float = 0.05,            # Guard-rail large
        max_open_positions: int = 3,
        max_correlated_positions: int = 2,
        max_total_notional_pct: float = 0.30, # Max 30% du capital en notionnel total
        db_path: Optional[str] = None,
    ):
        self.max_leverage = max_leverage
        self.max_position_pct = max_position_pct
        self.min_sl_pct = min_sl_pct
        self.max_sl_pct = max_sl_pct
        self.max_open_positions = max_open_positions
        self.max_correlated_positions = max_correlated_positions
        self.max_total_notional_pct = max_total_notional_pct

        # Source de vérité unique : liste en mémoire + DB en sync
        self.open_positions: list[Order] = []
        self._repo: Optional[object] = None
        self._last_capital: float = 0.0

        # Chargement depuis DB si disponible
        if db_path:
            self._load_from_db(db_path)

    def _load_from_db(self, db_path: str) -> None:
        """Charge les positions ouvertes depuis SQLite au démarrage."""
        try:
            from db.repositories import OpenPositionRepository
        except ImportError:
            logger.warning("SafetyKernel: OpenPositionRepository non disponible")
            return

        try:
            self._repo = OpenPositionRepository(db_path=db_path)
            rows = self._repo.load_all()
            for row in rows:
                order = Order(
                    symbol=row["symbol"],
                    direction=row["direction"],
                    size_usdt=row["size_usdt"],
                    leverage=row.get("leverage", 1.0),
                    sl_pct=row.get("sl_pct", 0.01),
                    tp_pct=row.get("tp_pct", 0.025),
                    source_strate=row.get("source_strate", ""),
                    confidence=row.get("confidence", 0.0),
                    mode=row.get("mode", "paper"),
                )
                self.open_positions.append(order)
            if rows:
                logger.info(
                    f"SafetyKernel: {len(rows)} position(s) rechargée(s) depuis DB"
                )
        except Exception as e:
            logger.warning(f"SafetyKernel: impossible de charger DB ({e}) — positions vides")

    def validate(self, order: Order, capital: float) -> SafetyReport:
        """
        Validation complète. Retourne SafetyReport.
        cleared=False → reflex withdrawal, ordre annulé.
        """
        self._last_capital = capital

        # 1. Leverage individuel
        if order.leverage > self.max_leverage:
            logger.warning(
                f"SafetyKernel: Leverage {order.leverage}x > max {self.max_leverage}x → REJECTED"
            )
            return SafetyReport(
                False, f"LEVERAGE_EXCEEDED ({order.leverage}x > {self.max_leverage}x)"
            )

        # 2. Stop Loss bounds (garde-fous larges — compute_atr_sl est la source fine)
        if order.sl_pct < self.min_sl_pct:
            return SafetyReport(
                False, f"SL_TOO_TIGHT ({order.sl_pct:.2%} < {self.min_sl_pct:.2%})"
            )
        if order.sl_pct > self.max_sl_pct:
            return SafetyReport(
                False, f"SL_TOO_WIDE ({order.sl_pct:.2%} > {self.max_sl_pct:.2%})"
            )

        # 3. Position size — ajustement automatique (pas rejet)
        max_size = capital * self.max_position_pct
        adjusted_size = None
        effective_size = order.size_usdt
        if effective_size > max_size:
            logger.warning(
                f"SafetyKernel: Size ajustée {effective_size:.0f} → {max_size:.0f} USDT"
            )
            adjusted_size = max_size
            effective_size = max_size

        # 4. Nombre de positions ouvertes
        if len(self.open_positions) >= self.max_open_positions:
            return SafetyReport(
                False,
                f"MAX_POSITIONS ({len(self.open_positions)}/{self.max_open_positions})",
            )

        # 5. Corrélation BTC/ETH/BNB — éviter trop d'exposition crypto corrélée
        crypto_pairs = {"BTCUSDT", "ETHUSDT", "BNBUSDT"}
        crypto_positions = [p for p in self.open_positions if p.symbol in crypto_pairs]
        if order.symbol in crypto_pairs:
            if len(crypto_positions) >= self.max_correlated_positions:
                return SafetyReport(
                    False,
                    f"CORRELATED_OVEREXPOSURE (crypto: {len(crypto_positions)})",
                )

        # 6. [NOUVEAU] Plafonnement du notionnel global total
        if capital > 0:
            current_notional = sum(
                p.size_usdt * p.leverage for p in self.open_positions
            )
            new_notional = current_notional + effective_size * order.leverage
            max_notional = capital * self.max_total_notional_pct

            if new_notional > max_notional:
                remaining_notional = max_notional - current_notional
                if remaining_notional <= 0:
                    return SafetyReport(
                        False,
                        f"GLOBAL_NOTIONAL_EXCEEDED "
                        f"(current={current_notional:.0f}$, max={max_notional:.0f}$)",
                    )
                allowed_size = remaining_notional / order.leverage
                if allowed_size < effective_size:
                    logger.warning(
                        f"SafetyKernel: Notionnel global — size ajustée "
                        f"{effective_size:.0f} → {allowed_size:.0f} USDT"
                    )
                    adjusted_size = allowed_size
                    effective_size = allowed_size

        reason = "SIZE_ADJUSTED" if adjusted_size else "CLEARED"
        logger.info(
            f"SafetyKernel: ✅ {reason} — {order.symbol} {order.direction} "
            f"{effective_size:.0f}$ | SL:{order.sl_pct:.1%} | "
            f"Notionnel: {sum(p.size_usdt * p.leverage for p in self.open_positions):.0f}$"
        )
        return SafetyReport(True, reason, adjusted_size=adjusted_size, adjusted_leverage=order.leverage)

    def register_open(self, order: Order) -> None:
        """Enregistre une position ouverte en mémoire ET en DB."""
        self.open_positions.append(order)
        if self._repo:
            try:
                self._repo.save_position(order)
            except Exception as e:
                logger.warning(f"SafetyKernel: échec persistence position ({e})")

    def register_close(self, symbol: str) -> None:
        """Retire une position fermée de la mémoire ET de la DB."""
        self.open_positions = [p for p in self.open_positions if p.symbol != symbol]
        if self._repo:
            try:
                self._repo.remove_position(symbol)
            except Exception as e:
                logger.warning(f"SafetyKernel: échec suppression position DB ({e})")

    def reconcile(self, live_symbols: list[str]) -> None:
        """
        Réconciliation avec les positions réelles de l'exchange.
        Appelé au démarrage en mode live pour corriger les désynchronisations.
        """
        stale = [p for p in self.open_positions if p.symbol not in live_symbols]
        for p in stale:
            logger.warning(
                f"SafetyKernel: position stale supprimée "
                f"(non trouvée sur exchange) — {p.symbol}"
            )
            self.register_close(p.symbol)
        if stale:
            logger.info(
                f"SafetyKernel: réconciliation terminée — "
                f"{len(stale)} position(s) stale supprimée(s)"
            )

    def get_notional_usage(self, capital: float) -> dict:
        """Retourne le résumé de l'exposition globale notionnelle."""
        total_notional = sum(p.size_usdt * p.leverage for p in self.open_positions)
        max_notional = capital * self.max_total_notional_pct
        return {
            "total_notional": round(total_notional, 2),
            "max_notional": round(max_notional, 2),
            "usage_pct": round(total_notional / max_notional, 4) if max_notional > 0 else 0.0,
            "n_positions": len(self.open_positions),
        }
