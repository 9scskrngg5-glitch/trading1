"""
Dynamic Position Sizer — Kelly Criterion + Risk-Adjusted Sizing.

Stratégies de sizing :
  1. FIXED       : % fixe du capital (classique 2%)
  2. KELLY       : Kelly Criterion — optimal mathématique
  3. HALF_KELLY  : demi-Kelly (plus conservateur, recommandé)
  4. VOLATILITY  : ajusté à la volatilité (ATR-normalized)
  5. ADAPTIVE    : combinaison Kelly + vol + drawdown + streak

Wall Street note : Kelly pur surdimensionne souvent.
Le demi-Kelly offre ~75% du rendement du Kelly complet avec ~50% du drawdown.
"""

from __future__ import annotations

import logging
import math
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SizingMethod(str, Enum):
    FIXED       = "fixed"
    KELLY       = "kelly"
    HALF_KELLY  = "half_kelly"
    VOLATILITY  = "volatility"
    ADAPTIVE    = "adaptive"


class DynamicSizer:
    """
    Calcule la taille de position optimale en fonction du contexte.

    Usage:
        sizer = DynamicSizer(method="adaptive", base_risk_pct=2.0)
        risk_pct = sizer.compute(
            win_rate=0.55, avg_win=2.5, avg_loss=1.0,
            confidence=75, drawdown_pct=3.0, atr_pct=1.2,
            consecutive_wins=2, max_drawdown_pct=15.0,
        )
    """

    def __init__(
        self,
        method: str = "adaptive",
        base_risk_pct: float = 2.0,
        min_risk_pct:  float = 0.5,
        max_risk_pct:  float = 5.0,
    ):
        self.method        = SizingMethod(method)
        self.base_risk_pct = base_risk_pct
        self.min_risk_pct  = min_risk_pct
        self.max_risk_pct  = max_risk_pct

    def compute(
        self,
        win_rate:       float = 0.50,  # 0.0 à 1.0
        avg_win_pct:    float = 2.5,   # % moyen des gains
        avg_loss_pct:   float = 1.0,   # % moyen des pertes (positif)
        confidence:     int   = 50,    # 0 à 100
        drawdown_pct:   float = 0.0,   # drawdown courant
        max_drawdown_pct: float = 15.0,
        atr_pct:        float = 1.5,   # ATR en % du prix
        streak:         int   = 0,     # +N = wins, -N = losses
        total_trades:   int   = 0,     # trades dans l'historique
    ) -> float:
        """
        Retourne le % du capital à risquer sur ce trade.
        """
        if self.method == SizingMethod.FIXED:
            return self._fixed()
        elif self.method == SizingMethod.KELLY:
            return self._kelly(win_rate, avg_win_pct, avg_loss_pct)
        elif self.method == SizingMethod.HALF_KELLY:
            return self._half_kelly(win_rate, avg_win_pct, avg_loss_pct)
        elif self.method == SizingMethod.VOLATILITY:
            return self._volatility(atr_pct)
        elif self.method == SizingMethod.ADAPTIVE:
            return self._adaptive(
                win_rate, avg_win_pct, avg_loss_pct,
                confidence, drawdown_pct, max_drawdown_pct,
                atr_pct, streak, total_trades,
            )
        return self.base_risk_pct

    # ── Méthodes de sizing ───────────────────────────────────────────────────

    def _fixed(self) -> float:
        """Risque fixe — simple et fiable."""
        return self.base_risk_pct

    def _kelly(self, wr: float, avg_win: float, avg_loss: float) -> float:
        """
        Kelly Criterion : f* = (p * b - q) / b
        où p = win rate, q = 1-p, b = ratio gains/pertes moyen.

        Clampé entre min et max pour éviter les excès.
        """
        if wr <= 0 or avg_loss <= 0:
            return self.min_risk_pct

        b = avg_win / avg_loss   # odds ratio
        q = 1 - wr
        kelly = (wr * b - q) / b

        if kelly <= 0:
            return self.min_risk_pct

        kelly_pct = kelly * 100
        return self._clamp(kelly_pct)

    def _half_kelly(self, wr: float, avg_win: float, avg_loss: float) -> float:
        """
        Demi-Kelly — compromis optimal entre rendement et drawdown.
        ~75% du rendement du Kelly complet, ~50% du drawdown.
        """
        full_kelly = self._kelly(wr, avg_win, avg_loss)
        return self._clamp(full_kelly * 0.5)

    def _volatility(self, atr_pct: float) -> float:
        """
        Vol-adjusted sizing : inverse de la volatilité.
        Plus le marché est volatile, plus on réduit la taille.

        Cible : normaliser le risque réel à ~1 ATR par trade.
        """
        if atr_pct <= 0:
            return self.base_risk_pct

        # Référence : ATR = 1.5% → risque = base_risk_pct
        ref_atr = 1.5
        vol_factor = ref_atr / max(atr_pct, 0.1)
        risk = self.base_risk_pct * vol_factor
        return self._clamp(risk)

    def _adaptive(
        self,
        wr: float,
        avg_win: float,
        avg_loss: float,
        confidence: int,
        dd_pct: float,
        max_dd: float,
        atr_pct: float,
        streak: int,
        total_trades: int,
    ) -> float:
        """
        Sizing adaptatif multi-facteurs — approche Wall Street.

        Compose 4 facteurs multiplicatifs sur le base_risk :
          1. Kelly factor     : ajuste selon l'edge statistique
          2. Confidence factor: confiance du signal (50→1.0, 100→1.5)
          3. Drawdown factor  : réduit quand DD monte
          4. Streak factor    : réduit après pertes, augmente après wins
          5. Vol factor       : réduit en haute volatilité
          6. Sample factor    : conservateur si peu de trades historiques
        """
        risk = self.base_risk_pct

        # 1. Kelly factor (si assez de data)
        if total_trades >= 20 and wr > 0 and avg_loss > 0:
            half_kelly = self._half_kelly(wr, avg_win, avg_loss)
            # Blend 50/50 entre fixe et Kelly
            kelly_factor = (half_kelly / self.base_risk_pct)
            kelly_factor = max(0.5, min(kelly_factor, 2.0))
            risk *= kelly_factor

        # 2. Confidence factor : 0-50 → 0.5x, 50 → 1.0x, 75 → 1.25x, 100 → 1.5x
        conf_factor = max(confidence / 100, 0.5)
        risk *= conf_factor

        # 3. Drawdown factor : linéaire 1.0 → 0.3 entre 0% et max_dd
        if max_dd > 0:
            dd_ratio = min(dd_pct / max_dd, 1.0)
            dd_factor = max(1.0 - dd_ratio * 0.7, 0.3)
            risk *= dd_factor

        # 4. Streak factor :
        #    +3 wins → 1.15x (momentum)
        #    -3 losses → 0.7x (protection)
        if streak >= 3:
            risk *= min(1.0 + streak * 0.05, 1.25)  # cap à +25%
        elif streak <= -2:
            risk *= max(1.0 + streak * 0.1, 0.5)    # cap à -50%

        # 5. Vol factor
        if atr_pct > 0:
            vol_factor = 1.5 / max(atr_pct, 0.1)
            vol_factor = max(0.5, min(vol_factor, 1.5))
            risk *= vol_factor

        # 6. Sample size factor : conservateur avec peu de data
        if total_trades < 30:
            sample_factor = max(total_trades / 30, 0.4)
            risk *= sample_factor

        return self._clamp(risk)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _clamp(self, value: float) -> float:
        return round(max(self.min_risk_pct, min(value, self.max_risk_pct)), 3)
