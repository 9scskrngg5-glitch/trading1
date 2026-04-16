"""
Strate 1 — World Model Engine
"Avant de regarder les prix, comprends la réalité qui les cause."

Théorie : W. Brian Arthur (Complexity Economics) — les économies sont des systèmes
adaptatifs complexes, pas des équilibres. Dalio's "economic machine" — modélise
les flux, pas les prix.

Sources de données :
  FRED API     → M2, CPI, PCE, Yield Curve (2Y-10Y), ISM, UNRATE, FFR
  yfinance     → DXY, VIX, Gold, Oil WTI, Copper
  CoinGecko    → BTC dominance, total market cap (gratuit, sans clé)
  Binance REST → funding rates (via httpx, clé optionnelle)

Régimes :
  RISK_ON     → macro positive, VIX bas, DXY en baisse, crypto en hausse
  RISK_OFF    → VIX élevé, DXY en hausse, crypto en baisse, courbe inversée
  STAGFLATION → inflation forte, croissance faible
  DEFLATION   → inflation négative, prix en chute
  TRANSITION  → signaux mixtes, régime en changement

Cache :
  vault/world_model/cache.json — FRED/yfinance : 6h, Binance/CoinGecko : 15min

Usage :
    engine = WorldModelEngine(fred_api_key="...", vault_path=Path("vault"))
    await engine.initialize()
    snapshot = await engine.fetch_macro_snapshot()
    regime   = engine.classify_regime(snapshot)
    mc       = engine.run_monte_carlo(snapshot, n_scenarios=1000)
    vector   = engine.get_world_state_vector()
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

CACHE_TTL_MACRO_SEC  = 6 * 3600    # 6 heures pour FRED / yfinance
CACHE_TTL_CRYPTO_SEC = 15 * 60     # 15 minutes pour Binance / CoinGecko

MONTE_CARLO_DAYS = 180             # 6 mois
MONTE_CARLO_N    = 1000            # scénarios

BINANCE_REST = "https://api.binance.com"
COINGECKO    = "https://api.coingecko.com/api/v3"

# Séries FRED et leur signification
FRED_SERIES = {
    "m2":           "M2SL",       # M2 Money Supply (milliards USD)
    "cpi":          "CPIAUCSL",   # CPI tous urbains (index)
    "pce":          "PCEPILFE",   # PCE core (index)
    "yield_curve":  "T10Y2Y",     # 10Y − 2Y spread (points de base → %)
    "ism":          "NAPM",       # ISM Manufacturing PMI
    "unemployment": "UNRATE",     # Taux de chômage (%)
    "fed_funds":    "FEDFUNDS",   # Fed Funds Rate (%)
}

# Tickers yfinance
YFINANCE_TICKERS = {
    "dxy":    "DX-Y.NYB",  # Dollar Index
    "vix":    "^VIX",      # VIX
    "gold":   "GC=F",      # Gold futures
    "oil":    "CL=F",      # WTI Crude Oil futures
    "copper": "HG=F",      # Copper futures
}

# Seuils de classification de régime
REGIME_THRESHOLDS = {
    "vix_high":         25.0,   # VIX > 25 → stress
    "vix_extreme":      35.0,   # VIX > 35 → panique
    "yield_curve_inv":  -0.20,  # Spread < -0.20% → courbe inversée (récession)
    "ism_expansion":    50.0,   # ISM > 50 → expansion
    "ism_contraction":  45.0,   # ISM < 45 → contraction forte
    "cpi_high":          4.0,   # CPI YoY > 4% → inflation élevée
    "cpi_deflation":     0.0,   # CPI YoY < 0 → déflation
    "unemployment_high": 6.0,   # Chômage > 6% → récession potentielle
    "dxy_strong":      104.0,   # DXY > 104 → dollar fort → risk-off
    "btc_dom_high":     55.0,   # BTC dominance > 55% → alt-coins en retrait
}


# ── Énumérations et dataclasses ───────────────────────────────────────────────

class MacroRegime(str, Enum):
    RISK_ON     = "risk_on"
    RISK_OFF    = "risk_off"
    STAGFLATION = "stagflation"
    DEFLATION   = "deflation"
    TRANSITION  = "transition"


@dataclass
class MacroSnapshot:
    """Instantané complet de l'état macroéconomique mondial."""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # FRED
    m2_growth_yoy:      float = 0.0   # % croissance M2 YoY
    cpi_yoy:            float = 2.0   # % CPI YoY
    pce_yoy:            float = 2.0   # % PCE YoY
    yield_curve:        float = 0.5   # spread 10Y−2Y en %
    ism_pmi:            float = 50.0  # ISM Manufacturing PMI
    unemployment:       float = 4.0   # % chômage
    fed_funds_rate:     float = 5.0   # % taux directeur Fed

    # yfinance
    dxy:                float = 100.0  # Dollar Index
    vix:                float = 20.0   # VIX
    gold_usd:           float = 2000.0 # Gold $/oz
    oil_usd:            float = 75.0   # WTI $/baril
    copper_usd:         float = 4.0    # Copper $/lb

    # Crypto (CoinGecko + Binance)
    btc_dominance:      float = 50.0   # % dominance BTC
    total_market_cap_b: float = 2000.0 # Capitalisation totale crypto en Mds USD
    btc_funding_rate:   float = 0.01   # % funding rate BTC (8h)
    eth_funding_rate:   float = 0.01   # % funding rate ETH (8h)

    # Indicateurs dérivés (calculés dans post_init)
    real_rate:          float = 0.0    # fed_funds_rate − cpi_yoy
    yield_curve_signal: int   = 0      # +1 normale, 0 flat, -1 inversée

    # Qualité des données
    data_quality:       float = 1.0    # 0.0 (tout simulé) → 1.0 (tout réel)
    sources_used:       list  = field(default_factory=list)

    def __post_init__(self):
        self.real_rate = self.fed_funds_rate - self.cpi_yoy
        if self.yield_curve > 0.5:
            self.yield_curve_signal = 1
        elif self.yield_curve < REGIME_THRESHOLDS["yield_curve_inv"]:
            self.yield_curve_signal = -1
        else:
            self.yield_curve_signal = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MacroSnapshot":
        d = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        obj = cls(**d)
        return obj


@dataclass
class RegimeClassification:
    """Résultat de la classification de régime macroéconomique."""
    regime:     MacroRegime
    confidence: float   # 0.0 → 1.0
    scores:     dict    # {regime_name: score} pour traçabilité
    signals:    list    # Signaux ayant contribué à la décision
    timestamp:  str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "regime":     self.regime.value,
            "confidence": round(self.confidence, 3),
            "scores":     {k: round(v, 3) for k, v in self.scores.items()},
            "signals":    self.signals,
            "timestamp":  self.timestamp,
        }


@dataclass
class ScenarioDistribution:
    """Distribution de probabilités issue du Monte Carlo."""
    n_scenarios:    int
    horizon_days:   int
    # Probabilités de régime à l'horizon
    prob_bull:      float   # prix BTC > +20%
    prob_bear:      float   # prix BTC < -20%
    prob_neutral:   float   # entre -20% et +20%
    # Statistiques de la distribution
    median_return:  float   # médiane des retours simulés
    var_95:         float   # Value at Risk 95% (perte maximale dans 95% des cas)
    cvar_95:        float   # Expected Shortfall 95%
    best_case:      float   # 95e percentile des retours
    worst_case:     float   # 5e percentile des retours
    # Paths résumés (percentiles)
    path_p10:       list    # trajectoire au 10e percentile
    path_p50:       list    # trajectoire médiane
    path_p90:       list    # trajectoire au 90e percentile
    timestamp:      str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "n_scenarios":   self.n_scenarios,
            "horizon_days":  self.horizon_days,
            "prob_bull":     round(self.prob_bull, 3),
            "prob_bear":     round(self.prob_bear, 3),
            "prob_neutral":  round(self.prob_neutral, 3),
            "median_return": round(self.median_return, 4),
            "var_95":        round(self.var_95, 4),
            "cvar_95":       round(self.cvar_95, 4),
            "best_case":     round(self.best_case, 4),
            "worst_case":    round(self.worst_case, 4),
            "timestamp":     self.timestamp,
        }


# ── Moteur principal ──────────────────────────────────────────────────────────

class WorldModelEngine:
    """
    Moteur de modélisation du monde macroéconomique.

    Agrège des données macro (FRED, yfinance, CoinGecko, Binance),
    classifie le régime courant, et projette des scénarios Monte Carlo.

    Conçu pour alimenter les agents du Parlement (Strate 6) avec un vecteur
    d'état normalisé de 14 dimensions.

    Fail-graceful : si une source de données est indisponible, le moteur
    utilise les dernières valeurs en cache ou des valeurs neutres par défaut.
    """

    def __init__(
        self,
        fred_api_key: str          = "",
        vault_path:   Optional[Path] = None,
        http_client=None,           # httpx.AsyncClient injecté (tests)
    ):
        self._fred_key    = fred_api_key
        self._vault_path  = vault_path
        self._http        = http_client  # None → créé dans initialize()
        self._owns_http   = http_client is None

        self._last_snapshot:  Optional[MacroSnapshot]       = None
        self._last_regime:    Optional[RegimeClassification] = None
        self._last_mc:        Optional[ScenarioDistribution] = None

        # Timestamps de dernière mise à jour par source
        self._ts_macro:  float = 0.0
        self._ts_crypto: float = 0.0

        if vault_path:
            wm_dir = vault_path / "world_model"
            wm_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path = wm_dir / "cache.json"
        else:
            self._cache_path = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Crée le client HTTP et charge le cache existant."""
        if self._owns_http:
            import httpx
            self._http = httpx.AsyncClient(timeout=15)
        self._load_cache()
        logger.info("[Strate1] WorldModelEngine initialisé.")

    async def close(self) -> None:
        if self._owns_http and self._http:
            await self._http.aclose()

    # ── API principale ────────────────────────────────────────────────────────

    async def fetch_macro_snapshot(self) -> MacroSnapshot:
        """
        Récupère l'état macroéconomique complet.

        Politique de cache :
          FRED/yfinance  → rafraîchi si > 6 heures
          CoinGecko/Binance → rafraîchi si > 15 minutes

        Returns:
            MacroSnapshot avec data_quality ∈ [0, 1] et sources_used listant
            les sources réellement contactées.
        """
        now = time.time()
        macro_stale  = (now - self._ts_macro)  > CACHE_TTL_MACRO_SEC
        crypto_stale = (now - self._ts_crypto) > CACHE_TTL_CRYPTO_SEC

        # Partir du dernier snapshot ou d'un snapshot neutre
        if self._last_snapshot:
            snap = MacroSnapshot(**{
                k: getattr(self._last_snapshot, k)
                for k in MacroSnapshot.__dataclass_fields__
            })
        else:
            snap = MacroSnapshot()

        snap.sources_used = []
        sources_ok = 0
        sources_tried = 0

        # ── Données macro (FRED + yfinance) ──────────────────────────────────
        if macro_stale:
            sources_tried += 2

            fred_data = await self._fetch_fred()
            if fred_data:
                snap.m2_growth_yoy  = fred_data.get("m2_growth_yoy",  snap.m2_growth_yoy)
                snap.cpi_yoy        = fred_data.get("cpi_yoy",        snap.cpi_yoy)
                snap.pce_yoy        = fred_data.get("pce_yoy",        snap.pce_yoy)
                snap.yield_curve    = fred_data.get("yield_curve",     snap.yield_curve)
                snap.ism_pmi        = fred_data.get("ism_pmi",         snap.ism_pmi)
                snap.unemployment   = fred_data.get("unemployment",    snap.unemployment)
                snap.fed_funds_rate = fred_data.get("fed_funds_rate",  snap.fed_funds_rate)
                snap.sources_used.append("FRED")
                sources_ok += 1

            yf_data = await self._fetch_yfinance()
            if yf_data:
                snap.dxy      = yf_data.get("dxy",    snap.dxy)
                snap.vix      = yf_data.get("vix",    snap.vix)
                snap.gold_usd = yf_data.get("gold",   snap.gold_usd)
                snap.oil_usd  = yf_data.get("oil",    snap.oil_usd)
                snap.copper_usd = yf_data.get("copper", snap.copper_usd)
                snap.sources_used.append("yfinance")
                sources_ok += 1

            if fred_data or yf_data:
                self._ts_macro = now

        # ── Données crypto (CoinGecko + Binance) ─────────────────────────────
        if crypto_stale:
            sources_tried += 2

            cg_data = await self._fetch_coingecko()
            if cg_data:
                snap.btc_dominance      = cg_data.get("btc_dominance", snap.btc_dominance)
                snap.total_market_cap_b = cg_data.get("total_market_cap_b", snap.total_market_cap_b)
                snap.sources_used.append("CoinGecko")
                sources_ok += 1

            fr_data = await self._fetch_funding_rates()
            if fr_data:
                snap.btc_funding_rate = fr_data.get("btc", snap.btc_funding_rate)
                snap.eth_funding_rate = fr_data.get("eth", snap.eth_funding_rate)
                snap.sources_used.append("Binance")
                sources_ok += 1

            if cg_data or fr_data:
                self._ts_crypto = now

        # ── Indicateurs dérivés ───────────────────────────────────────────────
        snap.real_rate = snap.fed_funds_rate - snap.cpi_yoy
        if snap.yield_curve > 0.5:
            snap.yield_curve_signal = 1
        elif snap.yield_curve < REGIME_THRESHOLDS["yield_curve_inv"]:
            snap.yield_curve_signal = -1
        else:
            snap.yield_curve_signal = 0

        snap.timestamp    = datetime.now(timezone.utc).isoformat()
        snap.data_quality = sources_ok / max(sources_tried, 1) if sources_tried > 0 else (
            1.0 if self._last_snapshot else 0.0
        )

        self._last_snapshot = snap
        self._save_cache()

        logger.info(
            "[Strate1] Snapshot | CPI=%.1f%% VIX=%.1f DXY=%.1f BTC_dom=%.1f%% "
            "YieldCurve=%.2f%% Qualité=%.0f%% Sources=%s",
            snap.cpi_yoy, snap.vix, snap.dxy, snap.btc_dominance,
            snap.yield_curve, snap.data_quality * 100, snap.sources_used,
        )
        return snap

    def classify_regime(self, snapshot: MacroSnapshot) -> RegimeClassification:
        """
        Classifie le régime macroéconomique courant.

        Scoring multi-indicateurs : chaque indicateur vote pour un régime.
        Le régime final = score le plus élevé. Confiance = écart entre
        le 1er et le 2e score normalisé par le total.

        Returns:
            RegimeClassification avec régime, confiance [0,1], scores détaillés
            et liste des signaux ayant contribué.
        """
        scores = {r.value: 0.0 for r in MacroRegime}
        signals = []

        # ── VIX (stress du marché) ────────────────────────────────────────────
        if snapshot.vix > REGIME_THRESHOLDS["vix_extreme"]:
            scores[MacroRegime.RISK_OFF.value] += 3.0
            signals.append(f"VIX extrême ({snapshot.vix:.1f} > {REGIME_THRESHOLDS['vix_extreme']})")
        elif snapshot.vix > REGIME_THRESHOLDS["vix_high"]:
            scores[MacroRegime.RISK_OFF.value] += 2.0
            signals.append(f"VIX élevé ({snapshot.vix:.1f} > {REGIME_THRESHOLDS['vix_high']})")
        else:
            scores[MacroRegime.RISK_ON.value] += 1.5
            signals.append(f"VIX bas ({snapshot.vix:.1f}) → risk-on")

        # ── Yield Curve ───────────────────────────────────────────────────────
        if snapshot.yield_curve < REGIME_THRESHOLDS["yield_curve_inv"]:
            scores[MacroRegime.RISK_OFF.value] += 2.5
            signals.append(f"Courbe inversée (10Y-2Y={snapshot.yield_curve:.2f}%) → récession")
        elif snapshot.yield_curve < 0:
            scores[MacroRegime.TRANSITION.value] += 1.5
            signals.append(f"Courbe légèrement inversée ({snapshot.yield_curve:.2f}%)")
        else:
            scores[MacroRegime.RISK_ON.value] += 1.0
            signals.append(f"Courbe normale ({snapshot.yield_curve:.2f}%) → expansion")

        # ── CPI / Inflation ───────────────────────────────────────────────────
        # Note : DEFLATION et STAGFLATION reçoivent des scores élevés car ce sont
        # des régimes "override" — leur signal est dominant par nature.
        if snapshot.cpi_yoy < REGIME_THRESHOLDS["cpi_deflation"]:
            scores[MacroRegime.DEFLATION.value] += 5.0
            signals.append(f"Déflation (CPI={snapshot.cpi_yoy:.1f}%)")
        elif snapshot.cpi_yoy > REGIME_THRESHOLDS["cpi_high"]:
            if snapshot.ism_pmi < REGIME_THRESHOLDS["ism_contraction"]:
                scores[MacroRegime.STAGFLATION.value] += 5.0
                signals.append(f"Stagflation (CPI={snapshot.cpi_yoy:.1f}% + ISM={snapshot.ism_pmi:.1f})")
            else:
                scores[MacroRegime.STAGFLATION.value] += 2.0
                scores[MacroRegime.RISK_OFF.value]    += 1.0
                signals.append(f"Inflation élevée (CPI={snapshot.cpi_yoy:.1f}%)")
        else:
            scores[MacroRegime.RISK_ON.value] += 1.0
            signals.append(f"Inflation contrôlée (CPI={snapshot.cpi_yoy:.1f}%)")

        # ── ISM Manufacturing ─────────────────────────────────────────────────
        if snapshot.ism_pmi > REGIME_THRESHOLDS["ism_expansion"]:
            scores[MacroRegime.RISK_ON.value] += 1.5
            signals.append(f"ISM en expansion ({snapshot.ism_pmi:.1f})")
        elif snapshot.ism_pmi < REGIME_THRESHOLDS["ism_contraction"]:
            scores[MacroRegime.RISK_OFF.value] += 1.5
            signals.append(f"ISM en contraction forte ({snapshot.ism_pmi:.1f})")

        # ── DXY (Dollar) ──────────────────────────────────────────────────────
        if snapshot.dxy > REGIME_THRESHOLDS["dxy_strong"]:
            scores[MacroRegime.RISK_OFF.value] += 1.5
            signals.append(f"Dollar fort (DXY={snapshot.dxy:.1f}) → risk-off")
        else:
            scores[MacroRegime.RISK_ON.value] += 1.0
            signals.append(f"Dollar faible/neutre (DXY={snapshot.dxy:.1f}) → risk-on")

        # ── Fed Funds Rate / Taux réels ───────────────────────────────────────
        if snapshot.real_rate > 2.0:
            scores[MacroRegime.RISK_OFF.value] += 1.5
            signals.append(f"Taux réels élevés ({snapshot.real_rate:.1f}%) → conditions restrictives")
        elif snapshot.real_rate < 0:
            scores[MacroRegime.RISK_ON.value] += 1.5
            signals.append(f"Taux réels négatifs ({snapshot.real_rate:.1f}%) → liquidité abondante")

        # ── Chômage ───────────────────────────────────────────────────────────
        if snapshot.unemployment > REGIME_THRESHOLDS["unemployment_high"]:
            scores[MacroRegime.RISK_OFF.value]    += 1.0
            scores[MacroRegime.STAGFLATION.value] += 0.5
            signals.append(f"Chômage élevé ({snapshot.unemployment:.1f}%)")

        # ── BTC Dominance (appétit crypto) ────────────────────────────────────
        if snapshot.btc_dominance > REGIME_THRESHOLDS["btc_dom_high"]:
            scores[MacroRegime.RISK_OFF.value] += 0.5
            signals.append(f"BTC dominance élevée ({snapshot.btc_dominance:.1f}%) → fuite vers la qualité crypto")
        else:
            scores[MacroRegime.RISK_ON.value] += 0.5
            signals.append(f"BTC dominance basse ({snapshot.btc_dominance:.1f}%) → appétit alt-coins")

        # ── Funding rates (sentiment leveragé) ───────────────────────────────
        avg_funding = (snapshot.btc_funding_rate + snapshot.eth_funding_rate) / 2
        if avg_funding > 0.05:
            scores[MacroRegime.RISK_ON.value]  += 1.0
            signals.append(f"Funding rate positif élevé ({avg_funding:.3f}%) → euphorie levée")
        elif avg_funding < -0.01:
            scores[MacroRegime.RISK_OFF.value] += 1.0
            signals.append(f"Funding rate négatif ({avg_funding:.3f}%) → panique short")

        # ── Sélection du régime dominant ─────────────────────────────────────
        total = sum(scores.values())
        if total == 0:
            regime = MacroRegime.TRANSITION
            confidence = 0.0
        else:
            sorted_regimes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            top_name, top_score = sorted_regimes[0]
            sec_score = sorted_regimes[1][1] if len(sorted_regimes) > 1 else 0.0
            regime     = MacroRegime(top_name)
            # Confiance = écart normalisé entre le 1er et le 2e
            confidence = float(np.clip((top_score - sec_score) / max(total, 1), 0.0, 1.0))

        result = RegimeClassification(
            regime=regime,
            confidence=confidence,
            scores=scores,
            signals=signals,
        )
        self._last_regime = result

        logger.info(
            "[Strate1] Régime : %s (confiance=%.0f%%) | Top signaux: %s",
            regime.value, confidence * 100,
            " | ".join(signals[:3]),
        )
        return result

    def run_monte_carlo(
        self,
        snapshot:    MacroSnapshot,
        n_scenarios: int = MONTE_CARLO_N,
        horizon:     int = MONTE_CARLO_DAYS,
        asset:       str = "BTC",
        seed:        Optional[int] = None,
    ) -> ScenarioDistribution:
        """
        Simule n_scenarios trajectoires de prix sur `horizon` jours.

        Modèle : Geometric Brownian Motion (GBM) avec drift et volatilité
        paramétrés par le régime macroéconomique courant.

        Drift annualisé par régime (pour BTC) :
          RISK_ON     : +80% (marché haussier)
          RISK_OFF    : -40% (marché baissier)
          STAGFLATION : +20% (hedge inflation mais croissance faible)
          DEFLATION   : -60% (fuite vers cash)
          TRANSITION  : +10% (incertitude)

        Args:
            snapshot:    Dernier MacroSnapshot.
            n_scenarios: Nombre de simulations Monte Carlo.
            horizon:     Horizon en jours.
            asset:       Actif simulé (BTC par défaut).
            seed:        Seed pour reproductibilité (tests).

        Returns:
            ScenarioDistribution avec probabilités bull/bear/neutral et CVaR.
        """
        regime = self.classify_regime(snapshot).regime

        # Paramètres GBM par régime (drift et vol annualisés)
        regime_params: dict[MacroRegime, dict] = {
            MacroRegime.RISK_ON:     {"mu": 0.80,  "sigma": 0.80},
            MacroRegime.RISK_OFF:    {"mu": -0.40, "sigma": 1.20},
            MacroRegime.STAGFLATION: {"mu": 0.20,  "sigma": 0.90},
            MacroRegime.DEFLATION:   {"mu": -0.60, "sigma": 1.00},
            MacroRegime.TRANSITION:  {"mu": 0.10,  "sigma": 1.00},
        }
        # Stocker le snapshot pour que get_world_state_vector() fonctionne
        # même si fetch_macro_snapshot() n'a pas encore été appelé.
        if self._last_snapshot is None:
            self._last_snapshot = snapshot

        p     = regime_params[regime]
        mu    = p["mu"]
        sigma = p["sigma"]

        # Ajustements fins selon indicateurs clés
        if snapshot.vix > REGIME_THRESHOLDS["vix_extreme"]:
            sigma *= 1.3   # volatilité accrue en panique
        if snapshot.real_rate > 3.0:
            mu -= 0.20     # taux réels très élevés → pression baissière
        if snapshot.yield_curve_signal == -1:
            mu -= 0.15     # courbe inversée → signal de récession
        if snapshot.btc_funding_rate > 0.10:
            sigma *= 1.15  # euphorie levée → risque de flush

        # Paramètres journaliers
        dt      = 1.0 / 365.0
        mu_d    = mu * dt
        sigma_d = sigma * math.sqrt(dt)

        rng = np.random.default_rng(seed)
        # Simulations : n_scenarios × horizon returns
        rand_returns = rng.standard_normal((n_scenarios, horizon))
        daily_returns = mu_d - 0.5 * sigma_d**2 + sigma_d * rand_returns  # GBM log-returns

        # Prix cumulatif (normalisé, départ à 1.0)
        price_paths = np.exp(np.cumsum(daily_returns, axis=1))  # shape: (N, horizon)

        # Retours finaux
        final_returns = price_paths[:, -1] - 1.0

        # Probabilités à l'horizon
        prob_bull    = float(np.mean(final_returns > 0.20))
        prob_bear    = float(np.mean(final_returns < -0.20))
        prob_neutral = 1.0 - prob_bull - prob_bear

        # Statistiques de distribution
        sorted_ret = np.sort(final_returns)
        var_95  = float(-np.percentile(final_returns, 5))   # perte au 5e percentile
        cvar_95 = float(-np.mean(sorted_ret[:int(n_scenarios * 0.05)]))  # moyenne des 5% pires

        # Trajectoires résumées (percentiles)
        path_p10 = [float(np.percentile(price_paths[:, d], 10)) for d in range(horizon)]
        path_p50 = [float(np.percentile(price_paths[:, d], 50)) for d in range(horizon)]
        path_p90 = [float(np.percentile(price_paths[:, d], 90)) for d in range(horizon)]

        result = ScenarioDistribution(
            n_scenarios   = n_scenarios,
            horizon_days  = horizon,
            prob_bull     = prob_bull,
            prob_bear     = prob_bear,
            prob_neutral  = prob_neutral,
            median_return = float(np.median(final_returns)),
            var_95        = var_95,
            cvar_95       = cvar_95,
            best_case     = float(np.percentile(final_returns, 95)),
            worst_case    = float(np.percentile(final_returns, 5)),
            path_p10      = path_p10,
            path_p50      = path_p50,
            path_p90      = path_p90,
        )
        self._last_mc = result

        logger.info(
            "[Strate1] Monte Carlo %s | Régime:%s | Bull=%.0f%% Bear=%.0f%% "
            "Neutral=%.0f%% | Médiane:%.0f%% | CVaR95:%.0f%%",
            asset, regime.value,
            prob_bull * 100, prob_bear * 100, prob_neutral * 100,
            result.median_return * 100, cvar_95 * 100,
        )
        return result

    def get_world_state_vector(self) -> np.ndarray:
        """
        Retourne le vecteur d'état normalisé du monde pour le Parlement (Strate 6).

        14 dimensions, toutes normalisées en [-1, +1] ou [0, 1] selon l'indicateur.
        Utilisé par les agents du Parlement comme contexte standardisé.

        Si aucun snapshot n'est disponible, retourne le vecteur neutre (zéros).

        Returns:
            np.ndarray de shape (14,)
        """
        if self._last_snapshot is None:
            return np.zeros(14, dtype=np.float32)

        s = self._last_snapshot

        def clip_norm(val: float, lo: float, hi: float) -> float:
            """Normalise val ∈ [lo, hi] → [-1, +1]."""
            mid   = (hi + lo) / 2
            scale = (hi - lo) / 2
            return float(np.clip((val - mid) / scale, -1.0, 1.0))

        vector = np.array([
            # [0] CPI YoY normalisé (-2% → +10%) → [-1, +1]
            clip_norm(s.cpi_yoy, -2.0, 10.0),
            # [1] PCE YoY normalisé (-2% → +8%)
            clip_norm(s.pce_yoy, -2.0, 8.0),
            # [2] Yield Curve normalisé (-2% → +3%)
            clip_norm(s.yield_curve, -2.0, 3.0),
            # [3] ISM PMI normalisé (35 → 65)
            clip_norm(s.ism_pmi, 35.0, 65.0),
            # [4] Taux réels normalisés (-5% → +5%)
            clip_norm(s.real_rate, -5.0, 5.0),
            # [5] Chômage normalisé (2% → 12%)
            clip_norm(s.unemployment, 2.0, 12.0),
            # [6] VIX normalisé (10 → 50) → [-1, +1] (VIX élevé = -1)
            -clip_norm(s.vix, 10.0, 50.0),
            # [7] DXY normalisé (85 → 115) → [-1, +1] (DXY fort = -1)
            -clip_norm(s.dxy, 85.0, 115.0),
            # [8] Gold normalisé (1200 → 3000)
            clip_norm(s.gold_usd, 1200.0, 3000.0),
            # [9] Oil normalisé (30 → 120)
            clip_norm(s.oil_usd, 30.0, 120.0),
            # [10] M2 Growth normalisé (-5% → +20%)
            clip_norm(s.m2_growth_yoy, -5.0, 20.0),
            # [11] BTC Dominance normalisé (30% → 70%)
            clip_norm(s.btc_dominance, 30.0, 70.0),
            # [12] BTC Funding Rate normalisé (-0.1% → +0.1%)
            clip_norm(s.btc_funding_rate, -0.10, 0.10),
            # [13] Total Market Cap normalisé (500B → 5000B USD)
            clip_norm(s.total_market_cap_b, 500.0, 5000.0),
        ], dtype=np.float32)

        return vector

    # ── Accès au dernier état ─────────────────────────────────────────────────

    @property
    def last_snapshot(self) -> Optional[MacroSnapshot]:
        return self._last_snapshot

    @property
    def last_regime(self) -> Optional[RegimeClassification]:
        return self._last_regime

    @property
    def last_monte_carlo(self) -> Optional[ScenarioDistribution]:
        return self._last_mc

    # ── Fetchers par source ───────────────────────────────────────────────────

    async def _fetch_fred(self) -> Optional[dict]:
        """
        Récupère les séries FRED via l'API REST.
        Retourne None si la clé est absente ou si l'API est indisponible.
        Utilise fredapi (pip install fredapi) si disponible, sinon httpx direct.
        """
        if not self._fred_key:
            logger.debug("[Strate1] FRED_API_KEY absent — données FRED ignorées.")
            return None

        try:
            # Essai avec fredapi si disponible
            data = await asyncio.to_thread(self._fetch_fred_sync)
            return data
        except Exception as exc:
            logger.warning("[Strate1] FRED fetch échoué: %s", exc)
            return None

    def _fetch_fred_sync(self) -> Optional[dict]:
        """Appel synchrone FRED — exécuté dans un thread pool via asyncio.to_thread."""
        try:
            from fredapi import Fred
            fred = Fred(api_key=self._fred_key)
        except ImportError:
            # Fallback : REST direct via requests (synchrone)
            return self._fetch_fred_rest_sync()

        result = {}
        try:
            # M2 Money Supply — calcul croissance YoY
            m2 = fred.get_series("M2SL", limit=14)
            if len(m2) >= 13:
                m2_now  = float(m2.iloc[-1])
                m2_year = float(m2.iloc[-13])
                result["m2_growth_yoy"] = (m2_now - m2_year) / m2_year * 100

            # CPI YoY
            cpi = fred.get_series("CPIAUCSL", limit=14)
            if len(cpi) >= 13:
                result["cpi_yoy"] = (float(cpi.iloc[-1]) - float(cpi.iloc[-13])) / float(cpi.iloc[-13]) * 100

            # PCE Core YoY
            pce = fred.get_series("PCEPILFE", limit=14)
            if len(pce) >= 13:
                result["pce_yoy"] = (float(pce.iloc[-1]) - float(pce.iloc[-13])) / float(pce.iloc[-13]) * 100

            # Yield Curve (déjà en %)
            yc = fred.get_series("T10Y2Y", limit=5)
            if len(yc) > 0:
                result["yield_curve"] = float(yc.iloc[-1])

            # ISM PMI
            ism = fred.get_series("NAPM", limit=3)
            if len(ism) > 0:
                result["ism_pmi"] = float(ism.iloc[-1])

            # Taux de chômage
            unrate = fred.get_series("UNRATE", limit=3)
            if len(unrate) > 0:
                result["unemployment"] = float(unrate.iloc[-1])

            # Fed Funds Rate
            ffr = fred.get_series("FEDFUNDS", limit=3)
            if len(ffr) > 0:
                result["fed_funds_rate"] = float(ffr.iloc[-1])

        except Exception as exc:
            logger.warning("[Strate1] fredapi series error: %s", exc)

        return result if result else None

    def _fetch_fred_rest_sync(self) -> Optional[dict]:
        """Fallback REST FRED sans fredapi — utilise requests."""
        try:
            import requests
        except ImportError:
            return None

        result = {}
        base = "https://api.stlouisfed.org/fred/series/observations"

        def get_last(series_id: str, limit: int = 14) -> list[float]:
            try:
                resp = requests.get(base, params={
                    "series_id":    series_id,
                    "api_key":      self._fred_key,
                    "file_type":    "json",
                    "sort_order":   "desc",
                    "limit":        limit,
                }, timeout=10)
                data = resp.json()
                vals = [
                    float(o["value"]) for o in data.get("observations", [])
                    if o["value"] != "."
                ]
                return list(reversed(vals))
            except Exception:
                return []

        try:
            m2 = get_last("M2SL", 14)
            if len(m2) >= 13:
                result["m2_growth_yoy"] = (m2[-1] - m2[-13]) / m2[-13] * 100

            cpi = get_last("CPIAUCSL", 14)
            if len(cpi) >= 13:
                result["cpi_yoy"] = (cpi[-1] - cpi[-13]) / cpi[-13] * 100

            pce = get_last("PCEPILFE", 14)
            if len(pce) >= 13:
                result["pce_yoy"] = (pce[-1] - pce[-13]) / pce[-13] * 100

            yc = get_last("T10Y2Y", 5)
            if yc:
                result["yield_curve"] = yc[-1]

            ism = get_last("NAPM", 3)
            if ism:
                result["ism_pmi"] = ism[-1]

            unrate = get_last("UNRATE", 3)
            if unrate:
                result["unemployment"] = unrate[-1]

            ffr = get_last("FEDFUNDS", 3)
            if ffr:
                result["fed_funds_rate"] = ffr[-1]

        except Exception as exc:
            logger.warning("[Strate1] FRED REST error: %s", exc)

        return result if result else None

    async def _fetch_yfinance(self) -> Optional[dict]:
        """
        Récupère DXY, VIX, Gold, Oil, Copper via yfinance.
        Retourne None si yfinance n'est pas installé.
        """
        try:
            data = await asyncio.to_thread(self._fetch_yfinance_sync)
            return data
        except Exception as exc:
            logger.warning("[Strate1] yfinance fetch échoué: %s", exc)
            return None

    def _fetch_yfinance_sync(self) -> Optional[dict]:
        """Appel synchrone yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            logger.debug("[Strate1] yfinance non installé — pip install yfinance")
            return None

        result = {}
        mapping = {
            "dxy":    "DX-Y.NYB",
            "vix":    "^VIX",
            "gold":   "GC=F",
            "oil":    "CL=F",
            "copper": "HG=F",
        }
        for key, ticker in mapping.items():
            try:
                t    = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if not hist.empty:
                    result[key] = float(hist["Close"].iloc[-1])
            except Exception as exc:
                logger.debug("[Strate1] yfinance %s: %s", ticker, exc)

        return result if result else None

    async def _fetch_coingecko(self) -> Optional[dict]:
        """
        Récupère BTC dominance et total market cap via CoinGecko (gratuit, sans clé).
        """
        if not self._http:
            return None
        try:
            resp = await self._http.get(
                f"{COINGECKO}/global",
                headers={"Accept": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            btc_dom  = data.get("market_cap_percentage", {}).get("btc", 0.0)
            total_mc = data.get("total_market_cap", {}).get("usd", 0.0) / 1e9  # → milliards
            return {
                "btc_dominance":      round(float(btc_dom), 2),
                "total_market_cap_b": round(float(total_mc), 1),
            }
        except Exception as exc:
            logger.warning("[Strate1] CoinGecko fetch échoué: %s", exc)
            return None

    async def _fetch_funding_rates(self) -> Optional[dict]:
        """
        Récupère les funding rates BTC et ETH depuis Binance Futures.
        Retourne None si l'endpoint est indisponible.
        """
        if not self._http:
            return None
        result = {}
        for symbol, key in [("BTCUSDT", "btc"), ("ETHUSDT", "eth")]:
            try:
                resp = await self._http.get(
                    f"{BINANCE_REST}/fapi/v1/fundingRate",
                    params={"symbol": symbol, "limit": 1},
                    timeout=8,
                )
                resp.raise_for_status()
                data = resp.json()
                if data:
                    result[key] = float(data[-1].get("fundingRate", 0.01))
            except Exception as exc:
                logger.debug("[Strate1] Binance funding %s: %s", symbol, exc)
        return result if result else None

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _save_cache(self) -> None:
        if not self._cache_path or not self._last_snapshot:
            return
        try:
            cache = {
                "snapshot":   self._last_snapshot.to_dict(),
                "ts_macro":   self._ts_macro,
                "ts_crypto":  self._ts_crypto,
            }
            if self._last_regime:
                cache["regime"] = self._last_regime.to_dict()
            self._cache_path.write_text(
                json.dumps(cache, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.debug("[Strate1] Cache save error: %s", exc)

    def _load_cache(self) -> None:
        if not self._cache_path or not self._cache_path.exists():
            return
        try:
            cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            self._last_snapshot = MacroSnapshot.from_dict(cache.get("snapshot", {}))
            self._ts_macro      = float(cache.get("ts_macro",  0.0))
            self._ts_crypto     = float(cache.get("ts_crypto", 0.0))
            if "regime" in cache:
                d = cache["regime"]
                self._last_regime = RegimeClassification(
                    regime     = MacroRegime(d["regime"]),
                    confidence = d["confidence"],
                    scores     = d["scores"],
                    signals    = d["signals"],
                    timestamp  = d["timestamp"],
                )
            logger.info(
                "[Strate1] Cache chargé | snapshot du %s",
                self._last_snapshot.timestamp[:19] if self._last_snapshot else "N/A",
            )
        except Exception as exc:
            logger.warning("[Strate1] Cache load error: %s", exc)
