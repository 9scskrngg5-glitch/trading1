"""
Backtest Runner — ORACLE v2 pipeline walk-forward.

Rôle
----
Wrapper qui :
  1. Télécharge l'OHLCV via `ccxt` (Binance par défaut, 1h par défaut).
  2. Instancie les Strates 0–5 + `SignalAggregator` + `DynamicSizer`.
  3. Rejoue barre-par-barre **sans look-ahead** (`iloc[:i+1]` pour décider
     à la barre `i`, exécution à la barre `i+1` au prix d'ouverture).
  4. Applique SL = ATR × 1.5, TP = ATR × 2.5, frais 0.1 % par côté.
  5. Walk-forward : 180 j train / 30 j test / 30 j step.
  6. Agrège total_return, Sharpe, max drawdown, win rate, nombre de trades,
     métriques par fold.
  7. Persiste sorties dans `trading_bot/vault/backtest/`.

Ce runner n'est **pas** un wrapper de `backtester.py` (l'ancien, qui utilisait
ScanAgent directement). Ce fichier est intentionnellement neuf : on ajoute une
couche par-dessus ce qui existe, on ne touche pas au code qui tourne.

Règles non négociables (rappel CLAUDE.md)
-----------------------------------------
* **Pas de look-ahead.** Décision calculée sur `df.iloc[:i+1]`, exécution sur
  `df.iloc[i+1]["open"]`. La barre courante est observée *close-only* avant la
  décision, puis la prochaine barre sert au fill.
* **Fail-safe.** Chaque étape critique est wrappée en `try/except`. Un fold
  qui crash n'interrompt pas les autres — il est logué `status="failed"`.
* **Persistence.** Un timestamp ISO UTC + hash du run est écrit dans le
  dossier `vault/backtest/<timestamp>_<symbol>_<timeframe>.json`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Constantes par défaut ────────────────────────────────────────────────────

DEFAULT_EXCHANGE     = "binance"
DEFAULT_SYMBOL       = "BTC/USDT"
DEFAULT_TIMEFRAME    = "1h"
DEFAULT_HISTORY_DAYS = 365 * 2       # 2 ans d'OHLCV par défaut

# Stop-loss / take-profit (en multiples d'ATR)
SL_ATR_MULT = 1.5
TP_ATR_MULT = 2.5

# Frais par côté (entry + exit)
FEE_RATE_PER_SIDE = 0.001  # 0.1 %

# Walk-forward (en jours)
WF_TRAIN_DAYS = 180
WF_TEST_DAYS  = 30
WF_STEP_DAYS  = 30

# Fenêtre ATR
ATR_WINDOW = 14

# Capital initial de simulation
DEFAULT_INITIAL_CAPITAL = 10_000.0

# Barres minimum à laisser passer avant d'autoriser la première décision
# (pour que les fenêtres glissantes des strates aient de la matière)
WARMUP_BARS = 200


# ── Types ────────────────────────────────────────────────────────────────────

@dataclass
class BacktestTrade:
    entry_time:   str
    exit_time:    str
    side:         str       # "LONG" | "SHORT"
    entry_price:  float
    exit_price:   float
    size_pct:     float     # % capital risqué
    pnl_pct:      float     # P&L du trade en % du capital au moment de l'entrée
    pnl_usd:      float
    exit_reason:  str       # "SL" | "TP" | "END_OF_DATA" | "FORCED_CLOSE"
    conviction:   float
    fold_id:      int


@dataclass
class FoldMetrics:
    fold_id:      int
    train_start:  str
    train_end:    str
    test_start:   str
    test_end:     str
    n_trades:     int
    total_return: float
    sharpe:       float
    max_drawdown: float
    win_rate:     float
    status:       str = "ok"        # "ok" | "failed" | "no_trades"
    error:        Optional[str] = None


@dataclass
class BacktestReport:
    symbol:       str
    timeframe:    str
    exchange:     str
    start_time:   str
    end_time:     str
    initial_capital: float
    final_capital:   float
    total_return: float
    sharpe:       float
    max_drawdown: float
    win_rate:     float
    n_trades:     int
    folds:        list[FoldMetrics]
    trades:       list[BacktestTrade]
    run_hash:     str
    config:       dict[str, Any] = field(default_factory=dict)


# ── Data ─────────────────────────────────────────────────────────────────────

def fetch_ohlcv_ccxt(
    symbol:    str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    days:      int = DEFAULT_HISTORY_DAYS,
    exchange:  str = DEFAULT_EXCHANGE,
) -> pd.DataFrame:
    """
    Télécharge OHLCV via ccxt en paginant. Retourne un DataFrame à index UTC.

    Colonnes : open, high, low, close, volume
    Index    : DatetimeIndex en UTC

    L'import `ccxt` est local pour permettre aux tests de monkeypatch ce
    module sans dépendance dure au chargement.
    """
    import ccxt  # local import

    ex_cls = getattr(ccxt, exchange)
    ex = ex_cls({"enableRateLimit": True})
    ex.load_markets()

    ms_per_bar = ex.parse_timeframe(timeframe) * 1000
    since = ex.milliseconds() - days * 24 * 60 * 60 * 1000

    all_rows: list[list[float]] = []
    while True:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not batch:
            break
        all_rows.extend(batch)
        since = batch[-1][0] + ms_per_bar
        if len(batch) < 1000:
            break

    if not all_rows:
        raise RuntimeError(f"no OHLCV returned for {symbol} on {exchange}")

    df = pd.DataFrame(
        all_rows, columns=["ts", "open", "high", "low", "close", "volume"]
    )
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["ts"]).set_index("ts").sort_index()
    return df.astype(float)


# ── ATR sans look-ahead ──────────────────────────────────────────────────────

def compute_atr(df: pd.DataFrame, window: int = ATR_WINDOW) -> pd.Series:
    """
    Average True Range standard (Wilder). Appliqué en `rolling` — donc
    l'ATR à la barre `i` n'utilise que des barres ≤ `i`.
    """
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=window, min_periods=window).mean()


# ── Boucle d'exécution barre-par-barre ───────────────────────────────────────

def _simulate_fold(
    df_fold:     pd.DataFrame,
    aggregator:  Any,
    fold_id:     int,
    initial_capital: float,
    warmup:      int,
) -> tuple[list[BacktestTrade], list[float]]:
    """
    Rejoue un fold de test barre par barre. Règle stricte :

      - La décision à `i` est basée sur `df_fold.iloc[:i+1]` (close `i` inclus).
      - Si la décision est LONG/SHORT et qu'on est flat, on *entre* à
        `df_fold.iloc[i+1]["open"]` (pas de look-ahead).
      - Une fois in-position, on suit high/low de chaque barre jusqu'à toucher
        SL ou TP. Si les deux sont touchés la même barre, on est conservateur
        et on enregistre un SL (hypothèse la plus défavorable).
      - Une seule position à la fois. Si le signal se retourne alors qu'on est
        long, on ne ferme pas de force — on laisse SL/TP gérer la sortie.

    Returns:
        trades      : liste de BacktestTrade du fold
        equity_curve: équity USD à chaque barre du fold (pour Sharpe/DD fold)
    """
    trades: list[BacktestTrade] = []
    equity = initial_capital
    equity_curve: list[float] = []

    atr = compute_atr(df_fold)

    position: Optional[dict[str, Any]] = None  # None = flat

    for i in range(len(df_fold) - 1):
        equity_curve.append(equity)

        # Warm-up : le test commence au premier bar du fold, mais certaines
        # strates ont besoin d'historique. `warmup` est passé par le caller
        # en nombre de barres du fold (0 si train assez gros).
        if i < warmup:
            continue

        bar = df_fold.iloc[i]
        next_bar = df_fold.iloc[i + 1]
        atr_i = atr.iloc[i] if not np.isnan(atr.iloc[i]) else 0.0

        # ── 1. Gestion de position existante : vérifier SL/TP sur la barre i+1.
        if position is not None:
            hit_sl = False
            hit_tp = False
            nb_high, nb_low = next_bar["high"], next_bar["low"]

            if position["side"] == "LONG":
                if nb_low <= position["sl_price"]:
                    hit_sl = True
                if nb_high >= position["tp_price"]:
                    hit_tp = True
                exit_price = (
                    position["sl_price"] if hit_sl
                    else position["tp_price"] if hit_tp
                    else None
                )
            else:  # SHORT
                if nb_high >= position["sl_price"]:
                    hit_sl = True
                if nb_low <= position["tp_price"]:
                    hit_tp = True
                exit_price = (
                    position["sl_price"] if hit_sl
                    else position["tp_price"] if hit_tp
                    else None
                )

            if exit_price is not None:
                gross_move = (
                    (exit_price - position["entry_price"]) / position["entry_price"]
                    if position["side"] == "LONG"
                    else (position["entry_price"] - exit_price) / position["entry_price"]
                )
                # Frais aller-retour
                net_move = gross_move - 2 * FEE_RATE_PER_SIDE
                # P&L en % du capital basé sur le risk_pct alloué
                pnl_pct = net_move * (position["size_pct"] / position["risk_ref"])
                # risk_ref = SL distance en %, donc size_pct/risk_ref = leverage implicite
                pnl_usd = position["capital_at_entry"] * pnl_pct / 100.0
                equity += pnl_usd

                trades.append(BacktestTrade(
                    entry_time=str(position["entry_time"]),
                    exit_time=str(next_bar.name),
                    side=position["side"],
                    entry_price=float(position["entry_price"]),
                    exit_price=float(exit_price),
                    size_pct=float(position["size_pct"]),
                    pnl_pct=float(pnl_pct),
                    pnl_usd=float(pnl_usd),
                    exit_reason="SL" if hit_sl else "TP",
                    conviction=float(position["conviction"]),
                    fold_id=fold_id,
                ))
                position = None
                # Pas de ré-entrée la même barre — on repart propre.
                continue

        # ── 2. Décider à la barre courante (flat seulement).
        if position is not None or atr_i <= 0 or np.isnan(atr_i):
            continue

        prices_slice = df_fold["close"].iloc[: i + 1]
        volume_slice = df_fold["volume"].iloc[: i + 1]

        try:
            decision = aggregator.aggregate(
                prices=prices_slice,
                volume=volume_slice,
                asset="BTC/USDT",
                timeframe="1h",
            )
        except Exception as exc:
            logger.warning("[fold %d bar %d] aggregator failed: %s", fold_id, i, exc)
            continue

        signal = decision.get("signal", "FLAT")
        if signal == "FLAT":
            continue

        # ── 3. Sizing via aggregator.size_position
        # Win-rate initial inconnu → on assume 50/50 et un R = 1.67 (TP/SL).
        # L'ADAPTIVE sizer pondérera la conviction.
        try:
            size = aggregator.size_position(
                capital=equity,
                win_rate=0.50,
                avg_win=TP_ATR_MULT,
                avg_loss=SL_ATR_MULT,
                atr_pct=float(atr_i / bar["close"] * 100.0),
                total_trades=len(trades),
            )
            risk_pct = float(size.get("risk_pct", 0.0))
        except Exception as exc:
            logger.warning("[fold %d bar %d] sizer failed: %s", fold_id, i, exc)
            continue

        if risk_pct <= 0:
            continue

        # ── 4. Entrée à la barre suivante (au prix d'ouverture).
        entry_price = float(next_bar["open"])
        if signal == "LONG":
            sl_price = entry_price - SL_ATR_MULT * atr_i
            tp_price = entry_price + TP_ATR_MULT * atr_i
        else:  # SHORT
            sl_price = entry_price + SL_ATR_MULT * atr_i
            tp_price = entry_price - TP_ATR_MULT * atr_i

        # Distance SL en % → sert à convertir risk_pct en leverage implicite
        sl_distance_pct = abs(entry_price - sl_price) / entry_price * 100.0
        if sl_distance_pct <= 0:
            continue

        position = {
            "side": signal,
            "entry_time": next_bar.name,
            "entry_price": entry_price,
            "sl_price": float(sl_price),
            "tp_price": float(tp_price),
            "size_pct": risk_pct,
            "risk_ref": sl_distance_pct,  # pour calcul P&L
            "capital_at_entry": equity,
            "conviction": float(decision.get("conviction", 0.0)),
        }

    # ── Fin du fold : on ferme toute position ouverte au dernier close ──
    if position is not None:
        last_bar = df_fold.iloc[-1]
        exit_price = float(last_bar["close"])
        gross_move = (
            (exit_price - position["entry_price"]) / position["entry_price"]
            if position["side"] == "LONG"
            else (position["entry_price"] - exit_price) / position["entry_price"]
        )
        net_move = gross_move - 2 * FEE_RATE_PER_SIDE
        pnl_pct = net_move * (position["size_pct"] / position["risk_ref"])
        pnl_usd = position["capital_at_entry"] * pnl_pct / 100.0
        equity += pnl_usd
        trades.append(BacktestTrade(
            entry_time=str(position["entry_time"]),
            exit_time=str(last_bar.name),
            side=position["side"],
            entry_price=float(position["entry_price"]),
            exit_price=exit_price,
            size_pct=float(position["size_pct"]),
            pnl_pct=float(pnl_pct),
            pnl_usd=float(pnl_usd),
            exit_reason="END_OF_DATA",
            conviction=float(position["conviction"]),
            fold_id=fold_id,
        ))

    equity_curve.append(equity)
    return trades, equity_curve


# ── Métriques ────────────────────────────────────────────────────────────────

def _sharpe(returns: list[float], periods_per_year: int = 24 * 365) -> float:
    """Sharpe annualisé. `returns` = log-returns par barre (timeframe natif)."""
    if len(returns) < 2:
        return 0.0
    arr = np.asarray(returns, dtype=float)
    std = arr.std(ddof=1)
    if std == 0:
        return 0.0
    return float(arr.mean() / std * math.sqrt(periods_per_year))


def _max_drawdown(equity_curve: list[float]) -> float:
    """Max drawdown (en fraction de l'équité au pic)."""
    if not equity_curve:
        return 0.0
    arr = np.asarray(equity_curve, dtype=float)
    running_max = np.maximum.accumulate(arr)
    dd = (arr - running_max) / running_max
    return float(dd.min())


def _fold_metrics(
    fold_id:     int,
    train_start: pd.Timestamp, train_end: pd.Timestamp,
    test_start:  pd.Timestamp, test_end:  pd.Timestamp,
    trades:      list[BacktestTrade],
    equity_curve: list[float],
    initial_capital: float,
    periods_per_year: int,
) -> FoldMetrics:
    if not trades or len(equity_curve) < 2:
        return FoldMetrics(
            fold_id=fold_id,
            train_start=train_start.isoformat(),
            train_end=train_end.isoformat(),
            test_start=test_start.isoformat(),
            test_end=test_end.isoformat(),
            n_trades=len(trades),
            total_return=0.0,
            sharpe=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            status="no_trades" if not trades else "ok",
        )

    final = equity_curve[-1]
    total_return = (final - initial_capital) / initial_capital

    bar_returns = [
        math.log(equity_curve[k] / equity_curve[k - 1])
        for k in range(1, len(equity_curve))
        if equity_curve[k - 1] > 0 and equity_curve[k] > 0
    ]
    sharpe = _sharpe(bar_returns, periods_per_year)
    mdd = _max_drawdown(equity_curve)
    wins = sum(1 for t in trades if t.pnl_usd > 0)
    wr = wins / len(trades) if trades else 0.0

    return FoldMetrics(
        fold_id=fold_id,
        train_start=train_start.isoformat(),
        train_end=train_end.isoformat(),
        test_start=test_start.isoformat(),
        test_end=test_end.isoformat(),
        n_trades=len(trades),
        total_return=total_return,
        sharpe=sharpe,
        max_drawdown=mdd,
        win_rate=wr,
        status="ok",
    )


# ── Runner principal ─────────────────────────────────────────────────────────

class BacktestRunner:
    """
    Walk-forward backtester pour pipeline ORACLE v2 complet.

    Responsabilités :
      - gérer l'acquisition des données (ccxt) ou accepter un DataFrame prêt,
      - découper en folds train/test/step,
      - déléguer la décision au `SignalAggregator` fourni,
      - calculer les métriques et persister.

    Design : l'aggregator et les strates sont injectés. Ce fichier ne
    connaît pas le détail des strates (aucun import du module `strate_*`),
    il parle seulement à l'interface `aggregator.aggregate(...)` et
    `aggregator.size_position(...)`. On peut ainsi le tester avec des mocks.
    """

    def __init__(
        self,
        aggregator:  Any,
        vault_path:  Path = Path("trading_bot/vault/backtest"),
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        train_days:  int = WF_TRAIN_DAYS,
        test_days:   int = WF_TEST_DAYS,
        step_days:   int = WF_STEP_DAYS,
    ):
        self.aggregator       = aggregator
        self.vault_path       = Path(vault_path)
        self.initial_capital  = initial_capital
        self.train_days       = train_days
        self.test_days        = test_days
        self.step_days        = step_days

        self.vault_path.mkdir(parents=True, exist_ok=True)

    # ── API publique ──────────────────────────────────────────────────────────

    def run(
        self,
        df:         Optional[pd.DataFrame] = None,
        symbol:     str = DEFAULT_SYMBOL,
        timeframe: str  = DEFAULT_TIMEFRAME,
        exchange:  str  = DEFAULT_EXCHANGE,
        days:      int  = DEFAULT_HISTORY_DAYS,
    ) -> BacktestReport:
        """
        Lance le backtest walk-forward. Si `df` est None, télécharge via ccxt.
        """
        if df is None:
            logger.info("[BacktestRunner] fetching %s %s from %s (%d days)",
                        symbol, timeframe, exchange, days)
            df = fetch_ohlcv_ccxt(symbol, timeframe, days, exchange)
        else:
            df = df.copy()
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")

        if len(df) < WARMUP_BARS * 2:
            raise ValueError(
                f"dataframe too small ({len(df)} bars); "
                f"need at least {WARMUP_BARS * 2}."
            )

        periods_per_year = self._periods_per_year(timeframe)

        folds = self._build_folds(df.index[0], df.index[-1])
        logger.info("[BacktestRunner] %d folds planned", len(folds))

        all_trades:  list[BacktestTrade] = []
        fold_metrics: list[FoldMetrics]  = []

        equity = self.initial_capital
        global_curve: list[float] = [equity]

        for fold_id, (train_start, train_end, test_start, test_end) in enumerate(folds):
            # Slice de test — warmup intégré depuis le train.
            fold_slice = df.loc[train_start:test_end]
            if fold_slice.empty:
                continue

            # Warmup : barres du train dans la slice.
            warmup_bars = int((fold_slice.index < test_start).sum())
            warmup_bars = max(warmup_bars, WARMUP_BARS)

            try:
                trades, curve = _simulate_fold(
                    df_fold=fold_slice,
                    aggregator=self.aggregator,
                    fold_id=fold_id,
                    initial_capital=equity,
                    warmup=warmup_bars,
                )
            except Exception as exc:
                logger.error("[BacktestRunner] fold %d crashed: %s", fold_id, exc)
                fold_metrics.append(FoldMetrics(
                    fold_id=fold_id,
                    train_start=train_start.isoformat(),
                    train_end=train_end.isoformat(),
                    test_start=test_start.isoformat(),
                    test_end=test_end.isoformat(),
                    n_trades=0, total_return=0.0, sharpe=0.0,
                    max_drawdown=0.0, win_rate=0.0,
                    status="failed", error=str(exc),
                ))
                continue

            # Mise à jour équité globale : on chaîne les folds.
            if curve:
                equity = curve[-1]
                global_curve.extend(curve[1:] if len(curve) > 1 else curve)

            all_trades.extend(trades)

            fm = _fold_metrics(
                fold_id=fold_id,
                train_start=train_start, train_end=train_end,
                test_start=test_start,  test_end=test_end,
                trades=trades,
                equity_curve=curve,
                initial_capital=(curve[0] if curve else equity),
                periods_per_year=periods_per_year,
            )
            fold_metrics.append(fm)
            logger.info(
                "[BacktestRunner] fold %d : n=%d ret=%+.2f%% sharpe=%.2f "
                "mdd=%.2f%% wr=%.1f%%",
                fold_id, fm.n_trades, fm.total_return * 100, fm.sharpe,
                fm.max_drawdown * 100, fm.win_rate * 100,
            )

        # Métriques globales
        final_capital = equity
        total_return = (final_capital - self.initial_capital) / self.initial_capital
        bar_returns = [
            math.log(global_curve[k] / global_curve[k - 1])
            for k in range(1, len(global_curve))
            if global_curve[k - 1] > 0 and global_curve[k] > 0
        ]
        sharpe = _sharpe(bar_returns, periods_per_year)
        mdd = _max_drawdown(global_curve)
        wins = sum(1 for t in all_trades if t.pnl_usd > 0)
        wr = wins / len(all_trades) if all_trades else 0.0

        report = BacktestReport(
            symbol=symbol,
            timeframe=timeframe,
            exchange=exchange,
            start_time=df.index[0].isoformat(),
            end_time=df.index[-1].isoformat(),
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            sharpe=sharpe,
            max_drawdown=mdd,
            win_rate=wr,
            n_trades=len(all_trades),
            folds=fold_metrics,
            trades=all_trades,
            run_hash=self._hash_run(symbol, timeframe, exchange, df),
            config={
                "train_days":  self.train_days,
                "test_days":   self.test_days,
                "step_days":   self.step_days,
                "sl_atr_mult": SL_ATR_MULT,
                "tp_atr_mult": TP_ATR_MULT,
                "fee_rate":    FEE_RATE_PER_SIDE,
                "atr_window":  ATR_WINDOW,
                "warmup_bars": WARMUP_BARS,
            },
        )

        self._persist(report)
        return report

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_folds(
        self, first_ts: pd.Timestamp, last_ts: pd.Timestamp,
    ) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
        """
        Génère les tuples (train_start, train_end, test_start, test_end).
        train_end == test_start (pas de gap).
        """
        folds = []
        train_start = first_ts
        train_end = train_start + timedelta(days=self.train_days)
        while train_end + timedelta(days=self.test_days) <= last_ts:
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_days)
            folds.append((train_start, train_end, test_start, test_end))
            train_start = train_start + timedelta(days=self.step_days)
            train_end = train_start + timedelta(days=self.train_days)
        return folds

    @staticmethod
    def _periods_per_year(timeframe: str) -> int:
        """Nombre de barres par an pour annualiser Sharpe."""
        tf = timeframe.strip().lower()
        if tf.endswith("m"):
            n = int(tf[:-1]); return max(1, 365 * 24 * 60 // n)
        if tf.endswith("h"):
            n = int(tf[:-1]); return max(1, 365 * 24 // n)
        if tf.endswith("d"):
            n = int(tf[:-1]); return max(1, 365 // n)
        return 365 * 24  # défaut 1h

    @staticmethod
    def _hash_run(symbol: str, timeframe: str, exchange: str, df: pd.DataFrame) -> str:
        payload = f"{exchange}:{symbol}:{timeframe}:{df.index[0]}:{df.index[-1]}:{len(df)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def _persist(self, report: BacktestReport) -> Path:
        """Écrit le rapport JSON dans le vault. Retourne le path écrit."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_sym = report.symbol.replace("/", "-").replace(":", "")
        filename = f"{ts}_{safe_sym}_{report.timeframe}_{report.run_hash}.json"
        out = self.vault_path / filename

        payload = {
            "symbol":         report.symbol,
            "timeframe":      report.timeframe,
            "exchange":       report.exchange,
            "start_time":     report.start_time,
            "end_time":       report.end_time,
            "initial_capital": report.initial_capital,
            "final_capital":   report.final_capital,
            "total_return":    report.total_return,
            "sharpe":          report.sharpe,
            "max_drawdown":    report.max_drawdown,
            "win_rate":        report.win_rate,
            "n_trades":        report.n_trades,
            "run_hash":        report.run_hash,
            "config":          report.config,
            "folds":           [asdict(f) for f in report.folds],
            "trades":          [asdict(t) for t in report.trades],
        }
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        logger.info("[BacktestRunner] report saved → %s", out)
        return out
