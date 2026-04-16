"""
Configuration centralisée ORACLE v2 — Validation Pydantic.

Chargement par priorité :
  1. Variables d'environnement
  2. Fichier .env (si python-dotenv installé)
  3. Valeurs par défaut ci-dessous

Validation :
  - Pydantic BaseSettings (recommandé) : validation au démarrage, fail-fast
  - Fallback dataclass si pydantic non installé : avertissement, pas de validation
  - validate_live_credentials() : bloque si API keys absentes en mode live

Installation recommandée : pip install pydantic pydantic-settings python-dotenv
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("ORACLE.Config")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── Defaults partagés (source de vérité unique) ─────────────────────────────
# Modifier ici, une seule fois, pour changer une valeur par défaut.

_D = {
    # Binance
    "BINANCE_API_KEY":       "",
    "BINANCE_SECRET":        "",
    "BINANCE_TESTNET":       True,
    # Capital.com
    "CAPITAL_API_KEY":       "",
    "CAPITAL_PASSWORD":      "",
    # Telegram
    "TELEGRAM_TOKEN":        "",
    "TELEGRAM_CHAT_ID":      "",
    # Polymarket — lecture publique (Gamma API, pas de clé)
    "POLYMARKET_MIN_EDGE":   0.05,
    "POLYMARKET_MIN_VOLUME": 25_000.0,
    "POLYMARKET_KELLY_MAX":  0.30,
    # Polymarket CLOB — trading actif (optionnel)
    "POLYMARKET_PRIVATE_KEY":    "",
    "POLYMARKET_API_KEY":        "",
    "POLYMARKET_API_SECRET":     "",
    "POLYMARKET_API_PASSPHRASE": "",
    "POLYMARKET_PROXY_WALLET":   "",
    # BTC Latency Arbitrage
    "BTC_LATENCY_ARB_ENABLED":    True,
    "BTC_LATENCY_ARB_INTERVAL":   30,
    "BTC_LATENCY_ARB_MIN_EDGE":   0.05,
    "BTC_LATENCY_ARB_MIN_VOLUME": 10_000.0,
    "BTC_LATENCY_ARB_KELLY_MAX":  0.25,
    "BTC_SIGMA_ANNUAL":           0.85,
    # Trading
    "TRADING_PAIRS":         ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    "BTC_FOCUS_SYMBOL":      "BTCUSDT",
    "PRIMARY_TIMEFRAME":     "5m",
    "SECONDARY_TIMEFRAMES":  ["15m", "1h"],
    "MAX_LEVERAGE":          2.0,
    "MAX_POSITION_SIZE_PCT": 0.10,
    "MAX_TOTAL_NOTIONAL_PCT": 0.30,
    # Risk management
    "MAX_DAILY_DRAWDOWN":      0.02,
    "MAX_CONSECUTIVE_LOSSES":  3,
    "MAX_SESSION_TRADES":      8,
    "MAX_OPEN_POSITIONS":      3,
    # SL/TP dynamique ATR-based
    "ATR_SL_MULTIPLIER":  1.5,
    "TARGET_RISK_PCT":    0.01,
    "MIN_SL_PCT":         0.003,
    "MAX_SL_PCT":         0.05,
    "DEFAULT_TP_RATIO":   2.5,
    # Brainstem adaptatif
    "ADAPTIVE_DRAWDOWN":       True,
    "HIGH_EDGE_THRESHOLD":     0.75,
    "HIGH_EDGE_MAX_DRAWDOWN":  0.04,
    # Parliament
    "WORKING_MEMORY_WINDOW":    3,
    "WORKING_MEMORY_CONSENSUS": 2,
    "WORKING_MEMORY_TTL":       300.0,
    "PARLIAMENT_QUORUM":        0.60,
    # Twitter / X
    "TWITTER_BEARER_TOKEN": "",
    "TWITTER_ENABLED":      True,
    "TWITTER_CACHE_TTL":    300,
    "TWITTER_MIN_TWEETS":   10,
    "TWITTER_MAX_CONF":     0.70,
    # LLM / Narrator
    "ANTHROPIC_API_KEY":  "",
    "FREE_GPT4_URL":      "http://127.0.0.1:5500",
    "NARRATOR_ENABLED":   True,
    "NARRATOR_LLM":       True,
    # Mode & Timezone
    "MODE":     "paper",
    "TIMEZONE": "Pacific/Tahiti",
}

# ─── Détection Pydantic ───────────────────────────────────────────────────────

_HAS_PYDANTIC = False
_PYDANTIC_V2  = False

try:
    try:
        from pydantic_settings import BaseSettings
        from pydantic import field_validator, model_validator
        _HAS_PYDANTIC = True
        _PYDANTIC_V2  = True
    except ImportError:
        from pydantic import BaseSettings, validator  # type: ignore
        _HAS_PYDANTIC = True
except ImportError:
    pass


# ─── Config Pydantic (recommandée) ────────────────────────────────────────────

if _HAS_PYDANTIC:

    class OracleConfig(BaseSettings):  # type: ignore
        """
        Configuration ORACLE v2 avec validation Pydantic.
        Chargement automatique depuis .env et variables d'environnement.
        """

        # ── Binance ──────────────────────────────────────────────────────
        BINANCE_API_KEY:  str  = _D["BINANCE_API_KEY"]
        BINANCE_SECRET:   str  = _D["BINANCE_SECRET"]
        BINANCE_TESTNET:  bool = _D["BINANCE_TESTNET"]

        # ── Capital.com ───────────────────────────────────────────────────
        CAPITAL_API_KEY:  str = _D["CAPITAL_API_KEY"]
        CAPITAL_PASSWORD: str = _D["CAPITAL_PASSWORD"]

        # ── Telegram ──────────────────────────────────────────────────────
        TELEGRAM_TOKEN:   str = _D["TELEGRAM_TOKEN"]
        TELEGRAM_CHAT_ID: str = _D["TELEGRAM_CHAT_ID"]

        # ── Polymarket (lecture + CLOB) ───────────────────────────────────
        POLYMARKET_MIN_EDGE:      float = _D["POLYMARKET_MIN_EDGE"]
        POLYMARKET_MIN_VOLUME:    float = _D["POLYMARKET_MIN_VOLUME"]
        POLYMARKET_KELLY_MAX:     float = _D["POLYMARKET_KELLY_MAX"]
        POLYMARKET_PRIVATE_KEY:   str   = _D["POLYMARKET_PRIVATE_KEY"]
        POLYMARKET_API_KEY:       str   = _D["POLYMARKET_API_KEY"]
        POLYMARKET_API_SECRET:    str   = _D["POLYMARKET_API_SECRET"]
        POLYMARKET_API_PASSPHRASE: str  = _D["POLYMARKET_API_PASSPHRASE"]
        POLYMARKET_PROXY_WALLET:  str   = _D["POLYMARKET_PROXY_WALLET"]

        # ── BTC Latency Arbitrage ─────────────────────────────────────────
        BTC_LATENCY_ARB_ENABLED:    bool  = _D["BTC_LATENCY_ARB_ENABLED"]
        BTC_LATENCY_ARB_INTERVAL:   int   = _D["BTC_LATENCY_ARB_INTERVAL"]
        BTC_LATENCY_ARB_MIN_EDGE:   float = _D["BTC_LATENCY_ARB_MIN_EDGE"]
        BTC_LATENCY_ARB_MIN_VOLUME: float = _D["BTC_LATENCY_ARB_MIN_VOLUME"]
        BTC_LATENCY_ARB_KELLY_MAX:  float = _D["BTC_LATENCY_ARB_KELLY_MAX"]
        BTC_SIGMA_ANNUAL:           float = _D["BTC_SIGMA_ANNUAL"]

        # ── Trading ───────────────────────────────────────────────────────
        TRADING_PAIRS:          list  = _D["TRADING_PAIRS"]
        BTC_FOCUS_SYMBOL:       str   = _D["BTC_FOCUS_SYMBOL"]
        PRIMARY_TIMEFRAME:      str   = _D["PRIMARY_TIMEFRAME"]
        SECONDARY_TIMEFRAMES:   list  = _D["SECONDARY_TIMEFRAMES"]
        MAX_LEVERAGE:           float = _D["MAX_LEVERAGE"]
        MAX_POSITION_SIZE_PCT:  float = _D["MAX_POSITION_SIZE_PCT"]
        MAX_TOTAL_NOTIONAL_PCT: float = _D["MAX_TOTAL_NOTIONAL_PCT"]

        # ── Risk management ───────────────────────────────────────────────
        MAX_DAILY_DRAWDOWN:     float = _D["MAX_DAILY_DRAWDOWN"]
        MAX_CONSECUTIVE_LOSSES: int   = _D["MAX_CONSECUTIVE_LOSSES"]
        MAX_SESSION_TRADES:     int   = _D["MAX_SESSION_TRADES"]
        MAX_OPEN_POSITIONS:     int   = _D["MAX_OPEN_POSITIONS"]

        # ── SL/TP dynamique ────────────────────────────────────────────────
        ATR_SL_MULTIPLIER: float = _D["ATR_SL_MULTIPLIER"]
        TARGET_RISK_PCT:   float = _D["TARGET_RISK_PCT"]
        MIN_SL_PCT:        float = _D["MIN_SL_PCT"]
        MAX_SL_PCT:        float = _D["MAX_SL_PCT"]
        DEFAULT_TP_RATIO:  float = _D["DEFAULT_TP_RATIO"]

        # ── Brainstem adaptatif ────────────────────────────────────────────
        ADAPTIVE_DRAWDOWN:      bool  = _D["ADAPTIVE_DRAWDOWN"]
        HIGH_EDGE_THRESHOLD:    float = _D["HIGH_EDGE_THRESHOLD"]
        HIGH_EDGE_MAX_DRAWDOWN: float = _D["HIGH_EDGE_MAX_DRAWDOWN"]

        # ── Parliament ─────────────────────────────────────────────────────
        WORKING_MEMORY_WINDOW:    int   = _D["WORKING_MEMORY_WINDOW"]
        WORKING_MEMORY_CONSENSUS: int   = _D["WORKING_MEMORY_CONSENSUS"]
        WORKING_MEMORY_TTL:       float = _D["WORKING_MEMORY_TTL"]
        PARLIAMENT_QUORUM:        float = _D["PARLIAMENT_QUORUM"]

        # ── Twitter / X ────────────────────────────────────────────────────
        TWITTER_BEARER_TOKEN: str   = _D["TWITTER_BEARER_TOKEN"]
        TWITTER_ENABLED:      bool  = _D["TWITTER_ENABLED"]
        TWITTER_CACHE_TTL:    int   = _D["TWITTER_CACHE_TTL"]
        TWITTER_MIN_TWEETS:   int   = _D["TWITTER_MIN_TWEETS"]
        TWITTER_MAX_CONF:     float = _D["TWITTER_MAX_CONF"]

        # ── LLM / Narrator ─────────────────────────────────────────────────
        ANTHROPIC_API_KEY: str  = _D["ANTHROPIC_API_KEY"]
        FREE_GPT4_URL:     str  = _D["FREE_GPT4_URL"]
        NARRATOR_ENABLED:  bool = _D["NARRATOR_ENABLED"]
        NARRATOR_LLM:      bool = _D["NARRATOR_LLM"]

        # ── Mode & Timezone ────────────────────────────────────────────────
        MODE:     str = _D["MODE"]
        TIMEZONE: str = _D["TIMEZONE"]

        def validate_live_credentials(self) -> None:
            """
            Vérifie les credentials requis pour le mode live.
            Appelé par OracleSystem.run() avant de démarrer.
            Lève une exception si un champ critique est absent ou invalide.
            """
            from exceptions import MissingCredentialError, ConfigurationError
            if self.MODE == "live":
                if not self.BINANCE_API_KEY:
                    raise MissingCredentialError("BINANCE_API_KEY", mode="live")
                if not self.BINANCE_SECRET:
                    raise MissingCredentialError("BINANCE_SECRET", mode="live")
            if not (0 < self.MAX_LEVERAGE <= 10):
                raise ConfigurationError(
                    f"MAX_LEVERAGE={self.MAX_LEVERAGE} invalide (0 < x ≤ 10)"
                )
            if not (0 < self.MAX_POSITION_SIZE_PCT <= 1.0):
                raise ConfigurationError(
                    f"MAX_POSITION_SIZE_PCT={self.MAX_POSITION_SIZE_PCT} invalide"
                )
            if not (0 < self.MAX_DAILY_DRAWDOWN <= 0.5):
                raise ConfigurationError(
                    f"MAX_DAILY_DRAWDOWN={self.MAX_DAILY_DRAWDOWN} invalide (0 < x ≤ 0.5)"
                )
            if self.ATR_SL_MULTIPLIER <= 0:
                raise ConfigurationError(
                    f"ATR_SL_MULTIPLIER={self.ATR_SL_MULTIPLIER} doit être > 0"
                )

        class Config:
            env_file = ".env"
            case_sensitive = True


# ─── Fallback dataclass (si pydantic absent) ─────────────────────────────────

else:
    logger.warning(
        "pydantic / pydantic-settings non installé — validation désactivée.\n"
        "Installez : pip install pydantic pydantic-settings python-dotenv"
    )
    from dataclasses import dataclass, field as _field

    def _g(key: str, default=None):
        """Lit une variable d'env ; renvoie le default si absente."""
        return os.getenv(key, default if default is not None else _D.get(key, ""))

    @dataclass
    class OracleConfig:  # type: ignore
        BINANCE_API_KEY:       str   = _field(default_factory=lambda: _g("BINANCE_API_KEY"))
        BINANCE_SECRET:        str   = _field(default_factory=lambda: _g("BINANCE_SECRET"))
        BINANCE_TESTNET:       bool  = _D["BINANCE_TESTNET"]
        CAPITAL_API_KEY:       str   = _field(default_factory=lambda: _g("CAPITAL_API_KEY"))
        CAPITAL_PASSWORD:      str   = _field(default_factory=lambda: _g("CAPITAL_PASSWORD"))
        TELEGRAM_TOKEN:        str   = _field(default_factory=lambda: _g("TELEGRAM_TOKEN"))
        TELEGRAM_CHAT_ID:      str   = _field(default_factory=lambda: _g("TELEGRAM_CHAT_ID"))
        POLYMARKET_MIN_EDGE:   float = _D["POLYMARKET_MIN_EDGE"]
        POLYMARKET_MIN_VOLUME: float = _D["POLYMARKET_MIN_VOLUME"]
        POLYMARKET_KELLY_MAX:  float = _D["POLYMARKET_KELLY_MAX"]
        POLYMARKET_PRIVATE_KEY:    str = _field(default_factory=lambda: _g("POLYMARKET_PRIVATE_KEY"))
        POLYMARKET_API_KEY:        str = _field(default_factory=lambda: _g("POLYMARKET_API_KEY"))
        POLYMARKET_API_SECRET:     str = _field(default_factory=lambda: _g("POLYMARKET_API_SECRET"))
        POLYMARKET_API_PASSPHRASE: str = _field(default_factory=lambda: _g("POLYMARKET_API_PASSPHRASE"))
        POLYMARKET_PROXY_WALLET:   str = _field(default_factory=lambda: _g("POLYMARKET_PROXY_WALLET"))
        BTC_LATENCY_ARB_ENABLED:    bool  = _D["BTC_LATENCY_ARB_ENABLED"]
        BTC_LATENCY_ARB_INTERVAL:   int   = _D["BTC_LATENCY_ARB_INTERVAL"]
        BTC_LATENCY_ARB_MIN_EDGE:   float = _D["BTC_LATENCY_ARB_MIN_EDGE"]
        BTC_LATENCY_ARB_MIN_VOLUME: float = _D["BTC_LATENCY_ARB_MIN_VOLUME"]
        BTC_LATENCY_ARB_KELLY_MAX:  float = _D["BTC_LATENCY_ARB_KELLY_MAX"]
        BTC_SIGMA_ANNUAL:           float = _D["BTC_SIGMA_ANNUAL"]
        TRADING_PAIRS:         list  = _field(default_factory=lambda: list(_D["TRADING_PAIRS"]))
        BTC_FOCUS_SYMBOL:      str   = _D["BTC_FOCUS_SYMBOL"]
        PRIMARY_TIMEFRAME:     str   = _D["PRIMARY_TIMEFRAME"]
        SECONDARY_TIMEFRAMES:  list  = _field(default_factory=lambda: list(_D["SECONDARY_TIMEFRAMES"]))
        MAX_LEVERAGE:          float = _D["MAX_LEVERAGE"]
        MAX_POSITION_SIZE_PCT: float = _D["MAX_POSITION_SIZE_PCT"]
        MAX_TOTAL_NOTIONAL_PCT: float = _D["MAX_TOTAL_NOTIONAL_PCT"]
        MAX_DAILY_DRAWDOWN:     float = _D["MAX_DAILY_DRAWDOWN"]
        MAX_CONSECUTIVE_LOSSES: int   = _D["MAX_CONSECUTIVE_LOSSES"]
        MAX_SESSION_TRADES:     int   = _D["MAX_SESSION_TRADES"]
        MAX_OPEN_POSITIONS:     int   = _D["MAX_OPEN_POSITIONS"]
        ATR_SL_MULTIPLIER:     float = _D["ATR_SL_MULTIPLIER"]
        TARGET_RISK_PCT:       float = _D["TARGET_RISK_PCT"]
        MIN_SL_PCT:            float = _D["MIN_SL_PCT"]
        MAX_SL_PCT:            float = _D["MAX_SL_PCT"]
        DEFAULT_TP_RATIO:      float = _D["DEFAULT_TP_RATIO"]
        ADAPTIVE_DRAWDOWN:      bool  = _D["ADAPTIVE_DRAWDOWN"]
        HIGH_EDGE_THRESHOLD:    float = _D["HIGH_EDGE_THRESHOLD"]
        HIGH_EDGE_MAX_DRAWDOWN: float = _D["HIGH_EDGE_MAX_DRAWDOWN"]
        WORKING_MEMORY_WINDOW:    int   = _D["WORKING_MEMORY_WINDOW"]
        WORKING_MEMORY_CONSENSUS: int   = _D["WORKING_MEMORY_CONSENSUS"]
        WORKING_MEMORY_TTL:       float = _D["WORKING_MEMORY_TTL"]
        PARLIAMENT_QUORUM:        float = _D["PARLIAMENT_QUORUM"]
        TWITTER_BEARER_TOKEN: str   = _field(default_factory=lambda: _g("TWITTER_BEARER_TOKEN"))
        TWITTER_ENABLED:      bool  = _D["TWITTER_ENABLED"]
        TWITTER_CACHE_TTL:    int   = _D["TWITTER_CACHE_TTL"]
        TWITTER_MIN_TWEETS:   int   = _D["TWITTER_MIN_TWEETS"]
        TWITTER_MAX_CONF:     float = _D["TWITTER_MAX_CONF"]
        ANTHROPIC_API_KEY: str  = _field(default_factory=lambda: _g("ANTHROPIC_API_KEY"))
        FREE_GPT4_URL:     str  = _field(default_factory=lambda: _g("FREE_GPT4_URL", "http://127.0.0.1:5500"))
        NARRATOR_ENABLED:  bool = _D["NARRATOR_ENABLED"]
        NARRATOR_LLM:      bool = _D["NARRATOR_LLM"]
        MODE:     str = _field(default_factory=lambda: _g("ORACLE_MODE", "paper"))
        TIMEZONE: str = _D["TIMEZONE"]

        def validate_live_credentials(self) -> None:
            from exceptions import MissingCredentialError
            if self.MODE == "live":
                if not self.BINANCE_API_KEY:
                    raise MissingCredentialError("BINANCE_API_KEY", mode="live")
                if not self.BINANCE_SECRET:
                    raise MissingCredentialError("BINANCE_SECRET", mode="live")


# ─── Singleton global ─────────────────────────────────────────────────────────

try:
    config: OracleConfig = OracleConfig()
except Exception as e:
    logger.error(f"Erreur création config: {e}")
    raise
