"""
DebateLogger — Structured audit trail for parliament deliberations.

Stores every council debate round as a structured record.
Useful for:
  - Post-hoc analysis of why a trade was taken / rejected
  - Hebbian weight calibration review
  - Brier score attribution

Storage: in-memory ring buffer (last N debates) + optional SQLite append.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Optional

logger = logging.getLogger("ORACLE.Parliament.DebateLogger")


@dataclass
class DebateRound:
    """Single parliament debate record."""
    symbol: str
    ts: float                        # Unix timestamp
    n_votes: int
    direction: str                   # Final decision
    strength: float                  # Conviction [0,1]
    agent_verdicts: list[dict]       # [{agent_id, decision, confidence, reasoning}]
    ml_votes: list[dict]             # [{strategy_id, decision, confidence}]
    final_consensus: Optional[str]   # "LONG" | "SHORT" | None
    execution_triggered: bool = False
    notes: str = ""


class DebateLogger:
    """
    Ring-buffer debate logger with optional SQLite persistence.

    Parameters
    ----------
    maxlen : int
        In-memory ring buffer capacity.
    db_path : str | None
        Path to SQLite file. If None, memory-only mode.
    """

    def __init__(self, maxlen: int = 500, db_path: Optional[str] = None):
        self._buffer: deque[DebateRound] = deque(maxlen=maxlen)
        self._db_path = db_path
        if db_path:
            self._ensure_db(db_path)

    # ── Write ──────────────────────────────────────────────────────────────────

    def log(self, round_: DebateRound) -> None:
        """Append a debate round to buffer (and SQLite if configured)."""
        self._buffer.append(round_)
        if self._db_path:
            try:
                self._write_db(round_)
            except Exception as e:
                logger.warning(f"DebateLogger DB write failed: {e}")

    def log_simple(
        self,
        symbol: str,
        direction: str,
        strength: float,
        votes: list,
        ml_votes: Optional[list] = None,
        execution_triggered: bool = False,
        notes: str = "",
    ) -> DebateRound:
        """
        Convenience method — build and log a DebateRound from raw inputs.

        Parameters
        ----------
        votes : list
            List of Vote objects (brain.parliament.Vote) or plain tuples.
        ml_votes : list | None
            List of MLCouncil Vote objects.
        """
        def _serialize_vote(v) -> dict:
            if hasattr(v, "__dataclass_fields__"):
                return {
                    "agent_id": getattr(v, "strate_name", getattr(v, "strategy_id", str(v))),
                    "decision": getattr(v, "direction", getattr(v, "decision", "?")),
                    "confidence": float(getattr(v, "confidence", 0.0)),
                    "reasoning": getattr(v, "reasoning", ""),
                }
            if isinstance(v, tuple) and len(v) >= 3:
                return {"agent_id": v[0], "decision": v[1], "confidence": float(v[2]), "reasoning": v[3] if len(v) > 3 else ""}
            return {"raw": str(v)}

        round_ = DebateRound(
            symbol=symbol,
            ts=time.time(),
            n_votes=len(votes),
            direction=direction,
            strength=float(strength),
            agent_verdicts=[_serialize_vote(v) for v in votes],
            ml_votes=[_serialize_vote(v) for v in (ml_votes or [])],
            final_consensus=direction if direction != "NEUTRAL" else None,
            execution_triggered=execution_triggered,
            notes=notes,
        )
        self.log(round_)
        return round_

    # ── Read ───────────────────────────────────────────────────────────────────

    def last(self, n: int = 10) -> list[DebateRound]:
        """Return last N debates."""
        return list(self._buffer)[-n:]

    def for_symbol(self, symbol: str, n: int = 20) -> list[DebateRound]:
        """Return last N debates for a specific symbol."""
        return [r for r in self._buffer if r.symbol == symbol][-n:]

    def win_rate(self, symbol: Optional[str] = None) -> dict:
        """
        Compute simple debate → outcome correlation.

        For each debate where execution was triggered, check if direction
        was subsequently profitable (requires manual outcome tagging via
        ``tag_outcome()``).
        """
        records = list(self._buffer) if symbol is None else self.for_symbol(symbol, n=1000)
        executed = [r for r in records if r.execution_triggered]
        if not executed:
            return {"total": 0, "executed": 0}
        wins = [r for r in executed if "WIN" in r.notes.upper()]
        losses = [r for r in executed if "LOSS" in r.notes.upper()]
        return {
            "total": len(records),
            "executed": len(executed),
            "wins": len(wins),
            "losses": len(losses),
            "winrate": len(wins) / len(executed) if executed else 0.0,
        }

    def tag_outcome(self, symbol: str, ts: float, outcome: str) -> bool:
        """Tag a past debate with 'WIN' or 'LOSS'."""
        for round_ in self._buffer:
            if round_.symbol == symbol and abs(round_.ts - ts) < 1.0:
                round_.notes = f"{round_.notes} | {outcome.upper()}"
                return True
        return False

    def summary(self) -> str:
        """Human-readable summary of last 10 debates."""
        lines = ["Parliament Debate Log (last 10):", "─" * 50]
        for r in self.last(10):
            ts_str = time.strftime("%H:%M:%S", time.localtime(r.ts))
            lines.append(
                f"[{ts_str}] {r.symbol:10s} {r.direction:7s} "
                f"({r.strength:.0%}) n={r.n_votes} "
                f"{'✓EXEC' if r.execution_triggered else ''}"
            )
        return "\n".join(lines)

    # ── SQLite persistence ──────────────────────────────────────────────────────

    @staticmethod
    def _ensure_db(db_path: str) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS parliament_debates (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol        TEXT    NOT NULL,
                    ts            REAL    NOT NULL,
                    direction     TEXT    NOT NULL,
                    strength      REAL    NOT NULL,
                    n_votes       INTEGER NOT NULL,
                    execution     INTEGER NOT NULL DEFAULT 0,
                    agent_json    TEXT,
                    ml_json       TEXT,
                    notes         TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON parliament_debates(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts     ON parliament_debates(ts)")
            conn.commit()

    def _write_db(self, round_: DebateRound) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO parliament_debates
                    (symbol, ts, direction, strength, n_votes, execution, agent_json, ml_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                round_.symbol,
                round_.ts,
                round_.direction,
                round_.strength,
                round_.n_votes,
                int(round_.execution_triggered),
                json.dumps(round_.agent_verdicts),
                json.dumps(round_.ml_votes),
                round_.notes,
            ))
            conn.commit()
