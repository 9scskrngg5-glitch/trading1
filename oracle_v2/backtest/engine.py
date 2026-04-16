"""
BacktestEngine — Moteur de backtest vectorisé ORACLE v2.

Simule les signaux RSI+MACD sur 90 jours de bougies 5min (≈ 25 920 candles).
Utilise numpy pour le calcul vectorisé, pandas optionnel pour le chargement CSV.

Usage:
    engine = BacktestEngine(sl_pct=0.01, tp_pct=0.025)
    ohlcv = [{"open": ..., "high": ..., "low": ..., "close": ..., "volume": ..., "ts": ...}, ...]
    result = engine.run(ohlcv, symbol="BTCUSDT")
    print(result)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

import numpy as np

logger = logging.getLogger("ORACLE.Backtest")

# ─── Configuration par défaut ──────────────────────────────────────────────────
_DEFAULT_DAYS = 90
_RSI_PERIOD = 14
_EMA_FAST = 12
_EMA_SLOW = 26
_MACD_SIGNAL = 9
_RSI_LONG = 35.0
_RSI_SHORT = 65.0


# ─── Résultat ─────────────────────────────────────────────────────────────────

@dataclass
class BacktestTrade:
    entry_idx: int
    direction: str      # "LONG" | "SHORT"
    entry_price: float
    exit_price: float
    pnl_pct: float
    bars_held: int


@dataclass
class BacktestResult:
    symbol: str
    period_days: int
    n_candles: int
    n_trades: int
    win_rate: float
    pnl_pct: float          # PnL total cumulé
    max_drawdown: float
    sharpe_ratio: float
    best_trade: float
    worst_trade: float
    trades: List[BacktestTrade] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Backtest {self.symbol} [{self.period_days}j | {self.n_candles} candles]\n"
            f"  Trades  : {self.n_trades} | WR {self.win_rate:.1%} | PnL {self.pnl_pct:+.2%}\n"
            f"  Drawdown: {self.max_drawdown:.2%} | Sharpe: {self.sharpe_ratio:.2f}\n"
            f"  Best/Worst: {self.best_trade:+.2%} / {self.worst_trade:+.2%}"
        )


# ─── BacktestEngine ───────────────────────────────────────────────────────────

class BacktestEngine:
    """
    Moteur vectorisé sur 90 jours.

    Génère des signaux RSI+MACD sur la série complète, puis simule
    chaque trade avec SL fixe / TP fixe et commission ronde.
    """

    def __init__(
        self,
        sl_pct: float = 0.01,
        tp_pct: float = 0.025,
        commission: float = 0.001,
        rsi_long: float = _RSI_LONG,
        rsi_short: float = _RSI_SHORT,
    ):
        self.sl_pct = sl_pct
        self.tp_pct = tp_pct
        self.commission = commission
        self.rsi_long = rsi_long
        self.rsi_short = rsi_short

    # ── Indicateurs vectorisés ────────────────────────────────────────

    @staticmethod
    def _ema_series(closes: np.ndarray, period: int) -> np.ndarray:
        """EMA vectorisée — O(n)."""
        k = 2.0 / (period + 1)
        ema = np.empty(len(closes))
        ema[:period] = np.nan
        ema[period - 1] = closes[:period].mean()
        for i in range(period, len(closes)):
            ema[i] = closes[i] * k + ema[i - 1] * (1 - k)
        return ema

    @staticmethod
    def _rsi_series(closes: np.ndarray, period: int = _RSI_PERIOD) -> np.ndarray:
        """RSI vectorisé — Wilder smoothing."""
        delta = np.diff(closes, prepend=closes[0])
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)

        avg_gain = np.empty(len(closes))
        avg_loss = np.empty(len(closes))
        avg_gain[:] = np.nan
        avg_loss[:] = np.nan

        avg_gain[period] = gain[1:period + 1].mean()
        avg_loss[period] = loss[1:period + 1].mean()

        for i in range(period + 1, len(closes)):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period

        rs = np.where(avg_loss == 0, np.inf, avg_gain / avg_loss)
        rsi = 100 - (100 / (1 + rs))
        rsi[:period] = 50.0  # valeur neutre pour les candles sans data
        return rsi

    def _macd_signal_series(self, closes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Retourne (macd_line, signal_line) — séries complètes."""
        ema_f = self._ema_series(closes, _EMA_FAST)
        ema_s = self._ema_series(closes, _EMA_SLOW)
        macd = ema_f - ema_s
        # Signal = EMA9 de MACD, en ignorant les NaN initiaux
        signal = self._ema_series(np.where(np.isnan(macd), 0.0, macd), _MACD_SIGNAL)
        return macd, signal

    # ── Génération des signaux ────────────────────────────────────────

    def _generate_signals(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
    ) -> list[tuple[int, str]]:
        """
        Retourne [(idx, "LONG"|"SHORT"), ...] pour toutes les bougies
        qui satisfont les conditions RSI+MACD.

        L'anti-chevauchement (une seule position ouverte à la fois)
        est géré dans run() avec next_valid_entry.
        """
        rsi = self._rsi_series(closes)
        macd, sig = self._macd_signal_series(closes)

        warmup = max(_RSI_PERIOD, _EMA_SLOW + _MACD_SIGNAL) + 2

        long_mask = (rsi < self.rsi_long) & (macd > sig)
        short_mask = (rsi > self.rsi_short) & (macd < sig)

        signals = []
        for i in range(warmup, len(closes)):
            if long_mask[i]:
                signals.append((i, "LONG"))
            elif short_mask[i]:
                signals.append((i, "SHORT"))

        return signals

    # ── Simulation d'un trade ─────────────────────────────────────────

    def _simulate_trade(
        self,
        entry_idx: int,
        direction: str,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
    ) -> BacktestTrade:
        """Simule un trade SL/TP en cherchant le premier niveau touché."""
        entry = closes[entry_idx]
        if direction == "LONG":
            tp = entry * (1 + self.tp_pct)
            sl = entry * (1 - self.sl_pct)
        else:
            tp = entry * (1 - self.tp_pct)
            sl = entry * (1 + self.sl_pct)

        future_h = highs[entry_idx + 1:]
        future_l = lows[entry_idx + 1:]

        if direction == "LONG":
            tp_hits = np.where(future_h >= tp)[0]
            sl_hits = np.where(future_l <= sl)[0]
        else:
            tp_hits = np.where(future_l <= tp)[0]
            sl_hits = np.where(future_h >= sl)[0]

        tp_bar = tp_hits[0] if len(tp_hits) > 0 else len(closes)
        sl_bar = sl_hits[0] if len(sl_hits) > 0 else len(closes)

        if tp_bar <= sl_bar and tp_bar < len(closes):
            # TP touché en premier — gain symétrique LONG et SHORT
            pnl = self.tp_pct - self.commission * 2
            exit_price = tp
            bars = tp_bar + 1
        elif sl_bar < tp_bar and sl_bar < len(closes):
            # SL touché en premier — perte symétrique LONG et SHORT
            pnl = -self.sl_pct - self.commission * 2
            exit_price = sl
            bars = sl_bar + 1
        else:
            # Position tenue jusqu'à la fin des données
            final_price = closes[-1]
            pnl = (
                (final_price - entry) / entry
                if direction == "LONG"
                else (entry - final_price) / entry
            ) - self.commission * 2
            exit_price = final_price
            bars = len(closes) - entry_idx - 1

        return BacktestTrade(
            entry_idx=entry_idx,
            direction=direction,
            entry_price=entry,
            exit_price=exit_price,
            pnl_pct=pnl,
            bars_held=bars,
        )

    # ── Métriques ─────────────────────────────────────────────────────

    def _equity_curve(self, trades: list, closes: np.ndarray) -> np.ndarray:
        """
        Courbe d'équité bar-à-bar à partir des trades non-chevauchants.

        - Entre les trades  : équité stable (pas de position ouverte).
        - Pendant un trade  : PnL latent calculé sur le close de chaque bougie.
        - À la clôture      : PnL réalisé verrouillé.

        Retourne un tableau de longueur len(closes).
        """
        n = len(closes)
        equity = np.ones(n)
        running = 1.0
        last_exit = 0

        for trade in sorted(trades, key=lambda t: t.entry_idx):
            entry = trade.entry_idx
            exit_bar = min(entry + trade.bars_held, n - 1)
            entry_price = trade.entry_price

            # Période sans position : équité plate
            if entry > last_exit:
                equity[last_exit:entry] = running

            # Période avec position ouverte : PnL latent vectorisé
            c = closes[entry:exit_bar + 1]
            if trade.direction == "LONG":
                unrealized = (c - entry_price) / entry_price
            else:
                unrealized = (entry_price - c) / entry_price
            equity[entry:exit_bar + 1] = running * (1 + unrealized - self.commission)

            # Clôture : verrouillage du PnL réalisé
            running = running * (1 + trade.pnl_pct)
            last_exit = exit_bar + 1

        # Après le dernier trade : équité plate
        equity[last_exit:] = running
        return equity

    @staticmethod
    def _max_drawdown(equity: np.ndarray) -> float:
        """Drawdown maximal sur la courbe d'équité bar-à-bar."""
        if len(equity) == 0:
            return 0.0
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / np.where(peak == 0, 1.0, peak)
        return float(np.min(drawdown))

    @staticmethod
    def _sharpe(pnl_series: np.ndarray, period_days: int = 90) -> float:
        """
        Sharpe annualisé basé sur la fréquence réelle des trades.

        Annualisation : √(trades_par_an) où trades_par_an = n / période_en_jours × 365.
        Cela évite la sur-annualisation qui survenait en appliquant le nombre
        de bougies 5min/an à des rendements par-trade.
        """
        n = len(pnl_series)
        if n < 2:
            return 0.0
        mean = np.mean(pnl_series)
        std = np.std(pnl_series, ddof=1)
        if std < 1e-10:
            return 0.0
        trades_per_year = n / max(period_days, 1) * 365
        return float(mean / std * np.sqrt(trades_per_year))

    # ── Point d'entrée public ─────────────────────────────────────────

    def run(self, ohlcv: list, symbol: str = "BTCUSDT") -> BacktestResult:
        """
        Lance le backtest sur les données fournies.

        ohlcv : liste de dict avec clés open/high/low/close/volume/(ts optionnel).
                 Doit couvrir au minimum quelques jours; idéalement 90j de 5min.
        """
        if not ohlcv:
            logger.warning("BacktestEngine.run(): liste OHLCV vide")
            return BacktestResult(symbol, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        closes = np.array([c["close"] for c in ohlcv], dtype=float)
        highs = np.array([c["high"] for c in ohlcv], dtype=float)
        lows = np.array([c["low"] for c in ohlcv], dtype=float)

        n = len(closes)
        # Estimation du nombre de jours (5min = 12 candles/h = 288/jour)
        period_days = max(1, round(n / 288))

        all_signals = self._generate_signals(closes, highs, lows)
        logger.info(f"[Backtest] {symbol}: {n} candles | {len(all_signals)} signaux candidats")

        # Simulation sans chevauchement : on n'entre pas dans un nouveau
        # trade tant que le précédent n'est pas clôturé.
        trades: list[BacktestTrade] = []
        next_valid_entry = 0

        for idx, direction in all_signals:
            if idx < next_valid_entry or idx + 1 >= n:
                continue
            trade = self._simulate_trade(idx, direction, closes, highs, lows)
            trades.append(trade)
            next_valid_entry = idx + trade.bars_held + 1  # ré-entrée interdite pendant le trade

        logger.info(f"[Backtest] {symbol}: {len(trades)} trades exécutés (non-chevauchants)")

        if not trades:
            return BacktestResult(symbol, period_days, n, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        pnl_arr = np.array([t.pnl_pct for t in trades])
        wins = np.sum(pnl_arr > 0)
        total_pnl = float(np.sum(pnl_arr))

        # Drawdown sur la courbe d'équité bar-à-bar (inclut pertes latentes intra-trade)
        equity_curve = self._equity_curve(trades, closes)

        result = BacktestResult(
            symbol=symbol,
            period_days=period_days,
            n_candles=n,
            n_trades=len(trades),
            win_rate=float(wins / len(trades)),
            pnl_pct=total_pnl,
            max_drawdown=self._max_drawdown(equity_curve),
            sharpe_ratio=self._sharpe(pnl_arr, period_days),
            best_trade=float(pnl_arr.max()),
            worst_trade=float(pnl_arr.min()),
            trades=trades,
        )
        logger.info(str(result))
        return result
