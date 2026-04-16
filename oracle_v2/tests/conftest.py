"""
Fixtures pytest globales pour oracle_v2.

tmp_oracle_db (autouse) — Redirige toute I/O SQLite vers un répertoire
temporaire isolé par test. Chaque test commence avec une base vierge.

Couvre : HebbianWeightManager, TradeRepository, OpenPositionRepository,
         RiskMetricsRepository, SafetyKernel (db_path).
"""
import pytest


@pytest.fixture(autouse=True)
def tmp_oracle_db(tmp_path):
    """
    Redirige TOUTES les repositories SQLite vers tmp_path.
    Garantit l'isolation totale entre tests.
    """
    import oracle_v2.brain.parliament as parl_mod
    import oracle_v2.db.repositories as repo_mod
    from oracle_v2.events import reset_event_bus

    test_db = str(tmp_path / "oracle_test.db")

    # ── HebbianWeightManager ────────────────────────────────────────
    _orig_hebbian = parl_mod.HebbianWeightManager.__init__

    def _hebbian_init(self, strate_names, db_path=None):
        _orig_hebbian(self, strate_names, db_path=test_db)

    parl_mod.HebbianWeightManager.__init__ = _hebbian_init

    # ── TradeRepository ─────────────────────────────────────────────
    _orig_trade = repo_mod.TradeRepository.__init__

    def _trade_init(self, db_path=None):
        _orig_trade(self, db_path=test_db)

    repo_mod.TradeRepository.__init__ = _trade_init

    # ── OpenPositionRepository ──────────────────────────────────────
    _orig_open_pos = repo_mod.OpenPositionRepository.__init__

    def _open_pos_init(self, db_path=None):
        _orig_open_pos(self, db_path=test_db)

    repo_mod.OpenPositionRepository.__init__ = _open_pos_init

    # ── RiskMetricsRepository ────────────────────────────────────────
    _orig_risk = repo_mod.RiskMetricsRepository.__init__

    def _risk_init(self, db_path=None):
        _orig_risk(self, db_path=test_db)

    repo_mod.RiskMetricsRepository.__init__ = _risk_init

    # ── Event Bus — réinitialiser entre chaque test ──────────────────
    reset_event_bus()

    yield

    # ── Restauration ────────────────────────────────────────────────
    parl_mod.HebbianWeightManager.__init__ = _orig_hebbian
    repo_mod.TradeRepository.__init__ = _orig_trade
    repo_mod.OpenPositionRepository.__init__ = _orig_open_pos
    repo_mod.RiskMetricsRepository.__init__ = _risk_init
    reset_event_bus()
