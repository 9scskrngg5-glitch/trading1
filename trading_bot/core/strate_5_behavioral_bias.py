"""
Strate 5 — Behavioral Bias Arbitrage Engine
"Les marchés ne sont pas rationnels — ils sont humains." — Daniel Kahneman

Théorie : La finance comportementale (Kahneman & Tversky, 1979-2002) identifie des biais
cognitifs systématiques qui créent des opportunités d'arbitrage :

| Biais              | Détection                                      | Stratégie                    |
|--------------------|------------------------------------------------|------------------------------|
| Anchoring          | Prix qui stagne sur nombres ronds (100, 50, 25) | Sortie violente → momentum   |
| Loss Aversion      | Support défendu trop longtemps (3+ tests)       | Break → capitulation         |
| Recency Bias       | 5+ bougies consécutives même direction          | Mean reversion               |
| Disposition Effect | Volume spike + prix stagne près plus-hauts      | Momentum sous-estimé         |
| Herding            | Long/short ratio > 85% unidirectionnel          | Signal contrarien            |
| FOMO               | Volume 3x moyenne + accélération prix           | Pic parabolique → crash      |
| Panic              | Volume spike + mouvement 3-sigma bas            | Rebond technique ("dead cat")|

Chaque bias détecté retourne :
  - bias_type : identifiant du biais
  - confidence : [0, 1] — confiance de la détection
  - intensity : [0, 1] — intensité du biais
  - signal : "bullish" / "bearish" / "neutral"
  - contrarian_action : "long" / "short" / "wait"
  - expiry_hours : durée de vie estimée du signal

Stockage : vault/world_model/behavioral_biases.db
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Constantes de détection ───────────────────────────────────────────────────

# Anchoring : prix proche d'un nombre rond
ROUND_NUMBER_TOLERANCE_PCT = 0.002  # 0.2% du nombre rond
ROUND_NUMBERS = [10, 20, 25, 50, 75, 100, 200, 500, 1000, 5000, 10000, 50000, 100000]

# Loss Aversion : support/résistance testé多次
SUPPORT_TEST_THRESHOLD = 3  # 3+ tests pour signaler une défense obstinée

# Recency Bias : bougies consécutives
CONSECUTIVE_CANDLES_THRESHOLD = 5

# Disposition Effect : volume + stagnation
VOLUME_SPIKE_MULT = 2.0  # 2x la moyenne
STAGNATION_TOLERANCE_PCT = 0.005  # 0.5% de range

# Herding : positioning extrême
HERDING_RATIO_THRESHOLD = 0.85  # 85% unidirectionnel

# FOMO : volume + accélération
FOMO_VOLUME_MULT = 3.0  # 3x la moyenne
FOMO_ACCELERATION_THRESHOLD = 0.02  # 2% d'accélération

# Panic : mouvement extrême
PANIC_SIGMA = 3.0  # 3-sigma
PANIC_VOLUME_MULT = 2.5  # volume spike


# ── Énumérations ──────────────────────────────────────────────────────────────

class BiasType(str, Enum):
    ANCHORING = "anchoring"           # accroche aux nombres ronds
    LOSS_AVERSION = "loss_aversion"   # défense obstinée de support
    RECENCY = "recency"               # extrapolation du récent
    DISPOSITION = "disposition"       # vendre gagnants / garder perdants
    HERDING = "herding"               # suivi du troupeau
    FOMO = "fomo"                     # peur de rater
    PANIC = "panic"                   # vente panique


class SignalDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ContrarianAction(str, Enum):
    LONG = "long"
    SHORT = "short"
    WAIT = "wait"


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class BiasSignal:
    """Signal de biais comportemental détecté."""
    bias_type:      BiasType
    confidence:     float           # [0, 1] — confiance détection
    intensity:      float           # [0, 1] — intensité du biais
    signal:         SignalDirection
    contrarian_action: ContrarianAction
    expiry_hours:   int             # durée de vie estimée
    metadata:       dict            # données de détection
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "bias_type": self.bias_type.value,
            "confidence": round(self.confidence, 3),
            "intensity": round(self.intensity, 3),
            "signal": self.signal.value,
            "contrarian_action": self.contrarian_action.value,
            "expiry_hours": self.expiry_hours,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    def summary(self) -> str:
        icon = {
            BiasType.ANCHORING: "🎯", BiasType.LOSS_AVERSION: "🛡️",
            BiasType.RECENCY: "📺", BiasType.DISPOSITION: "💰",
            BiasType.HERDING: "🐑", BiasType.FOMO: "🚀", BiasType.PANIC: "😱"
        }[self.bias_type]
        return (
            f"{icon} {self.bias_type.value}: {self.signal.value} | "
            f"conf={self.confidence:.0%} intens={self.intensity:.0%} → "
            f"contrarian: {self.contrarian_action.value}"
        )


@dataclass
class BehavioralBiasResult:
    """Résultat complet de l'analyse des biais comportementaux."""
    biases_detected:    list[BiasSignal]
    aggregate_signal:   SignalDirection
    contrarian_score:   float           # [0, 100] — opportunité contrarienne
    sizing_modifier:    float           # multiplicateur de position
    positioning_bias:   str             # "long" / "short" / "neutral"
    signals:            list[str]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "biases_detected": [b.to_dict() for b in self.biases_detected],
            "aggregate_signal": self.aggregate_signal.value,
            "contrarian_score": round(self.contrarian_score, 2),
            "sizing_modifier": round(self.sizing_modifier, 2),
            "positioning_bias": self.positioning_bias,
            "signals": self.signals,
            "timestamp": self.timestamp,
        }

    def summary(self) -> str:
        n = len(self.biases_detected)
        return (
            f"🧠 Biais comportementaux : {n} détecté(s)\n"
            f"  Signal agrégé : {self.aggregate_signal.value} | "
            f"Contrarian score : {self.contrarian_score:.0f}/100\n"
            f"  Sizing ×{self.sizing_modifier:.2f} | bias={self.positioning_bias}\n"
            f"  {' | '.join(self.signals[:3])}"
        )


class BacktestResult:
    """Résultats du backtest de la strate behavioral bias."""

    def __init__(self, results: list[dict]):
        self.results = results

    def summary(self) -> str:
        if not self.results:
            return "Aucun résultat de backtest."

        n = len(self.results)
        by_bias = {}
        for r in self.results:
            for bias in r.get("biases", []):
                btype = bias.get("bias_type", "unknown")
                by_bias.setdefault(btype, []).append(r)

        lines = [
            f"\n{'═' * 57}",
            f"  BACKTEST STRATE 5 — Behavioral Bias Arbitrage",
            f"{'═' * 57}",
            f"  Observations : {n}",
        ]
        for btype, rows in sorted(by_bias.items()):
            lines.append(f"  {btype.upper():<22}: {len(rows):>4} ({len(rows)/n:.1%})")

        if self.results and "pnl_pct" in self.results[0]:
            for btype in ["anchoring", "loss_aversion", "recency", "herding", "fomo", "panic"]:
                pnl = [r["pnl_pct"] for r in by_bias.get(btype, []) if "pnl_pct" in r]
                if pnl:
                    lines.append(
                        f"  P&L {btype.upper():<18}: {np.mean(pnl):+.3f}%  "
                        f"WR={sum(1 for x in pnl if x > 0) / len(pnl):.1%}"
                    )

        lines.append(f"{'═' * 57}\n")
        return "\n".join(lines)


# ── Moteur principal ──────────────────────────────────────────────────────────

class BehavioralBiasEngine:
    """
    Strate 5 — Behavioral Bias Arbitrage (Kahneman & Tversky).

    Détecte les biais comportementaux systématiques dans les données de marché
    et génère des signaux contrariens exploitables.

    Usage :
        engine = BehavioralBiasEngine(vault_path=Path("vault"))
        result = engine.analyze(
            prices=btc_prices,
            volume=btc_volume,
            long_short_ratio=0.88,  # optionnel
        )
        # result["contrarian_score"], result["biases_detected"]...

        bt = engine.backtest(df)  # df avec 'close', 'volume', optionnel 'pnl_pct'
        print(bt.summary())
    """

    def __init__(self, vault_path: Optional[Path] = None):
        self._vault_path = vault_path

        self._db_path: Optional[Path] = None
        if vault_path:
            db_dir = vault_path / "world_model"
            db_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = db_dir / "behavioral_biases.db"
            self._init_db()

        self._last_result: Optional[BehavioralBiasResult] = None

    # ── Interface publique ────────────────────────────────────────────────────

    def analyze(
        self,
        prices:          pd.Series,
        volume:          Optional[pd.Series] = None,
        long_short_ratio: Optional[float] = None,
        asset:           str = "BTC",
    ) -> dict:
        """
        Analyse les biais comportementaux sur les données de marché.

        Args:
            prices:          Série de prix de clôture
            volume:          Série de volume (optionnel)
            long_short_ratio: Ratio long/short global (optionnel, pour herding)
            asset:           Identifiant de l'actif

        Returns:
            dict avec : biases_detected, aggregate_signal, contrarian_score,
            sizing_modifier, positioning_bias, signals, timestamp.
        """
        prices_arr = np.array(prices.dropna(), dtype=float)
        volume_arr = np.array(volume.dropna(), dtype=float) if volume is not None else None

        if len(prices_arr) < 10:
            logger.warning("[Strate5] Série trop courte — état NEUTRAL")
            return self._neutral_result().to_dict()

        biases: list[BiasSignal] = []

        # 1. Anchoring
        anchoring = self._detect_anchoring(prices_arr)
        if anchoring:
            biases.append(anchoring)

        # 2. Loss Aversion
        loss_aversion = self._detect_loss_aversion(prices_arr)
        if loss_aversion:
            biases.append(loss_aversion)

        # 3. Recency Bias
        recency = self._detect_recency_bias(prices_arr)
        if recency:
            biases.append(recency)

        # 4. Disposition Effect
        if volume_arr is not None:
            disposition = self._detect_disposition_effect(prices_arr, volume_arr)
            if disposition:
                biases.append(disposition)

        # 5. Herding
        if long_short_ratio is not None:
            herding = self._detect_herding(long_short_ratio)
            if herding:
                biases.append(herding)

        # 6. FOMO
        if volume_arr is not None:
            fomo = self._detect_fomo(prices_arr, volume_arr)
            if fomo:
                biases.append(fomo)

        # 7. Panic
        if volume_arr is not None:
            panic = self._detect_panic(prices_arr, volume_arr)
            if panic:
                biases.append(panic)

        # Agrégation
        aggregate_signal = self._aggregate_signal(biases)
        contrarian_score = self._compute_contrarian_score(biases)
        sizing_modifier = self._compute_sizing_modifier(biases)
        positioning_bias = self._get_positioning_bias(aggregate_signal, contrarian_score)
        signals = self._generate_signals(biases)

        result = BehavioralBiasResult(
            biases_detected=biases,
            aggregate_signal=aggregate_signal,
            contrarian_score=contrarian_score,
            sizing_modifier=sizing_modifier,
            positioning_bias=positioning_bias,
            signals=signals,
        )

        logger.info("[Strate5] %s | asset=%s", result.summary(), asset)
        self._last_result = result
        self._save_to_db(result, asset)
        return result.to_dict()

    def backtest(self, df: pd.DataFrame) -> BacktestResult:
        """
        Backtest de la strate behavioral bias sur DataFrame historique.

        Args:
            df: DataFrame avec :
                - 'close' (float) — prix de clôture
                - 'volume' (float, optionnel)
                - 'long_short_ratio' (float, optionnel)
                - 'pnl_pct' (float, optionnel) — pour métriques qualité
        """
        if "close" not in df.columns:
            logger.warning("[Strate5] Backtest : colonne 'close' manquante.")
            return BacktestResult(results=[])

        prices = df["close"].values.astype(float)
        volume = df["volume"].values.astype(float) if "volume" in df.columns else None
        ls_ratio = df["long_short_ratio"].values if "long_short_ratio" in df.columns else None

        results: list[dict] = []
        window = 20  # fenêtre glissante

        for i in range(window, len(df)):
            window_prices = pd.Series(prices[i - window:i + 1])
            window_volume = pd.Series(volume[i - window:i + 1]) if volume is not None else None
            ls = float(ls_ratio[i]) if ls_ratio is not None else None

            res = self.analyze(window_prices, window_volume, ls)

            row: dict = {
                "idx": i,
                "biases": res["biases_detected"],
                "contrarian_score": res["contrarian_score"],
                "sizing_modifier": res["sizing_modifier"],
            }
            if "pnl_pct" in df.columns:
                row["pnl_pct"] = float(df["pnl_pct"].iloc[i])
            results.append(row)

        return BacktestResult(results=results)

    @property
    def last_result(self) -> Optional[BehavioralBiasResult]:
        return self._last_result

    # ── Détection des biais ───────────────────────────────────────────────────

    def _detect_anchoring(self, prices: np.ndarray) -> Optional[BiasSignal]:
        """
        Détecte l'ancrage sur les nombres ronds.

        Méthode : le prix actuel est-il à moins de 0.2% d'un nombre rond ?
        Si oui, et que le prix stagne (range < 0.5%), signal de sortie imminente.
        """
        current_price = prices[-1]
        price_range = (np.max(prices[-10:]) - np.min(prices[-10:])) / np.mean(prices[-10:])

        for round_num in ROUND_NUMBERS:
            distance_pct = abs(current_price - round_num) / round_num
            if distance_pct <= ROUND_NUMBER_TOLERANCE_PCT:
                # Prix accroché à un nombre rond
                if price_range <= STAGNATION_TOLERANCE_PCT * 2:
                    # Stagnation → sortie violente probable
                    direction = SignalDirection.BEARISH if current_price > round_num else SignalDirection.BULLISH
                    return BiasSignal(
                        bias_type=BiasType.ANCHORING,
                        confidence=0.7,
                        intensity=1.0 - distance_pct / ROUND_NUMBER_TOLERANCE_PCT,
                        signal=direction,
                        contrarian_action=ContrarianAction.SHORT if direction == SignalDirection.BEARISH else ContrarianAction.LONG,
                        expiry_hours=12,
                        metadata={"round_number": round_num, "distance_pct": distance_pct, "price_range": price_range},
                    )
        return None

    def _detect_loss_aversion(self, prices: np.ndarray) -> Optional[BiasSignal]:
        """
        Détecte la défense obstinée d'un support/résistance.

        Méthode : compter les tests d'un niveau (plus-haut ou plus-bas local).
        3+ tests sans cassure → probabilité de cassure augmente.
        """
        if len(prices) < 20:
            return None

        # Trouver le support/résistance local
        window = min(20, len(prices))
        recent = prices[-window:]

        high = np.max(recent)
        low = np.min(recent)
        current = prices[-1]

        # Compter les tests du support
        support_tests = sum(1 for p in recent[-10:] if abs(p - low) / low < 0.005)
        resistance_tests = sum(1 for p in recent[-10:] if abs(p - high) / high < 0.005)

        if support_tests >= SUPPORT_TEST_THRESHOLD:
            # Support défendu多次 → cassure imminente (bearish)
            confidence = min(0.5 + support_tests * 0.1, 0.9)
            return BiasSignal(
                bias_type=BiasType.LOSS_AVERSION,
                confidence=confidence,
                intensity=support_tests / 5.0,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=24,
                metadata={"support_level": low, "tests": support_tests},
            )

        if resistance_tests >= SUPPORT_TEST_THRESHOLD:
            # Résistance défendue多次 → cassure haussière
            confidence = min(0.5 + resistance_tests * 0.1, 0.9)
            return BiasSignal(
                bias_type=BiasType.LOSS_AVERSION,
                confidence=confidence,
                intensity=resistance_tests / 5.0,
                signal=SignalDirection.BULLISH,
                contrarian_action=ContrarianAction.LONG,
                expiry_hours=24,
                metadata={"resistance_level": high, "tests": resistance_tests},
            )

        return None

    def _detect_recency_bias(self, prices: np.ndarray) -> Optional[BiasSignal]:
        """
        Détecte l'extrapolation du récent (5+ bougies même direction).

        Méthode : compter les bougies consécutives dans la même direction.
        5+ → mean reversion probable.
        """
        if len(prices) < CONSECUTIVE_CANDLES_THRESHOLD + 2:
            return None

        # Direction des bougies
        directions = np.diff(prices)
        consecutive_up = 0
        consecutive_down = 0

        for d in reversed(directions[-10:]):
            if d > 0:
                consecutive_up += 1
                consecutive_down = 0
            else:
                consecutive_down += 1
                consecutive_up = 0

            if consecutive_up >= CONSECUTIVE_CANDLES_THRESHOLD:
                # 5+ bougies haussières → mean reversion (bearish)
                confidence = min(0.5 + (consecutive_up - CONSECUTIVE_CANDLES_THRESHOLD) * 0.1, 0.85)
                return BiasSignal(
                    bias_type=BiasType.RECENCY,
                    confidence=confidence,
                    intensity=consecutive_up / 10.0,
                    signal=SignalDirection.BEARISH,
                    contrarian_action=ContrarianAction.SHORT,
                    expiry_hours=6,
                    metadata={"consecutive_up": consecutive_up},
                )

            if consecutive_down >= CONSECUTIVE_CANDLES_THRESHOLD:
                # 5+ baissières → rebond (bullish)
                confidence = min(0.5 + (consecutive_down - CONSECUTIVE_CANDLES_THRESHOLD) * 0.1, 0.85)
                return BiasSignal(
                    bias_type=BiasType.RECENCY,
                    confidence=confidence,
                    intensity=consecutive_down / 10.0,
                    signal=SignalDirection.BULLISH,
                    contrarian_action=ContrarianAction.LONG,
                    expiry_hours=6,
                    metadata={"consecutive_down": consecutive_down},
                )

        return None

    def _detect_disposition_effect(
        self,
        prices: np.ndarray,
        volume: np.ndarray,
    ) -> Optional[BiasSignal]:
        """
        Détecte l'effet de disposition (vendre les gagnants trop tôt).

        Méthode : volume spike + prix stagne près des plus-hauts.
        Les investisseurs vendent leurs gains → accumulation silencieuse.
        """
        if len(prices) < 20:
            return None

        recent_volume = volume[-10:]
        avg_volume = np.mean(recent_volume[:-1]) if len(recent_volume) > 1 else np.mean(recent_volume)
        current_volume = recent_volume[-1]

        if current_volume < VOLUME_SPIKE_MULT * avg_volume:
            return None

        # Prix près des plus-hauts ?
        high = np.max(prices[-20:])
        current = prices[-1]
        near_high = (high - current) / high < STAGNATION_TOLERANCE_PCT * 2

        if near_high:
            # Volume spike + stagnation près ATH → accumulation (bullish)
            confidence = 0.65
            return BiasSignal(
                bias_type=BiasType.DISPOSITION,
                confidence=confidence,
                intensity=current_volume / avg_volume / VOLUME_SPIKE_MULT,
                signal=SignalDirection.BULLISH,
                contrarian_action=ContrarianAction.LONG,
                expiry_hours=48,
                metadata={
                    "volume_spike": current_volume / avg_volume,
                    "distance_from_high": (high - current) / high,
                },
            )

        return None

    def _detect_herding(self, long_short_ratio: float) -> Optional[BiasSignal]:
        """
        Détecte le comportement moutonnier (herding).

        Méthode : long/short ratio > 85% unidirectionnel.
        Quand tout le monde est positionné dans un sens → contrarien.
        """
        if long_short_ratio > HERDING_RATIO_THRESHOLD:
            # Tout le monde est long → top signal (bearish)
            intensity = (long_short_ratio - HERDING_RATIO_THRESHOLD) / (1 - HERDING_RATIO_THRESHOLD)
            return BiasSignal(
                bias_type=BiasType.HERDING,
                confidence=0.8,
                intensity=intensity,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=72,
                metadata={"long_short_ratio": long_short_ratio},
            )

        if long_short_ratio < (1 - HERDING_RATIO_THRESHOLD):
            # Tout le monde est short → bottom signal (bullish)
            intensity = ((1 - HERDING_RATIO_THRESHOLD) - long_short_ratio) / (1 - HERDING_RATIO_THRESHOLD)
            return BiasSignal(
                bias_type=BiasType.HERDING,
                confidence=0.8,
                intensity=intensity,
                signal=SignalDirection.BULLISH,
                contrarian_action=ContrarianAction.LONG,
                expiry_hours=72,
                metadata={"long_short_ratio": long_short_ratio},
            )

        return None

    def _detect_fomo(
        self,
        prices: np.ndarray,
        volume: np.ndarray,
    ) -> Optional[BiasSignal]:
        """
        Détecte la peur de rater (FOMO).

        Méthode : volume 3x moyenne + accélération des prix.
        Signal de pic parabolique → crash imminent.
        """
        if len(prices) < 20:
            return None

        recent_volume = volume[-10:]
        avg_volume = np.mean(recent_volume[:-1]) if len(recent_volume) > 1 else np.mean(recent_volume)
        current_volume = recent_volume[-1]

        if current_volume < FOMO_VOLUME_MULT * avg_volume:
            return None

        # Accélération des prix ?
        returns = np.diff(np.log(prices))
        recent_returns = returns[-5:]
        acceleration = np.mean(recent_returns) - np.mean(returns[:5]) if len(returns) >= 10 else np.mean(recent_returns)

        if acceleration > FOMO_ACCELERATION_THRESHOLD:
            # FOMO détecté → pic imminent (bearish)
            confidence = min(0.6 + (current_volume / avg_volume - FOMO_VOLUME_MULT) * 0.1, 0.9)
            return BiasSignal(
                bias_type=BiasType.FOMO,
                confidence=confidence,
                intensity=acceleration / FOMO_ACCELERATION_THRESHOLD,
                signal=SignalDirection.BEARISH,
                contrarian_action=ContrarianAction.SHORT,
                expiry_hours=24,
                metadata={
                    "volume_spike": current_volume / avg_volume,
                    "acceleration": acceleration,
                },
            )

        return None

    def _detect_panic(
        self,
        prices: np.ndarray,
        volume: np.ndarray,
    ) -> Optional[BiasSignal]:
        """
        Détecte la panique (vente massive).

        Méthode : mouvement 3-sigma + volume spike.
        Signal de rebond technique ("dead cat bounce").
        """
        if len(prices) < 30:
            return None

        returns = np.diff(np.log(prices))
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)

        if std_ret < 1e-6:
            return None

        current_return = returns[-1]
        z_score = (current_return - mean_ret) / std_ret

        if z_score < -PANIC_SIGMA:
            # Mouvement 3-sigma vers le bas
            recent_volume = volume[-10:]
            avg_volume = np.mean(recent_volume[:-1]) if len(recent_volume) > 1 else np.mean(recent_volume)
            current_volume = recent_volume[-1]

            if current_volume > PANIC_VOLUME_MULT * avg_volume:
                # Panique confirmée → rebond probable (bullish)
                confidence = min(0.7 + abs(z_score) * 0.05, 0.95)
                return BiasSignal(
                    bias_type=BiasType.PANIC,
                    confidence=confidence,
                    intensity=abs(z_score) / PANIC_SIGMA,
                    signal=SignalDirection.BULLISH,
                    contrarian_action=ContrarianAction.LONG,
                    expiry_hours=12,
                    metadata={
                        "z_score": z_score,
                        "volume_spike": current_volume / avg_volume,
                    },
                )

        return None

    # ── Agrégation ────────────────────────────────────────────────────────────

    def _aggregate_signal(self, biases: list[BiasSignal]) -> SignalDirection:
        """Agrège les signaux de biais en un signal directionnel."""
        if not biases:
            return SignalDirection.NEUTRAL

        bullish_score = sum(b.intensity * b.confidence for b in biases if b.signal == SignalDirection.BULLISH)
        bearish_score = sum(b.intensity * b.confidence for b in biases if b.signal == SignalDirection.BEARISH)

        diff = bullish_score - bearish_score
        if diff > 0.3:
            return SignalDirection.BULLISH
        if diff < -0.3:
            return SignalDirection.BEARISH
        return SignalDirection.NEUTRAL

    def _compute_contrarian_score(self, biases: list[BiasSignal]) -> float:
        """
        Calcule un score d'opportunité contrarienne [0, 100].

        Plus il y a de biais détectés avec forte intensité, plus l'opportunité
        contrarienne est forte.
        """
        if not biases:
            return 0.0

        score = sum(b.intensity * b.confidence * 20 for b in biases)
        return min(score, 100.0)

    def _compute_sizing_modifier(self, biases: list[BiasSignal]) -> float:
        """
        Calcule le modificateur de sizing basé sur les biais.

        Biais détectés → opportunité contrarienne → sizing augmenté.
        """
        if not biases:
            return 1.0

        # Base : 1.0
        # +0.05 par biais avec confidence > 0.6, max +20%
        high_conf_biases = sum(1 for b in biases if b.confidence > 0.6)
        modifier = 1.0 + 0.05 * min(high_conf_biases, 4)
        return np.clip(modifier, 0.8, 1.2)

    def _get_positioning_bias(
        self,
        aggregate: SignalDirection,
        contrarian_score: float,
    ) -> str:
        """Déduit le biais de positionnement."""
        if contrarian_score < 30:
            return "neutral"
        if aggregate == SignalDirection.BULLISH:
            return "long"
        if aggregate == SignalDirection.BEARISH:
            return "short"
        return "neutral"

    def _generate_signals(self, biases: list[BiasSignal]) -> list[str]:
        """Génère des descriptions textuelles pour les logs."""
        if not biases:
            return ["Aucun biais comportemental détecté"]
        return [b.summary() for b in biases[:5]]

    # ── Résultat neutre ───────────────────────────────────────────────────────

    @staticmethod
    def _neutral_result() -> BehavioralBiasResult:
        return BehavioralBiasResult(
            biases_detected=[],
            aggregate_signal=SignalDirection.NEUTRAL,
            contrarian_score=0.0,
            sizing_modifier=1.0,
            positioning_bias="neutral",
            signals=["Données insuffisantes"],
        )

    # ── SQLite ────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS behavioral_biases (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp          TEXT NOT NULL,
                        asset              TEXT NOT NULL,
                        bias_type          TEXT NOT NULL,
                        confidence         REAL NOT NULL,
                        intensity          REAL NOT NULL,
                        signal             TEXT NOT NULL,
                        contrarian_action  TEXT NOT NULL,
                        metadata           TEXT,
                        created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS behavioral_results (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp          TEXT NOT NULL,
                        asset              TEXT NOT NULL,
                        aggregate_signal   TEXT NOT NULL,
                        contrarian_score   REAL NOT NULL,
                        sizing_modifier    REAL NOT NULL,
                        biases_count       INTEGER NOT NULL,
                        created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_biases_ts
                    ON behavioral_biases (timestamp DESC)
                """)
                conn.commit()
        except Exception as exc:
            logger.warning("[Strate5] DB init error: %s", exc)

    def _save_to_db(self, result: BehavioralBiasResult, asset: str) -> None:
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                # Sauvegarde les résultats agrégés
                conn.execute("""
                    INSERT INTO behavioral_results
                    (timestamp, asset, aggregate_signal, contrarian_score,
                     sizing_modifier, biases_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    result.timestamp, asset, result.aggregate_signal.value,
                    result.contrarian_score, result.sizing_modifier,
                    len(result.biases_detected),
                ))

                # Sauvegarde chaque biais individuel
                for bias in result.biases_detected:
                    conn.execute("""
                        INSERT INTO behavioral_biases
                        (timestamp, asset, bias_type, confidence, intensity,
                         signal, contrarian_action, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        result.timestamp, asset, bias.bias_type.value,
                        bias.confidence, bias.intensity,
                        bias.signal.value, bias.contrarian_action.value,
                        json.dumps(bias.metadata),
                    ))

                conn.commit()
        except Exception as exc:
            logger.debug("[Strate5] DB save error: %s", exc)

    def get_history(self, asset: str = "BTC", limit: int = 50) -> list[dict]:
        """Récupère l'historique des analyses."""
        if not self._db_path or not self._db_path.exists():
            return []
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute("""
                    SELECT timestamp, aggregate_signal, contrarian_score,
                           sizing_modifier, biases_count
                    FROM behavioral_results
                    WHERE asset = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (asset, limit)).fetchall()
            return [
                {
                    "timestamp": r[0],
                    "aggregate_signal": r[1],
                    "contrarian_score": r[2],
                    "sizing_modifier": r[3],
                    "biases_count": r[4],
                }
                for r in rows
            ]
        except Exception as exc:
            logger.debug("[Strate5] DB history error: %s", exc)
            return []
