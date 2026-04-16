"""
Strates Cognitives ORACLE v2.
Cinq strates théoriques/comportementales : Épistémique, Minsky, Réflexivité,
Comportemental, Fractal. Leurs votes s'ajoutent aux strates techniques dans le Parlement.

Remplace l'ancien legacy_bridge.py — imports DIRECTS depuis strates/, sans fallback
chaîné ni dépendance externe. Si une strate est absente ou cassée, elle est ignorée
silencieusement : le système continue sans elle.

Usage dans oracle_system.py :
    self.cognitive_mgr = CognitiveStrateManager(vault_path=...)

Usage dans cycle_manager.py :
    votes.extend(self._s.cognitive_mgr.generate_votes(symbol, ohlcv_list, predict_features))
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("ORACLE.CognitiveStrates")

# ─── Chargement des strates (une seule tentative chacune) ────────────────────

_STRATE0       = None   # EpistemologicalEngine
_STRATE2       = None   # MinskyDetector
_MACRO_SNAPSHOT = None  # MacroSnapshot (requis par Minsky)
_STRATE4       = None   # ReflexivityEngine
_STRATE5       = None   # BehavioralBiasEngine
_STRATE7       = None   # FractalRiskEngine

try:
    from strates.strate_0_epistemic import EpistemologicalEngine
    _STRATE0 = EpistemologicalEngine
except Exception as _e:
    logger.debug(f"strate_0 (Épistémique) non disponible: {_e}")

try:
    from strates.strate_2_minsky import MinskyDetector
    from strates.strate_1_world_model import MacroSnapshot
    _STRATE2, _MACRO_SNAPSHOT = MinskyDetector, MacroSnapshot
except Exception as _e:
    logger.debug(f"strate_2 (Minsky) non disponible: {_e}")

try:
    from strates.strate_4_reflexivity import ReflexivityEngine
    _STRATE4 = ReflexivityEngine
except Exception as _e:
    logger.debug(f"strate_4 (Réflexivité) non disponible: {_e}")

try:
    from strates.strate_5_behavioral_bias import BehavioralBiasEngine
    _STRATE5 = BehavioralBiasEngine
except Exception as _e:
    logger.debug(f"strate_5 (Comportemental) non disponible: {_e}")

try:
    from strates.strate_7_fractal_risk import FractalRiskEngine
    _STRATE7 = FractalRiskEngine
except Exception as _e:
    logger.debug(f"strate_7 (Fractal) non disponible: {_e}")


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_vote(name: str, direction: str, confidence: float, reasoning: str):
    """Construit un Vote parlement normalisé."""
    from brain.parliament import Vote
    direction = direction.upper()
    if direction not in ("LONG", "SHORT", "NEUTRAL"):
        direction = "NEUTRAL"
    return Vote(name, direction, max(0.0, min(1.0, confidence)), reasoning)


def _to_series(ohlcv_list: list, field: str = "close"):
    """Convertit une liste OHLCV en pd.Series (ou liste si pandas absent)."""
    vals = [getattr(c, field, 0) for c in ohlcv_list]
    try:
        import pandas as pd
        return pd.Series(vals, dtype=float)
    except ImportError:
        return vals


def _make_macro_snapshot(price_list: list):
    """Construit un MacroSnapshot synthétique depuis les prix (approximation VIX)."""
    if _MACRO_SNAPSHOT is None or len(price_list) < 20:
        return None
    arr = np.array(price_list, dtype=float)
    returns = np.diff(np.log(np.maximum(arr, 1e-10)))
    vol_daily = float(np.std(returns[-20:])) if len(returns) >= 20 else 0.02
    vix = vol_daily * np.sqrt(252) * 100
    trend = (arr[-1] - arr[-20]) / arr[-20] if len(arr) >= 20 else 0.0
    funding = float(np.clip(trend * 0.5, -0.05, 0.05))
    try:
        return _MACRO_SNAPSHOT(
            vix=float(vix), btc_funding_rate=funding, btc_dominance=50.0,
            yield_curve=0.3, real_rate=0.5, ism_pmi=50.0, total_market_cap_b=2000.0,
        )
    except Exception as e:
        logger.debug(f"MacroSnapshot construction échouée: {e}")
        return None


def _momentum(prices, lookback: int) -> float:
    """Retourne le momentum sur `lookback` bougies (compatible Series et list)."""
    try:
        p = prices.iloc if hasattr(prices, "iloc") else prices
        if len(prices) < lookback:
            return 0.0
        return (p[-1] - p[-lookback]) / (p[-lookback] or 1e-10)
    except Exception:
        return 0.0


# ─── CognitiveStrateManager ──────────────────────────────────────────────────

class CognitiveStrateManager:
    """
    Gestionnaire des 5 strates cognitives d'ORACLE v2.

    Chaque strate est initialisée une fois au démarrage et réutilisée à chaque
    cycle. Si une strate plante à l'init ou à l'exécution, elle est ignorée —
    le système ne crashe jamais à cause d'une strate cognitive absente.

    Strates gérées :
        EPISTEMIQUE   — filtre bruit/signal (Fischer Black)
        MINSKY        — phase de marché macro (Minsky + VIX synthétique)
        REFLEXIVITE   — boucle de rétroaction (Soros)
        COMPORTEMENTAL — biais cognitifs (Kahneman)
        FRACTAL       — Hurst + Kelly (Mandelbrot)
    """

    def __init__(self, vault_path: Optional[str] = None):
        _vault = Path(vault_path) if vault_path else (
            Path(__file__).parent.parent / "vault" / "cognitive"
        )
        _vault.mkdir(parents=True, exist_ok=True)

        self._engines: dict = {}

        # Tableau d'initialisation : (nom, classe, kwargs)
        _init_cfg = [
            ("EPISTEMIQUE",    _STRATE0, {"vault_path": _vault}),
            ("MINSKY",         _STRATE2, {"vault_path": _vault}),
            ("REFLEXIVITE",    _STRATE4, {}),
            ("COMPORTEMENTAL", _STRATE5, {"vault_path": _vault}),
            ("FRACTAL",        _STRATE7, {}),
        ]

        for name, cls, kwargs in _init_cfg:
            if cls is not None:
                try:
                    self._engines[name] = cls(**kwargs)
                except Exception as e:
                    logger.debug(f"Init {name} échoué: {e}")

        if self._engines:
            logger.info(f"CognitiveStrates actives: {', '.join(self._engines)}")
        else:
            logger.warning("CognitiveStrates: aucune strate disponible (imports manquants ?)")

    @property
    def available(self) -> list[str]:
        return list(self._engines.keys())

    def generate_votes(
        self,
        symbol: str,
        ohlcv_list: list,
        features: Optional[dict] = None,
        trade_history: Optional[list] = None,
    ) -> list:
        """
        Exécute les strates disponibles et retourne leurs votes Parlement.

        Args:
            symbol       : ex. "BTCUSDT"
            ohlcv_list   : liste OHLCV oracle_v2 (objets avec attribut .close)
            features     : dict optionnel {rsi, macd, volume_ratio, ...}
            trade_history: liste de trades fermés (pour strate comportementale)

        Returns:
            list[Vote] — votes filtrés (confidence > 0)
        """
        if len(ohlcv_list) < 20:
            return []

        votes = []
        prices      = _to_series(ohlcv_list)
        price_list  = [getattr(c, "close", 0) for c in ohlcv_list]

        # ── EPISTEMIQUE — filtre bruit/signal ────────────────────────────
        if "EPISTEMIQUE" in self._engines:
            try:
                dummy_preds = np.full(10, float(np.mean(price_list[-10:])))
                allowed, info = self._engines["EPISTEMIQUE"].should_trade(
                    prices=prices, macro_factors=None,
                    predictions=dummy_preds, asset=symbol, timeframe="5m",
                )
                snr     = float(info.get("snr", 0))
                entropy = float(info.get("entropy", 1))
                if not allowed:
                    votes.append(_make_vote(
                        "EPISTEMIQUE", "NEUTRAL",
                        0.5 + (1.0 - snr) * 0.3,
                        f"Gate fermé — SNR={snr:.2f} entropy={entropy:.2f}",
                    ))
                else:
                    mom = _momentum(prices, 5)
                    direction = "LONG" if mom > 0 else "SHORT" if mom < 0 else "NEUTRAL"
                    votes.append(_make_vote(
                        "EPISTEMIQUE", direction, min(0.85, snr),
                        f"Signal clair — SNR={snr:.2f} entropy={entropy:.2f}",
                    ))
            except Exception as e:
                logger.debug(f"EPISTEMIQUE run échoué: {e}")

        # ── MINSKY — phase de marché ─────────────────────────────────────
        if "MINSKY" in self._engines:
            try:
                snap = _make_macro_snapshot(price_list)
                if snap:
                    result = self._engines["MINSKY"].detect_phase(snap)
                    bias   = result.positioning_bias.lower()
                    dir_   = {"long": "LONG", "short": "SHORT"}.get(bias, "NEUTRAL")
                    conf   = min(0.80, getattr(result, "confidence", 0.5))
                    phase  = result.phase.name if hasattr(result.phase, "name") else str(result.phase)
                    sizing = getattr(result, "sizing_multiplier", 1.0)
                    votes.append(_make_vote(
                        "MINSKY", dir_, conf,
                        f"Phase {phase} | sizing×{sizing:.1f} | {bias}",
                    ))
            except Exception as e:
                logger.debug(f"MINSKY run échoué: {e}")

        # ── REFLEXIVITE — boucle de Soros ────────────────────────────────
        if "REFLEXIVITE" in self._engines:
            try:
                result = self._engines["REFLEXIVITE"].analyze(prices=prices)
                if isinstance(result, dict):
                    bias   = result.get("positioning_bias", "neutral").lower()
                    dir_   = {"long": "LONG", "short": "SHORT"}.get(bias, "NEUTRAL")
                    sizing = float(result.get("sizing_modifier", 1.0))
                    conf   = min(0.80, abs(sizing - 1.0) * 2 + 0.3)
                    sigs   = result.get("signals", [])
                    rsn    = sigs[0][:80] if sigs else f"Reflexivity sizing={sizing:.2f}"
                    votes.append(_make_vote("REFLEXIVITE", dir_, conf, rsn))
            except Exception as e:
                logger.debug(f"REFLEXIVITE run échoué: {e}")

        # ── COMPORTEMENTAL — biais Kahneman ──────────────────────────────
        if "COMPORTEMENTAL" in self._engines:
            try:
                result = self._engines["COMPORTEMENTAL"].analyze(
                    trades=trade_history or [], prices=prices,
                )
                if isinstance(result, dict):
                    agg    = result.get("aggregate_signal", "neutral").lower()
                    dir_   = {"bullish": "LONG", "bearish": "SHORT"}.get(agg, "NEUTRAL")
                    conf   = float(result.get("aggregate_confidence", 0.4))
                    sigs   = result.get("signals", [])
                    rsn    = sigs[0][:80] if sigs else f"Bias: {agg}"
                    if dir_ != "NEUTRAL":
                        votes.append(_make_vote("COMPORTEMENTAL", dir_, min(0.75, conf), rsn))
            except Exception as e:
                logger.debug(f"COMPORTEMENTAL run échoué: {e}")

        # ── FRACTAL — Hurst + Kelly ───────────────────────────────────────
        if "FRACTAL" in self._engines:
            try:
                result = self._engines["FRACTAL"].analyze(prices=prices)
                if isinstance(result, dict):
                    hurst = float(result.get("hurst", 0.5))
                    kelly = float(result.get("kelly_fraction", 0.1))
                    mom   = _momentum(prices, 10)
                    if hurst > 0.6:
                        dir_  = "LONG" if mom > 0 else "SHORT"
                        conf  = min(0.80, (hurst - 0.5) * 2 * kelly * 3)
                        rsn   = f"Hurst={hurst:.3f} persistant | Kelly={kelly:.1%}"
                    elif hurst < 0.4:
                        dir_  = "SHORT" if mom > 0 else "LONG"
                        conf  = min(0.70, (0.5 - hurst) * 2 * kelly * 3)
                        rsn   = f"Hurst={hurst:.3f} mean-revert | Kelly={kelly:.1%}"
                    else:
                        dir_, conf = "NEUTRAL", 0.3
                        rsn = f"Hurst={hurst:.3f} neutre"
                    votes.append(_make_vote("FRACTAL", dir_, max(0.0, conf), rsn))
            except Exception as e:
                logger.debug(f"FRACTAL run échoué: {e}")

        return votes

    def get_status(self) -> dict:
        return {"available": self.available, "count": len(self._engines)}
