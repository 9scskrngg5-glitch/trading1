"""Tests SafetyKernel v2 — notionnel global, persistance DB, réconciliation."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from oracle_v2.brain.safety_kernel import SafetyKernel, Order


def make_order(**kwargs) -> Order:
    defaults = dict(
        symbol="BTCUSDT", direction="LONG",
        size_usdt=500.0, leverage=1.0,
        sl_pct=0.010, tp_pct=0.025,
        source_strate="PARLIAMENT", confidence=0.75,
        mode="paper",
    )
    defaults.update(kwargs)
    return Order(**defaults)


class TestSafetyKernelV2:

    # ── Plafonnement notionnel global ─────────────────────────────────

    def test_rejects_when_global_notional_full(self):
        """Si 30% du capital est déjà déployé, refuser un nouvel ordre."""
        sk = SafetyKernel(
            max_position_pct=0.50,      # large pour ne pas bloquer sur size
            max_open_positions=10,       # large
            max_total_notional_pct=0.30,
        )
        capital = 10_000.0
        # Ouvrir une position de 3000$ (30% du capital × 1x levier)
        existing = make_order(size_usdt=3_000.0, leverage=1.0)
        sk.register_open(existing)
        # Essayer d'en ouvrir une autre
        new_order = make_order(size_usdt=100.0, leverage=1.0)
        report = sk.validate(new_order, capital)
        assert not report.cleared
        assert "GLOBAL_NOTIONAL_EXCEEDED" in report.reason

    def test_adjusts_size_to_fit_remaining_notional(self):
        """Si le notionnel restant est insuffisant, ajuster la taille."""
        sk = SafetyKernel(
            max_position_pct=1.0,
            max_open_positions=10,
            max_total_notional_pct=0.30,
        )
        capital = 10_000.0
        # 2000$ déjà déployés (20%)
        sk.register_open(make_order(size_usdt=2_000.0, leverage=1.0))
        # Essayer 2000$ supplémentaires → dépasse 30% (max=3000$, reste=1000$)
        order = make_order(size_usdt=2_000.0, leverage=1.0)
        report = sk.validate(order, capital)
        assert report.cleared
        assert report.adjusted_size is not None
        assert report.adjusted_size <= 1_000.0 + 0.01   # reste max ~1000$

    def test_notional_usage_report(self):
        sk = SafetyKernel(max_total_notional_pct=0.30)
        sk.register_open(make_order(size_usdt=1_000.0, leverage=2.0))
        usage = sk.get_notional_usage(capital=10_000.0)
        assert usage["total_notional"] == 2_000.0      # 1000 × 2x
        assert usage["max_notional"] == 3_000.0        # 10000 × 30%
        assert usage["usage_pct"] == pytest.approx(2/3, abs=0.01)

    def test_leverage_multiplies_notional(self):
        """Leverage 2x compte double dans le notionnel."""
        sk = SafetyKernel(max_total_notional_pct=0.30, max_open_positions=10)
        capital = 10_000.0
        # 1500$ × 2x = 3000$ = 30% → notionnel saturé
        sk.register_open(make_order(size_usdt=1_500.0, leverage=2.0))
        order = make_order(size_usdt=100.0, leverage=1.0)
        report = sk.validate(order, capital)
        assert not report.cleared
        assert "GLOBAL_NOTIONAL_EXCEEDED" in report.reason

    # ── Persistance DB ────────────────────────────────────────────────

    def test_positions_persisted_and_reloaded(self, tmp_path):
        """Les positions doivent survivre à la recréation du SafetyKernel."""
        db_path = str(tmp_path / "test.db")
        sk1 = SafetyKernel(db_path=db_path)
        order = make_order(symbol="ETHUSDT", size_usdt=500.0)
        sk1.register_open(order)
        assert len(sk1.open_positions) == 1

        # Recréer un SafetyKernel depuis la même DB
        sk2 = SafetyKernel(db_path=db_path)
        assert len(sk2.open_positions) == 1
        assert sk2.open_positions[0].symbol == "ETHUSDT"

    def test_position_removed_from_db_on_close(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        sk1 = SafetyKernel(db_path=db_path)
        sk1.register_open(make_order(symbol="BTCUSDT"))
        sk1.register_close("BTCUSDT")

        sk2 = SafetyKernel(db_path=db_path)
        assert len(sk2.open_positions) == 0

    # ── Réconciliation ────────────────────────────────────────────────

    def test_reconcile_removes_stale_positions(self):
        sk = SafetyKernel()
        sk.register_open(make_order(symbol="BTCUSDT"))
        sk.register_open(make_order(symbol="ETHUSDT"))
        # L'exchange ne connaît que BTCUSDT
        sk.reconcile(live_symbols=["BTCUSDT"])
        assert len(sk.open_positions) == 1
        assert sk.open_positions[0].symbol == "BTCUSDT"

    def test_reconcile_no_change_when_all_match(self):
        sk = SafetyKernel()
        sk.register_open(make_order(symbol="BTCUSDT"))
        sk.reconcile(live_symbols=["BTCUSDT"])
        assert len(sk.open_positions) == 1

    # ── Bounds SL larges (guard-rails) ────────────────────────────────

    def test_rejects_sl_below_hard_floor(self):
        sk = SafetyKernel(min_sl_pct=0.003)
        order = make_order(sl_pct=0.001)
        report = sk.validate(order, capital=10_000)
        assert not report.cleared
        assert "SL_TOO_TIGHT" in report.reason

    def test_allows_sl_up_to_5pct(self):
        """Avec les nouveaux guard-rails larges, 4% doit passer."""
        sk = SafetyKernel(max_sl_pct=0.05)
        order = make_order(sl_pct=0.04)
        report = sk.validate(order, capital=10_000)
        assert report.cleared
