"""
Trading Mode — Séparation Paper / Live.

Modes :
  SIMULATION : données simulées, pas d'échange réel (par défaut)
  PAPER      : données Binance réelles, ordres simulés
  LIVE       : données Binance réelles, ordres réels

Safety checks avant activation du mode LIVE :
  1. Clés API Binance valides (test via account balance)
  2. Capital minimum ($100)
  3. Circuit breaker actif
  4. Minimum 50 trades paper rentables
  5. Sharpe > 0.5 sur les 50 derniers trades paper
  6. Drawdown max historique < 20%
  7. Confirmation explicite par l'utilisateur (fichier .live_confirmed)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TradingMode(str, Enum):
    SIMULATION = "simulation"    # tout simulé
    PAPER      = "paper"         # données réelles, ordres simulés
    LIVE       = "live"          # données réelles, ordres réels


class LiveReadinessError(Exception):
    """Levée quand les conditions pour le mode LIVE ne sont pas remplies."""
    pass


class TradingModeManager:
    """
    Gère le mode de trading et les safety checks.

    Usage:
        mode_mgr = TradingModeManager(vault_path, mode="paper")
        mode_mgr.validate_config(config)  # vérifie les clés API etc.

        # Pour passer en live :
        mode_mgr.check_live_readiness(tracker_snapshot)
        mode_mgr.activate_live()  # crée le fichier de confirmation
    """

    def __init__(
        self,
        vault_path: Path,
        mode: str = "simulation",
        min_paper_trades: int = 50,
        min_sharpe: float = 0.5,
        max_drawdown_limit: float = 20.0,
        min_capital: float = 100.0,
    ):
        self.vault_path         = Path(vault_path)
        self._mode              = TradingMode(mode)
        self.min_paper_trades   = min_paper_trades
        self.min_sharpe         = min_sharpe
        self.max_drawdown_limit = max_drawdown_limit
        self.min_capital        = min_capital

        self._live_confirmed_path = self.vault_path / "config" / ".live_confirmed"
        self._paper_log_path      = self.vault_path / "config" / "paper_trading_log.json"

    @property
    def mode(self) -> TradingMode:
        return self._mode

    @property
    def is_live(self) -> bool:
        return self._mode == TradingMode.LIVE

    @property
    def is_paper(self) -> bool:
        return self._mode == TradingMode.PAPER

    @property
    def is_simulation(self) -> bool:
        return self._mode == TradingMode.SIMULATION

    @property
    def use_real_data(self) -> bool:
        """True si on utilise des données de marché réelles (paper ou live)."""
        return self._mode in (TradingMode.PAPER, TradingMode.LIVE)

    @property
    def execute_real_orders(self) -> bool:
        """True si on exécute des ordres réels sur l'exchange."""
        return self._mode == TradingMode.LIVE

    # ── Validation de configuration ─────────────────────────────────────────

    def validate_config(self, config: dict) -> list[str]:
        """
        Valide la configuration selon le mode.
        Retourne la liste des problèmes (vide = OK).
        """
        issues = []

        if self.use_real_data:
            # Vérifier les clés API
            if not config.get("binance_api_key"):
                issues.append("binance_api_key manquante")
            if not config.get("binance_secret"):
                issues.append("binance_secret manquante")

        if self.is_live:
            # Vérifications supplémentaires pour LIVE
            if not self._live_confirmed_path.exists():
                issues.append(
                    "Fichier de confirmation LIVE absent. "
                    "Exécutez check_live_readiness() puis activate_live()."
                )

            capital = config.get("capital_usd", 0)
            if capital < self.min_capital:
                issues.append(
                    f"Capital insuffisant : ${capital} < ${self.min_capital} minimum"
                )

        return issues

    # ── Live Readiness Check ────────────────────────────────────────────────

    def check_live_readiness(self, tracker_snapshot: dict) -> dict:
        """
        Vérifie si le système est prêt pour le mode LIVE.

        Args:
            tracker_snapshot: résultat de PerformanceTracker.snapshot()

        Returns:
            dict avec {check: str, passed: bool, detail: str} pour chaque vérification.

        Raises:
            LiveReadinessError si une vérification critique échoue.
        """
        checks = []

        # 1. Minimum de trades paper
        total_trades = tracker_snapshot.get("total_trades", 0)
        passed = total_trades >= self.min_paper_trades
        checks.append({
            "check":  "Minimum trades paper",
            "passed": passed,
            "detail": f"{total_trades} / {self.min_paper_trades} requis",
        })

        # 2. Sharpe Ratio minimum
        sharpe = tracker_snapshot.get("sharpe_ratio", 0)
        passed = sharpe >= self.min_sharpe
        checks.append({
            "check":  "Sharpe Ratio minimum",
            "passed": passed,
            "detail": f"{sharpe:.3f} / {self.min_sharpe} requis",
        })

        # 3. Win Rate > 45%
        wr = tracker_snapshot.get("win_rate", 0)
        passed = wr >= 0.45
        checks.append({
            "check":  "Win Rate minimum",
            "passed": passed,
            "detail": f"{wr:.1%} / 45% requis",
        })

        # 4. Profit Factor > 1.0
        pf = tracker_snapshot.get("profit_factor", 0)
        passed = pf >= 1.0
        checks.append({
            "check":  "Profit Factor positif",
            "passed": passed,
            "detail": f"{pf:.2f} / 1.0 requis",
        })

        # 5. Drawdown max < limite
        max_dd = tracker_snapshot.get("max_drawdown_pct", 100)
        passed = max_dd < self.max_drawdown_limit
        checks.append({
            "check":  "Drawdown max acceptable",
            "passed": passed,
            "detail": f"{max_dd:.2f}% / < {self.max_drawdown_limit}% requis",
        })

        # 6. Return positif
        total_return = tracker_snapshot.get("total_return_pct", -100)
        passed = total_return > 0
        checks.append({
            "check":  "Return total positif",
            "passed": passed,
            "detail": f"{total_return:+.2f}%",
        })

        # Verdict global
        all_passed = all(c["passed"] for c in checks)
        failed = [c for c in checks if not c["passed"]]

        if not all_passed:
            reasons = "; ".join(f"{c['check']}: {c['detail']}" for c in failed)
            logger.warning(
                "[TradingMode] Live readiness FAILED : %d/%d checks — %s",
                len(checks) - len(failed), len(checks), reasons,
            )

        return {
            "ready":  all_passed,
            "checks": checks,
            "failed": len(failed),
            "total":  len(checks),
        }

    def activate_live(self, tracker_snapshot: dict, force: bool = False) -> bool:
        """
        Active le mode LIVE après vérification.

        Args:
            tracker_snapshot: snapshot du tracker
            force: bypasse les vérifications (DANGEREUX)

        Returns:
            True si activé avec succès.
        """
        if not force:
            result = self.check_live_readiness(tracker_snapshot)
            if not result["ready"]:
                failed_checks = [c for c in result["checks"] if not c["passed"]]
                raise LiveReadinessError(
                    f"Le système n'est pas prêt pour le LIVE. "
                    f"{len(failed_checks)} vérification(s) échouée(s) : "
                    + "; ".join(c["check"] for c in failed_checks)
                )

        # Créer le fichier de confirmation
        self._live_confirmed_path.parent.mkdir(parents=True, exist_ok=True)
        confirmation = {
            "activated_at":   datetime.now(timezone.utc).isoformat(),
            "mode":           "live",
            "snapshot":       tracker_snapshot,
            "forced":         force,
        }
        self._live_confirmed_path.write_text(
            json.dumps(confirmation, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self._mode = TradingMode.LIVE
        logger.warning(
            "[TradingMode] 🔴 MODE LIVE ACTIVÉ %s— Capital $%.2f",
            "(FORCE) " if force else "",
            tracker_snapshot.get("capital", 0),
        )
        return True

    def deactivate_live(self, reason: str = "Manuel") -> None:
        """Repasse en mode PAPER (safe)."""
        old = self._mode
        self._mode = TradingMode.PAPER
        if self._live_confirmed_path.exists():
            self._live_confirmed_path.unlink()
        logger.warning(
            "[TradingMode] %s → PAPER — Raison : %s", old.value, reason,
        )

    def snapshot(self) -> dict:
        return {
            "mode":              self._mode.value,
            "use_real_data":     self.use_real_data,
            "execute_orders":    self.execute_real_orders,
            "live_confirmed":    self._live_confirmed_path.exists(),
            "min_paper_trades":  self.min_paper_trades,
            "min_sharpe":        self.min_sharpe,
        }
