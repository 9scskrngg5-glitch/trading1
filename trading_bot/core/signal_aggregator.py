"""
Signal Aggregator — ORACLE v2 core plumbing.

Rôle
----
Relie les sorties hétérogènes des Strates 0–5 à la décision de position
(`DynamicSizer`). Ce fichier est le chaînon manquant : les strates ont chacune
leur propre interface (S0 retourne `(bool, dict)`, S1 retourne un
`RegimeClassification`, S2 un `MinskyResult`, S3/S4/S5 un `dict` via `analyze()`).
Plutôt que d'imposer une uniformisation invasive, l'aggregator héberge un
adaptateur par strate — chaque adaptateur sait appeler la bonne méthode et
traduire son retour en un triplet normalisé `(direction, confidence, sizing)`.

Règles non négociables
----------------------
* **S0 est un gate absolu.** Si `should_trade()` refuse, on retourne
  immédiatement `FLAT` avec `reason="S0_GATE"`. Les strates suivantes ne
  sont même pas appelées — inutile de brûler du calcul sur du bruit.
* **Chaque strate est isolée dans un `try/except`.** Une strate qui crash est
  marquée `skipped` dans `strate_scores` et son poids est réparti sur les
  strates qui ont répondu. Une panne locale ne doit jamais faire tomber le
  pipeline entier (voir règle 7 du CLAUDE.md).
* **Pas de look-ahead.** Le caller fournit les données historiques (jusqu'à la
  barre courante incluse). L'aggregator ne fetch rien de lui-même.
* **Pas de magic numbers cachés.** Les poids sont des constantes nommées en
  tête de module, modifiables en un endroit.

Poids (fixes, débattus offline)
-------------------------------
    S1 (World Model / macro)     : 0.15  — lent, contexte
    S2 (Minsky cycle)            : 0.20  — position dans le cycle
    S3 (Narrative SIR)           : 0.20  — sentiment épidémiologique
    S4 (Reflexivity)             : 0.25  — boucle prix↔sentiment, edge le + net
    S5 (Behavioral Bias)         : 0.20  — contrarian detector

Sortie
------
    {
      "signal":        "LONG" | "SHORT" | "FLAT",
      "conviction":    float ∈ [-1, +1],      # signé
      "confidence":    float ∈ [0, 1],        # |conviction| pondéré par fiabilité
      "strate_scores": dict[str, dict],       # détail par strate (+ raisons si skip)
      "gate_passed":   bool,                  # S0
      "reason":        str,                   # narratif court
      "timestamp":     str,                   # ISO UTC
    }
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Constantes ───────────────────────────────────────────────────────────────

STRATE_WEIGHTS: dict[str, float] = {
    "s1": 0.15,
    "s2": 0.20,
    "s3": 0.20,
    "s4": 0.25,
    "s5": 0.20,
}
assert abs(sum(STRATE_WEIGHTS.values()) - 1.0) < 1e-9, "weights must sum to 1.0"

# Seuils de décision — en dessous de ce seuil de conviction absolue → FLAT.
# Raison : mieux vaut ne rien faire qu'entrer avec un edge infinitésimal qui
# sera mangé par les frais + slippage.
CONVICTION_FLAT_THRESHOLD = 0.15

# Bornes duracité pour éviter les sorties absurdes si un adaptateur déraille.
SIGNAL_MIN, SIGNAL_MAX = -1.0, 1.0
CONFIDENCE_MIN, CONFIDENCE_MAX = 0.0, 1.0


# ── Résultat normalisé par strate ────────────────────────────────────────────

@dataclass
class StrateReading:
    """
    Lecture normalisée d'une strate après passage par son adaptateur.

    direction   : signé ∈ [-1, +1]  (> 0 = haussier, < 0 = baissier, 0 = neutre)
    confidence  : non signé ∈ [0, 1] (fiabilité de la lecture elle-même)
    sizing      : multiplicateur ∈ [0, 2] proposé par la strate (1.0 = neutre)
    ok          : False si la strate a crashé ou n'avait pas les inputs requis
    reason      : texte court (pourquoi ce signal / pourquoi skip)
    raw         : payload brut de la strate (pour debug / audit log)
    """
    direction:  float = 0.0
    confidence: float = 0.0
    sizing:     float = 1.0
    ok:         bool  = True
    reason:     str   = ""
    raw:        dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "direction":  round(float(self.direction), 4),
            "confidence": round(float(self.confidence), 4),
            "sizing":     round(float(self.sizing), 4),
            "ok":         self.ok,
            "reason":     self.reason,
        }


# ── Adaptateurs ──────────────────────────────────────────────────────────────
# Chaque adaptateur est pur : prend les inputs, renvoie un StrateReading.
# Aucun effet de bord (pas de log persistant ici — le log de la strate elle-même
# s'occupe déjà de la persistance).

def _clip_dir(x: float) -> float:
    return float(np.clip(x, SIGNAL_MIN, SIGNAL_MAX))


def _clip_conf(x: float) -> float:
    return float(np.clip(x, CONFIDENCE_MIN, CONFIDENCE_MAX))


def _bias_to_direction(bias: str) -> float:
    """
    Convertit un `positioning_bias` textuel en direction signée.
    Accepte les variantes courantes rencontrées dans les strates ORACLE.
    """
    if not isinstance(bias, str):
        return 0.0
    b = bias.strip().lower()
    if b in {"long", "bullish", "buy", "risk_on"}:
        return 1.0
    if b in {"short", "bearish", "sell", "risk_off"}:
        return -1.0
    if b in {"strong_long", "strong_bullish"}:
        return 1.0
    if b in {"strong_short", "strong_bearish"}:
        return -1.0
    return 0.0


def _await_if_needed(result: Any) -> Any:
    """
    Si la strate retourne une coroutine, l'exécute. Les adaptateurs sont
    synchrones côté signal_aggregator — on gère l'async ici pour ne pas
    forcer toute la chaîne à être async.
    """
    if inspect.iscoroutine(result):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Dans un contexte async déjà ouvert, on laisse le caller gérer.
                raise RuntimeError(
                    "coroutine returned from sync adapter while inside running loop"
                )
            return loop.run_until_complete(result)
        except RuntimeError:
            return asyncio.run(result)
    return result


# S1 — World Model : fetch_macro_snapshot + classify_regime
def adapt_s1(engine: Any, macro_snapshot: Optional[Any] = None) -> StrateReading:
    """
    Si un `macro_snapshot` est fourni (cas backtest / cache), on l'utilise
    directement. Sinon on appelle `fetch_macro_snapshot()` (async) pour
    rafraîchir — coûteux, à faire au plus une fois par barre dans le
    caller, pas ici.

    Le régime macro donne la direction de fond (risk-on → bullish crypto).
    """
    try:
        if macro_snapshot is None:
            snap = _await_if_needed(engine.fetch_macro_snapshot())
        else:
            snap = macro_snapshot

        regime = engine.classify_regime(snap)

        # `regime` expose typiquement .regime (str), .confidence (float),
        # .risk_score (float). On gère plusieurs noms pour robustesse.
        regime_name = (
            getattr(regime, "regime", None)
            or getattr(regime, "name", None)
            or getattr(regime, "label", None)
            or ""
        )
        conf = float(
            getattr(regime, "confidence", 0.5)
            or 0.5
        )

        direction = _bias_to_direction(regime_name)
        # Risk-on ≈ bullish crypto ; risk-off ≈ bearish.
        if direction == 0.0:
            rname = str(regime_name).lower()
            if "risk_on" in rname or "expansion" in rname:
                direction = 1.0
            elif "risk_off" in rname or "contraction" in rname or "recession" in rname:
                direction = -1.0

        return StrateReading(
            direction=_clip_dir(direction),
            confidence=_clip_conf(conf),
            sizing=1.0,
            ok=True,
            reason=f"regime={regime_name}",
            raw={"regime": str(regime_name), "confidence": conf},
        )
    except Exception as exc:
        logger.warning("[S1 adapter] skipped: %s", exc)
        return StrateReading(ok=False, reason=f"s1_error:{exc!s}")


# S2 — Minsky : detect_phase
def adapt_s2(
    engine: Any,
    macro_snapshot: Optional[Any] = None,
    crypto_data: Optional[Any]    = None,
) -> StrateReading:
    """
    MinskyResult expose : phase, confidence, sizing_multiplier, positioning_bias.

    Les 5 phases Minsky :
      displacement → boom → euphoria → distress → revulsion
    Euphoria et Distress demandent une posture contrarienne (short),
    Displacement/Boom autorisent le long.
    """
    try:
        result = engine.detect_phase(macro_snapshot, crypto_data)

        bias = getattr(result, "positioning_bias", "")
        direction = _bias_to_direction(bias)

        if direction == 0.0:
            phase = str(getattr(result, "phase", "")).lower()
            if phase in {"displacement", "boom"}:
                direction = 1.0
            elif phase in {"euphoria", "distress", "revulsion"}:
                direction = -1.0

        conf = float(getattr(result, "confidence", 0.5) or 0.5)
        sizing = float(getattr(result, "sizing_multiplier", 1.0) or 1.0)
        sizing = float(np.clip(sizing, 0.0, 2.0))

        return StrateReading(
            direction=_clip_dir(direction),
            confidence=_clip_conf(conf),
            sizing=sizing,
            ok=True,
            reason=f"phase={getattr(result, 'phase', '?')} bias={bias}",
            raw={
                "phase": str(getattr(result, "phase", "")),
                "positioning_bias": str(bias),
                "sizing_multiplier": sizing,
            },
        )
    except Exception as exc:
        logger.warning("[S2 adapter] skipped: %s", exc)
        return StrateReading(ok=False, reason=f"s2_error:{exc!s}")


# S3 — Narrative SIR : analyze() async → dict
def adapt_s3(engine: Any) -> StrateReading:
    """
    `analyze()` est async et self-fetching (Reddit/RSS). À ne pas appeler
    dans une boucle de backtest serrée — dans ce cas, le caller peut
    fournir un stub sync.

    Clés attendues : market_impact (float signé), sizing_modifier (float),
    dominant_r0 (float), ecosystem_heat (float ∈ [0, 1]).
    """
    try:
        payload = _await_if_needed(engine.analyze())
        if not isinstance(payload, dict):
            payload = {}

        impact  = float(payload.get("market_impact", 0.0))
        heat    = float(payload.get("ecosystem_heat", 0.0))
        sizing  = float(payload.get("sizing_modifier", 1.0))
        sizing  = float(np.clip(sizing, 0.0, 2.0))

        # market_impact signé ∈ [-1, +1] en pratique. La conf est la chaleur
        # narrative : plus le narratif est chaud, plus la lecture est fiable.
        return StrateReading(
            direction=_clip_dir(impact),
            confidence=_clip_conf(heat),
            sizing=sizing,
            ok=True,
            reason=f"narrative_impact={impact:+.2f} heat={heat:.2f}",
            raw=payload,
        )
    except Exception as exc:
        logger.warning("[S3 adapter] skipped: %s", exc)
        return StrateReading(ok=False, reason=f"s3_error:{exc!s}")


# S4 — Reflexivity : analyze(prices, sentiment_proxy, asset)
def adapt_s4(
    engine: Any,
    prices: pd.Series,
    sentiment_proxy: Optional[pd.Series] = None,
    asset: str = "BTC",
) -> StrateReading:
    """
    Retourne loop/hurst/reflexivity_index/xcorr/sizing_modifier/positioning_bias.
    L'indice de réflexivité combine Hurst (persistence) et cross-corrélation.
    """
    try:
        payload = engine.analyze(prices, sentiment_proxy, asset)
        if not isinstance(payload, dict):
            payload = {}

        bias = payload.get("positioning_bias", "")
        direction = _bias_to_direction(bias)

        # `reflexivity_index` signé : + = boucle haussière, - = boucle baissière.
        rindex = float(payload.get("reflexivity_index", 0.0))
        if direction == 0.0:
            direction = np.sign(rindex)
        # On combine : direction de bias × magnitude |rindex|
        mag = min(abs(rindex), 1.0)
        signed = direction * mag if direction != 0.0 else rindex

        hurst = payload.get("hurst", 0.5)
        # Confidence : distance à 0.5 (random walk). Hurst proche de 0.5 = pas
        # d'edge ; Hurst ≠ 0.5 = persistence ou mean-reversion exploitable.
        hurst_f = float(hurst) if hurst is not None else 0.5
        conf = min(abs(hurst_f - 0.5) * 2.0, 1.0)

        sizing = float(payload.get("sizing_modifier", 1.0))
        sizing = float(np.clip(sizing, 0.0, 2.0))

        return StrateReading(
            direction=_clip_dir(signed),
            confidence=_clip_conf(conf),
            sizing=sizing,
            ok=True,
            reason=f"reflexivity={rindex:+.2f} hurst={hurst_f:.2f} bias={bias}",
            raw=payload,
        )
    except Exception as exc:
        logger.warning("[S4 adapter] skipped: %s", exc)
        return StrateReading(ok=False, reason=f"s4_error:{exc!s}")


# S5 — Behavioral Bias : analyze(prices, volume, long_short_ratio, asset)
def adapt_s5(
    engine: Any,
    prices: pd.Series,
    volume: Optional[pd.Series] = None,
    long_short_ratio: Optional[float] = None,
    asset: str = "BTC",
) -> StrateReading:
    """
    Detector contrarien. `aggregate_signal` est typiquement ∈ [-1, +1] :
    positif = foule trop bearish, entrer long ; négatif = foule trop bullish,
    entrer short. C'est signé dans le sens *contrarian*, donc on l'utilise
    directement comme direction.
    """
    try:
        payload = engine.analyze(prices, volume, long_short_ratio, asset)
        if not isinstance(payload, dict):
            payload = {}

        signal = float(payload.get("aggregate_signal", 0.0))
        contrarian = float(payload.get("contrarian_score", abs(signal)))
        sizing = float(payload.get("sizing_modifier", 1.0))
        sizing = float(np.clip(sizing, 0.0, 2.0))

        bias = payload.get("positioning_bias", "")
        if signal == 0.0:
            signal = _bias_to_direction(bias)

        conf = min(abs(contrarian), 1.0)

        return StrateReading(
            direction=_clip_dir(signal),
            confidence=_clip_conf(conf),
            sizing=sizing,
            ok=True,
            reason=f"contrarian={signal:+.2f} bias={bias}",
            raw=payload,
        )
    except Exception as exc:
        logger.warning("[S5 adapter] skipped: %s", exc)
        return StrateReading(ok=False, reason=f"s5_error:{exc!s}")


# ── Résultat d'agrégation ────────────────────────────────────────────────────

@dataclass
class AggregateResult:
    signal:        str
    conviction:    float
    confidence:    float
    strate_scores: dict[str, dict]
    gate_passed:   bool
    reason:        str
    timestamp:     str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sizing_hint:   float = 1.0

    def to_dict(self) -> dict:
        return {
            "signal":        self.signal,
            "conviction":    round(float(self.conviction), 4),
            "confidence":    round(float(self.confidence), 4),
            "strate_scores": self.strate_scores,
            "gate_passed":   self.gate_passed,
            "reason":        self.reason,
            "timestamp":     self.timestamp,
            "sizing_hint":   round(float(self.sizing_hint), 4),
        }


# ── Aggregator ───────────────────────────────────────────────────────────────

class SignalAggregator:
    """
    Assemble les lectures des 6 strates en une décision unique.

    Utilisation typique :
        agg = SignalAggregator(s0, s1, s2, s3, s4, s5, sizer)
        res = agg.aggregate(
            prices=df["close"],
            volume=df["volume"],
            long_short_ratio=None,   # facultatif
            sentiment_proxy=None,    # facultatif
            macro_snapshot=cached_snap,  # évite le fetch FRED dans une boucle
            predictions=np.array([0.6, 0.55, 0.62]),  # multi-TF
            asset="BTC/USDT",
            timeframe="1h",
        )
        # res: dict comme décrit en tête de module.
        capital_at_risk_pct = agg.size_position(
            capital=10_000, win_rate=0.55, avg_win=2.5, avg_loss=1.0,
        )
    """

    def __init__(
        self,
        s0: Any,
        s1: Any,
        s2: Any,
        s3: Any,
        s4: Any,
        s5: Any,
        sizer: Any,
        conviction_flat_threshold: float = CONVICTION_FLAT_THRESHOLD,
    ):
        self.s0 = s0
        self.s1 = s1
        self.s2 = s2
        self.s3 = s3
        self.s4 = s4
        self.s5 = s5
        self.sizer = sizer
        self.conviction_flat_threshold = conviction_flat_threshold

        # Dernière décision — lue par `size_position`.
        self._last: Optional[AggregateResult] = None

    # ── Gate ──────────────────────────────────────────────────────────────────

    def _s0_gate(
        self,
        prices:        pd.Series,
        macro_factors: Optional[pd.DataFrame],
        predictions:   Optional[np.ndarray],
        asset:         str,
        timeframe:     str,
    ) -> tuple[bool, dict]:
        """
        Encapsule l'appel à S0 dans un try/except. Un crash de S0 est conservateur :
        on bloque (allowed=False) plutôt que de laisser passer un signal douteux.
        """
        try:
            allowed, info = self.s0.should_trade(
                prices, macro_factors, predictions, asset, timeframe,
            )
            return bool(allowed), dict(info)
        except Exception as exc:
            logger.error("[S0 gate] crashed, defaulting to BLOCKED: %s", exc)
            return False, {"allowed": False, "reason": f"s0_crash:{exc!s}"}

    # ── Agrégation ────────────────────────────────────────────────────────────

    def aggregate(
        self,
        prices:            pd.Series,
        volume:            Optional[pd.Series]    = None,
        long_short_ratio:  Optional[float]        = None,
        sentiment_proxy:   Optional[pd.Series]    = None,
        macro_snapshot:    Optional[Any]          = None,
        macro_factors:     Optional[pd.DataFrame] = None,
        predictions:       Optional[np.ndarray]   = None,
        crypto_data:       Optional[Any]          = None,
        asset:             str                    = "BTC/USDT",
        timeframe:         str                    = "1h",
    ) -> dict:
        """
        Pipeline complet :

          1. S0 → gate (si bloqué, retour FLAT immédiat).
          2. S1..S5 → lectures normalisées via adaptateurs (chaque try/except).
          3. Pondération par `STRATE_WEIGHTS`, avec renormalisation si certaines
             strates ont été skippées — on ne pénalise pas les survivantes.
          4. Classification LONG/SHORT/FLAT selon la conviction.
        """
        # ---------- 1. Gate S0 ----------
        gate_passed, gate_info = self._s0_gate(
            prices, macro_factors, predictions, asset, timeframe,
        )

        if not gate_passed:
            res = AggregateResult(
                signal="FLAT",
                conviction=0.0,
                confidence=0.0,
                strate_scores={"s0": gate_info},
                gate_passed=False,
                reason=f"S0_GATE: {gate_info.get('reason', 'blocked')}",
                sizing_hint=0.0,
            )
            self._last = res
            return res.to_dict()

        # ---------- 2. Lectures S1..S5 ----------
        readings: dict[str, StrateReading] = {
            "s1": adapt_s1(self.s1, macro_snapshot=macro_snapshot),
            "s2": adapt_s2(self.s2, macro_snapshot=macro_snapshot, crypto_data=crypto_data),
            "s3": adapt_s3(self.s3),
            "s4": adapt_s4(self.s4, prices, sentiment_proxy, asset),
            "s5": adapt_s5(self.s5, prices, volume, long_short_ratio, asset),
        }

        # ---------- 3. Pondération ----------
        live_keys = [k for k, r in readings.items() if r.ok]
        if not live_keys:
            # Toutes les strates ont crashé — très rare, mais on protège.
            scores_dump = {k: r.to_dict() for k, r in readings.items()}
            scores_dump["s0"] = gate_info
            res = AggregateResult(
                signal="FLAT",
                conviction=0.0,
                confidence=0.0,
                strate_scores=scores_dump,
                gate_passed=True,
                reason="all_strates_skipped",
                sizing_hint=0.0,
            )
            self._last = res
            return res.to_dict()

        live_weight_sum = sum(STRATE_WEIGHTS[k] for k in live_keys)
        # Renormalisation : le poids des strates mortes est redistribué
        # proportionnellement sur les vivantes.
        norm_weights = {
            k: STRATE_WEIGHTS[k] / live_weight_sum for k in live_keys
        }

        conviction = sum(
            readings[k].direction * norm_weights[k] for k in live_keys
        )
        weighted_confidence = sum(
            readings[k].confidence * norm_weights[k] for k in live_keys
        )
        sizing_hint = sum(
            readings[k].sizing * norm_weights[k] for k in live_keys
        )

        conviction = _clip_dir(conviction)
        weighted_confidence = _clip_conf(weighted_confidence)
        sizing_hint = float(np.clip(sizing_hint, 0.0, 2.0))

        # ---------- 4. Classification ----------
        if abs(conviction) < self.conviction_flat_threshold:
            signal = "FLAT"
            reason = (
                f"|conviction|={abs(conviction):.3f} < "
                f"{self.conviction_flat_threshold:.2f} (edge trop fin)"
            )
        elif conviction > 0:
            signal = "LONG"
            reason = f"conviction={conviction:+.3f} (long)"
        else:
            signal = "SHORT"
            reason = f"conviction={conviction:+.3f} (short)"

        # Confiance finale : conviction absolue pondérée par la fiabilité
        # moyenne des strates vivantes. Deux strates qui disent +1 avec
        # confiance 0.2 ne valent pas une strate qui dit +1 avec confiance 1.0.
        final_confidence = _clip_conf(
            abs(conviction) * (0.5 + 0.5 * weighted_confidence)
        )

        scores_dump = {k: r.to_dict() for k, r in readings.items()}
        scores_dump["s0"] = gate_info

        res = AggregateResult(
            signal=signal,
            conviction=conviction,
            confidence=final_confidence,
            strate_scores=scores_dump,
            gate_passed=True,
            reason=reason,
            sizing_hint=sizing_hint,
        )
        self._last = res

        logger.info(
            "[Aggregator] %s conviction=%+.3f confidence=%.3f "
            "live_strates=%d/5 sizing_hint=%.2f",
            signal, conviction, final_confidence, len(live_keys), sizing_hint,
        )
        return res.to_dict()

    # ── Sizing ────────────────────────────────────────────────────────────────

    def size_position(
        self,
        capital:  float,
        win_rate: float,
        avg_win:  float,
        avg_loss: float,
        drawdown_pct:    float = 0.0,
        max_drawdown_pct: float = 15.0,
        atr_pct:  float = 1.5,
        streak:   int   = 0,
        total_trades: int = 0,
    ) -> dict:
        """
        Transforme la dernière conviction en taille de position concrète via
        `DynamicSizer` en mode ADAPTIVE.

        La `confidence` [0, 1] est convertie en `confidence` [0, 100]
        attendue par `DynamicSizer.compute`, et la `sizing_hint` de
        l'aggregator est appliquée comme multiplicateur final.

        Returns:
            {
              "risk_pct":     float,  # % du capital à risquer
              "risk_usd":     float,  # $ à risquer
              "signal":       str,    # LONG / SHORT / FLAT
              "conviction":   float,  # report de la dernière agrégation
            }

        En FLAT, retourne risk=0 — on ne dimensionne pas un trade qu'on ne
        prend pas.
        """
        if self._last is None:
            raise RuntimeError(
                "size_position() called before aggregate() — rien à dimensionner."
            )

        last = self._last

        if last.signal == "FLAT" or not last.gate_passed:
            return {
                "risk_pct": 0.0,
                "risk_usd": 0.0,
                "signal": last.signal,
                "conviction": last.conviction,
            }

        confidence_pct = int(round(last.confidence * 100))
        confidence_pct = max(0, min(100, confidence_pct))

        base_risk = self.sizer.compute(
            win_rate=win_rate,
            avg_win_pct=avg_win,
            avg_loss_pct=avg_loss,
            confidence=confidence_pct,
            drawdown_pct=drawdown_pct,
            max_drawdown_pct=max_drawdown_pct,
            atr_pct=atr_pct,
            streak=streak,
            total_trades=total_trades,
        )

        # `sizing_hint` vient des strates (Minsky, Reflexivity, etc.) et
        # représente un ajustement contextuel (0.0 = désactiver, 2.0 = doubler).
        risk_pct = float(base_risk) * float(last.sizing_hint)
        # Garde-fous ultimes : on ne déborde pas des bornes du sizer.
        risk_pct = float(np.clip(
            risk_pct, self.sizer.min_risk_pct, self.sizer.max_risk_pct
        ))

        risk_usd = capital * risk_pct / 100.0

        return {
            "risk_pct":   round(risk_pct, 4),
            "risk_usd":   round(risk_usd, 2),
            "signal":     last.signal,
            "conviction": round(float(last.conviction), 4),
        }

    # ── Accès à la dernière décision ──────────────────────────────────────────

    def last(self) -> Optional[dict]:
        """Retourne la dernière agrégation (dict), ou None si jamais appelée."""
        return self._last.to_dict() if self._last else None
