"""
Schémas SQLite pour ORACLE v2.
Toutes les tables sont créées avec IF NOT EXISTS — idempotent.
"""

CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           REAL    NOT NULL,
    symbol       TEXT    NOT NULL,
    direction    TEXT    NOT NULL,
    size_usdt    REAL,
    sl_pct       REAL,
    tp_pct       REAL,
    confidence   REAL,
    source_strate TEXT,
    mode         TEXT    DEFAULT 'paper',
    pnl_pct      REAL,
    closed_at    REAL
)
"""

CREATE_HEBBIAN = """
CREATE TABLE IF NOT EXISTS hebbian_weights (
    strate      TEXT PRIMARY KEY,
    weight      REAL NOT NULL DEFAULT 1.0,
    updated_at  REAL NOT NULL
)
"""

# Persistance des positions ouvertes du SafetyKernel (survit aux redémarrages)
CREATE_OPEN_POSITIONS = """
CREATE TABLE IF NOT EXISTS open_positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT    NOT NULL,
    direction    TEXT    NOT NULL,
    size_usdt    REAL    NOT NULL,
    leverage     REAL    NOT NULL DEFAULT 1.0,
    sl_pct       REAL,
    tp_pct       REAL,
    source_strate TEXT,
    confidence   REAL,
    opened_at    REAL    NOT NULL,
    mode         TEXT    DEFAULT 'paper'
)
"""

# Métriques de risque journalières (VaR/CVaR/Sortino)
CREATE_RISK_METRICS = """
CREATE TABLE IF NOT EXISTS risk_metrics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           REAL    NOT NULL,
    var_95       REAL,
    cvar_95      REAL,
    sortino      REAL,
    n_trades     INTEGER
)
"""
