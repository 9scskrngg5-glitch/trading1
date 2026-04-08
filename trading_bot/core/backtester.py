"""
Backtester — Simulation historique de la stratégie de trading.
Rejoue les candles OHLCV une par une à travers le pipeline complet :
  ScanAgent (scoring adaptatif) → RiskAgent (sizing ATR) → simulation SL/TP → métriques.

Supporte le multi-paire, l'export Obsidian (vault/backtest/) et la récupération
de données historiques via ccxt (Binance REST).

Usage CLI :
    python -m core.backtester
    python core/backtester.py
"""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from models.signals import SignalType, TechnicalSignal, MarketType
from models.orders import OrderSide
from models.learning import TradeOutcome, ExitReason, MarketRegime

logger = logging.getLogger(__name__)

# ── Constantes par défaut ────────────────────────────────────────────────────

RISK_FREE_RATE      = 0.045    # 4.5 % annuel (T-bills US)
TRADING_DAYS        = 252
DEFAULT_CAPITAL     = 10_000.0
DEFAULT_RISK_PCT    = 2.0      # % du capital par trade
MAX_POSITIONS       = 5
DEFAULT_SL_ATR_MULT = 1.5
DEFAULT_TP_RR_RATIO = 2.5
MIN_CONFIDENCE      = 40       # seuil minimum pour ouvrir un trade
SLIPPAGE_BPS        = 5.0      # slippage simulé (5 bps = 0.05 %)
FEE_PCT             = 0.075    # frais taker Binance (0.075 %)
MIN_BARS_WARMUP     = 60       # candles nécessaires pour les indicateurs


# ── Dataclasses résultat ─────────────────────────────────────────────────────

@dataclass
class BacktestTrade:
    """Enregistrement d'un trade simulé pendant le backtest."""
    order_id:       str
    asset:          str
    side:           OrderSide
    entry_price:    float
    exit_price:     float
    stop_loss:      float
    take_profit:    float
    quantity:       float
    entry_time:     datetime
    exit_time:      datetime
    exit_reason:    ExitReason
    pnl_pct:        float  = 0.0
    pnl_usd:        float  = 0.0
    is_win:         bool   = False
    confidence:     int    = 0
    fees_usd:       float  = 0.0
    slippage_bps:   float  = 0.0
    bars_held:      int    = 0
    max_favorable:  float  = 0.0   # meilleur P&L non réalisé (%)
    max_adverse:    float  = 0.0   # pire P&L non réalisé (%)

    def __post_init__(self):
        direction = 1.0 if self.side == OrderSide.BUY else -1.0
        self.pnl_pct = direction * (self.exit_price - self.entry_price) / self.entry_price * 100
        self.pnl_usd = self.pnl_pct / 100 * self.entry_price * self.quantity - self.fees_usd
        self.is_win  = self.pnl_usd > 0

    def to_trade_outcome(self) -> TradeOutcome:
        """Convertit en TradeOutcome pour compatibilité avec PerformanceTracker."""
        return TradeOutcome(
            order_id    = self.order_id,
            asset       = self.asset,
            side        = self.side,
            entry_price = self.entry_price,
            exit_price  = self.exit_price,
            stop_loss   = self.stop_loss,
            take_profit = self.take_profit,
            quantity    = self.quantity,
            entry_time  = self.entry_time,
            exit_time   = self.exit_time,
            exit_reason = self.exit_reason,
            exchange    = "backtest",
            confidence  = self.confidence,
            max_favorable = self.max_favorable,
            max_adverse   = self.max_adverse,
        )


@dataclass
class BacktestResult:
    """Résultat complet d'un backtest."""
    trades:         list[BacktestTrade]
    equity_curve:   list[float]
    metrics:        dict
    trade_log:      list[dict]
    pairs:          list[str]
    timeframe:      str
    start_date:     Optional[datetime] = None
    end_date:       Optional[datetime] = None
    initial_capital: float = DEFAULT_CAPITAL
    total_bars:     int    = 0

    def summary(self) -> str:
        """Résumé texte compact des résultats."""
        m = self.metrics
        lines = [
            f"══════ BACKTEST RÉSULTAT ══════",
            f"Paires        : {', '.join(self.pairs)}",
            f"Timeframe     : {self.timeframe}",
            f"Période       : {self.start_date} → {self.end_date}",
            f"Barres totales: {self.total_bars}",
            f"───────────────────────────────",
            f"Capital initial : ${self.initial_capital:,.2f}",
            f"Capital final   : ${m.get('capital_final', 0):,.2f}",
            f"Return total    : {m.get('total_return_pct', 0):+.2f}%",
            f"───────────────────────────────",
            f"Trades          : {m.get('total_trades', 0)}",
            f"Win Rate        : {m.get('win_rate', 0):.1%}",
            f"Profit Factor   : {m.get('profit_factor', 0):.2f}",
            f"Expectancy      : ${m.get('expectancy_usd', 0):+.2f}/trade",
            f"───────────────────────────────",
            f"Sharpe Ratio    : {m.get('sharpe_ratio', 0):.3f}",
            f"Sortino Ratio   : {m.get('sortino_ratio', 0):.3f}",
            f"Calmar Ratio    : {m.get('calmar_ratio', 0):.3f}",
            f"───────────────────────────────",
            f"Max Drawdown    : {m.get('max_drawdown_pct', 0):.2f}%",
            f"Avg Holding     : {m.get('avg_bars_held', 0):.0f} barres",
            f"══════════════════════════════",
        ]
        return "\n".join(lines)


# ── Position ouverte interne ─────────────────────────────────────────────────

@dataclass
class _OpenPosition:
    """Représentation interne d'une position ouverte pendant le backtest."""
    order_id:      str
    asset:         str
    side:          OrderSide
    entry_price:   float
    stop_loss:     float
    take_profit:   float
    quantity:      float
    entry_time:    datetime
    confidence:    int
    entry_bar_idx: int
    fees_entry:    float
    slippage_bps:  float
    max_favorable: float = 0.0
    max_adverse:   float = 0.0
    bars_held:     int   = 0


# ══════════════════════════════════════════════════════════════════════════════
#  Moteur de Backtest
# ══════════════════════════════════════════════════════════════════════════════

class Backtester:
    """
    Moteur de backtesting qui rejoue le pipeline de trading complet.

    Flux :
        1. Réception OHLCV historique (DataFrame par paire)
        2. Calcul des indicateurs (RSI, MACD, BB, ATR) — méthodes ScanAgent
        3. Scoring adaptatif (_adaptive_score) → génération de TechnicalSignal
        4. Sizing de position (ATR-based SL/TP, 2% risk/trade)
        5. Simulation du cycle de vie du trade (SL/TP hit sur chaque barre)
        6. Calcul des métriques PerformanceTracker
        7. Export Obsidian (vault/backtest/)

    Paramètres configurables :
        capital, risk_pct, sl_atr_mult, tp_rr_ratio, max_positions,
        min_confidence, slippage_bps, fee_pct, indicator_weights
    """

    def __init__(
        self,
        initial_capital: float = DEFAULT_CAPITAL,
        risk_pct:        float = DEFAULT_RISK_PCT,
        sl_atr_mult:     float = DEFAULT_SL_ATR_MULT,
        tp_rr_ratio:     float = DEFAULT_TP_RR_RATIO,
        max_positions:   int   = MAX_POSITIONS,
        min_confidence:  int   = MIN_CONFIDENCE,
        slippage_bps:    float = SLIPPAGE_BPS,
        fee_pct:         float = FEE_PCT,
        indicator_weights: Optional[dict[str, float]] = None,
    ):
        self.initial_capital = initial_capital
        self.risk_pct        = risk_pct
        self.sl_atr_mult     = sl_atr_mult
        self.tp_rr_ratio     = tp_rr_ratio
        self.max_positions   = max_positions
        self.min_confidence  = min_confidence
        self.slippage_bps    = slippage_bps
        self.fee_pct         = fee_pct

        # Poids adaptatifs des indicateurs (défauts neutres)
        self.weights = indicator_weights or {
            "w_rsi": 1.0, "w_macd": 1.0, "w_bb": 1.0, "w_vol": 1.0,
        }

        # État interne — réinitialisé à chaque run()
        self._capital:        float = initial_capital
        self._peak_capital:   float = initial_capital
        self._equity_curve:   list[float] = [initial_capital]
        self._open_positions: dict[str, _OpenPosition] = {}
        self._closed_trades:  list[BacktestTrade] = []
        self._trade_log:      list[dict] = []
        self._daily_returns:  list[float] = []

    # ── Point d'entrée principal ──────────────────────────────────────────────

    async def run(
        self,
        data: dict[str, pd.DataFrame],
        timeframe: str = "1h",
    ) -> BacktestResult:
        """
        Lance le backtest sur un ensemble de paires.

        Args:
            data:      Dict {paire: DataFrame OHLCV} avec colonnes :
                       timestamp, open, high, low, close, volume
            timeframe: Intervalle des candles ("1h", "4h", "1d")

        Returns:
            BacktestResult contenant trades, equity curve, métriques, log.
        """
        # Réinitialisation de l'état
        self._capital        = self.initial_capital
        self._peak_capital   = self.initial_capital
        self._equity_curve   = [self.initial_capital]
        self._open_positions = {}
        self._closed_trades  = []
        self._trade_log      = []
        self._daily_returns  = []

        pairs = list(data.keys())
        logger.info(
            "Démarrage backtest : %d paire(s) [%s] | Capital=$%.2f | TF=%s",
            len(pairs), ", ".join(pairs), self.initial_capital, timeframe,
        )

        # Pré-calcul des indicateurs pour chaque paire
        indicators: dict[str, pd.DataFrame] = {}
        for pair, df in data.items():
            indicators[pair] = self._compute_indicators(df)

        # Déterminer la plage commune d'indices
        min_len = min(len(df) for df in indicators.values())
        total_bars = min_len - MIN_BARS_WARMUP
        if total_bars <= 0:
            logger.warning("Pas assez de données pour le backtest (min %d barres)", MIN_BARS_WARMUP)
            return self._build_result(pairs, timeframe, data, total_bars=0)

        # Replay barre par barre
        for bar_idx in range(MIN_BARS_WARMUP, min_len):
            # 1. Vérifier SL/TP sur les positions ouvertes
            for pair in list(self._open_positions.keys()):
                df_pair = indicators[pair]
                if bar_idx < len(df_pair):
                    self._check_exit(pair, df_pair, bar_idx)

            # 2. Générer des signaux et ouvrir de nouvelles positions
            for pair in pairs:
                df_pair = indicators[pair]
                if bar_idx >= len(df_pair):
                    continue
                if pair in self._open_positions:
                    continue  # déjà en position sur cette paire
                if len(self._open_positions) >= self.max_positions:
                    continue  # max positions atteint

                signal = self._generate_signal(pair, df_pair, bar_idx, timeframe)
                if signal and signal.signal != SignalType.NEUTRAL:
                    if signal.confidence >= self.min_confidence:
                        self._open_position(signal, df_pair, bar_idx)

            # 3. Mettre à jour le max favorable / adverse des positions ouvertes
            for pair, pos in self._open_positions.items():
                df_pair = indicators[pair]
                if bar_idx < len(df_pair):
                    self._update_mfe_mae(pos, df_pair, bar_idx)
                    pos.bars_held += 1

            # 4. Enregistrer le point d'equity
            self._equity_curve.append(self._capital)

        # Fermer les positions restantes à la dernière barre
        for pair in list(self._open_positions.keys()):
            df_pair = indicators[pair]
            last_idx = min(min_len - 1, len(df_pair) - 1)
            self._force_close(pair, df_pair, last_idx, ExitReason.TIMEOUT)

        return self._build_result(pairs, timeframe, data, total_bars)

    # ── Indicateurs techniques (réutilisation ScanAgent) ─────────────────────

    @staticmethod
    def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Pré-calcule tous les indicateurs techniques sur le DataFrame OHLCV.
        Ajoute les colonnes : rsi, macd_hist, prev_macd_hist, bb_pos, vol_ratio, atr.
        """
        from agents.scan_agent import ScanAgent

        out = df.copy()
        close = out["close"]
        high  = out["high"]
        low   = out["low"]
        vol   = out["volume"]

        out["rsi"]       = ScanAgent._rsi(close)
        _, _, hist        = ScanAgent._macd(close)
        out["macd_hist"]  = hist
        out["prev_macd"]  = hist.shift(1)
        bb_up, _, bb_lo   = ScanAgent._bollinger(close)
        bb_range          = bb_up - bb_lo
        out["bb_pos"]     = (close - bb_lo) / bb_range.clip(lower=1e-9)
        out["atr"]        = ScanAgent._atr(high, low, close)

        # Volume ratio vs moyenne 20 périodes
        vol_ma = vol.rolling(20).mean()
        out["vol_ratio"] = vol / vol_ma.clip(lower=1e-9)

        return out

    # ── Génération de signal ─────────────────────────────────────────────────

    def _generate_signal(
        self,
        pair: str,
        df: pd.DataFrame,
        bar_idx: int,
        timeframe: str,
    ) -> Optional[TechnicalSignal]:
        """
        Génère un TechnicalSignal à partir de la barre courante.
        Utilise ScanAgent._adaptive_score() pour le scoring.
        """
        from agents.scan_agent import ScanAgent

        row = df.iloc[bar_idx]

        rsi_val       = float(row["rsi"])       if not pd.isna(row["rsi"])       else None
        macd_val      = float(row["macd_hist"]) if not pd.isna(row["macd_hist"]) else None
        prev_macd_val = float(row["prev_macd"]) if not pd.isna(row["prev_macd"]) else None
        bb_pos_val    = float(row["bb_pos"])     if not pd.isna(row["bb_pos"])     else None
        vol_ratio_val = float(row["vol_ratio"]) if not pd.isna(row["vol_ratio"]) else None
        atr_val       = float(row["atr"])        if not pd.isna(row["atr"])        else None

        # Valeurs requises pour le scoring
        if any(v is None for v in [rsi_val, macd_val, prev_macd_val, bb_pos_val, vol_ratio_val]):
            return None

        direction, confidence = ScanAgent._adaptive_score(
            rsi           = rsi_val,
            macd_hist     = macd_val,
            prev_macd_hist= prev_macd_val,
            bb_position   = bb_pos_val,
            vol_ratio     = vol_ratio_val,
            w_rsi         = self.weights.get("w_rsi", 1.0),
            w_macd        = self.weights.get("w_macd", 1.0),
            w_bb          = self.weights.get("w_bb", 1.0),
            w_vol         = self.weights.get("w_vol", 1.0),
        )

        last_close = float(row["close"])

        # Déterminer le type de marché
        forex_ccy = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"}
        parts = pair.replace("/", " ").upper().split()
        is_forex = len(set(parts) & forex_ccy) >= 2

        # Extraire le timestamp si disponible
        ts = datetime.now(timezone.utc)
        if "timestamp" in df.columns:
            ts_raw = row["timestamp"]
            if isinstance(ts_raw, (int, float)):
                ts = datetime.fromtimestamp(ts_raw / 1000, tz=timezone.utc)
            elif isinstance(ts_raw, datetime):
                ts = ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=timezone.utc)
            elif isinstance(ts_raw, pd.Timestamp):
                ts = ts_raw.to_pydatetime()
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)

        return TechnicalSignal(
            asset       = pair,
            signal      = direction,
            confidence  = confidence,
            timeframe   = timeframe,
            market      = MarketType.FOREX if is_forex else MarketType.CRYPTO,
            rsi         = round(rsi_val, 2),
            macd_hist   = round(macd_val, 6),
            bb_position = round(bb_pos_val, 3),
            volume_ratio= round(vol_ratio_val, 2),
            entry_price = round(last_close, 6),
            atr         = round(atr_val, 6) if atr_val else None,
            timestamp   = ts,
        )

    # ── Ouverture de position ────────────────────────────────────────────────

    def _open_position(
        self,
        signal: TechnicalSignal,
        df: pd.DataFrame,
        bar_idx: int,
    ) -> None:
        """
        Ouvre une position simulée avec sizing ATR (style RiskAgent).
        Applique le slippage à l'entrée.
        """
        entry_price = signal.entry_price
        atr_val     = signal.atr or (entry_price * 0.015)
        is_buy      = (signal.signal == SignalType.BULLISH)

        # Slippage à l'entrée
        slip_pct  = self.slippage_bps / 10_000
        if is_buy:
            entry_price *= (1 + slip_pct)
        else:
            entry_price *= (1 - slip_pct)

        # SL / TP basés sur ATR
        sl_dist = atr_val * self.sl_atr_mult
        tp_dist = sl_dist * self.tp_rr_ratio

        if is_buy:
            sl = entry_price - sl_dist
            tp = entry_price + tp_dist
        else:
            sl = entry_price + sl_dist
            tp = entry_price - tp_dist

        side = OrderSide.BUY if is_buy else OrderSide.SELL

        # Sizing : risque fixe en % du capital
        risk_usd    = self._capital * (self.risk_pct / 100)
        conf_factor = max(signal.confidence / 100, 0.5)
        qty         = risk_usd * conf_factor / max(sl_dist, 1e-9)

        if qty <= 0:
            return

        # Frais d'entrée
        fees_entry = entry_price * qty * (self.fee_pct / 100)
        self._capital -= fees_entry

        order_id = f"bt_{uuid.uuid4().hex[:8]}"

        pos = _OpenPosition(
            order_id      = order_id,
            asset         = signal.asset,
            side          = side,
            entry_price   = round(entry_price, 6),
            stop_loss     = round(sl, 6),
            take_profit   = round(tp, 6),
            quantity      = round(qty, 6),
            entry_time    = signal.timestamp,
            confidence    = signal.confidence,
            entry_bar_idx = bar_idx,
            fees_entry    = fees_entry,
            slippage_bps  = self.slippage_bps,
        )

        self._open_positions[signal.asset] = pos

        self._trade_log.append({
            "event":    "OPEN",
            "bar":      bar_idx,
            "asset":    signal.asset,
            "side":     side.value,
            "price":    pos.entry_price,
            "sl":       pos.stop_loss,
            "tp":       pos.take_profit,
            "qty":      pos.quantity,
            "conf":     signal.confidence,
            "capital":  round(self._capital, 2),
        })

        logger.debug(
            "OPEN %s %s @ %.6f | SL:%.6f TP:%.6f | qty:%.6f | conf:%d",
            side.value, signal.asset, pos.entry_price,
            pos.stop_loss, pos.take_profit, pos.quantity, signal.confidence,
        )

    # ── Vérification SL / TP ─────────────────────────────────────────────────

    def _check_exit(self, pair: str, df: pd.DataFrame, bar_idx: int) -> None:
        """
        Vérifie si le SL ou TP est touché sur la barre courante.
        Utilise le high/low de la barre pour une simulation réaliste.
        """
        pos = self._open_positions.get(pair)
        if not pos:
            return

        row  = df.iloc[bar_idx]
        high = float(row["high"])
        low  = float(row["low"])

        is_buy = (pos.side == OrderSide.BUY)

        # Vérification SL
        sl_hit = False
        tp_hit = False

        if is_buy:
            if low <= pos.stop_loss:
                sl_hit = True
            if high >= pos.take_profit:
                tp_hit = True
        else:  # SELL
            if high >= pos.stop_loss:
                sl_hit = True
            if low <= pos.take_profit:
                tp_hit = True

        # Si les deux sont touchés sur la même barre, on priorise le SL
        # (hypothèse conservatrice : le prix a d'abord touché le SL)
        if sl_hit:
            self._close_position(pair, pos.stop_loss, bar_idx, ExitReason.STOP_LOSS, df)
        elif tp_hit:
            self._close_position(pair, pos.take_profit, bar_idx, ExitReason.TAKE_PROFIT, df)

    # ── MFE / MAE (Max Favorable / Adverse Excursion) ────────────────────────

    @staticmethod
    def _update_mfe_mae(pos: _OpenPosition, df: pd.DataFrame, bar_idx: int) -> None:
        """Met à jour le max favorable et max adverse excursion."""
        row  = df.iloc[bar_idx]
        high = float(row["high"])
        low  = float(row["low"])

        if pos.side == OrderSide.BUY:
            favorable = (high - pos.entry_price) / pos.entry_price * 100
            adverse   = (pos.entry_price - low) / pos.entry_price * 100
        else:
            favorable = (pos.entry_price - low) / pos.entry_price * 100
            adverse   = (high - pos.entry_price) / pos.entry_price * 100

        pos.max_favorable = max(pos.max_favorable, favorable)
        pos.max_adverse   = max(pos.max_adverse, adverse)

    # ── Fermeture de position ────────────────────────────────────────────────

    def _close_position(
        self,
        pair: str,
        exit_price: float,
        bar_idx: int,
        reason: ExitReason,
        df: pd.DataFrame,
    ) -> None:
        """Ferme une position et enregistre le trade."""
        pos = self._open_positions.pop(pair, None)
        if not pos:
            return

        # Slippage à la sortie
        slip_pct = self.slippage_bps / 10_000
        if pos.side == OrderSide.BUY:
            exit_price *= (1 - slip_pct)   # on vend → slippage défavorable
        else:
            exit_price *= (1 + slip_pct)   # on rachète → slippage défavorable

        # Frais de sortie
        fees_exit = exit_price * pos.quantity * (self.fee_pct / 100)
        total_fees = pos.fees_entry + fees_exit

        # Extraire le timestamp de sortie
        exit_time = datetime.now(timezone.utc)
        if "timestamp" in df.columns:
            ts_raw = df.iloc[bar_idx]["timestamp"]
            if isinstance(ts_raw, (int, float)):
                exit_time = datetime.fromtimestamp(ts_raw / 1000, tz=timezone.utc)
            elif isinstance(ts_raw, datetime):
                exit_time = ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=timezone.utc)
            elif isinstance(ts_raw, pd.Timestamp):
                exit_time = ts_raw.to_pydatetime()
                if exit_time.tzinfo is None:
                    exit_time = exit_time.replace(tzinfo=timezone.utc)

        trade = BacktestTrade(
            order_id     = pos.order_id,
            asset        = pair,
            side         = pos.side,
            entry_price  = pos.entry_price,
            exit_price   = round(exit_price, 6),
            stop_loss    = pos.stop_loss,
            take_profit  = pos.take_profit,
            quantity     = pos.quantity,
            entry_time   = pos.entry_time,
            exit_time    = exit_time,
            exit_reason  = reason,
            confidence   = pos.confidence,
            fees_usd     = total_fees,
            slippage_bps = pos.slippage_bps,
            bars_held    = pos.bars_held,
            max_favorable= pos.max_favorable,
            max_adverse  = pos.max_adverse,
        )

        # Mise à jour du capital
        self._capital += trade.pnl_usd
        if self._capital > self._peak_capital:
            self._peak_capital = self._capital

        self._closed_trades.append(trade)

        # Return journalier approximatif
        days = max(trade.bars_held / 24, 1 / 24)   # hypothèse 1h = 1 barre
        daily_ret = trade.pnl_pct / 100 / days
        self._daily_returns.append(daily_ret)

        self._trade_log.append({
            "event":    "CLOSE",
            "bar":      bar_idx,
            "asset":    pair,
            "side":     pos.side.value,
            "entry":    pos.entry_price,
            "exit":     round(exit_price, 6),
            "reason":   reason.value,
            "pnl_pct":  round(trade.pnl_pct, 4),
            "pnl_usd":  round(trade.pnl_usd, 2),
            "fees":     round(total_fees, 4),
            "bars":     trade.bars_held,
            "capital":  round(self._capital, 2),
        })

        logger.debug(
            "CLOSE %s %s @ %.6f → %.6f | %s | P&L: %+.2f%% ($%+.2f)",
            pos.side.value, pair, pos.entry_price, exit_price,
            reason.value, trade.pnl_pct, trade.pnl_usd,
        )

    def _force_close(
        self,
        pair: str,
        df: pd.DataFrame,
        bar_idx: int,
        reason: ExitReason,
    ) -> None:
        """Fermeture forcée au prix de clôture de la dernière barre."""
        close_price = float(df.iloc[bar_idx]["close"])
        self._close_position(pair, close_price, bar_idx, reason, df)

    # ── Calcul des métriques ─────────────────────────────────────────────────

    def _compute_metrics(self) -> dict:
        """Calcule toutes les métriques de performance (style PerformanceTracker)."""
        trades = self._closed_trades
        n = len(trades)

        if n == 0:
            return {
                "total_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
                "expectancy_usd": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0,
                "calmar_ratio": 0.0, "max_drawdown_pct": 0.0, "total_return_pct": 0.0,
                "capital_final": self._capital, "total_fees_usd": 0.0,
                "avg_bars_held": 0, "avg_pnl_pct": 0.0,
                "best_trade_pct": 0.0, "worst_trade_pct": 0.0,
                "max_consecutive_wins": 0, "max_consecutive_losses": 0,
                "long_trades": 0, "short_trades": 0,
                "long_win_rate": 0.0, "short_win_rate": 0.0,
            }

        wins   = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]
        longs  = [t for t in trades if t.side == OrderSide.BUY]
        shorts = [t for t in trades if t.side == OrderSide.SELL]

        # Win Rate
        win_rate = len(wins) / n

        # Profit Factor
        gross_profit = sum(t.pnl_usd for t in wins) if wins else 0.0
        gross_loss   = abs(sum(t.pnl_usd for t in losses)) if losses else 0.001
        profit_factor = gross_profit / max(gross_loss, 0.001)

        # Expectancy
        expectancy = sum(t.pnl_usd for t in trades) / n

        # Drawdown max sur l'equity curve
        eq = np.array(self._equity_curve)
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / np.maximum(peak, 1e-9) * 100
        max_dd = float(dd.max())

        # Sharpe Ratio
        sharpe = 0.0
        if len(self._daily_returns) >= 10:
            rets = np.array(self._daily_returns)
            excess = rets - RISK_FREE_RATE / TRADING_DAYS
            std = rets.std()
            if std > 1e-9:
                sharpe = float(excess.mean() / std * math.sqrt(TRADING_DAYS))

        # Sortino Ratio
        sortino = 0.0
        if len(self._daily_returns) >= 10:
            rets = np.array(self._daily_returns)
            excess = rets - RISK_FREE_RATE / TRADING_DAYS
            neg_rets = rets[rets < 0]
            if len(neg_rets) > 0:
                ds = neg_rets.std()
                if ds > 1e-9:
                    sortino = float(excess.mean() / ds * math.sqrt(TRADING_DAYS))

        # Calmar Ratio
        total_return = (self._capital - self.initial_capital) / self.initial_capital * 100
        calmar = total_return / max(max_dd, 0.001)

        # Séquences consécutives
        max_wins = max_losses = cur_wins = cur_losses = 0
        for t in trades:
            if t.is_win:
                cur_wins += 1
                cur_losses = 0
                max_wins = max(max_wins, cur_wins)
            else:
                cur_losses += 1
                cur_wins = 0
                max_losses = max(max_losses, cur_losses)

        # Win rate par direction
        long_wr  = sum(1 for t in longs if t.is_win) / max(len(longs), 1)
        short_wr = sum(1 for t in shorts if t.is_win) / max(len(shorts), 1)

        return {
            "total_trades":           n,
            "win_rate":               round(win_rate, 4),
            "profit_factor":          round(profit_factor, 3),
            "expectancy_usd":         round(expectancy, 2),
            "sharpe_ratio":           round(sharpe, 3),
            "sortino_ratio":          round(sortino, 3),
            "calmar_ratio":           round(calmar, 3),
            "max_drawdown_pct":       round(max_dd, 2),
            "total_return_pct":       round(total_return, 2),
            "capital_final":          round(self._capital, 2),
            "total_fees_usd":         round(sum(t.fees_usd for t in trades), 2),
            "avg_bars_held":          round(sum(t.bars_held for t in trades) / n, 1),
            "avg_pnl_pct":            round(sum(t.pnl_pct for t in trades) / n, 4),
            "best_trade_pct":         round(max(t.pnl_pct for t in trades), 4),
            "worst_trade_pct":        round(min(t.pnl_pct for t in trades), 4),
            "max_consecutive_wins":   max_wins,
            "max_consecutive_losses": max_losses,
            "long_trades":            len(longs),
            "short_trades":           len(shorts),
            "long_win_rate":          round(long_wr, 4),
            "short_win_rate":         round(short_wr, 4),
        }

    # ── Construction du résultat ─────────────────────────────────────────────

    def _build_result(
        self,
        pairs: list[str],
        timeframe: str,
        data: dict[str, pd.DataFrame],
        total_bars: int,
    ) -> BacktestResult:
        """Construit le BacktestResult final."""
        metrics = self._compute_metrics()

        # Extraire les dates de début et fin
        start_date = end_date = None
        for df in data.values():
            if "timestamp" in df.columns and len(df) > 0:
                ts_first = df.iloc[0]["timestamp"]
                ts_last  = df.iloc[-1]["timestamp"]
                if isinstance(ts_first, (int, float)):
                    start_date = datetime.fromtimestamp(ts_first / 1000, tz=timezone.utc)
                    end_date   = datetime.fromtimestamp(ts_last / 1000, tz=timezone.utc)
                elif isinstance(ts_first, (datetime, pd.Timestamp)):
                    start_date = pd.Timestamp(ts_first).to_pydatetime()
                    end_date   = pd.Timestamp(ts_last).to_pydatetime()
                break

        return BacktestResult(
            trades          = self._closed_trades,
            equity_curve    = self._equity_curve,
            metrics         = metrics,
            trade_log       = self._trade_log,
            pairs           = pairs,
            timeframe       = timeframe,
            start_date      = start_date,
            end_date        = end_date,
            initial_capital = self.initial_capital,
            total_bars      = total_bars,
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  Récupération de données historiques (Binance via ccxt)
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def fetch_historical_data(
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        days: int = 365,
        exchange_id: str = "binance",
    ) -> pd.DataFrame:
        """
        Récupère les données OHLCV historiques depuis Binance via ccxt.

        Pagine automatiquement pour récupérer de grandes quantités de données
        (ccxt retourne max ~1000 candles par requête).

        Args:
            symbol:      Paire de trading (ex: "BTC/USDT")
            timeframe:   Intervalle ("1m", "5m", "15m", "1h", "4h", "1d")
            days:        Nombre de jours d'historique
            exchange_id: Identifiant de l'exchange ccxt

        Returns:
            DataFrame avec colonnes : timestamp, open, high, low, close, volume
        """
        try:
            import ccxt.async_support as ccxt
        except ImportError:
            raise ImportError(
                "ccxt est requis pour la récupération de données. "
                "Installez-le avec : pip install ccxt"
            )

        exchange_class = getattr(ccxt, exchange_id, None)
        if not exchange_class:
            raise ValueError(f"Exchange '{exchange_id}' non supporté par ccxt")

        exchange = exchange_class({"enableRateLimit": True})

        try:
            # Calcul du timestamp de départ
            since_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

            # Mapping timeframe → durée en ms
            tf_ms_map = {
                "1m": 60_000, "3m": 180_000, "5m": 300_000,
                "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000,
                "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
                "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000,
                "1w": 604_800_000,
            }
            tf_ms = tf_ms_map.get(timeframe, 3_600_000)
            limit_per_request = 1000

            all_candles: list = []
            current_since = since_ms

            logger.info(
                "Récupération %s %s depuis %d jours (%s)...",
                symbol, timeframe, days, exchange_id,
            )

            while True:
                candles = await exchange.fetch_ohlcv(
                    symbol, timeframe, since=current_since, limit=limit_per_request,
                )
                if not candles:
                    break

                all_candles.extend(candles)
                logger.debug(
                    "  ... %d candles récupérées (total: %d)",
                    len(candles), len(all_candles),
                )

                # Avancer le curseur temporel
                last_ts = candles[-1][0]
                current_since = last_ts + tf_ms

                # Si on a reçu moins que le max, on a tout récupéré
                if len(candles) < limit_per_request:
                    break

                # Pause pour respecter le rate limit
                await asyncio.sleep(exchange.rateLimit / 1000)

            logger.info("Total : %d candles %s pour %s", len(all_candles), timeframe, symbol)

        finally:
            await exchange.close()

        if not all_candles:
            raise ValueError(f"Aucune donnée récupérée pour {symbol} {timeframe}")

        df = pd.DataFrame(
            all_candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )

        # Supprimer les doublons éventuels
        df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)

        logger.info(
            "DataFrame prêt : %d lignes | %s → %s",
            len(df),
            datetime.fromtimestamp(df.iloc[0]["timestamp"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
            datetime.fromtimestamp(df.iloc[-1]["timestamp"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
        )

        return df

    # ══════════════════════════════════════════════════════════════════════════
    #  Export Obsidian (vault/backtest/)
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def write_obsidian_report(
        result: BacktestResult,
        vault_path: str | Path = "vault",
    ) -> Path:
        """
        Écrit le rapport de backtest en Markdown Obsidian dans vault/backtest/.

        Args:
            result:     BacktestResult du backtest
            vault_path: Chemin vers le vault Obsidian

        Returns:
            Path du fichier créé.
        """
        vault = Path(vault_path).resolve()
        bt_dir = vault / "backtest"
        bt_dir.mkdir(parents=True, exist_ok=True)

        m = result.metrics
        ts = datetime.now(timezone.utc)
        pairs_str = "_".join(p.replace("/", "-") for p in result.pairs)
        filename = f"bt_{ts.strftime('%Y-%m-%d_%H%M')}_{pairs_str}"
        filepath = bt_dir / f"{filename}.md"

        # Frontmatter YAML
        import yaml
        frontmatter = {
            "date":          ts.strftime("%Y-%m-%d %H:%M UTC"),
            "type":          "backtest",
            "pairs":         result.pairs,
            "timeframe":     result.timeframe,
            "start_date":    result.start_date.isoformat() if result.start_date else "?",
            "end_date":      result.end_date.isoformat() if result.end_date else "?",
            "capital_initial": result.initial_capital,
            "capital_final":   m.get("capital_final", 0),
            "total_return":    m.get("total_return_pct", 0),
            "sharpe":          m.get("sharpe_ratio", 0),
            "sortino":         m.get("sortino_ratio", 0),
            "calmar":          m.get("calmar_ratio", 0),
            "max_drawdown":    m.get("max_drawdown_pct", 0),
            "win_rate":        m.get("win_rate", 0),
            "total_trades":    m.get("total_trades", 0),
            "tags":            ["backtest", "performance", "strategie"],
        }
        fm_block = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Résumé des trades par paire
        trades_by_pair: dict[str, list[BacktestTrade]] = {}
        for t in result.trades:
            trades_by_pair.setdefault(t.asset, []).append(t)

        pair_rows = ""
        for pair, trades in trades_by_pair.items():
            n_t   = len(trades)
            n_w   = sum(1 for t in trades if t.is_win)
            wr    = n_w / max(n_t, 1)
            pnl   = sum(t.pnl_usd for t in trades)
            pair_rows += f"| {pair} | {n_t} | {wr:.1%} | ${pnl:+,.2f} |\n"

        # 10 derniers trades (ou tous si < 10)
        recent_trades = result.trades[-10:] if len(result.trades) > 10 else result.trades
        trade_rows = ""
        for t in recent_trades:
            icon = "W" if t.is_win else "L"
            trade_rows += (
                f"| {icon} | {t.asset} | {t.side.value} | "
                f"`{t.entry_price:.2f}` | `{t.exit_price:.2f}` | "
                f"`{t.pnl_pct:+.2f}%` | `${t.pnl_usd:+.2f}` | "
                f"{t.exit_reason.value} | {t.bars_held} |\n"
            )

        # Distribution des exits
        sl_count = sum(1 for t in result.trades if t.exit_reason == ExitReason.STOP_LOSS)
        tp_count = sum(1 for t in result.trades if t.exit_reason == ExitReason.TAKE_PROFIT)
        to_count = sum(1 for t in result.trades if t.exit_reason == ExitReason.TIMEOUT)
        total_t  = max(len(result.trades), 1)

        # Equity curve résumé (10 points)
        eq = result.equity_curve
        eq_step = max(len(eq) // 10, 1)
        eq_samples = [eq[i] for i in range(0, len(eq), eq_step)]

        content = f"""## Rapport de Backtest — {', '.join(result.pairs)}

> **Timeframe** : `{result.timeframe}` | **Période** : {result.start_date} → {result.end_date}
> **Barres traitées** : {result.total_bars} | **Trades exécutés** : {m.get('total_trades', 0)}

---

### Métriques Financières
| Métrique | Valeur | Benchmark |
|---|---|---|
| Capital initial | `${result.initial_capital:,.2f}` | — |
| Capital final | `${m.get('capital_final', 0):,.2f}` | — |
| Return total | `{m.get('total_return_pct', 0):+.2f}%` | > 0% |
| Win Rate | `{m.get('win_rate', 0):.1%}` | > 50% |
| Profit Factor | `{m.get('profit_factor', 0):.2f}` | > 1.5 |
| Expectancy | `${m.get('expectancy_usd', 0):+.2f}/trade` | > $0 |
| Sharpe Ratio | `{m.get('sharpe_ratio', 0):.3f}` | > 1.0 |
| Sortino Ratio | `{m.get('sortino_ratio', 0):.3f}` | > 1.5 |
| Calmar Ratio | `{m.get('calmar_ratio', 0):.3f}` | > 0.5 |
| Max Drawdown | `{m.get('max_drawdown_pct', 0):.2f}%` | < 15% |
| Frais totaux | `${m.get('total_fees_usd', 0):,.2f}` | — |

### Statistiques Directionnelles
| Direction | Trades | Win Rate |
|---|---|---|
| LONG | {m.get('long_trades', 0)} | {m.get('long_win_rate', 0):.1%} |
| SHORT | {m.get('short_trades', 0)} | {m.get('short_win_rate', 0):.1%} |

### Distribution des Sorties
| Type | Count | % |
|---|---|---|
| Stop-Loss | {sl_count} | {sl_count/total_t:.0%} |
| Take-Profit | {tp_count} | {tp_count/total_t:.0%} |
| Timeout | {to_count} | {to_count/total_t:.0%} |

### Séquences
| Métrique | Valeur |
|---|---|
| Max wins consécutifs | {m.get('max_consecutive_wins', 0)} |
| Max losses consécutifs | {m.get('max_consecutive_losses', 0)} |
| Meilleur trade | `{m.get('best_trade_pct', 0):+.2f}%` |
| Pire trade | `{m.get('worst_trade_pct', 0):+.2f}%` |
| Durée moy. (barres) | `{m.get('avg_bars_held', 0):.0f}` |

### Performance par Paire
| Paire | Trades | Win Rate | P&L |
|---|---|---|---|
{pair_rows}

### Derniers Trades
| Res | Paire | Dir | Entrée | Sortie | P&L% | P&L$ | Raison | Barres |
|---|---|---|---|---|---|---|---|---|
{trade_rows}

### Equity Curve (échantillons)
```
{' → '.join(f'${v:,.0f}' for v in eq_samples)}
```

### Paramètres du Backtest
| Paramètre | Valeur |
|---|---|
| Capital initial | `${result.initial_capital:,.2f}` |
| Risque / trade | `{DEFAULT_RISK_PCT}%` |
| SL multiplier | `{DEFAULT_SL_ATR_MULT}x ATR` |
| TP ratio | `1:{DEFAULT_TP_RR_RATIO}` |
| Max positions | `{MAX_POSITIONS}` |
| Slippage | `{SLIPPAGE_BPS} bps` |
| Frais taker | `{FEE_PCT}%` |
| Confiance minimum | `{MIN_CONFIDENCE}/100` |

---
*Backtest généré le {ts.strftime('%Y-%m-%d %H:%M UTC')}*
"""

        text = f"---\n{fm_block}---\n\n{content}"
        filepath.write_text(text, encoding="utf-8")
        logger.info("Rapport Obsidian écrit : %s", filepath)
        return filepath


# ══════════════════════════════════════════════════════════════════════════════
#  Point d'entrée CLI
# ══════════════════════════════════════════════════════════════════════════════

async def run_backtest():
    """
    Point d'entrée CLI : récupère 1 an de BTC/USDT 1h et lance le backtest.
    Écrit le rapport dans vault/backtest/.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    symbol    = "BTC/USDT"
    timeframe = "1h"
    days      = 365

    print(f"\n{'═'*60}")
    print(f"  BACKTEST — {symbol} {timeframe} ({days} jours)")
    print(f"{'═'*60}\n")

    # 1. Récupération des données historiques
    print("[1/4] Récupération des données historiques via Binance...")
    try:
        df = await Backtester.fetch_historical_data(
            symbol=symbol, timeframe=timeframe, days=days,
        )
        print(f"      {len(df)} candles récupérées.")
    except ImportError:
        print("      ccxt non installé — génération de données simulées...")
        df = _generate_simulated_data(symbol, timeframe, days)
        print(f"      {len(df)} candles simulées.")
    except Exception as exc:
        print(f"      Erreur ccxt ({exc}) — génération de données simulées...")
        df = _generate_simulated_data(symbol, timeframe, days)
        print(f"      {len(df)} candles simulées.")

    # 2. Configuration du backtester
    print("[2/4] Configuration du moteur de backtest...")
    bt = Backtester(
        initial_capital = 10_000.0,
        risk_pct        = 2.0,
        sl_atr_mult     = 1.5,
        tp_rr_ratio     = 2.5,
        max_positions   = 5,
        min_confidence  = 40,
        slippage_bps    = 5.0,
        fee_pct         = 0.075,
    )

    # 3. Exécution du backtest
    print("[3/4] Exécution du backtest...")
    result = await bt.run(
        data={symbol: df},
        timeframe=timeframe,
    )

    # 4. Résultats
    print("[4/4] Résultats :\n")
    print(result.summary())

    # Écriture du rapport Obsidian
    vault_path = Path(__file__).resolve().parent.parent / "vault"
    report_path = Backtester.write_obsidian_report(result, vault_path)
    print(f"\nRapport Obsidian : {report_path}")


def _generate_simulated_data(
    symbol: str,
    timeframe: str,
    days: int,
) -> pd.DataFrame:
    """
    Génère des données OHLCV simulées réalistes pour les tests.
    Utilisé comme fallback si ccxt n'est pas disponible.
    """
    tf_hours = {"1m": 1/60, "5m": 5/60, "15m": 0.25, "30m": 0.5,
                "1h": 1, "2h": 2, "4h": 4, "1d": 24, "1w": 168}
    hours_per_candle = tf_hours.get(timeframe, 1)
    n_candles = int(days * 24 / hours_per_candle)

    rng = np.random.default_rng(42)

    # Prix de départ selon le symbole
    base_prices = {
        "BTC/USDT": 42000.0, "ETH/USDT": 2200.0, "SOL/USDT": 100.0,
        "BNB/USDT": 300.0,
    }
    base = base_prices.get(symbol, 100.0)

    # Simulation avec tendance + mean-reversion + volatilité variable
    returns = rng.normal(0.0001, 0.008, n_candles)

    # Ajouter des régimes de tendance
    regime_len = n_candles // 6
    for i in range(0, n_candles, regime_len):
        drift = rng.choice([-0.002, -0.001, 0, 0.001, 0.002])
        end = min(i + regime_len, n_candles)
        returns[i:end] += drift

    closes = base * np.cumprod(1 + np.clip(returns, -0.08, 0.08))

    # Génération OHLC réaliste
    spread = closes * rng.uniform(0.001, 0.004, n_candles)
    highs  = closes + np.abs(rng.normal(0, spread))
    lows   = closes - np.abs(rng.normal(0, spread))
    opens  = closes * (1 + rng.normal(0, 0.001, n_candles))
    volume = rng.uniform(500, 5000, n_candles) * (base / 100)

    # Timestamps
    start_ts = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    tf_ms = int(hours_per_candle * 3_600_000)
    timestamps = [start_ts + i * tf_ms for i in range(n_candles)]

    return pd.DataFrame({
        "timestamp": timestamps,
        "open":      opens,
        "high":      highs,
        "low":       lows,
        "close":     closes,
        "volume":    volume,
    })


if __name__ == "__main__":
    asyncio.run(run_backtest())
