"""
Strate 0 — Epistemological Engine
"Est-ce qu'ORACLE trade du signal ou du bruit ?"

Basé sur l'observation de Fischer Black : 90%+ des mouvements de prix
sont du bruit pur. Avant de générer le moindre signal, ORACLE doit répondre :
"Ai-je assez de signal pour justifier un trade ?"

Conditions du gate (configurables) :
  SNR < SNR_THRESHOLD (défaut 0.35)             → bloque
  uncertainty > UNCERTAINTY_THRESHOLD (défaut 0.40) → bloque
  Les deux doivent passer pour qu'un trade soit autorisé.

Métriques :
  - Shannon entropy sur fenêtre glissante de rendements log
  - Mutual information normalisée (prix ↔ facteurs macro ou autocorrélation proxy)
  - Variance d'ensemble des prédictions = incertitude épistémique

Usage :
    engine = EpistemologicalEngine(vault_path=Path("vault"))
    allowed, info = engine.should_trade(prices, macro_factors, predictions,
                                        asset="BTC/USDT", timeframe="1h")
    # info = {allowed, snr, entropy, uncertainty, mi_score, reason, timestamp}
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Seuils par défaut ─────────────────────────────────────────────────────────
SNR_THRESHOLD         = 0.35   # en dessous → trop de bruit
UNCERTAINTY_THRESHOLD = 0.40   # au dessus  → trop d'incertitude
ENTROPY_WINDOW        = 50     # candles pour le calcul d'entropie
ENTROPY_BINS          = 10     # bins de discrétisation des rendements
MI_LAGS               = 5      # lags pour l'autocorrélation (proxy MI)

# Poids du composite SNR (entropie inverse vs MI)
_W_ENTROPY = 0.70
_W_MI      = 0.30


# ── Résultat du gate ──────────────────────────────────────────────────────────

@dataclass
class GateResult:
    allowed:     bool
    snr:         float
    entropy:     float
    uncertainty: float
    mi_score:    float
    reason:      str
    asset:       str = ""
    timeframe:   str = ""
    timestamp:   str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "allowed":     self.allowed,
            "snr":         round(self.snr, 4),
            "entropy":     round(self.entropy, 4),
            "uncertainty": round(self.uncertainty, 4),
            "mi_score":    round(self.mi_score, 4),
            "reason":      self.reason,
            "asset":       self.asset,
            "timeframe":   self.timeframe,
            "timestamp":   self.timestamp,
        }


# ── Résultat de backtest ──────────────────────────────────────────────────────

class BacktestResult:
    """Résultats du backtest du gate épistémologique sur données historiques."""

    def __init__(self, results: list[dict]):
        self.results = results

    def summary(self) -> str:
        if not self.results:
            return "Aucun résultat de backtest."

        total      = len(self.results)
        passed     = sum(1 for r in self.results if r["allowed"])
        blocked    = total - passed
        block_rate = blocked / max(total, 1)

        snrs = [r["snr"] for r in self.results]

        lines = [
            f"\n{'═' * 57}",
            f"  BACKTEST STRATE 0 — Epistemological Gate",
            f"{'═' * 57}",
            f"  Signaux évalués : {total}",
            f"  Signaux passés  : {passed}  ({1 - block_rate:.1%})",
            f"  Signaux bloqués : {blocked}  ({block_rate:.1%})",
            f"\n  SNR  moyen      : {np.mean(snrs):.3f}",
            f"  SNR  médian     : {np.median(snrs):.3f}",
            f"  SNR  [min, max] : [{np.min(snrs):.3f}, {np.max(snrs):.3f}]",
        ]

        # Métriques de qualité si pnl_pct disponible
        if "pnl_pct" in self.results[0]:
            all_pnl     = [r["pnl_pct"] for r in self.results]
            passed_pnl  = [r["pnl_pct"] for r in self.results if r["allowed"]]
            blocked_pnl = [r["pnl_pct"] for r in self.results if not r["allowed"]]

            def wr(lst: list) -> str:
                if not lst:
                    return "—"
                return f"{sum(1 for x in lst if x > 0) / len(lst):.1%}"

            lines += [
                f"\n  P&L moyen (tous)    : {np.mean(all_pnl):+.3f}%  WR={wr(all_pnl)}",
            ]
            if passed_pnl:
                lines.append(
                    f"  P&L moyen (passés)  : {np.mean(passed_pnl):+.3f}%  WR={wr(passed_pnl)}"
                )
            if blocked_pnl:
                lines.append(
                    f"  P&L moyen (bloqués) : {np.mean(blocked_pnl):+.3f}%  WR={wr(blocked_pnl)}"
                )
                noise_saved = -np.mean(blocked_pnl)
                lines.append(
                    f"  Bruit évité         : {noise_saved:+.3f}% moyen / trade bloqué"
                )

        lines.append(f"{'═' * 57}\n")
        return "\n".join(lines)


# ── Moteur épistémologique ────────────────────────────────────────────────────

class EpistemologicalEngine:
    """
    Gate épistémologique — filtre signal vs bruit avant chaque décision.

    Peut être instancié en mode standalone (tests, backtest) ou intégré
    dans PredictAgent (via EpistemologicalGate wrapper).

    Chaque décision est loguée dans vault/epistemic/gate_log.jsonl.
    """

    def __init__(
        self,
        snr_threshold:         float         = SNR_THRESHOLD,
        uncertainty_threshold: float         = UNCERTAINTY_THRESHOLD,
        entropy_window:        int           = ENTROPY_WINDOW,
        entropy_bins:          int           = ENTROPY_BINS,
        vault_path:            Optional[Path] = None,
    ):
        self.snr_threshold         = snr_threshold
        self.uncertainty_threshold = uncertainty_threshold
        self.entropy_window        = entropy_window
        self.entropy_bins          = entropy_bins
        self._vault_path           = vault_path

        if vault_path:
            ep_dir = vault_path / "epistemic"
            ep_dir.mkdir(parents=True, exist_ok=True)

        # Statistiques de session
        self._total_evaluated = 0
        self._total_blocked   = 0

    # ── Interface publique ────────────────────────────────────────────────────

    def compute_entropy(self, prices: pd.Series, window: Optional[int] = None) -> float:
        """
        Entropie de Shannon sur rendements logarithmiques, normalisée ∈ [0, 1].

          0.0 → signal pur (rendements directionnels et réguliers)
          1.0 → bruit pur  (rendements uniformément distribués)

        Args:
            prices: Series de prix de clôture (ordre chronologique).
            window: Nombre de candles à utiliser (défaut: self.entropy_window).
        """
        w = window or self.entropy_window
        if len(prices) < w + 1:
            return 1.0  # données insuffisantes → bruit

        returns = np.log(prices.iloc[-w:] / prices.iloc[-w:].shift(1)).dropna().values
        if len(returns) < 2:
            return 1.0

        # ── Entropie directionnelle (binaire : up / down) ──────────────────
        # Un marché directionnel (tendance) → p_up ≈ 1 ou p_down ≈ 1 → H ≈ 0.
        # Un marché aléatoire → p_up ≈ 0.5 → H = 1.0 (entropie max binaire).
        n_up   = float(np.sum(returns > 0))
        n_down = float(len(returns) - n_up)
        p_up   = n_up   / len(returns)
        p_down = n_down / len(returns)
        h_dir  = 0.0
        if p_up   > 0:
            h_dir -= p_up   * math.log2(p_up)
        if p_down > 0:
            h_dir -= p_down * math.log2(p_down)
        # h_dir ∈ [0, 1] car max = log2(2) = 1

        # ── Entropie de magnitude (distribution des tailles de mouvement) ──
        # Pénalise les alternances irrégulières de gros/petits mouvements.
        abs_returns = np.abs(returns)
        counts, _   = np.histogram(abs_returns, bins=self.entropy_bins)
        counts      = counts[counts > 0]
        if len(counts) > 1:
            probs    = counts / counts.sum()
            h_mag    = float(-np.sum(probs * np.log2(probs))) / math.log2(self.entropy_bins)
        else:
            h_mag = 0.0  # tous les mouvements de même amplitude → signal fort

        # ── Composite : 70% directionnel + 30% magnitude ──
        h_composite = 0.70 * h_dir + 0.30 * h_mag
        return float(np.clip(h_composite, 0.0, 1.0))

    def compute_snr(
        self,
        prices:        pd.Series,
        macro_factors: Optional[pd.DataFrame] = None,
        window:        Optional[int]          = None,
    ) -> tuple[float, float]:
        """
        Calcule le Signal-to-Noise Ratio composite et le score MI.

        Returns:
            (snr, mi_score) — tous deux ∈ [0, 1].
            snr = _W_ENTROPY * (1 − entropy) + _W_MI * mi_score
        """
        entropy = self.compute_entropy(prices, window)
        snr_entropy = 1.0 - entropy

        if macro_factors is not None and not macro_factors.empty:
            mi_score = self._mutual_information_macro(prices, macro_factors, window)
        else:
            mi_score = self._autocorrelation_proxy(prices, window)

        snr = _W_ENTROPY * snr_entropy + _W_MI * mi_score
        return float(np.clip(snr, 0.0, 1.0)), float(np.clip(mi_score, 0.0, 1.0))

    def compute_epistemic_uncertainty(self, predictions: np.ndarray) -> float:
        """
        Incertitude épistémique à partir d'un ensemble de prédictions.

        `predictions` = tableau de scores de confiance (0–100 ou 0.0–1.0)
        issus de plusieurs timeframes, agents ou modèles.

          0.0 → consensus parfait (toutes les prédictions identiques)
          1.0 → désaccord total

        Args:
            predictions: Array de scores de confiance.
        """
        if len(predictions) == 0:
            return 1.0
        if len(predictions) == 1:
            return 0.0

        arr = np.asarray(predictions, dtype=float)
        if arr.max() > 1.0:
            arr = arr / 100.0

        # std max théorique pour U[0,1] = 0.5 → normalise à [0, 1]
        std = float(np.std(arr))
        return float(np.clip(std / 0.5, 0.0, 1.0))

    def should_trade(
        self,
        prices:        pd.Series,
        macro_factors: Optional[pd.DataFrame] = None,
        predictions:   Optional[np.ndarray]   = None,
        asset:         str                    = "",
        timeframe:     str                    = "",
    ) -> tuple[bool, dict]:
        """
        Gate principal — décide si un trade est épistémiquement justifié.

        Args:
            prices:        Series de prix de clôture (chronologique).
            macro_factors: DataFrame de facteurs macro (optionnel, Strate 1).
            predictions:   Array de confidences (multi-TF, multi-agent).
            asset:         Identifiant de l'actif (pour le log).
            timeframe:     Timeframe analysé (pour le log).

        Returns:
            (allowed: bool, info: dict)
            info contient: snr, entropy, uncertainty, mi_score, reason, timestamp.
        """
        self._total_evaluated += 1

        snr, mi_score = self.compute_snr(prices, macro_factors)
        # Retrouver l'entropie brute depuis le SNR composite
        entropy_raw = 1.0 - (snr - _W_MI * mi_score) / _W_ENTROPY

        if predictions is not None and len(predictions) > 0:
            uncertainty = self.compute_epistemic_uncertainty(predictions)
        else:
            uncertainty = 0.25  # valeur neutre conservatrice si pas de prédictions multiples

        snr_ok  = snr >= self.snr_threshold
        unc_ok  = uncertainty <= self.uncertainty_threshold
        allowed = snr_ok and unc_ok

        parts = []
        if not snr_ok:
            parts.append(
                f"SNR={snr:.3f} < seuil {self.snr_threshold:.2f} (bruit dominant, H={entropy_raw:.3f})"
            )
        if not unc_ok:
            parts.append(
                f"incertitude={uncertainty:.3f} > seuil {self.uncertainty_threshold:.2f}"
            )
        reason = "AUTORISÉ" if allowed else "BLOQUÉ — " + " | ".join(parts)

        result = GateResult(
            allowed=allowed,
            snr=snr,
            entropy=float(np.clip(entropy_raw, 0.0, 1.0)),
            uncertainty=uncertainty,
            mi_score=mi_score,
            reason=reason,
            asset=asset,
            timeframe=timeframe,
        )

        if not allowed:
            self._total_blocked += 1
            logger.info(
                "[Strate0] ❌ %s/%s BLOQUÉ | SNR=%.3f MI=%.3f unc=%.3f H=%.3f",
                asset, timeframe, snr, mi_score, uncertainty, entropy_raw,
            )
        else:
            logger.debug(
                "[Strate0] ✅ %s/%s PASS  | SNR=%.3f MI=%.3f unc=%.3f H=%.3f",
                asset, timeframe, snr, mi_score, uncertainty, entropy_raw,
            )

        self._persist_result(result)
        return allowed, result.to_dict()

    # ── Backtest ──────────────────────────────────────────────────────────────

    def backtest(
        self,
        df:             pd.DataFrame,
        price_col:      str = "close",
        confidence_col: str = "confidence",
        timeframe:      str = "1h",
    ) -> BacktestResult:
        """
        Rejoue le gate sur un DataFrame historique ligne par ligne.

        `df` doit avoir au minimum une colonne `close`.
        Si `confidence` est présente, elle sert de prédiction unique.
        Si `pnl_pct` est présente, le résumé affichera les métriques qualité.

        Returns:
            BacktestResult avec .summary() pour affichage.
        """
        results: list[dict] = []
        prices_series = df[price_col]

        for i in range(self.entropy_window + 1, len(df)):
            prices = prices_series.iloc[: i + 1]

            preds = None
            if confidence_col in df.columns:
                preds = np.array([float(df[confidence_col].iloc[i])])

            allowed, info = self.should_trade(
                prices=prices,
                predictions=preds,
                timeframe=timeframe,
            )

            row: dict = {
                "idx":       i,
                "allowed":   allowed,
                "snr":       info["snr"],
                "entropy":   info["entropy"],
                "uncertainty": info["uncertainty"],
            }
            if "pnl_pct" in df.columns:
                row["pnl_pct"] = float(df["pnl_pct"].iloc[i])
            results.append(row)

        return BacktestResult(results=results)

    # ── Stats de session ──────────────────────────────────────────────────────

    @property
    def block_rate(self) -> float:
        """Taux de blocage depuis le démarrage."""
        if self._total_evaluated == 0:
            return 0.0
        return self._total_blocked / self._total_evaluated

    def session_stats(self) -> dict:
        return {
            "total_evaluated": self._total_evaluated,
            "total_blocked":   self._total_blocked,
            "block_rate":      round(self.block_rate, 3),
        }

    # ── Helpers internes ─────────────────────────────────────────────────────

    def _mutual_information_macro(
        self,
        prices: pd.Series,
        macro:  pd.DataFrame,
        window: Optional[int] = None,
    ) -> float:
        """MI normalisée entre rendements prix et chaque facteur macro."""
        w = window or self.entropy_window
        if macro.empty or len(prices) < w + 1:
            return 0.3

        returns = np.log(prices / prices.shift(1)).dropna().values[-w:]
        scores: list[float] = []

        for col in macro.columns:
            factor = macro[col].dropna().values
            n = min(len(returns), len(factor))
            if n < 10:
                continue
            mi = self._mi_histogram(returns[-n:], factor[-n:])
            scores.append(mi)

        return float(np.mean(scores)) if scores else 0.3

    def _autocorrelation_proxy(
        self,
        prices: pd.Series,
        window: Optional[int] = None,
    ) -> float:
        """
        Proxy MI via autocorrélation à MI_LAGS lags.

        Un signal tendanciel a une autocorrélation significative.
        Du bruit pur a une autocorrélation proche de 0.
        Retourne la moyenne des |ACF| ∈ [0, 1].
        """
        w = window or self.entropy_window
        if len(prices) < w + MI_LAGS + 1:
            return 0.3

        returns = np.log(prices / prices.shift(1)).dropna().values[-w:]
        acfs: list[float] = []

        for lag in range(1, MI_LAGS + 1):
            if len(returns) <= lag:
                break
            r  = returns[:-lag]
            rl = returns[lag:]
            if len(r) > 2:
                corr = float(np.corrcoef(r, rl)[0, 1])
                if not math.isnan(corr):
                    acfs.append(abs(corr))

        return float(np.mean(acfs)) if acfs else 0.3

    @staticmethod
    def _mi_histogram(x: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
        """
        Mutual Information normalisée via histogramme 2D (NMI).

        NMI = MI(X,Y) / min(H(X), H(Y))
        Retourne ∈ [0, 1].
        """
        try:
            c_xy, _, _ = np.histogram2d(x, y, bins=bins)
            c_x  = c_xy.sum(axis=1)
            c_y  = c_xy.sum(axis=0)
            n    = c_xy.sum()
            if n == 0:
                return 0.0

            px  = c_x[c_x > 0] / n
            py  = c_y[c_y > 0] / n
            pxy = c_xy[c_xy > 0] / n

            hx  = -float(np.sum(px  * np.log2(px)))
            hy  = -float(np.sum(py  * np.log2(py)))
            hxy = -float(np.sum(pxy * np.log2(pxy)))

            mi    = hx + hy - hxy
            denom = min(hx, hy)
            if denom <= 0:
                return 0.0
            return float(np.clip(mi / denom, 0.0, 1.0))
        except Exception:
            return 0.0

    def _persist_result(self, result: GateResult) -> None:
        """Sauvegarde dans vault/epistemic/gate_log.jsonl (append)."""
        if not self._vault_path:
            return
        try:
            log_path = self._vault_path / "epistemic" / "gate_log.jsonl"
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        except Exception as exc:
            logger.debug("[Strate0] Persist error: %s", exc)
