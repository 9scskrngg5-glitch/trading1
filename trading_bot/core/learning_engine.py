"""
Learning Engine — Mémoire et compréhension ORACLE v2.

Décisions architecturales appliquées :
  Decision 1 : mémoire stockée dans SQLite (oracle_memory.db), plus dans le vault Obsidian.
  Decision 2 : apprentissage par compréhension LLM (Claude), pas par ajustement mécanique.

Flux :
    TradeOutcome → record_outcome()
        → _update_memory_sqlite()   (stats numériques → agent_memory table)
        → analyze_trade_outcome()   (Claude API → learning_insights + context_patterns)
        → _write_daily_journal()    (résumé lisible → vault/journal/YYYY-MM-DD.md)

L'interface publique reste identique pour les agents existants :
    load_memory(), save_memory(), get_memory(), record_outcome(), run_counterfactual()
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from models.learning import (
    AgentMemory, CounterfactualResult, TradeOutcome,
)
from core.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

LEARNING_RATE   = 0.10
MIN_TRADES      = 5
WEIGHT_MIN      = 0.3
WEIGHT_MAX      = 2.0

SL_MULTIPLIERS  = [0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0]
TP_RATIOS       = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]

# Seuil de PnL pour déclencher l'analyse LLM (évite d'appeler Claude pour chaque micro-trade)
LLM_ANALYSIS_THRESHOLD_PCT = 0.5  # trades avec |PnL| > 0.5% sont analysés


class LearningEngine:
    """
    Moteur d'apprentissage central partagé par tous les agents.

    Chaque agent dispose de sa propre AgentMemory, persistée dans SQLite.
    L'apprentissage qualitatif passe par Claude API (compréhension des causes)
    et non par ajustement aveugle de paramètres.
    """

    def __init__(self, obsidian: ObsidianClient, config: dict, telegram=None, llm_client=None):
        self.obsidian  = obsidian
        self.config    = config
        self.telegram  = telegram
        self.llm       = llm_client  # LLMClient optionnel — si None, analyse LLM désactivée

        self._memories: dict[str, AgentMemory] = {}
        self._outcomes: list[TradeOutcome]     = []

        # SQLite — même dossier que le vault pour cohérence
        self._db_path = Path(obsidian.vault_path) / "oracle_memory.db"
        self._init_db()

    # ── Init SQLite ───────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Crée les tables SQLite si absentes."""
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agent_memory (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name       TEXT NOT NULL,
                    regime           TEXT DEFAULT 'global',
                    total_trades     INTEGER DEFAULT 0,
                    total_wins       INTEGER DEFAULT 0,
                    total_pnl_usd    REAL DEFAULT 0.0,
                    total_pnl_pct    REAL DEFAULT 0.0,
                    best_trade_pct   REAL DEFAULT 0.0,
                    worst_trade_pct  REAL DEFAULT 0.0,
                    current_streak   INTEGER DEFAULT 0,
                    adaptive_params  TEXT DEFAULT '{}',
                    indicator_weights TEXT DEFAULT '{}',
                    indicator_stats  TEXT DEFAULT '{}',
                    asset_stats      TEXT DEFAULT '{}',
                    regime_params    TEXT DEFAULT '{}',
                    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(agent_name, regime)
                );

                CREATE TABLE IF NOT EXISTS learning_insights (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id          TEXT,
                    asset             TEXT,
                    direction         TEXT,
                    pnl_pct           REAL,
                    minsky_phase      INTEGER,
                    snr_score         REAL,
                    narrative_dominant TEXT,
                    context_snapshot  TEXT,
                    cause             TEXT,
                    extracted_rule    TEXT,
                    avoid_when        TEXT,
                    counterfactual    TEXT,
                    confidence        REAL DEFAULT 0.0,
                    contradicts_existing TEXT,
                    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS context_patterns (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_hash     TEXT UNIQUE,
                    minsky_phase     INTEGER,
                    regime           TEXT,
                    snr_range        TEXT,
                    narrative_state  TEXT,
                    observations     INTEGER DEFAULT 1,
                    wins             INTEGER DEFAULT 0,
                    avg_pnl          REAL DEFAULT 0.0,
                    rule             TEXT,
                    confidence       REAL DEFAULT 0.0,
                    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_insights_asset
                ON learning_insights (asset, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_patterns_minsky
                ON context_patterns (minsky_phase, regime);
            """)
            conn.commit()
        logger.info("[Learning] SQLite initialisé : %s", self._db_path)

    # ── Chargement / Sauvegarde de la mémoire ─────────────────────────────────

    def load_memory(self, agent_name: str) -> AgentMemory:
        """
        Charge la mémoire depuis SQLite.
        Si absent, tente une migration depuis le vault Obsidian (legacy),
        puis crée une mémoire par défaut.
        """
        row = self._read_memory_sqlite(agent_name)
        if row:
            mem = self._row_to_memory(agent_name, row)
            self._memories[agent_name] = mem
            logger.info(
                "[Learning] Mémoire SQLite chargée pour %s : %d trades, WR=%.1f%%",
                agent_name, mem.total_trades, mem.win_rate * 100,
            )
            return mem

        # Migration depuis Obsidian (legacy)
        legacy = self._migrate_from_obsidian(agent_name)
        if legacy:
            self.save_memory(legacy)
            self._memories[agent_name] = legacy
            return legacy

        # Première exécution
        logger.info("[Learning] Première exécution de %s — mémoire initialisée", agent_name)
        mem = AgentMemory.default(agent_name)
        self._memories[agent_name] = mem
        self.save_memory(mem)
        return mem

    def save_memory(self, mem: AgentMemory) -> None:
        """Persiste la mémoire dans SQLite. Ne touche plus au vault Obsidian."""
        mem.last_updated = datetime.now(timezone.utc).isoformat()
        mem.version += 1

        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO agent_memory
                    (agent_name, regime, total_trades, total_wins, total_pnl_usd,
                     total_pnl_pct, best_trade_pct, worst_trade_pct, current_streak,
                     adaptive_params, indicator_weights, indicator_stats,
                     asset_stats, regime_params, updated_at)
                VALUES (?, 'global', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_name, regime) DO UPDATE SET
                    total_trades      = excluded.total_trades,
                    total_wins        = excluded.total_wins,
                    total_pnl_usd     = excluded.total_pnl_usd,
                    total_pnl_pct     = excluded.total_pnl_pct,
                    best_trade_pct    = excluded.best_trade_pct,
                    worst_trade_pct   = excluded.worst_trade_pct,
                    current_streak    = excluded.current_streak,
                    adaptive_params   = excluded.adaptive_params,
                    indicator_weights = excluded.indicator_weights,
                    indicator_stats   = excluded.indicator_stats,
                    asset_stats       = excluded.asset_stats,
                    regime_params     = excluded.regime_params,
                    updated_at        = excluded.updated_at
            """, (
                mem.agent_name,
                mem.total_trades, mem.total_wins,
                round(mem.total_pnl_usd, 4), round(mem.total_pnl_pct, 4),
                round(mem.best_trade_pct, 4), round(mem.worst_trade_pct, 4),
                mem.current_streak,
                json.dumps(mem.adaptive_params),
                json.dumps(mem.indicator_weights),
                json.dumps(mem.indicator_stats),
                json.dumps(mem.asset_stats),
                json.dumps(mem.regime_params),
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()

    def get_memory(self, agent_name: str) -> AgentMemory:
        """Retourne la mémoire en cache ou la charge depuis SQLite."""
        if agent_name not in self._memories:
            return self.load_memory(agent_name)
        return self._memories[agent_name]

    # ── Enregistrement d'un résultat de trade ────────────────────────────────

    def record_outcome(self, outcome: TradeOutcome) -> None:
        """
        Point d'entrée principal après la clôture d'un trade.

        1. Met à jour les stats numériques des agents en SQLite
        2. Lance l'analyse contrefactuelle
        3. Planifie l'analyse LLM en arrière-plan (non-bloquant)
        4. Met à jour le journal Obsidian du jour
        """
        self._outcomes.append(outcome)
        logger.info(
            "[Learning] Trade %s : %s %+.2f%% (%s)",
            outcome.order_id, outcome.asset,
            outcome.pnl_pct,
            "WIN" if outcome.is_win else "LOSS",
        )

        for agent_name in ["ScanAgent", "ResearchAgent", "PredictAgent", "RiskAgent"]:
            self._update_memory(agent_name, outcome)

        # Analyse contrefactuelle (sync — léger)
        cf = None
        if not outcome.is_win:
            cf = self.run_counterfactual(outcome)
            if cf:
                self._apply_counterfactual_to_regime(cf, outcome)

        # Analyse LLM (async — ne bloque pas le pipeline)
        if self.llm and abs(outcome.pnl_pct) >= LLM_ANALYSIS_THRESHOLD_PCT:
            self._schedule_llm_analysis(outcome, cf)

        # Journal Obsidian — une seule entrée par trade
        self._append_to_daily_journal(outcome, cf)

    def _schedule_llm_analysis(
        self,
        outcome: TradeOutcome,
        cf: Optional[CounterfactualResult],
    ) -> None:
        """Lance l'analyse LLM en arrière-plan sans bloquer le pipeline."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.analyze_trade_outcome(outcome, cf=cf))
            else:
                # Contexte synchrone (tests, scripts)
                loop.run_until_complete(self.analyze_trade_outcome(outcome, cf=cf))
        except Exception as exc:
            logger.debug("[Learning] LLM schedule error: %s", exc)

    # ── Analyse LLM (Decision 2 — compréhension, pas ajustement aveugle) ─────

    async def analyze_trade_outcome(
        self,
        outcome: TradeOutcome,
        minsky_phase: Optional[int] = None,
        snr_score: Optional[float] = None,
        narrative_state: Optional[dict] = None,
        agent_votes: Optional[dict] = None,
        cf: Optional[CounterfactualResult] = None,
    ) -> Optional[dict]:
        """
        Appelle Claude pour comprendre POURQUOI ce trade a réussi ou échoué.

        Stocke la compréhension dans learning_insights + met à jour context_patterns.
        Ne modifie aucun paramètre mécanique — stocke des règles textuelles.

        Returns:
            dict avec : cause, extracted_rule, avoid_when, confidence,
            contradicts_existing — ou None si LLM indisponible.
        """
        if not self.llm:
            return None

        context = {
            "trade":            outcome.to_dict(),
            "minsky_phase":     minsky_phase,
            "snr_score":        snr_score,
            "narrative_dominant": (narrative_state or {}).get("dominant_narrative"),
            "narrative_r0":     (narrative_state or {}).get("dominant_r0"),
            "agent_votes":      agent_votes or {},
            "counterfactual":   cf.to_markdown() if cf else None,
        }

        # Récupère les patterns connus pour ce contexte
        known_patterns = self._get_relevant_patterns(minsky_phase, snr_score)
        patterns_text = "\n".join([p.get("rule", "") for p in known_patterns[:3]]) or "Aucun pattern connu."

        prompt = f"""Tu es le module d'introspection d'ORACLE v2.
Un trade vient de se clôturer. Analyse-le honnêtement.

Contexte :
{json.dumps(context, indent=2, ensure_ascii=False, default=str)}

Règles déjà apprises dans des contextes similaires :
{patterns_text}

Réponds en JSON avec exactement ces clés :
{{
  "cause": "La vraie cause de ce résultat (timing, contexte macro, biais comportemental, signal faible, saturation narrative ?)",
  "extracted_rule": "Règle générale apprise — très spécifique, pas générique. Exemple : 'Éviter les longs BTC quand Minsky >= 3 ET SNR < 0.35 ET R0 narratif décroissant'",
  "avoid_when": "Dans quels contextes futurs spécifiques éviter ce type de trade ?",
  "confidence": 0.0,
  "contradicts_existing": "Cette règle contredit-elle une règle existante ? Si oui, laquelle et pourquoi ?"
}}

Sois honnête. Sois spécifique. Pas de conseils génériques."""

        try:
            response = await self.llm.complete_async(prompt)
            insight = self._parse_llm_insight(response)
            if insight:
                self._store_insight(outcome, insight, context, minsky_phase, snr_score, narrative_state, cf)
                logger.info(
                    "[Learning] Insight LLM pour %s : %s",
                    outcome.asset, insight.get("extracted_rule", "")[:80],
                )
            return insight
        except Exception as exc:
            logger.warning("[Learning] Analyse LLM échouée pour %s : %s", outcome.asset, exc)
            return None

    @staticmethod
    def _parse_llm_insight(response: str) -> Optional[dict]:
        """Extrait le JSON de la réponse LLM."""
        import re
        try:
            # Cherche un bloc JSON dans la réponse
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except (json.JSONDecodeError, AttributeError):
            pass
        return None

    def _store_insight(
        self,
        outcome: TradeOutcome,
        insight: dict,
        context: dict,
        minsky_phase: Optional[int],
        snr_score: Optional[float],
        narrative_state: Optional[dict],
        cf: Optional[CounterfactualResult],
    ) -> None:
        """Stocke l'insight dans learning_insights et met à jour context_patterns."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO learning_insights
                    (trade_id, asset, direction, pnl_pct, minsky_phase, snr_score,
                     narrative_dominant, context_snapshot, cause, extracted_rule,
                     avoid_when, counterfactual, confidence, contradicts_existing)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                outcome.order_id,
                outcome.asset,
                outcome.side.value,
                round(outcome.pnl_pct, 4),
                minsky_phase,
                round(snr_score, 4) if snr_score is not None else None,
                (narrative_state or {}).get("dominant_narrative"),
                json.dumps(context, default=str),
                insight.get("cause"),
                insight.get("extracted_rule"),
                insight.get("avoid_when"),
                cf.to_markdown() if cf else None,
                float(insight.get("confidence", 0.0)),
                insight.get("contradicts_existing"),
            ))
            conn.commit()

        # Met à jour le pattern contextuel
        self._update_context_pattern(minsky_phase, snr_score, narrative_state, outcome, insight)

    def _update_context_pattern(
        self,
        minsky_phase: Optional[int],
        snr_score: Optional[float],
        narrative_state: Optional[dict],
        outcome: TradeOutcome,
        insight: dict,
    ) -> None:
        """Agrège les observations dans context_patterns par hash de contexte."""
        snr_bucket = self._snr_bucket(snr_score)
        narrative = (narrative_state or {}).get("dominant_narrative", "unknown")
        regime = outcome.regime.value if hasattr(outcome.regime, "value") else str(outcome.regime)

        pattern_hash = f"{minsky_phase}|{regime}|{snr_bucket}|{narrative}"

        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute(
                "SELECT id, observations, wins, avg_pnl FROM context_patterns WHERE pattern_hash = ?",
                (pattern_hash,)
            ).fetchone()

            if existing:
                obs   = existing[1] + 1
                wins  = existing[2] + (1 if outcome.is_win else 0)
                avg   = (existing[3] * existing[1] + outcome.pnl_pct) / obs
                conf  = min(0.5 + obs * 0.05, 0.95)
                conn.execute("""
                    UPDATE context_patterns
                    SET observations = ?, wins = ?, avg_pnl = ?,
                        rule = ?, confidence = ?, updated_at = ?
                    WHERE pattern_hash = ?
                """, (obs, wins, round(avg, 4), insight.get("extracted_rule"),
                      round(conf, 3), datetime.now(timezone.utc).isoformat(), pattern_hash))
            else:
                conn.execute("""
                    INSERT INTO context_patterns
                        (pattern_hash, minsky_phase, regime, snr_range, narrative_state,
                         observations, wins, avg_pnl, rule, confidence)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, 0.5)
                """, (
                    pattern_hash, minsky_phase, regime, snr_bucket, narrative,
                    1 if outcome.is_win else 0,
                    round(outcome.pnl_pct, 4),
                    insight.get("extracted_rule"),
                ))
            conn.commit()

    def get_context_patterns(
        self,
        minsky_phase: Optional[int] = None,
        snr_score: Optional[float] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Retourne les règles apprises pour un contexte donné.
        Utilisé par le Parlement (Strate 6) pour briefer les agents.
        """
        snr_bucket = self._snr_bucket(snr_score) if snr_score is not None else None
        query = "SELECT pattern_hash, rule, confidence, observations, wins, avg_pnl FROM context_patterns WHERE 1=1"
        params: list = []

        if minsky_phase is not None:
            query += " AND minsky_phase = ?"
            params.append(minsky_phase)
        if snr_bucket:
            query += " AND snr_range = ?"
            params.append(snr_bucket)

        query += " AND confidence >= 0.6 ORDER BY confidence DESC, observations DESC LIMIT ?"
        params.append(limit)

        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(query, params).fetchall()
            return [
                {
                    "pattern": r[0], "rule": r[1], "confidence": r[2],
                    "observations": r[3], "wins": r[4], "avg_pnl": r[5],
                }
                for r in rows if r[1]
            ]
        except Exception as exc:
            logger.debug("[Learning] get_context_patterns error: %s", exc)
            return []

    # ── Mise à jour des stats mémoire ─────────────────────────────────────────

    def _update_memory(self, agent_name: str, outcome: TradeOutcome) -> None:
        """Met à jour les stats numériques d'un agent en SQLite."""
        mem = self.get_memory(agent_name)

        mem.total_trades  += 1
        mem.total_pnl_usd += outcome.pnl_usd
        mem.total_pnl_pct += outcome.pnl_pct
        if outcome.is_win:
            mem.total_wins    += 1
            mem.current_streak = max(mem.current_streak + 1, 1)
        else:
            mem.current_streak = min(mem.current_streak - 1, -1)

        mem.best_trade_pct  = max(mem.best_trade_pct,  outcome.pnl_pct)
        mem.worst_trade_pct = min(mem.worst_trade_pct, outcome.pnl_pct)

        asset_key = outcome.asset
        ast = mem.asset_stats.setdefault(asset_key, {"total": 0, "wins": 0, "pnl_pct": 0.0})
        ast["total"]  += 1
        ast["wins"]   += int(outcome.is_win)
        ast["pnl_pct"] = ast["pnl_pct"] * (1 - LEARNING_RATE) + outcome.pnl_pct * LEARNING_RATE

        if agent_name == "ScanAgent" and outcome.tech_signal:
            self._update_indicator_weights(mem, outcome)

        self.save_memory(mem)

    def _update_indicator_weights(self, mem: AgentMemory, outcome: TradeOutcome) -> None:
        """Ajuste le poids de chaque indicateur selon le résultat du trade."""
        tech  = outcome.tech_signal
        alpha = mem.adaptive_params.get("learning_rate", LEARNING_RATE)

        indicators = {
            "rsi":    self._rsi_was_correct(tech.get("rsi"), outcome),
            "macd":   self._macd_was_correct(tech.get("macd_hist"), outcome),
            "bb":     self._bb_was_correct(tech.get("bb_position"), outcome),
            "volume": outcome.is_win,
        }

        for ind_name, was_correct in indicators.items():
            key = f"{ind_name}:{tech.get('timeframe','?')}:{outcome.asset}"
            current_weight = mem.indicator_weights.get(key, 1.0)

            if was_correct:
                new_weight = current_weight + alpha * (WEIGHT_MAX - current_weight)
            else:
                new_weight = current_weight - alpha * (current_weight - WEIGHT_MIN)

            mem.indicator_weights[key] = round(max(WEIGHT_MIN, min(WEIGHT_MAX, new_weight)), 4)

            stats_key = f"{ind_name}:{outcome.asset}"
            stats = mem.indicator_stats.setdefault(stats_key, {"total": 0, "wins": 0, "avg_pnl": 0.0})
            stats["total"] += 1
            stats["wins"]  += int(was_correct)
            stats["avg_pnl"] = stats["avg_pnl"] * (1 - alpha) + outcome.pnl_pct * alpha

    def _apply_counterfactual_to_regime(
        self, cf: CounterfactualResult, outcome: TradeOutcome
    ) -> None:
        """
        Stocke les résultats contrefactuels dans le contexte de l'insight futur.
        Ne modifie plus les paramètres directement — utilisé comme input pour le LLM.
        """
        if cf.improvement_pct > 0.5:
            logger.info(
                "[Learning] Contrefactuel %s : SL %.2fx TP 1:%.2f aurait donné +%.1f%%",
                outcome.asset, cf.best_sl_mult, cf.best_tp_ratio, cf.improvement_pct,
            )

    # ── Analyse contrefactuelle ───────────────────────────────────────────────

    def run_counterfactual(
        self,
        outcome: TradeOutcome,
        ohlcv_data: Optional[np.ndarray] = None,
    ) -> Optional[CounterfactualResult]:
        """
        Pour un trade perdant : cherche quelle combinaison SL/TP aurait été profitable.
        Résultat utilisé comme contexte pour l'analyse LLM.
        """
        if outcome.is_win:
            return None

        entry  = outcome.entry_price
        sl     = outcome.stop_loss
        atr_approx = abs(entry - sl) / 1.5
        is_buy = (outcome.side.value == "buy")

        best_pnl, best_sl, best_tp, best_exit = outcome.pnl_pct, 1.5, 2.5, outcome.exit_reason

        if ohlcv_data is not None and len(ohlcv_data) > 0:
            for sl_mult in SL_MULTIPLIERS:
                for tp_ratio in TP_RATIOS:
                    sim_sl = entry - sl_mult * atr_approx if is_buy else entry + sl_mult * atr_approx
                    sim_tp = entry + sl_mult * atr_approx * tp_ratio if is_buy else entry - sl_mult * atr_approx * tp_ratio
                    pnl, exit_reason = self._simulate_trade(ohlcv_data, entry, sim_sl, sim_tp, is_buy)
                    if pnl > best_pnl:
                        best_pnl, best_sl, best_tp, best_exit = pnl, sl_mult, tp_ratio, exit_reason
        else:
            if outcome.max_favorable > 0:
                for sl_mult in SL_MULTIPLIERS:
                    if sl_mult > 1.5:
                        for tp_ratio in TP_RATIOS:
                            sl_dist = sl_mult * atr_approx / entry * 100
                            tp_dist = sl_dist * tp_ratio
                            if outcome.max_favorable >= tp_dist * 0.7:
                                est_pnl = tp_dist * 0.8
                                if est_pnl > best_pnl:
                                    best_pnl, best_sl, best_tp = est_pnl, sl_mult, tp_ratio

        improvement = best_pnl - outcome.pnl_pct
        lesson = self._generate_lesson(outcome, best_sl, best_tp, improvement)

        return CounterfactualResult(
            trade_outcome   = outcome,
            actual_pnl_pct  = outcome.pnl_pct,
            actual_exit     = str(outcome.exit_reason),
            best_sl_mult    = best_sl,
            best_tp_ratio   = best_tp,
            best_pnl_pct    = best_pnl,
            best_exit       = str(best_exit),
            improvement_pct = improvement,
            lesson          = lesson,
            param_updates   = {"sl_atr_multiplier": best_sl, "tp_rr_ratio": best_tp},
        )

    # ── Journal Obsidian (simplifié — Decision 3) ─────────────────────────────

    def _append_to_daily_journal(
        self,
        outcome: TradeOutcome,
        cf: Optional[CounterfactualResult],
    ) -> None:
        """
        Ajoute une entrée au journal quotidien consolidé.
        Un seul fichier par jour au lieu d'un fichier par trade.
        """
        today_str = date.today().isoformat()
        result_icon = "WIN" if outcome.is_win else "LOSS"
        cf_note = f" — CF: SL {cf.best_sl_mult:.1f}x aurait donné {cf.best_pnl_pct:+.1f}%" if cf and cf.improvement_pct > 0.5 else ""

        entry = (
            f"- {datetime.now(timezone.utc).strftime('%H:%M')} UTC | "
            f"{outcome.asset} {outcome.side.value.upper()} {result_icon} {outcome.pnl_pct:+.2f}%"
            f"{cf_note}\n"
        )

        try:
            journal_dir = Path(self.obsidian.vault_path) / "journal"
            journal_dir.mkdir(exist_ok=True)
            journal_file = journal_dir / f"{today_str}.md"

            if not journal_file.exists():
                journal_file.write_text(
                    f"# ORACLE — Journal {today_str}\n\n"
                    f"## Macro Context\n<!-- Mis à jour par WorldModel -->\n\n"
                    f"## Trades\n",
                    encoding="utf-8",
                )

            with open(journal_file, "a", encoding="utf-8") as f:
                f.write(entry)

        except Exception as exc:
            logger.debug("[Learning] Journal write error: %s", exc)

    # ── Migration depuis Obsidian (legacy) ────────────────────────────────────

    def _migrate_from_obsidian(self, agent_name: str) -> Optional[AgentMemory]:
        """
        Tente de charger la mémoire depuis vault/config/{agent}_memory.md.
        Utilisé une seule fois lors de la migration SQLite.
        """
        try:
            note = self.obsidian.read_note("config", f"{agent_name}_memory")
            if note is None or not note.frontmatter:
                return None

            fm = note.frontmatter
            import re
            blocks = []
            for match in re.finditer(r'```json\s*\n(.*?)\n```', note.content, re.DOTALL):
                try:
                    blocks.append(json.loads(match.group(1)))
                except json.JSONDecodeError:
                    blocks.append({})

            mem = AgentMemory(
                agent_name      = agent_name,
                version         = fm.get("version", 1),
                total_trades    = fm.get("total_trades", 0),
                total_wins      = fm.get("total_wins", 0),
                total_pnl_usd   = fm.get("total_pnl_usd", 0.0),
                total_pnl_pct   = fm.get("total_pnl_pct", 0.0),
                best_trade_pct  = fm.get("best_trade_pct", 0.0),
                worst_trade_pct = fm.get("worst_trade_pct", 0.0),
                last_updated    = fm.get("last_updated", ""),
            )
            if len(blocks) >= 1:
                mem.adaptive_params    = blocks[0] or mem.adaptive_params
            if len(blocks) >= 2:
                mem.indicator_weights  = blocks[1] or {}
            if len(blocks) >= 3:
                mem.indicator_stats    = blocks[2] or {}
            if len(blocks) >= 4:
                mem.asset_stats        = blocks[3] or {}
            if len(blocks) >= 5:
                mem.regime_params      = blocks[4] or mem.regime_params

            logger.info("[Learning] Migration Obsidian → SQLite pour %s", agent_name)
            return mem
        except Exception as exc:
            logger.debug("[Learning] Migration error pour %s : %s", agent_name, exc)
            return None

    # ── Helpers SQLite ────────────────────────────────────────────────────────

    def _read_memory_sqlite(self, agent_name: str) -> Optional[tuple]:
        """Lit la ligne SQLite pour un agent."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                return conn.execute(
                    "SELECT * FROM agent_memory WHERE agent_name = ? AND regime = 'global'",
                    (agent_name,)
                ).fetchone()
        except Exception:
            return None

    def _row_to_memory(self, agent_name: str, row: tuple) -> AgentMemory:
        """Reconstruit un AgentMemory depuis une ligne SQLite."""
        # Colonnes : id, agent_name, regime, total_trades, total_wins, total_pnl_usd,
        #            total_pnl_pct, best_trade_pct, worst_trade_pct, current_streak,
        #            adaptive_params, indicator_weights, indicator_stats, asset_stats,
        #            regime_params, updated_at
        mem = AgentMemory(
            agent_name      = agent_name,
            total_trades    = row[3],
            total_wins      = row[4],
            total_pnl_usd   = row[5],
            total_pnl_pct   = row[6],
            best_trade_pct  = row[7],
            worst_trade_pct = row[8],
            current_streak  = row[9],
            last_updated    = row[15] or "",
        )
        try:
            mem.adaptive_params    = json.loads(row[10] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            mem.indicator_weights  = json.loads(row[11] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            mem.indicator_stats    = json.loads(row[12] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            mem.asset_stats        = json.loads(row[13] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            mem.regime_params      = json.loads(row[14] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        return mem

    @staticmethod
    def _snr_bucket(snr: Optional[float]) -> Optional[str]:
        """Discrétise un SNR en bucket pour le pattern_hash."""
        if snr is None:
            return None
        if snr < 0.2:   return "0.0-0.2"
        if snr < 0.35:  return "0.2-0.35"
        if snr < 0.5:   return "0.35-0.5"
        if snr < 0.7:   return "0.5-0.7"
        return "0.7-1.0"

    def _get_relevant_patterns(
        self,
        minsky_phase: Optional[int],
        snr_score: Optional[float],
    ) -> list[dict]:
        """Récupère les patterns pertinents pour le contexte actuel."""
        return self.get_context_patterns(minsky_phase, snr_score, limit=3)

    # ── Simulation contrefactuelle ────────────────────────────────────────────

    @staticmethod
    def _simulate_trade(
        ohlcv: np.ndarray, entry: float, sl: float, tp: float, is_buy: bool
    ) -> tuple[float, str]:
        for bar in ohlcv:
            _, o, h, l, c = float(bar[0]), float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
            if is_buy:
                if l <= sl:  return (sl - entry) / entry * 100, "stop_loss"
                if h >= tp:  return (tp - entry) / entry * 100, "take_profit"
            else:
                if h >= sl:  return (entry - sl) / entry * 100, "stop_loss"
                if l <= tp:  return (entry - tp) / entry * 100, "take_profit"
        last_close = float(ohlcv[-1][4])
        return (1 if is_buy else -1) * (last_close - entry) / entry * 100, "timeout"

    @staticmethod
    def _generate_lesson(
        outcome: TradeOutcome, best_sl: float, best_tp: float, improvement: float
    ) -> str:
        lessons = []
        if best_sl > 1.8:
            lessons.append(f"SL trop serré. Un SL à {best_sl}×ATR aurait évité le stop prématuré.")
        if best_tp > 3.0:
            lessons.append(f"TP conservateur. Ratio 1:{best_tp} aurait capturé +{improvement:.1f}%.")
        if improvement > 2.0:
            lessons.append(f"Trade potentiellement gagnant avec meilleurs params (+{improvement:.1f}% possible).")
        return " ".join(lessons) or f"Signal faible. Augmenter la confiance requise pour {outcome.asset}."

    @staticmethod
    def _rsi_was_correct(rsi: Optional[float], outcome: TradeOutcome) -> bool:
        if rsi is None:
            return outcome.is_win
        if outcome.side.value == "buy":
            return (rsi < 50 and outcome.is_win) or (rsi >= 50 and not outcome.is_win)
        return (rsi > 50 and outcome.is_win) or (rsi <= 50 and not outcome.is_win)

    @staticmethod
    def _macd_was_correct(macd_hist: Optional[float], outcome: TradeOutcome) -> bool:
        if macd_hist is None:
            return outcome.is_win
        if outcome.side.value == "buy":
            return (macd_hist > 0) == outcome.is_win
        return (macd_hist < 0) == outcome.is_win

    @staticmethod
    def _bb_was_correct(bb_pos: Optional[float], outcome: TradeOutcome) -> bool:
        if bb_pos is None:
            return outcome.is_win
        if outcome.side.value == "buy":
            return (bb_pos < 0.3) == outcome.is_win
        return (bb_pos > 0.7) == outcome.is_win
