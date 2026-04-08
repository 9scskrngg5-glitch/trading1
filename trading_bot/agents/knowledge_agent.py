"""
Agent 10 — Knowledge Agent (Financial Wikipedia)
Base de connaissances vectorielle pour le trading.

Architecture :
- FAISS (si installé) ou numpy cosine similarity (fallback)
- Chaque entrée = vecteur de features de marché + metadata
- Indexe les trades passés, régimes, patterns
- Répond aux requêtes de similarité des autres agents
- Vault : vault/patterns/

Features vector (8 dimensions) :
    [0] price_change_pct / 10   (normalisé)
    [1] volume_ratio / 3        (volume vs moyenne, normalisé)
    [2] adx / 100               (0–1)
    [3] atr_pct / 10            (normalisé)
    [4] confidence / 100        (0–1)
    [5] regime_encoded          (0=unknown, 0.25=ranging, 0.5=trending_up, 0.75=trending_down, 1.0=volatile)
    [6] direction_encoded       (0=sell, 0.5=neutral, 1.0=buy)
    [7] outcome_encoded         (0=loss, 0.5=unknown, 1.0=win) — pour les trades fermés
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from core.base_agent import BaseAgent
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)

# ── FAISS optionnel — fallback numpy si non installé ─────────────────────────
try:
    import faiss  # type: ignore
    FAISS_AVAILABLE = True
    logger.info("[KnowledgeAgent] FAISS disponible — recherche vectorielle accélérée")
except ImportError:
    FAISS_AVAILABLE = False
    logger.info("[KnowledgeAgent] FAISS non installé — numpy cosine similarity utilisé")

FEATURE_DIM = 8

REGIME_ENCODING = {
    "unknown":       0.00,
    "ranging":       0.25,
    "trending_up":   0.50,
    "trending_down": 0.75,
    "volatile":      1.00,
}

DIRECTION_ENCODING = {
    "sell":    0.0,
    "neutral": 0.5,
    "buy":     1.0,
    "long":    1.0,
    "short":   0.0,
}


class KnowledgeEntry:
    """Une entrée dans la base de connaissances."""

    __slots__ = ("id", "timestamp", "asset", "type", "vector", "metadata")

    def __init__(
        self,
        entry_id: str,
        timestamp: str,
        asset: str,
        entry_type: str,      # "trade", "pattern", "regime_event", "macro_event"
        vector: np.ndarray,
        metadata: dict,
    ):
        self.id        = entry_id
        self.timestamp = timestamp
        self.asset     = asset
        self.type      = entry_type
        self.vector    = vector.astype(np.float32)
        self.metadata  = metadata

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "timestamp": self.timestamp,
            "asset":     self.asset,
            "type":      self.type,
            "vector":    self.vector.tolist(),
            "metadata":  self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeEntry":
        return cls(
            entry_id   = d["id"],
            timestamp  = d["timestamp"],
            asset      = d["asset"],
            entry_type = d["type"],
            vector     = np.array(d["vector"], dtype=np.float32),
            metadata   = d["metadata"],
        )


class KnowledgeAgent(BaseAgent):
    """
    Agent de base de connaissances vectorielle — Financial Wikipedia.

    Fonctions :
    1. Indexe chaque trade clôturé, régime détecté, pattern repéré
    2. Répond aux requêtes de similarité (channel knowledge:query)
    3. Enrichit les décisions en rappelant les situations analogues passées
    4. Détecte les patterns récurrents gagnants/perdants
    5. Génère des notes Obsidian pour le graphe de connaissances
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        config: dict,
        telegram=None,
    ):
        super().__init__("KnowledgeAgent", "patterns", bus, obsidian, config)
        self.telegram = telegram

        self._entries: list[KnowledgeEntry] = []
        self._vectors: np.ndarray | None    = None   # matrice Nx8 pour numpy search
        self._index                         = None   # FAISS index si dispo

        self._db_path = (
            obsidian.vault_path.parent / "data" / "knowledge_db.json"
        )
        self._max_entries  = config.get("knowledge_max_entries", 5000)
        self._pattern_threshold = 3   # min occurrences pour créer une note de pattern

        # Stats
        self._queries_answered: int = 0
        self._entries_indexed:  int = 0

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        (self.obsidian.vault_path / "patterns").mkdir(exist_ok=True)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_db()
        self._rebuild_index()
        logger.info(
            "[%s] Base de connaissances chargée : %d entrées | FAISS=%s",
            self.name, len(self._entries), FAISS_AVAILABLE,
        )

    def _register_subscriptions(self) -> None:
        # Indexer les trades clôturés
        self.bus.subscribe(CHANNELS["portfolio_update"],     self._on_trade_closed)
        # Indexer les changements de régime
        self.bus.subscribe(CHANNELS["regime"],               self._on_regime_update)
        # Répondre aux requêtes de similarité
        self.bus.subscribe(CHANNELS["knowledge_query"],      self._on_knowledge_query)
        # Indexer les signaux techniques (patterns)
        self.bus.subscribe(CHANNELS["signals_technical"],    self._on_technical_signal)

    # ── Handlers bus ──────────────────────────────────────────────────────────

    async def _on_trade_closed(self, data: dict) -> None:
        """Indexe un trade clôturé avec son outcome."""
        if data.get("type") != "trade_closed":
            return

        is_win = data.get("is_win", False)
        vec    = self._build_trade_vector(data)
        if vec is None:
            return

        entry = KnowledgeEntry(
            entry_id   = f"trade_{data.get('asset', '?')}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            timestamp  = datetime.now(timezone.utc).isoformat(),
            asset      = data.get("asset", "?"),
            entry_type = "trade",
            vector     = vec,
            metadata   = {
                "is_win":     is_win,
                "pnl_pct":    data.get("pnl_pct", 0.0),
                "direction":  data.get("direction", "?"),
                "regime":     data.get("regime", "unknown"),
                "confidence": data.get("confidence", 0),
                "reason":     data.get("lesson", ""),
            },
        )
        self._add_entry(entry)
        await self._detect_and_write_patterns(entry)
        logger.debug("[%s] Trade indexé : %s %s", self.name, data.get("asset"), "WIN" if is_win else "LOSS")

    async def _on_regime_update(self, data: dict) -> None:
        """Indexe un changement de régime."""
        if data.get("type") != "regime_update":
            return

        vec = np.array([
            0.0,                                                    # price_change (n/a)
            0.0,                                                    # volume_ratio (n/a)
            min(float(data.get("adx",    0)) / 100.0, 1.0),       # adx
            min(float(data.get("atr_pct", 1)) / 10.0, 1.0),       # atr_pct
            0.5,                                                    # confidence (n/a)
            REGIME_ENCODING.get(data.get("regime", "unknown"), 0), # regime
            0.5,                                                    # direction (neutral)
            0.5,                                                    # outcome (unknown)
        ], dtype=np.float32)

        entry = KnowledgeEntry(
            entry_id   = f"regime_{data.get('asset','?')}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            timestamp  = datetime.now(timezone.utc).isoformat(),
            asset      = data.get("asset", "?"),
            entry_type = "regime_event",
            vector     = vec,
            metadata   = {
                "regime":         data.get("regime"),
                "adx":            data.get("adx"),
                "atr_pct":        data.get("atr_pct"),
                "volume_anomaly": data.get("volume_anomaly"),
            },
        )
        self._add_entry(entry)

    async def _on_technical_signal(self, data: dict) -> None:
        """Indexe les signaux techniques significatifs (confiance > 60)."""
        if int(data.get("confidence", 0)) < 60:
            return

        vec = self._build_signal_vector(data)
        if vec is None:
            return

        entry = KnowledgeEntry(
            entry_id   = f"signal_{data.get('asset','?')}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[:17]}",
            timestamp  = datetime.now(timezone.utc).isoformat(),
            asset      = data.get("asset", "?"),
            entry_type = "pattern",
            vector     = vec,
            metadata   = {
                "signal":     data.get("signal"),
                "confidence": data.get("confidence"),
                "timeframe":  data.get("timeframe", "1h"),
                "indicators": {
                    "rsi":  data.get("rsi"),
                    "macd": data.get("macd"),
                },
            },
        )
        self._add_entry(entry)

    async def _on_knowledge_query(self, data: dict) -> None:
        """
        Répond à une requête de similarité.
        Message attendu : {
            "requester":  "PredictAgent",
            "asset":      "BTC/USDT",
            "query_vec":  [8 floats],   ← optionnel, sinon reconstruit depuis les champs
            "context":    { ... },
            "k":          5,
        }
        """
        requester = data.get("requester", "?")
        asset     = data.get("asset", "?")
        k         = min(int(data.get("k", 5)), 20)

        # Construire le vecteur de requête
        query_vec_raw = data.get("query_vec")
        if query_vec_raw:
            query_vec = np.array(query_vec_raw, dtype=np.float32)
        else:
            ctx = data.get("context", {})
            query_vec = self._build_context_vector(ctx)

        if query_vec is None or len(self._entries) == 0:
            await self.bus.publish(CHANNELS["knowledge_result"], {
                "type":       "knowledge_response",
                "requester":  requester,
                "asset":      asset,
                "similar":    [],
                "insight":    "Base de connaissances vide — aucune situation similaire.",
                "win_rate":   0.5,
            })
            return

        # Recherche de similarité
        similar = self._search_similar(query_vec, k=k, asset_filter=asset)
        insight, win_rate = self._generate_insight(similar)

        self._queries_answered += 1
        logger.debug(
            "[%s] Requête de %s pour %s → %d résultats | WR historique=%.0f%%",
            self.name, requester, asset, len(similar), win_rate * 100,
        )

        await self.bus.publish(CHANNELS["knowledge_result"], {
            "type":       "knowledge_response",
            "requester":  requester,
            "asset":      asset,
            "similar":    similar,
            "insight":    insight,
            "win_rate":   round(win_rate, 3),
            "n_similar":  len(similar),
        })

    # ── Cycle principal ───────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        """Sauvegarde périodique de la DB + nettoyage si > max_entries."""
        if len(self._entries) > self._max_entries:
            # Garder les N plus récentes
            self._entries = self._entries[-self._max_entries:]
            self._rebuild_index()
            logger.info("[%s] DB nettoyée — %d entrées conservées", self.name, len(self._entries))

        self._save_db()
        logger.info(
            "[%s] DB: %d entrées | requêtes répondues: %d",
            self.name, len(self._entries), self._queries_answered,
        )

    # ── Index vectoriel ───────────────────────────────────────────────────────

    def _add_entry(self, entry: KnowledgeEntry) -> None:
        """Ajoute une entrée et met à jour l'index."""
        self._entries.append(entry)
        self._entries_indexed += 1

        vec = entry.vector.reshape(1, FEATURE_DIM)
        if FAISS_AVAILABLE and self._index is not None:
            self._index.add(vec)
        elif self._vectors is None:
            self._vectors = vec
        else:
            self._vectors = np.vstack([self._vectors, vec])

    def _rebuild_index(self) -> None:
        """Reconstruit l'index complet depuis self._entries."""
        if not self._entries:
            self._vectors = None
            self._index   = None
            return

        matrix = np.vstack([e.vector.reshape(1, FEATURE_DIM) for e in self._entries]).astype(np.float32)

        if FAISS_AVAILABLE:
            self._index = faiss.IndexFlatL2(FEATURE_DIM)
            self._index.add(matrix)
            self._vectors = None
        else:
            self._vectors = matrix
            self._index   = None

    def _search_similar(
        self,
        query: np.ndarray,
        k: int = 5,
        asset_filter: str | None = None,
    ) -> list[dict]:
        """
        Cherche les k entrées les plus similaires.
        FAISS si disponible, sinon cosine similarity numpy.
        """
        if not self._entries:
            return []

        q = query.reshape(1, FEATURE_DIM).astype(np.float32)

        if FAISS_AVAILABLE and self._index is not None:
            actual_k = min(k * 3, len(self._entries))   # sur-échantillonne pour filtrage asset
            distances, indices = self._index.search(q, actual_k)
            candidates = [
                (int(idx), float(dist))
                for idx, dist in zip(indices[0], distances[0])
                if 0 <= idx < len(self._entries)
            ]
        else:
            if self._vectors is None:
                return []
            # Cosine similarity
            norms = np.linalg.norm(self._vectors, axis=1, keepdims=True) + 1e-8
            q_norm = np.linalg.norm(q) + 1e-8
            sims = (self._vectors @ q.T).flatten() / (norms.flatten() * q_norm)
            top_k = min(k * 3, len(self._entries))
            indices = np.argsort(sims)[::-1][:top_k]
            candidates = [(int(i), float(1 - sims[i])) for i in indices]  # convert to distance

        # Filtrage optionnel par asset
        results = []
        for idx, dist in candidates:
            entry = self._entries[idx]
            if asset_filter and entry.asset != asset_filter:
                continue
            results.append({
                "id":        entry.id,
                "asset":     entry.asset,
                "type":      entry.type,
                "timestamp": entry.timestamp,
                "distance":  round(dist, 4),
                "metadata":  entry.metadata,
            })
            if len(results) >= k:
                break

        return results

    # ── Génération d'insights ──────────────────────────────────────────────────

    def _generate_insight(self, similar: list[dict]) -> tuple[str, float]:
        """
        Génère un insight textuel et un win_rate historique
        à partir des situations similaires trouvées.
        """
        if not similar:
            return "Aucune situation similaire trouvée.", 0.5

        trades = [s for s in similar if s["type"] == "trade"]
        if not trades:
            return f"{len(similar)} situations similaires trouvées (pas encore de trades).", 0.5

        wins   = sum(1 for t in trades if t["metadata"].get("is_win", False))
        total  = len(trades)
        wr     = wins / total if total > 0 else 0.5
        avg_pnl = sum(t["metadata"].get("pnl_pct", 0) for t in trades) / max(total, 1)

        if wr >= 0.65:
            outlook = "Contexte FAVORABLE — situations similaires gagnantes dans {:.0f}% des cas".format(wr * 100)
        elif wr <= 0.35:
            outlook = "Contexte DÉFAVORABLE — situations similaires perdantes dans {:.0f}% des cas".format((1 - wr) * 100)
        else:
            outlook = "Contexte NEUTRE — historique mixte ({:.0f}% WR sur {} trades similaires)".format(wr * 100, total)

        reasons = [t["metadata"].get("reason", "") for t in trades if t["metadata"].get("reason")]
        if reasons:
            common = max(set(reasons), key=reasons.count)
            outlook += f" | Motif fréquent : {common[:80]}"

        return outlook, wr

    async def _detect_and_write_patterns(self, new_entry: KnowledgeEntry) -> None:
        """Détecte les patterns récurrents et écrit des notes dans vault/patterns/."""
        if len(self._entries) < self._pattern_threshold:
            return

        # Chercher des situations similaires récentes
        similar = self._search_similar(new_entry.vector, k=10)
        trades  = [s for s in similar if s["type"] == "trade"]

        if len(trades) < self._pattern_threshold:
            return

        wins   = sum(1 for t in trades if t["metadata"].get("is_win"))
        wr     = wins / len(trades)

        if wr >= 0.70 or wr <= 0.30:
            self._write_pattern_note(new_entry, trades, wr)

    def _write_pattern_note(
        self,
        trigger: KnowledgeEntry,
        similar_trades: list[dict],
        win_rate: float,
    ) -> None:
        """Écrit une note de pattern dans vault/patterns/."""
        date_str   = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        asset_safe = trigger.asset.replace("/", "_")
        is_bullish = win_rate >= 0.70
        pattern_type = "winning" if is_bullish else "losing"
        emoji = "✅" if is_bullish else "⚠️"

        frontmatter = {
            "date":         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "agent":        "KnowledgeAgent",
            "asset":        trigger.asset,
            "type":         "pattern",
            "pattern_type": pattern_type,
            "win_rate":     round(win_rate, 3),
            "sample_size":  len(similar_trades),
            "tags":         ["pattern", trigger.asset.replace("/","_"), pattern_type],
        }

        trades_md = "\n".join(
            f"| `{t['timestamp'][:10]}` | `{t['metadata'].get('direction','?')}` "
            f"| `{'WIN' if t['metadata'].get('is_win') else 'LOSS'}` "
            f"| `{t['metadata'].get('pnl_pct',0):+.2f}%` |"
            for t in similar_trades[:8]
        )

        content = f"""## {emoji} Pattern Détecté — {trigger.asset}

**Type :** `{pattern_type.upper()}`
**Win Rate sur situations similaires :** `{win_rate:.0%}` ({len(similar_trades)} trades)

### Contexte du Pattern
| Paramètre | Valeur |
|---|---|
| Régime | `{trigger.metadata.get('regime', '?')}` |
| Direction | `{trigger.metadata.get('direction', '?')}` |
| Confiance | `{trigger.metadata.get('confidence', 0)}/100` |

### Trades Similaires
| Date | Direction | Résultat | P&L |
|---|---|---|---|
{trades_md}

### Insight
{self._generate_insight(similar_trades)[0]}

### Liens
[[agents/KnowledgeAgent]] | [[agents/PredictAgent]] | [[agents/MetaAgent]]
"""
        self.obsidian.write_note(
            "patterns",
            f"pattern_{asset_safe}_{pattern_type}_{date_str}",
            frontmatter,
            content,
        )

    # ── Constructeurs de vecteurs ──────────────────────────────────────────────

    def _build_trade_vector(self, data: dict) -> np.ndarray | None:
        """Construit le vecteur de feature pour un trade clôturé."""
        try:
            pnl_pct    = float(data.get("pnl_pct", 0.0))
            confidence = float(data.get("confidence", 50))
            regime     = str(data.get("regime", "unknown"))
            direction  = str(data.get("direction", "neutral")).lower()
            is_win     = bool(data.get("is_win", False))

            return np.array([
                max(min(pnl_pct / 10.0, 1.0), -1.0),
                0.5,                                                         # volume_ratio (n/a)
                0.3,                                                         # adx (n/a)
                0.2,                                                         # atr_pct (n/a)
                confidence / 100.0,
                REGIME_ENCODING.get(regime, 0.0),
                DIRECTION_ENCODING.get(direction, 0.5),
                1.0 if is_win else 0.0,
            ], dtype=np.float32)
        except Exception:
            return None

    def _build_signal_vector(self, data: dict) -> np.ndarray | None:
        """Construit le vecteur de feature pour un signal technique."""
        try:
            confidence = float(data.get("confidence", 50))
            signal     = str(data.get("signal", "neutral")).lower()
            rsi        = float(data.get("rsi", 50))

            return np.array([
                0.0,                                    # price_change (n/a)
                min(float(data.get("volume_ratio", 1.0)) / 3.0, 1.0),
                0.3,                                    # adx (n/a)
                0.2,                                    # atr_pct (n/a)
                confidence / 100.0,
                0.25,                                   # regime (n/a)
                DIRECTION_ENCODING.get(signal, 0.5),
                (rsi / 100.0),
            ], dtype=np.float32)
        except Exception:
            return None

    def _build_context_vector(self, ctx: dict) -> np.ndarray | None:
        """Construit un vecteur de requête depuis un contexte de marché."""
        try:
            return np.array([
                float(ctx.get("price_change_pct",  0.0)) / 10.0,
                min(float(ctx.get("volume_ratio",  1.0)) / 3.0, 1.0),
                min(float(ctx.get("adx",           20))  / 100.0, 1.0),
                min(float(ctx.get("atr_pct",        1))  / 10.0,  1.0),
                float(ctx.get("confidence",         50)) / 100.0,
                REGIME_ENCODING.get(ctx.get("regime", "unknown"), 0.0),
                DIRECTION_ENCODING.get(str(ctx.get("direction", "neutral")).lower(), 0.5),
                0.5,
            ], dtype=np.float32)
        except Exception:
            return None

    # ── Persistance ───────────────────────────────────────────────────────────

    def _save_db(self) -> None:
        """Sauvegarde la base de connaissances en JSON."""
        try:
            data = [e.to_dict() for e in self._entries]
            self._db_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("[%s] Erreur sauvegarde DB: %s", self.name, exc)

    def _load_db(self) -> None:
        """Charge la base depuis le fichier JSON s'il existe."""
        if not self._db_path.exists():
            logger.info("[%s] Nouvelle base de connaissances créée.", self.name)
            return
        try:
            raw = json.loads(self._db_path.read_text(encoding="utf-8"))
            self._entries = [KnowledgeEntry.from_dict(d) for d in raw]
            self._entries_indexed = len(self._entries)
            logger.info("[%s] %d entrées chargées depuis %s", self.name, len(self._entries), self._db_path)
        except Exception as exc:
            logger.warning("[%s] Erreur lecture DB: %s", self.name, exc)
            self._entries = []

    # ── API publique ──────────────────────────────────────────────────────────

    def query_sync(self, context: dict, k: int = 5, asset: str | None = None) -> dict:
        """
        API synchrone pour les agents qui veulent enrichir leur décision
        sans passer par le bus (appel direct dans le même process).
        """
        vec = self._build_context_vector(context)
        if vec is None or not self._entries:
            return {"similar": [], "insight": "Base vide.", "win_rate": 0.5}
        similar    = self._search_similar(vec, k=k, asset_filter=asset)
        insight, wr = self._generate_insight(similar)
        return {"similar": similar, "insight": insight, "win_rate": wr}

    @property
    def entry_count(self) -> int:
        return len(self._entries)
