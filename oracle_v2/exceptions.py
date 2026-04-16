"""
ORACLE v2 — Hiérarchie d'exceptions.

Policy de gestion des erreurs :
  - OracleException          : base, jamais levée directement
  - ConfigurationError       : fail-fast au démarrage (champs invalides)
  - ConnectorError           : loggé WARNING + système continue avec données stale
  - StrateError              : absorbé par safe_analyze() → NEUTRAL
  - SafetyViolation          : loggé WARNING + ordre annulé (jamais propagé)
  - BrainstemBlock           : loggé INFO (comportement normal de protection)
  - RepositoryError          : loggé WARNING + opération en mémoire en fallback
  - RateLimitError           : loggé WARNING + backoff automatique
"""
from __future__ import annotations


class OracleException(Exception):
    """Exception racine ORACLE v2."""


# ─── Configuration ────────────────────────────────────────────────────────────

class ConfigurationError(OracleException):
    """
    Levée au démarrage si la configuration est invalide.
    Fail-fast : le système refuse de démarrer plutôt que de crasher en prod.
    """


class MissingCredentialError(ConfigurationError):
    """Clé API ou secret absent alors qu'il est requis pour le mode actuel."""

    def __init__(self, field: str, mode: str = "live"):
        super().__init__(
            f"Credential '{field}' manquant. Requis pour le mode '{mode}'. "
            f"Définissez {field} dans votre fichier .env."
        )
        self.field = field
        self.mode = mode


# ─── Connecteurs ──────────────────────────────────────────────────────────────

class ConnectorError(OracleException):
    """Erreur de connecteur (réseau, auth, format). Non-fatale — système continue."""


class ConnectorUnavailableError(ConnectorError):
    """Le connecteur est hors ligne ou non initialisé."""

    def __init__(self, connector_name: str):
        super().__init__(f"Connecteur '{connector_name}' indisponible.")
        self.connector_name = connector_name


class RateLimitError(ConnectorError):
    """Rate limit API atteint. Backoff automatique requis."""

    def __init__(self, connector_name: str, retry_after: float = 60.0):
        super().__init__(
            f"Rate limit atteint sur '{connector_name}'. "
            f"Retry après {retry_after:.0f}s."
        )
        self.connector_name = connector_name
        self.retry_after = retry_after


# ─── Stratégies ───────────────────────────────────────────────────────────────

class StrateError(OracleException):
    """Erreur interne d'une strate. Absorbée par safe_analyze() → NEUTRAL."""

    def __init__(self, strate_name: str, cause: Exception):
        super().__init__(f"[{strate_name}] Erreur analyse: {cause}")
        self.strate_name = strate_name
        self.cause = cause


# ─── Safety ───────────────────────────────────────────────────────────────────

class SafetyViolation(OracleException):
    """
    Ordre rejeté par le SafetyKernel.
    Jamais propagée — loggée et ordre annulé silencieusement.
    """

    def __init__(self, symbol: str, reason: str):
        super().__init__(f"SafetyKernel REJECT {symbol}: {reason}")
        self.symbol = symbol
        self.reason = reason


class BrainstemBlock(OracleException):
    """
    Action bloquée par le Brainstem (circuit breaker).
    Comportement normal de protection — loggée INFO, pas WARNING.
    """

    def __init__(self, reason: str):
        super().__init__(f"Brainstem BLOCK: {reason}")
        self.reason = reason


# ─── Persistance ──────────────────────────────────────────────────────────────

class RepositoryError(OracleException):
    """
    Erreur SQLite. Non-fatale — opération en mémoire en fallback.
    Loggée WARNING avec traceback pour investigation post-mortem.
    """

    def __init__(self, operation: str, cause: Exception):
        super().__init__(f"Repository '{operation}' échoué: {cause}")
        self.operation = operation
        self.cause = cause
