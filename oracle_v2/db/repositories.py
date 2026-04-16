"""
Repositories SQLite pour ORACLE v2.

  TradeRepository     : journal des trades (paper + live).
  HebbianRepository   : persistance des poids Hebbian entre redémarrages.
  OpenPositionRepo    : positions ouvertes SafetyKernel (survit aux redémarrages).
  RiskMetricsRepo     : persistance VaR/CVaR/Sortino journaliers.
"""
import sqlite3
import time
import logging
from pathlib import Path

from .schema import CREATE_TRADES, CREATE_HEBBIAN, CREATE_OPEN_POSITIONS, CREATE_RISK_METRICS

logger = logging.getLogger("ORACLE.DB")

_DEFAULT_DB = Path(__file__).parent.parent / "vault" / "oracle.db"


# ─── TradeRepository ──────────────────────────────────────────────────────────

class TradeRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(_DEFAULT_DB)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(CREATE_TRADES)
            conn.commit()

    def insert_trade(
        self,
        symbol: str,
        direction: str,
        size_usdt: float,
        sl_pct: float,
        tp_pct: float,
        confidence: float,
        source_strate: str,
        mode: str,
    ) -> int:
        """Insère un trade et retourne son ID (pour close_trade)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO trades
                   (ts, symbol, direction, size_usdt, sl_pct, tp_pct,
                    confidence, source_strate, mode)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (time.time(), symbol, direction, size_usdt,
                 sl_pct, tp_pct, confidence, source_strate, mode),
            )
            conn.commit()
            return cursor.lastrowid  # ← retourne l'ID pour close_trade()

    def close_trade(self, trade_id: int, pnl_pct: float) -> None:
        """Enregistre le PnL réel à la fermeture du trade."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE trades SET pnl_pct=?, closed_at=? WHERE id=?",
                (pnl_pct, time.time(), trade_id),
            )
            conn.commit()
        logger.debug(f"Trade #{trade_id} fermé — PnL: {pnl_pct:+.2%}")

    def get_recent(self, limit: int = 50) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT
                     COUNT(*) as total,
                     SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                     SUM(CASE WHEN pnl_pct < 0 THEN 1 ELSE 0 END) as losses,
                     AVG(pnl_pct) as avg_pnl
                   FROM trades WHERE pnl_pct IS NOT NULL"""
            ).fetchone()
            total = row[0] or 0
            wins = row[1] or 0
            return {
                "total": total,
                "wins": wins,
                "losses": row[2] or 0,
                "winrate": wins / total if total > 0 else 0.0,
                "avg_pnl": row[3] or 0.0,
            }


# ─── HebbianRepository ────────────────────────────────────────────────────────

class HebbianRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(_DEFAULT_DB)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(CREATE_HEBBIAN)
            conn.commit()

    def load_all(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT strate, weight FROM hebbian_weights"
            ).fetchall()
            return {row[0]: row[1] for row in rows}

    def save_weight(self, strate: str, weight: float) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO hebbian_weights (strate, weight, updated_at)
                   VALUES (?, ?, ?)""",
                (strate, weight, time.time()),
            )
            conn.commit()


# ─── OpenPositionRepository ───────────────────────────────────────────────────

class OpenPositionRepository:
    """
    Persistance des positions ouvertes du SafetyKernel.

    CRITIQUE : permet au SafetyKernel de retrouver les positions après
    un crash ou redémarrage.  Sans cela, open_positions est vide au
    redémarrage → pyramidage involontaire possible.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(_DEFAULT_DB)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(CREATE_OPEN_POSITIONS)
            conn.commit()

    def save_position(self, order) -> int:
        """Persiste une position ouverte. Retourne l'ID de la ligne."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO open_positions
                   (symbol, direction, size_usdt, leverage, sl_pct, tp_pct,
                    source_strate, confidence, opened_at, mode)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order.symbol, order.direction, order.size_usdt,
                    getattr(order, "leverage", 1.0),
                    getattr(order, "sl_pct", 0.0),
                    getattr(order, "tp_pct", 0.0),
                    getattr(order, "source_strate", ""),
                    getattr(order, "confidence", 0.0),
                    time.time(),
                    getattr(order, "mode", "paper"),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def remove_position(self, symbol: str) -> int:
        """Supprime toutes les positions du symbole. Retourne le nombre supprimé."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM open_positions WHERE symbol = ?", (symbol,)
            )
            conn.commit()
            return cursor.rowcount

    def load_all(self) -> list[dict]:
        """Charge toutes les positions persistées (au démarrage)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM open_positions ORDER BY opened_at"
            ).fetchall()
            return [dict(r) for r in rows]

    def clear(self) -> None:
        """Efface toutes les positions (ex: réconciliation après crash)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM open_positions")
            conn.commit()


# ─── RiskMetricsRepository ────────────────────────────────────────────────────

class RiskMetricsRepository:
    """Persistance des métriques de risque (VaR/CVaR/Sortino)."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(_DEFAULT_DB)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(CREATE_RISK_METRICS)
            conn.commit()

    def save_snapshot(
        self,
        var_95: float,
        cvar_95: float,
        sortino: float,
        n_trades: int,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO risk_metrics (ts, var_95, cvar_95, sortino, n_trades)
                   VALUES (?, ?, ?, ?, ?)""",
                (time.time(), var_95, cvar_95, sortino, n_trades),
            )
            conn.commit()

    def get_latest(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM risk_metrics ORDER BY ts DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else {}
