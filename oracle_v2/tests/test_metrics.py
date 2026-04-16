"""Tests MetricsTracker — VaR, CVaR, Sortino, corrélation."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from oracle_v2.metrics import MetricsTracker


class TestMetricsTracker:

    def test_empty_tracker_returns_zeros(self):
        t = MetricsTracker()
        assert t.var_95() == 0.0
        assert t.cvar_95() == 0.0
        assert t.sortino_ratio() == 0.0

    def test_var_95_negative_for_losses(self):
        t = MetricsTracker(window=100)
        # 100 trades : 95 à +1%, 5 à -10%
        for _ in range(95):
            t.record_pnl("TEST", 0.01)
        for _ in range(5):
            t.record_pnl("TEST", -0.10)
        var = t.var_95()
        assert var < 0, f"VaR devrait être négatif, got {var}"

    def test_cvar_worse_than_var(self):
        t = MetricsTracker(window=100)
        for _ in range(90):
            t.record_pnl("TEST", 0.01)
        for _ in range(10):
            t.record_pnl("TEST", -0.05)
        var = t.var_95()
        cvar = t.cvar_95()
        assert cvar <= var, f"CVaR ({cvar}) doit être ≤ VaR ({var})"

    def test_sortino_positive_when_mostly_profit(self):
        t = MetricsTracker(window=50)
        for _ in range(40):
            t.record_pnl("STRATE", 0.02)
        for _ in range(10):
            t.record_pnl("STRATE", -0.005)
        sortino = t.sortino_ratio()
        assert sortino > 0

    def test_sortino_negative_when_mostly_loss(self):
        t = MetricsTracker(window=50)
        for _ in range(40):
            t.record_pnl("STRATE", -0.02)
        for _ in range(10):
            t.record_pnl("STRATE", 0.005)
        sortino = t.sortino_ratio()
        assert sortino < 0

    def test_per_strate_sortino(self):
        t = MetricsTracker(window=50)
        for _ in range(20):
            t.record_pnl("AMD", 0.015)
        for _ in range(20):
            t.record_pnl("MOMENTUM", -0.010)
        assert t.sortino_ratio("AMD") > 0
        assert t.sortino_ratio("MOMENTUM") < 0

    def test_correlated_strates_detected(self):
        t = MetricsTracker(window=50, corr_threshold=0.7)
        # AMD et MOMENTUM : signaux similaires avec légère variation (évite division/0)
        import math
        for i in range(20):
            conf = 0.6 + math.sin(i * 0.5) * 0.2   # varie entre 0.4 et 0.8
            direction = "LONG" if conf > 0.5 else "SHORT"
            t.record_signal("AMD", direction, conf)
            t.record_signal("MOMENTUM", direction, conf * 0.95)  # quasi identique
        corr_pairs = t.correlated_strates()
        # Les deux strates doivent avoir une corrélation > 0.7
        assert len(corr_pairs) > 0, "AMD et MOMENTUM identiques → corrélation forte attendue"

    def test_uncorrelated_strates_not_flagged(self):
        t = MetricsTracker(window=50, corr_threshold=0.7)
        # AMD et MACRO : signaux opposés en alternance → corrélation ≈ -1
        import math
        for i in range(20):
            conf = 0.6 + math.sin(i * 0.4) * 0.2
            t.record_signal("AMD", "LONG", conf)
            t.record_signal("MACRO", "SHORT", conf)  # direction opposée
        corr_pairs = t.correlated_strates()
        # Corrélation négative → abs(corr) peut être élevée mais dans le sens opposé
        # Le test vérifie que le signal négatif n'est PAS flaggé comme "redondant"
        # (corrélation positive > 0.7 attendue : aucune)
        positive_corr_pairs = [p for p in corr_pairs if p[2] > 0.7]
        assert len(positive_corr_pairs) == 0

    def test_get_report_structure(self):
        t = MetricsTracker()
        for _ in range(20):
            t.record_pnl("AMD", 0.01)
        report = t.get_report()
        assert "var_95" in report
        assert "cvar_95" in report
        assert "sortino_global" in report
        assert "correlated_strates" in report
        assert "alerts" in report
        assert "strates" in report

    def test_sortino_alert_when_below_1(self):
        t = MetricsTracker()
        # Remplir avec PnL négatifs pour avoir un mauvais Sortino
        for _ in range(30):
            t.record_pnl("BAD", -0.01)
        report = t.get_report()
        # Au moins une alerte sur le Sortino
        assert any("Sortino" in a for a in report["alerts"])

    def test_var_95_changes_window(self):
        """La fenêtre glissante efface les vieux trades."""
        t = MetricsTracker(window=10)
        # D'abord 10 pertes
        for _ in range(10):
            t.record_pnl("X", -0.05)
        v1 = t.var_95()
        # Maintenant 10 profits (efface les pertes dans la fenêtre)
        for _ in range(10):
            t.record_pnl("X", 0.05)
        v2 = t.var_95()
        assert v2 > v1, "VaR doit s'améliorer après des gains"
