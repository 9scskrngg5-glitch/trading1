"""
Tests unitaires — Strate 3 : Narrative Epidemiology Engine (SIR)

Couvre :
  - _estimate_r0 : croissance / déclin / données insuffisantes
  - _classify_phase : mapping R0 × viral_score → NarrativePhase
  - _compute_market_impact : croisements phase × narrative_type
  - _compute_sizing_modifier : logique de pondération
  - _aggregate_market_impact : consensus / désaccord
  - backtest() : replay sur DataFrame synthétique
  - BacktestResult.summary() : métriques
  - _xml_text : helper stdlib
  - Persistance désactivée (vault_path=None)

Les tests réseau (CryptoPanic, RSS) ne sont pas couverts ici
pour éviter la dépendance à internet en CI.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import pytest

from core.strate_3_narrative_sir import (
    NarrativeEpidemiologyEngine,
    NarrativePhase,
    NarrativeType,
    NarrativeRecord,
    BacktestResult,
    _xml_text,
    GAMMA_DEFAULT,
    R0_GROWTH_THRESHOLD,
    R0_PEAK_LOW,
    VIRAL_SEEDING_MAX,
    VIRAL_EXTINCT_MAX,
    DEFAULT_NARRATIVES,
)
import xml.etree.ElementTree as ET


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_engine(**kwargs) -> NarrativeEpidemiologyEngine:
    """Engine sans vault_path (pas d'I/O) pour les tests unitaires."""
    return NarrativeEpidemiologyEngine(vault_path=None, **kwargs)


def make_record(
    phase:          NarrativePhase = NarrativePhase.GROWTH,
    narrative_type: NarrativeType  = NarrativeType.BULLISH,
    viral_score:    float          = 0.5,
    r0:             float          = 1.5,
    market_impact:  str            = "bullish",
) -> NarrativeRecord:
    return NarrativeRecord(
        narrative_id   = "test_nar",
        volume_today   = 10.0,
        viral_score    = viral_score,
        r0             = r0,
        growth_rate    = 0.1,
        phase          = phase,
        narrative_type = narrative_type,
        market_impact  = market_impact,
    )


# ── _estimate_r0 ──────────────────────────────────────────────────────────────

class TestEstimateR0:
    def test_growing_series_r0_gt_1(self):
        """Une série croissante doit donner R0 > 1."""
        engine = make_engine()
        series = [10.0, 12.0, 14.4, 17.3, 20.7]  # +20% par jour
        r0, rate = engine._estimate_r0(series)
        assert r0 > 1.0, f"R0={r0} attendu >1 pour série croissante"
        assert rate > 0.0

    def test_declining_series_r0_lt_1(self):
        """Une série déclinante doit donner R0 < 1."""
        engine = make_engine()
        series = [100.0, 80.0, 64.0, 51.2, 40.96]  # −20% par jour
        r0, rate = engine._estimate_r0(series)
        assert r0 < 1.0, f"R0={r0} attendu <1 pour série déclinante"
        assert rate < 0.0

    def test_flat_series_r0_eq_1(self):
        """Une série plate doit donner R0 ≈ 1."""
        engine = make_engine()
        series = [50.0, 50.0, 50.0, 50.0, 50.0]
        r0, rate = engine._estimate_r0(series)
        assert abs(r0 - 1.0) < 0.01, f"R0={r0} attendu ≈1 pour série plate"
        assert abs(rate) < 0.001

    def test_single_point_returns_neutral(self):
        """Série trop courte → (1.0, 0.0) neutre."""
        engine = make_engine()
        r0, rate = engine._estimate_r0([42.0])
        assert r0 == 1.0
        assert rate == 0.0

    def test_r0_clipped_above_zero(self):
        """R0 ne peut pas être négatif même avec déclin brutal."""
        engine = make_engine()
        series = [1000.0, 1.0, 1.0]  # crash brutal
        r0, _ = engine._estimate_r0(series)
        assert r0 >= 0.0

    def test_r0_clipped_below_10(self):
        """R0 ne dépasse pas 10 même avec croissance explosive."""
        engine = make_engine()
        series = [1.0, 1000.0, 1000000.0]
        r0, _ = engine._estimate_r0(series)
        assert r0 <= 10.0

    def test_custom_gamma(self):
        """Un gamma plus petit donne un R0 amplifié pour la même croissance."""
        series = [10.0, 12.0, 14.0, 16.0]
        engine_low_gamma  = make_engine(gamma=0.05)
        engine_high_gamma = make_engine(gamma=0.20)
        r0_low,  _ = engine_low_gamma._estimate_r0(series)
        r0_high, _ = engine_high_gamma._estimate_r0(series)
        assert r0_low > r0_high, "Gamma plus bas → R0 plus élevé"


# ── _classify_phase ───────────────────────────────────────────────────────────

class TestClassifyPhase:
    def test_extinct(self):
        phase = NarrativeEpidemiologyEngine._classify_phase(0.5, VIRAL_EXTINCT_MAX - 0.001)
        assert phase == NarrativePhase.EXTINCT

    def test_seeding(self):
        phase = NarrativeEpidemiologyEngine._classify_phase(1.5, VIRAL_SEEDING_MAX - 0.001)
        assert phase == NarrativePhase.SEEDING

    def test_growth(self):
        phase = NarrativeEpidemiologyEngine._classify_phase(
            R0_GROWTH_THRESHOLD + 0.1, VIRAL_SEEDING_MAX + 0.1
        )
        assert phase == NarrativePhase.GROWTH

    def test_peak(self):
        phase = NarrativeEpidemiologyEngine._classify_phase(
            (R0_PEAK_LOW + R0_GROWTH_THRESHOLD) / 2, VIRAL_SEEDING_MAX + 0.1
        )
        assert phase == NarrativePhase.PEAK

    def test_decay(self):
        phase = NarrativeEpidemiologyEngine._classify_phase(
            R0_PEAK_LOW - 0.1, VIRAL_SEEDING_MAX + 0.1
        )
        assert phase == NarrativePhase.DECAY


# ── _compute_market_impact ────────────────────────────────────────────────────

class TestMarketImpact:
    @pytest.mark.parametrize("phase,expected", [
        (NarrativePhase.GROWTH,  "bullish"),
        (NarrativePhase.PEAK,    "neutral"),
        (NarrativePhase.DECAY,   "bearish"),
        (NarrativePhase.SEEDING, "neutral"),
        (NarrativePhase.EXTINCT, "neutral"),
    ])
    def test_bullish_narrative(self, phase, expected):
        impact = NarrativeEpidemiologyEngine._compute_market_impact(
            phase, NarrativeType.BULLISH
        )
        assert impact == expected, f"Phase={phase.value}: attendu {expected}, got {impact}"

    @pytest.mark.parametrize("phase,expected", [
        (NarrativePhase.GROWTH,  "bearish"),
        (NarrativePhase.PEAK,    "neutral"),
        (NarrativePhase.DECAY,   "bullish"),
        (NarrativePhase.SEEDING, "neutral"),
        (NarrativePhase.EXTINCT, "neutral"),
    ])
    def test_bearish_narrative(self, phase, expected):
        impact = NarrativeEpidemiologyEngine._compute_market_impact(
            phase, NarrativeType.BEARISH
        )
        assert impact == expected, f"Phase={phase.value}: attendu {expected}, got {impact}"


# ── _compute_sizing_modifier ──────────────────────────────────────────────────

class TestSizingModifier:
    def test_no_active_narratives_returns_1(self):
        engine = make_engine()
        records = []
        mod = engine._compute_sizing_modifier(records)
        assert mod == 1.0

    def test_bullish_growth_boosts_sizing(self):
        engine = make_engine()
        records = [
            make_record(phase=NarrativePhase.GROWTH, narrative_type=NarrativeType.BULLISH),
        ]
        mod = engine._compute_sizing_modifier(records)
        assert mod > 1.0, f"Sizing modifier {mod} devrait être >1 avec narrative GROWTH bullish"

    def test_bearish_growth_reduces_sizing(self):
        engine = make_engine()
        records = [
            make_record(phase=NarrativePhase.GROWTH, narrative_type=NarrativeType.BEARISH,
                        market_impact="bearish"),
        ]
        mod = engine._compute_sizing_modifier(records)
        assert mod < 1.0, f"Sizing modifier {mod} devrait être <1 avec narrative GROWTH bearish"

    def test_modifier_clipped_to_valid_range(self):
        engine = make_engine()
        # Cas extrême : beaucoup de narratives haussières en growth
        records = [
            make_record(phase=NarrativePhase.GROWTH, narrative_type=NarrativeType.BULLISH)
            for _ in range(10)
        ]
        mod = engine._compute_sizing_modifier(records)
        assert 0.70 <= mod <= 1.20

    def test_bullish_peak_reduces_sizing(self):
        engine = make_engine()
        records = [
            make_record(phase=NarrativePhase.PEAK, narrative_type=NarrativeType.BULLISH),
        ]
        mod = engine._compute_sizing_modifier(records)
        assert mod < 1.0


# ── _aggregate_market_impact ──────────────────────────────────────────────────

class TestAggregateMarketImpact:
    def test_all_bullish_returns_bullish(self):
        records = [
            make_record(market_impact="bullish", viral_score=0.8),
            make_record(market_impact="bullish", viral_score=0.6),
        ]
        result = NarrativeEpidemiologyEngine._aggregate_market_impact(records)
        assert result == "bullish"

    def test_all_bearish_returns_bearish(self):
        records = [
            make_record(market_impact="bearish", viral_score=0.8),
            make_record(market_impact="bearish", viral_score=0.6),
        ]
        result = NarrativeEpidemiologyEngine._aggregate_market_impact(records)
        assert result == "bearish"

    def test_mixed_returns_neutral(self):
        records = [
            make_record(market_impact="bullish", viral_score=0.5),
            make_record(market_impact="bearish", viral_score=0.5),
        ]
        result = NarrativeEpidemiologyEngine._aggregate_market_impact(records)
        assert result == "neutral"

    def test_empty_records_returns_neutral(self):
        result = NarrativeEpidemiologyEngine._aggregate_market_impact([])
        assert result == "neutral"

    def test_high_weight_dominates(self):
        """Un record très viral doit dominer les petits."""
        records = [
            make_record(market_impact="bullish",  viral_score=0.9),
            make_record(market_impact="bearish",  viral_score=0.05),
        ]
        result = NarrativeEpidemiologyEngine._aggregate_market_impact(records)
        assert result == "bullish"


# ── backtest ──────────────────────────────────────────────────────────────────

class TestBacktest:
    def _make_df(self, volumes: list[float], pnl: list[float] | None = None) -> pd.DataFrame:
        df = pd.DataFrame({"volume": volumes})
        if pnl:
            df["pnl_pct"] = pnl
        return df

    def test_backtest_no_volume_column(self):
        engine = make_engine()
        df = pd.DataFrame({"close": [100, 200, 300]})
        result = engine.backtest(df)
        assert result.results == []

    def test_backtest_returns_correct_count(self):
        engine = make_engine(r0_window_days=3)
        volumes = [10.0, 12.0, 15.0, 18.0, 22.0, 20.0, 16.0, 14.0]
        df = self._make_df(volumes)
        result = engine.backtest(df)
        # On attend len(df) - r0_window - 1 observations
        assert len(result.results) == len(volumes) - engine._r0_window - 1

    def test_backtest_phases_are_valid(self):
        engine = make_engine(r0_window_days=3)
        volumes = [5.0, 10.0, 20.0, 40.0, 80.0, 60.0, 40.0, 20.0]
        df = self._make_df(volumes)
        result = engine.backtest(df)
        valid_phases = {p.value for p in NarrativePhase}
        for row in result.results:
            assert row["phase"] in valid_phases

    def test_backtest_r0_present(self):
        engine = make_engine(r0_window_days=3)
        volumes = list(range(10, 20))
        df = self._make_df(volumes)
        result = engine.backtest(df)
        for row in result.results:
            assert "r0" in row
            assert 0.0 <= row["r0"] <= 10.0

    def test_backtest_with_pnl(self):
        engine = make_engine(r0_window_days=3)
        volumes = [10.0, 12.0, 15.0, 18.0, 22.0, 20.0, 16.0]
        pnl     = [0.5,   0.3,  0.8,  1.2,   0.1,  -0.5, -1.0]
        df = self._make_df(volumes, pnl)
        result = engine.backtest(df)
        for row in result.results:
            assert "pnl_pct" in row

    def test_backtest_summary_runs(self):
        engine = make_engine(r0_window_days=3)
        volumes = [10.0, 12.0, 15.0, 18.0, 22.0, 20.0, 16.0, 14.0]
        pnl     = [0.5,   0.3,  0.8,  1.2,   0.1,  -0.5, -1.0, -0.8]
        df = self._make_df(volumes, pnl)
        result = engine.backtest(df)
        summary = result.summary()
        assert "STRATE 3" in summary
        assert "Observations" in summary

    def test_backtest_growing_series_mostly_growth(self):
        """Une série monotone croissante → la majorité en phase GROWTH."""
        engine = make_engine(r0_window_days=3)
        volumes = [float(v) for v in range(5, 50)]
        df = self._make_df(volumes)
        result = engine.backtest(df)
        growth_count = sum(1 for r in result.results if r["phase"] == "growth")
        total = len(result.results)
        assert growth_count / total > 0.5, (
            f"Série croissante devrait être majoritairement en GROWTH : "
            f"{growth_count}/{total}"
        )


# ── BacktestResult.summary ────────────────────────────────────────────────────

class TestBacktestResultSummary:
    def test_empty_summary(self):
        bt = BacktestResult(results=[])
        assert "Aucun" in bt.summary()

    def test_summary_contains_phases(self):
        results = [
            {"phase": "growth", "r0": 1.5, "viral_score": 0.6},
            {"phase": "peak",   "r0": 1.0, "viral_score": 0.7},
            {"phase": "decay",  "r0": 0.7, "viral_score": 0.4},
        ]
        summary = BacktestResult(results=results).summary()
        assert "GROWTH" in summary
        assert "PEAK"   in summary
        assert "DECAY"  in summary


# ── _xml_text helper ──────────────────────────────────────────────────────────

class TestXmlText:
    def test_finds_first_tag(self):
        xml = "<item><title>Bitcoin halving</title></item>"
        elem = ET.fromstring(xml)
        assert _xml_text(elem, ["title"]) == "Bitcoin halving"

    def test_falls_back_to_second_tag(self):
        xml = "<item><summary>DeFi summer returns</summary></item>"
        elem = ET.fromstring(xml)
        assert _xml_text(elem, ["title", "summary"]) == "DeFi summer returns"

    def test_returns_empty_if_not_found(self):
        xml = "<item><other>text</other></item>"
        elem = ET.fromstring(xml)
        assert _xml_text(elem, ["title", "description"]) == ""

    def test_handles_empty_tag(self):
        xml = "<item><title></title></item>"
        elem = ET.fromstring(xml)
        assert _xml_text(elem, ["title"]) == ""


# ── Cohérence des constantes ──────────────────────────────────────────────────

class TestConstants:
    def test_gamma_positive(self):
        assert GAMMA_DEFAULT > 0.0

    def test_r0_thresholds_ordered(self):
        assert R0_PEAK_LOW < R0_GROWTH_THRESHOLD

    def test_viral_thresholds_ordered(self):
        assert VIRAL_EXTINCT_MAX < VIRAL_SEEDING_MAX

    def test_default_narratives_not_empty(self):
        assert len(DEFAULT_NARRATIVES) > 0
        for nid, keywords in DEFAULT_NARRATIVES.items():
            assert isinstance(keywords, list)
            assert len(keywords) > 0

    def test_engine_uses_default_narratives(self):
        engine = make_engine()
        assert engine._narratives is DEFAULT_NARRATIVES

    def test_engine_accepts_custom_narratives(self):
        custom = {"test_nar": ["bitcoin"]}
        engine = make_engine(narratives=custom)
        assert engine._narratives == custom
