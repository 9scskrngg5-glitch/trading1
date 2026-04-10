"""
Strate 3 — Narrative Epidemiology Engine
"Les marchés ne bougent pas sur des fondamentaux — ils bougent sur des récits." — Robert Shiller

Théorie : Shiller (Narrative Economics, 2019) modélise la propagation des récits
économiques avec un modèle SIR épidémiologique (Susceptible → Infected → Recovered).

Les narratives crypto suivent un cycle de vie prévisible en 5 phases :
  SEEDING  → récit embryonnaire, pas encore viral
  GROWTH   → R0 > 1.2, propagation exponentielle (signal : renforcer les longs)
  PEAK     → R0 ≈ 1, virulence maximale (signal : attention retournement, réduire)
  DECAY    → R0 < 0.9, récit qui s'épuise (signal : bearish si narrative haussière)
  EXTINCT  → récit mort, volume résiduel (signal : opportunité contrarian)

Mathématiques SIR discrètes :
  I(t) = volume articles/posts (proxy de la population "infectée")
  r    = E[ln(I(t)/I(t−1))]  [taux de croissance log quotidien]
  R0   = 1 + r / γ           [nombre reproductif]
  γ    = 0.10 /jour           [taux de guérison — narratives crypto durent ~10j]

Sources de données (sans nouvelles dépendances — httpx + stdlib xml.etree) :
  CryptoPanic   → posts tagués BTC/ETH, vote-count comme pondération virale
  RSS mainstream → CoinDesk, CoinTelegraph, Decrypt, Bitcoin Magazine, CryptoBriefing

Stockage : vault/world_model/narrative_sir.db
Cache :    1 heure par narrative pour éviter le rate-limit CryptoPanic
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Paramètres SIR ────────────────────────────────────────────────────────────

GAMMA_DEFAULT:    float = 0.10    # taux de guérison γ (1/demi-vie en jours)
R0_WINDOW_DAYS:   int   = 7       # fenêtre d'estimation du R0
NORM_WINDOW_DAYS: int   = 30      # fenêtre de normalisation du viral_score

# ── Seuils de phase ───────────────────────────────────────────────────────────

R0_GROWTH_THRESHOLD: float = 1.20   # R0 > 1.20 → GROWTH
R0_PEAK_LOW:         float = 0.90   # R0 ∈ [0.90, 1.20] → PEAK
VIRAL_SEEDING_MAX:   float = 0.05   # score < 5% → SEEDING
VIRAL_EXTINCT_MAX:   float = 0.02   # score < 2% → EXTINCT

# ── Cache et réseau ───────────────────────────────────────────────────────────

CACHE_TTL_SEC: int   = 3600   # 1 heure entre deux appels par narrative
HTTP_TIMEOUT:  float = 10.0   # secondes

CRYPTOPANIC_URL: str = "https://cryptopanic.com/api/developer/v2/posts/"

RSS_FEEDS: list[str] = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/feed",
    "https://cryptobriefing.com/feed/",
]

# ── Narratives par défaut (id → keywords) ─────────────────────────────────────

DEFAULT_NARRATIVES: dict[str, list[str]] = {
    "btc_store_of_value":     ["bitcoin store of value", "digital gold", "btc hedge inflation"],
    "institutional_adoption": ["institutional bitcoin", "etf bitcoin", "corporate treasury", "blackrock"],
    "halving_cycle":          ["bitcoin halving", "halving pump", "block reward", "mining reward"],
    "defi_summer":            ["defi", "yield farming", "liquidity pool", "dex volume"],
    "eth_ultrasound":         ["ultrasound money", "eth burn", "eip-1559", "ethereum deflationary"],
    "bear_capitulation":      ["crypto dead", "bitcoin obituary", "crypto winter", "capitulation"],
    "regulatory_crackdown":   ["sec bitcoin", "crypto regulation", "crypto ban", "exchange shutdown"],
    "ai_crypto":              ["ai crypto", "artificial intelligence blockchain", "crypto ai agent"],
}

# Narratives intrinsèquement baissières (peur, répression, capitulation)
_BEARISH_NARRATIVE_IDS: frozenset[str] = frozenset({"bear_capitulation", "regulatory_crackdown"})


# ── Énumérations ──────────────────────────────────────────────────────────────

class NarrativePhase(str, Enum):
    SEEDING = "seeding"
    GROWTH  = "growth"
    PEAK    = "peak"
    DECAY   = "decay"
    EXTINCT = "extinct"

    @property
    def emoji(self) -> str:
        return {"seeding": "🌱", "growth": "📈", "peak": "🔴", "decay": "📉", "extinct": "💀"}[self.value]


class NarrativeType(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class NarrativeRecord:
    """État SIR instantané d'une narrative unique."""
    narrative_id:   str
    volume_today:   float           # articles/posts comptés aujourd'hui
    viral_score:    float           # [0, 1] — I(t) / I_max sur fenêtre historique
    r0:             float           # nombre reproductif estimé
    growth_rate:    float           # taux de croissance log r (non clippé)
    phase:          NarrativePhase
    narrative_type: NarrativeType
    market_impact:  str             # "bullish" / "bearish" / "neutral"


@dataclass
class NarrativeSIRResult:
    """Résultat complet de l'analyse narrative SIR pour tous les actifs."""
    dominant_narrative: str
    dominant_phase:     NarrativePhase
    dominant_r0:        float
    ecosystem_heat:     float           # [0, 1] — chaleur narrative globale
    market_impact:      str             # impact agrégé : "bullish" / "bearish" / "neutral"
    sizing_modifier:    float           # multiplicateur de taille de position
    records:            list[NarrativeRecord]
    signals:            list[str]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Sérialise le résultat pour transmission au PredictAgent ou au log."""
        return {
            "dominant_narrative": self.dominant_narrative,
            "dominant_phase":     self.dominant_phase.value,
            "dominant_r0":        round(self.dominant_r0, 3),
            "ecosystem_heat":     round(self.ecosystem_heat, 3),
            "market_impact":      self.market_impact,
            "sizing_modifier":    round(self.sizing_modifier, 2),
            "narratives": [
                {
                    "id":          r.narrative_id,
                    "viral_score": round(r.viral_score, 3),
                    "r0":          round(r.r0, 3),
                    "phase":       r.phase.value,
                    "type":        r.narrative_type.value,
                    "impact":      r.market_impact,
                    "growth_rate": round(r.growth_rate, 4),
                }
                for r in self.records
            ],
            "signals":   self.signals,
            "timestamp": self.timestamp,
        }

    def summary(self) -> str:
        """Résumé une ligne pour les logs."""
        icon = self.dominant_phase.emoji
        return (
            f"{icon} Narrative dominante : '{self.dominant_narrative}' "
            f"(phase={self.dominant_phase.value}, R0={self.dominant_r0:.2f})\n"
            f"  Chaleur écosystème : {self.ecosystem_heat:.0%} | "
            f"Impact : {self.market_impact} | sizing ×{self.sizing_modifier:.2f}\n"
            f"  {' | '.join(self.signals[:3])}"
        )


class BacktestResult:
    """Résultats du backtest de la strate narrative SIR sur données historiques."""

    def __init__(self, results: list[dict]):
        self.results = results

    def summary(self) -> str:
        """Affiche les statistiques de backtest."""
        if not self.results:
            return "Aucun résultat de backtest."

        n = len(self.results)
        by_phase = {p.value: [r for r in self.results if r.get("phase") == p.value] for p in NarrativePhase}

        lines = [
            f"\n{'═' * 57}",
            f"  BACKTEST STRATE 3 — Narrative SIR",
            f"{'═' * 57}",
            f"  Observations : {n}",
        ]

        for phase, rows in by_phase.items():
            if rows:
                lines.append(f"  Phase {phase.upper():<10}: {len(rows):>4} ({len(rows)/n:.1%})")

        if self.results and "pnl_pct" in self.results[0]:
            for phase in [NarrativePhase.GROWTH, NarrativePhase.PEAK, NarrativePhase.DECAY]:
                pnl = [r["pnl_pct"] for r in by_phase[phase.value] if "pnl_pct" in r]
                if pnl:
                    lines.append(
                        f"  P&L moyen {phase.value.upper():<10}: {np.mean(pnl):+.3f}%  "
                        f"WR={sum(1 for x in pnl if x > 0)/len(pnl):.1%}"
                    )

        lines.append(f"{'═' * 57}\n")
        return "\n".join(lines)


# ── Moteur principal ──────────────────────────────────────────────────────────

class NarrativeEpidemiologyEngine:
    """
    Strate 3 — Modèle SIR épidémiologique des narratives crypto (Shiller 2019).

    Modélise la propagation des récits économiques en estimant un nombre
    reproductif R0 depuis la série temporelle du volume de mentions.

    Fail-safe : toute erreur réseau retourne un état neutre sans bloquer
    les autres strates ni le pipeline de trading.

    Usage :
        engine = NarrativeEpidemiologyEngine(vault_path=Path("vault"),
                                              cryptopanic_key="...",  # optionnel
                                              gamma=0.10)
        result = await engine.analyze()
        # result["dominant_narrative"], result["dominant_r0"], result["market_impact"]...

        bt = engine.backtest(df)   # df avec colonnes 'volume' et optionnel 'pnl_pct'
        print(bt.summary())
    """

    def __init__(
        self,
        vault_path:       Optional[Path]                    = None,
        gamma:            float                             = GAMMA_DEFAULT,
        cryptopanic_key:  Optional[str]                    = None,
        narratives:       Optional[dict[str, list[str]]]   = None,
        r0_window_days:   int                              = R0_WINDOW_DAYS,
        norm_window_days: int                              = NORM_WINDOW_DAYS,
    ):
        self._vault_path      = vault_path
        self._gamma           = gamma
        self._cp_key          = cryptopanic_key
        self._narratives      = narratives or DEFAULT_NARRATIVES
        self._r0_window       = r0_window_days
        self._norm_window     = norm_window_days

        # Cache mémoire : narrative_id → (timestamp_unix, volume)
        self._volume_cache: dict[str, tuple[float, float]] = {}

        self._db_path: Optional[Path] = None
        if vault_path:
            db_dir = vault_path / "world_model"
            db_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = db_dir / "narrative_sir.db"
            self._init_db()

        self._last_result: Optional[NarrativeSIRResult] = None

    # ── Interface publique ────────────────────────────────────────────────────

    async def analyze(self) -> dict:
        """
        Lance l'analyse narrative SIR complète.

        1. Fetche les volumes de mentions pour chaque narrative (CryptoPanic + RSS)
        2. Persiste les volumes dans SQLite
        3. Estime R0 depuis l'historique
        4. Classifie les phases et calcule l'impact marché agrégé
        5. Retourne un dict sérialisable (interface compatible PredictAgent)

        Returns:
            dict avec : dominant_narrative, dominant_phase, dominant_r0,
            ecosystem_heat, market_impact, sizing_modifier, narratives, signals.
        """
        today_str = date.today().isoformat()

        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "OracleTrading/2.0"},
        ) as client:
            volumes = await self._fetch_all_volumes(client)

        # Persiste et construit les records
        records: list[NarrativeRecord] = []
        for nid, keywords in self._narratives.items():
            vol = volumes.get(nid, 0.0)
            self._save_volume(nid, today_str, vol)

            history  = self._load_history(nid, self._norm_window)
            all_vols = [v for _, v in history] + [vol]
            max_vol  = max(all_vols) if all_vols else 1.0
            viral_score = float(np.clip(vol / max(max_vol, 1e-6), 0.0, 1.0))

            series_I = [v for _, v in sorted(history, key=lambda x: x[0])[-self._r0_window:]]
            series_I.append(vol)
            r0, growth_rate = self._estimate_r0(series_I)

            phase   = self._classify_phase(r0, viral_score)
            ntype   = NarrativeType.BEARISH if nid in _BEARISH_NARRATIVE_IDS else NarrativeType.BULLISH
            impact  = self._compute_market_impact(phase, ntype)

            records.append(NarrativeRecord(
                narrative_id   = nid,
                volume_today   = vol,
                viral_score    = viral_score,
                r0             = r0,
                growth_rate    = growth_rate,
                phase          = phase,
                narrative_type = ntype,
                market_impact  = impact,
            ))

        # Tri par pertinence : viral_score × R0
        records_sorted = sorted(records, key=lambda r: r.viral_score * max(r.r0, 0.1), reverse=True)
        dominant = records_sorted[0] if records_sorted else None

        ecosystem_heat   = float(np.mean([r.viral_score for r in records])) if records else 0.0
        sizing_modifier  = self._compute_sizing_modifier(records)
        market_impact    = self._aggregate_market_impact(records)
        signals          = self._generate_signals(records_sorted[:3])

        result = NarrativeSIRResult(
            dominant_narrative = dominant.narrative_id if dominant else "none",
            dominant_phase     = dominant.phase if dominant else NarrativePhase.SEEDING,
            dominant_r0        = dominant.r0 if dominant else 1.0,
            ecosystem_heat     = ecosystem_heat,
            market_impact      = market_impact,
            sizing_modifier    = sizing_modifier,
            records            = records,
            signals            = signals,
        )

        logger.info("[Strate3] %s", result.summary())
        self._last_result = result
        self._save_result_to_db(result)
        return result.to_dict()

    def backtest(self, df: pd.DataFrame) -> BacktestResult:
        """
        Backtest du modèle SIR sur un DataFrame historique.

        Rejoue le calcul de R0 et de phase sur une colonne de volume
        historique ligne par ligne (fenêtre glissante).

        Args:
            df: DataFrame avec au minimum :
                - 'volume' (float) — proxy I(t), ex. nb d'articles par jour
                - 'pnl_pct' (float, optionnel) — pour les métriques qualité
                - 'narrative_type' (str, optionnel) — "bullish" / "bearish"

        Returns:
            BacktestResult avec .summary() pour affichage.
        """
        if "volume" not in df.columns:
            logger.warning("[Strate3] Backtest : colonne 'volume' manquante.")
            return BacktestResult(results=[])

        series = df["volume"].values.astype(float)
        results: list[dict] = []

        for i in range(self._r0_window + 1, len(df)):
            window = series[max(0, i - self._r0_window): i + 1]
            r0, growth_rate = self._estimate_r0(list(window))

            max_vol = float(np.max(series[:i + 1])) if i > 0 else 1.0
            viral_score = float(np.clip(series[i] / max(max_vol, 1e-6), 0.0, 1.0))
            phase = self._classify_phase(r0, viral_score)

            row: dict = {
                "idx":         i,
                "r0":          round(r0, 3),
                "phase":       phase.value,
                "viral_score": round(viral_score, 3),
                "growth_rate": round(growth_rate, 4),
            }
            if "pnl_pct" in df.columns:
                row["pnl_pct"] = float(df["pnl_pct"].iloc[i])
            results.append(row)

        return BacktestResult(results=results)

    @property
    def last_result(self) -> Optional[NarrativeSIRResult]:
        """Dernier résultat calculé (None si jamais appelé)."""
        return self._last_result

    # ── SIR Core Math ─────────────────────────────────────────────────────────

    def _estimate_r0(self, volume_series: list[float]) -> tuple[float, float]:
        """
        Estime R0 et le taux de croissance r depuis une série I(t).

        Méthode log-linéaire :
          r  = moyenne des rendements log quotidiens de la série
          R0 = 1 + r / γ

        Si la série est trop courte (<2 points), retourne (1.0, 0.0) — neutre.
        Le R0 est clippé à [0, 10] pour éviter les artefacts numériques.

        Returns:
            (r0, growth_rate) — r0 ∈ [0, 10], growth_rate non clippé.
        """
        arr = np.array(volume_series, dtype=float)
        arr = np.maximum(arr, 1.0)  # évite log(0)

        if len(arr) < 2:
            return 1.0, 0.0

        log_returns = np.diff(np.log(arr))
        r = float(np.mean(log_returns))
        r0 = 1.0 + r / max(self._gamma, 1e-6)
        return float(np.clip(r0, 0.0, 10.0)), r

    @staticmethod
    def _classify_phase(r0: float, viral_score: float) -> NarrativePhase:
        """
        Classifie la phase SIR depuis R0 et le score viral normalisé.

        EXTINCT  : volume quasi-nul (< 2% du max historique)
        SEEDING  : volume faible (2%–5%), récit émergent
        GROWTH   : R0 > R0_GROWTH_THRESHOLD — expansion exponentielle
        PEAK     : R0 ∈ [R0_PEAK_LOW, R0_GROWTH_THRESHOLD] — virulence maximale
        DECAY    : R0 < R0_PEAK_LOW — récit en perte de vitesse
        """
        if viral_score < VIRAL_EXTINCT_MAX:
            return NarrativePhase.EXTINCT
        if viral_score < VIRAL_SEEDING_MAX:
            return NarrativePhase.SEEDING
        if r0 > R0_GROWTH_THRESHOLD:
            return NarrativePhase.GROWTH
        if r0 >= R0_PEAK_LOW:
            return NarrativePhase.PEAK
        return NarrativePhase.DECAY

    @staticmethod
    def _compute_market_impact(phase: NarrativePhase, ntype: NarrativeType) -> str:
        """
        Déduit l'impact marché de la combinaison (phase, type de narrative).

        Narrative BULLISH :
          GROWTH → "bullish"  (momentum narratif en expansion)
          PEAK   → "neutral"  (risque "sell the news", tous achetés)
          DECAY  → "bearish"  (le récit s'effondre, les gens décèlent)

        Narrative BEARISH :
          GROWTH → "bearish"  (la peur se propage)
          PEAK   → "neutral"  (peur maximale → contrarian bullish proche)
          DECAY  → "bullish"  (la peur s'estompe → rebond probable)
        """
        _BULLISH_MAP = {
            NarrativePhase.SEEDING: "neutral",
            NarrativePhase.GROWTH:  "bullish",
            NarrativePhase.PEAK:    "neutral",
            NarrativePhase.DECAY:   "bearish",
            NarrativePhase.EXTINCT: "neutral",
        }
        _BEARISH_MAP = {
            NarrativePhase.SEEDING: "neutral",
            NarrativePhase.GROWTH:  "bearish",
            NarrativePhase.PEAK:    "neutral",
            NarrativePhase.DECAY:   "bullish",
            NarrativePhase.EXTINCT: "neutral",
        }
        return _BULLISH_MAP[phase] if ntype == NarrativeType.BULLISH else _BEARISH_MAP[phase]

    def _compute_sizing_modifier(self, records: list[NarrativeRecord]) -> float:
        """
        Calcule le modificateur de sizing basé sur la cohérence des narratives.

        Logique de pondération :
          +5% par narrative haussière en GROWTH (cap : +10%)
          −10% par narrative baissière en GROWTH (cap : −10%)
          −5% par narrative haussière en PEAK   (cap : −10%) — risque retournement
          +3% si narrative baissière en DECAY   — signal contrarian

        Le modificateur est clippé ∈ [0.70, 1.20] pour rester cohérent
        avec les multiplicateurs des autres strates.
        """
        bullish_growth = sum(1 for r in records if r.phase == NarrativePhase.GROWTH  and r.narrative_type == NarrativeType.BULLISH)
        bearish_growth = sum(1 for r in records if r.phase == NarrativePhase.GROWTH  and r.narrative_type == NarrativeType.BEARISH)
        bullish_peak   = sum(1 for r in records if r.phase == NarrativePhase.PEAK    and r.narrative_type == NarrativeType.BULLISH)
        bearish_decay  = sum(1 for r in records if r.phase == NarrativePhase.DECAY   and r.narrative_type == NarrativeType.BEARISH)

        modifier = 1.0
        modifier += 0.05 * min(bullish_growth, 2)
        modifier -= 0.10 * min(bearish_growth, 1)
        modifier -= 0.05 * min(bullish_peak,   2)
        modifier += 0.03 * min(bearish_decay,  1)

        return float(np.clip(modifier, 0.70, 1.20))

    @staticmethod
    def _aggregate_market_impact(records: list[NarrativeRecord]) -> str:
        """
        Agrège l'impact marché de toutes les narratives pondérées par viral_score.

        Un score agrégé > 0.2 → "bullish", < −0.2 → "bearish", sinon "neutral".
        """
        score  = 0.0
        weight = 0.0
        for r in records:
            w = r.viral_score
            if r.market_impact == "bullish":
                score += w
            elif r.market_impact == "bearish":
                score -= w
            weight += w

        if weight < 1e-6:
            return "neutral"
        norm = score / weight
        if norm > 0.20:
            return "bullish"
        if norm < -0.20:
            return "bearish"
        return "neutral"

    # ── Fetch réseau ──────────────────────────────────────────────────────────

    async def _fetch_all_volumes(self, client: httpx.AsyncClient) -> dict[str, float]:
        """
        Fetche en séquence les volumes de chaque narrative.

        Séquentiel (pas parallèle) pour respecter les rate limits CryptoPanic.
        Chaque narrative est cachée 1 heure pour éviter les appels redondants.
        """
        volumes: dict[str, float] = {}
        for nid, keywords in self._narratives.items():
            try:
                volumes[nid] = await self._fetch_one_volume(client, nid, keywords)
            except Exception as exc:
                logger.debug("[Strate3] Volume fetch error '%s': %s", nid, exc)
                volumes[nid] = 0.0
        return volumes

    async def _fetch_one_volume(
        self,
        client:      httpx.AsyncClient,
        narrative_id: str,
        keywords:    list[str],
    ) -> float:
        """
        Fetche le volume de mentions pour une narrative avec cache 1h.

        Priorité : CryptoPanic (plus précis, votes pondérés) → RSS (fallback).
        """
        # Cache hit ?
        cached = self._volume_cache.get(narrative_id)
        if cached and (time.time() - cached[0]) < CACHE_TTL_SEC:
            return cached[1]

        volume = 0.0

        if self._cp_key:
            try:
                volume += await self._fetch_cryptopanic(client, keywords)
            except Exception as exc:
                logger.debug("[Strate3] CryptoPanic '%s': %s", narrative_id, exc)

        try:
            volume += await self._fetch_rss(client, keywords)
        except Exception as exc:
            logger.debug("[Strate3] RSS '%s': %s", narrative_id, exc)

        self._volume_cache[narrative_id] = (time.time(), volume)
        return volume

    async def _fetch_cryptopanic(
        self,
        client:   httpx.AsyncClient,
        keywords: list[str],
    ) -> float:
        """
        Fetche les posts CryptoPanic "hot" et compte ceux contenant les keywords.

        Les upvotes sont log-transformés pour pondérer la virality sans exploser
        sur les posts extrêmement populaires.

        Returns:
            Score de virality pondéré par upvotes (float ≥ 0).
        """
        params = {"auth_token": self._cp_key, "filter": "hot",
                  "currencies": "BTC,ETH", "public": "true"}
        resp = await client.get(CRYPTOPANIC_URL, params=params)
        resp.raise_for_status()
        posts = resp.json().get("results", [])

        kw_lower = [kw.lower() for kw in keywords]
        score = 0.0
        for post in posts:
            text = ((post.get("title") or "") + " " + (post.get("body") or "")).lower()
            if any(kw in text for kw in kw_lower):
                upvotes = (post.get("votes") or {}).get("positive", 0) or 0
                score += math.log1p(upvotes + 1)

        return score

    async def _fetch_rss(
        self,
        client:   httpx.AsyncClient,
        keywords: list[str],
    ) -> float:
        """
        Compte les articles RSS récents (24h) contenant les keywords.

        Utilise xml.etree.ElementTree (stdlib) — aucune dépendance externe.
        Supporte les formats RSS 2.0 (<item>) et Atom (<entry>).

        Returns:
            Nombre d'articles matchés (float).
        """
        kw_lower = [kw.lower() for kw in keywords]
        cutoff   = datetime.now(timezone.utc) - timedelta(hours=24)
        count    = 0.0

        for feed_url in RSS_FEEDS:
            try:
                resp = await client.get(feed_url)
                if resp.status_code != 200:
                    continue

                root  = ET.fromstring(resp.text)
                items = root.findall(".//item")
                if not items:
                    items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                for item in items:
                    title = _xml_text(item, ["title",
                                             "{http://www.w3.org/2005/Atom}title"])
                    desc  = _xml_text(item, ["description", "summary",
                                             "{http://www.w3.org/2005/Atom}summary"])
                    text  = (title + " " + desc).lower()
                    if any(kw in text for kw in kw_lower):
                        count += 1.0

            except Exception as exc:
                logger.debug("[Strate3] RSS parse error (%s): %s", feed_url, exc)

        return count

    # ── Signaux log ──────────────────────────────────────────────────────────

    @staticmethod
    def _generate_signals(top_records: list[NarrativeRecord]) -> list[str]:
        """Génère des descriptions textuelles des narratives les plus actives."""
        signals = []
        for r in top_records:
            if r.viral_score < VIRAL_EXTINCT_MAX:
                continue
            signals.append(
                f"{r.phase.emoji} '{r.narrative_id}' "
                f"R0={r.r0:.2f} score={r.viral_score:.0%} → {r.market_impact}"
            )
        return signals if signals else ["Aucune narrative dominante détectée"]

    # ── SQLite ────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Initialise les tables SQLite pour l'historique de volume et les résultats."""
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS narrative_volumes (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        narrative_id TEXT NOT NULL,
                        date         TEXT NOT NULL,
                        volume       REAL NOT NULL DEFAULT 0.0,
                        UNIQUE(narrative_id, date)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS narrative_results (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp          TEXT NOT NULL,
                        dominant_narrative TEXT NOT NULL,
                        dominant_phase     TEXT NOT NULL,
                        dominant_r0        REAL NOT NULL,
                        ecosystem_heat     REAL NOT NULL,
                        market_impact      TEXT NOT NULL,
                        sizing_modifier    REAL NOT NULL,
                        records_json       TEXT
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_volumes_nar_date
                    ON narrative_volumes (narrative_id, date DESC)
                """)
                conn.commit()
        except Exception as exc:
            logger.warning("[Strate3] DB init error: %s", exc)

    def _save_volume(self, narrative_id: str, date_str: str, volume: float) -> None:
        """
        Sauvegarde le volume journalier d'une narrative en SQLite.

        En cas de conflit (même date), accumule les volumes
        pour gérer les appels multiples dans la même journée.
        """
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT INTO narrative_volumes (narrative_id, date, volume)
                    VALUES (?, ?, ?)
                    ON CONFLICT(narrative_id, date)
                    DO UPDATE SET volume = MAX(excluded.volume, volume)
                """, (narrative_id, date_str, volume))
                conn.commit()
        except Exception as exc:
            logger.debug("[Strate3] DB volume save error: %s", exc)

    def _load_history(self, narrative_id: str, days: int) -> list[tuple[str, float]]:
        """
        Charge l'historique de volume pour une narrative sur N jours.

        Returns:
            Liste de (date_str, volume) triée par date ASC.
        """
        if not self._db_path or not self._db_path.exists():
            return []
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute("""
                    SELECT date, volume FROM narrative_volumes
                    WHERE narrative_id = ?
                    ORDER BY date DESC LIMIT ?
                """, (narrative_id, days)).fetchall()
            return [(r[0], float(r[1])) for r in reversed(rows)]
        except Exception as exc:
            logger.debug("[Strate3] DB history load error: %s", exc)
            return []

    def _save_result_to_db(self, result: NarrativeSIRResult) -> None:
        """Persiste le résultat complet pour traçabilité et analyse post-mortem."""
        if not self._db_path:
            return
        try:
            records_json = json.dumps([
                {"id": r.narrative_id, "r0": round(r.r0, 3),
                 "phase": r.phase.value, "viral_score": round(r.viral_score, 3)}
                for r in result.records
            ])
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT INTO narrative_results
                    (timestamp, dominant_narrative, dominant_phase, dominant_r0,
                     ecosystem_heat, market_impact, sizing_modifier, records_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.timestamp,
                    result.dominant_narrative,
                    result.dominant_phase.value,
                    result.dominant_r0,
                    result.ecosystem_heat,
                    result.market_impact,
                    result.sizing_modifier,
                    records_json,
                ))
                conn.commit()
        except Exception as exc:
            logger.debug("[Strate3] DB result save error: %s", exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _xml_text(element: ET.Element, tags: list[str]) -> str:
    """
    Extrait le texte du premier tag trouvé parmi une liste de candidats.
    Gère RSS 2.0 et Atom sans bibliothèque externe.
    """
    for tag in tags:
        child = element.find(tag)
        if child is not None and child.text:
            return child.text
    return ""
