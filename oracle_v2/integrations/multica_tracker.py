"""
MulticaTracker — Inspiration architecturale de multica-ai.

Multica est un gestionnaire de tâches AI-native (comme Linear mais avec des agents).
Ici, on applique ses patterns à ORACLE v2 :
  - Chaque décision du Parlement → "Issue" avec statut et assignee
  - Chaque trade → "Activity" loggée
  - Les agents (strates) sont des "Agent Assignees" avec performance tracking

Source : https://github.com/multica-ai/multica
"""
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("ORACLE.MulticaTracker")

TAHITI_TZ = timezone(timedelta(hours=-10))


# ─── Multica-inspired data model ─────────────────────────────────────────────

@dataclass
class TradeIssue:
    """
    Inspiré du modèle Issue de Multica.
    Représente une décision de trading du Parlement.
    """
    issue_id: str
    symbol: str
    direction: str                   # LONG / SHORT / NEUTRAL
    status: str = "open"             # open / in_progress / closed / rejected
    created_at: float = field(default_factory=time.time)
    closed_at: Optional[float] = None
    assignee_type: str = "agent"     # agent (strate) ou system
    assignee_id: str = ""            # nom de la strate principale
    confidence: float = 0.0
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl_pct: Optional[float] = None
    votes: List[str] = field(default_factory=list)
    reasoning: str = ""
    labels: List[str] = field(default_factory=list)  # ["polymarket", "hebbian", "high-confidence"]


@dataclass
class ActivityEntry:
    """Log d'activité — inspiré de multica Activity."""
    activity_id: str
    issue_id: str
    actor: str           # "brainstem" | "safety_kernel" | "parliament" | "strate:xxx"
    action: str          # "created" | "updated" | "closed" | "blocked" | "trade_executed"
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


# ─── MulticaTracker ──────────────────────────────────────────────────────────

class MulticaTracker:
    """
    Gestionnaire de tâches / issues inspiré de Multica pour ORACLE v2.

    Persiste les décisions dans un fichier JSONL pour audit.
    Multi-tenant via workspace_id (ici = mode : paper / live).
    """

    def __init__(self, vault_dir: str = "vault", workspace_id: str = "oracle"):
        self.workspace_id = workspace_id
        self.vault_path = Path(vault_dir)
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self._issues_file = self.vault_path / f"issues_{workspace_id}.jsonl"
        self._activity_file = self.vault_path / f"activity_{workspace_id}.jsonl"
        self._issues: dict[str, TradeIssue] = {}
        self._counter = 0
        self._load()
        logger.info(f"MulticaTracker: workspace={workspace_id}, {len(self._issues)} issues chargées")

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._issues_file.exists():
            return
        try:
            with open(self._issues_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    issue = TradeIssue(**data)
                    self._issues[issue.issue_id] = issue
                    # Mettre à jour le compteur
                    try:
                        n = int(issue.issue_id.split("-")[-1])
                        self._counter = max(self._counter, n)
                    except (ValueError, IndexError):
                        pass
        except Exception as e:
            logger.warning(f"MulticaTracker: erreur chargement issues: {e}")

    def _append_issue(self, issue: TradeIssue) -> None:
        try:
            with open(self._issues_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(issue)) + "\n")
        except Exception as e:
            logger.error(f"MulticaTracker: erreur écriture issue: {e}")

    def _append_activity(self, activity: ActivityEntry) -> None:
        try:
            with open(self._activity_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(activity)) + "\n")
        except Exception as e:
            logger.error(f"MulticaTracker: erreur écriture activity: {e}")

    # ── Issue lifecycle ────────────────────────────────────────────────────────

    def create_issue(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        votes: List[str],
        assignee_id: str = "",
        reasoning: str = "",
        labels: List[str] = None,
    ) -> TradeIssue:
        """Crée une Issue pour chaque décision de Parlement (inspiré multica)."""
        self._counter += 1
        issue_id = f"ORACLE-{self._counter:04d}"

        # Auto-labels
        auto_labels = []
        if confidence > 0.75:
            auto_labels.append("high-confidence")
        if "polymarket" in reasoning.lower():
            auto_labels.append("polymarket")
        if "hebbian" in reasoning.lower():
            auto_labels.append("hebbian")
        if direction == "NEUTRAL":
            auto_labels.append("no-trade")

        issue = TradeIssue(
            issue_id=issue_id,
            symbol=symbol,
            direction=direction,
            status="open" if direction != "NEUTRAL" else "rejected",
            assignee_id=assignee_id or "parliament",
            confidence=confidence,
            votes=votes,
            reasoning=reasoning[:300],
            labels=(labels or []) + auto_labels,
        )
        self._issues[issue_id] = issue
        self._append_issue(issue)

        # Activity log
        self._append_activity(ActivityEntry(
            activity_id=f"act-{int(time.time())}-{issue_id}",
            issue_id=issue_id,
            actor="parliament",
            action="created",
            metadata={"direction": direction, "confidence": confidence},
        ))

        logger.debug(f"MulticaTracker: Issue créée {issue_id} {direction} {symbol} ({confidence:.0%})")
        return issue

    def update_issue_entry(
        self,
        issue_id: str,
        entry_price: float,
    ) -> None:
        """Marque l'entrée en position."""
        issue = self._issues.get(issue_id)
        if not issue:
            return
        issue.status = "in_progress"
        issue.entry_price = entry_price
        self._append_activity(ActivityEntry(
            activity_id=f"act-{int(time.time())}-entry",
            issue_id=issue_id,
            actor="binance_connector",
            action="trade_executed",
            metadata={"entry_price": entry_price},
        ))

    def close_issue(
        self,
        issue_id: str,
        exit_price: float,
        pnl_pct: float,
        actor: str = "brainstem",
    ) -> None:
        """Ferme une Issue avec résultat de trade."""
        issue = self._issues.get(issue_id)
        if not issue:
            return
        issue.status = "closed"
        issue.closed_at = time.time()
        issue.exit_price = exit_price
        issue.pnl_pct = pnl_pct
        if pnl_pct > 0:
            issue.labels.append("profitable")
        else:
            issue.labels.append("loss")
        self._append_activity(ActivityEntry(
            activity_id=f"act-{int(time.time())}-close",
            issue_id=issue_id,
            actor=actor,
            action="closed",
            metadata={"exit_price": exit_price, "pnl_pct": pnl_pct},
        ))
        logger.info(f"MulticaTracker: Issue {issue_id} fermée — PnL {pnl_pct:+.2%}")

    def block_issue(
        self,
        issue_id: str,
        reason: str,
        actor: str = "safety_kernel",
    ) -> None:
        """Marque une Issue bloquée (Safety / Brainstem refus)."""
        issue = self._issues.get(issue_id)
        if not issue:
            return
        issue.status = "rejected"
        issue.labels.append("blocked")
        issue.reasoning += f" | BLOQUÉ: {reason}"
        self._append_activity(ActivityEntry(
            activity_id=f"act-{int(time.time())}-block",
            issue_id=issue_id,
            actor=actor,
            action="blocked",
            metadata={"reason": reason},
        ))

    # ── Analytics (inspiré multica workspace metrics) ──────────────────────────

    def get_stats(self) -> dict:
        """
        Retourne les métriques du workspace — similaire aux dashboard multica.
        """
        all_issues = list(self._issues.values())
        closed = [i for i in all_issues if i.status == "closed"]
        rejected = [i for i in all_issues if i.status == "rejected"]
        open_issues = [i for i in all_issues if i.status in ("open", "in_progress")]

        profitable = [i for i in closed if (i.pnl_pct or 0) > 0]
        losses = [i for i in closed if (i.pnl_pct or 0) < 0]

        total_pnl = sum(i.pnl_pct or 0 for i in closed)
        win_rate = len(profitable) / len(closed) if closed else 0.0

        # Performance par strate (assignee_type = agent)
        strate_performance: dict[str, dict] = {}
        for issue in closed:
            if not issue.assignee_id:
                continue
            sp = strate_performance.setdefault(issue.assignee_id, {"wins": 0, "losses": 0, "pnl": 0.0})
            if (issue.pnl_pct or 0) > 0:
                sp["wins"] += 1
            else:
                sp["losses"] += 1
            sp["pnl"] += issue.pnl_pct or 0

        return {
            "workspace_id": self.workspace_id,
            "total_issues": len(all_issues),
            "open": len(open_issues),
            "closed": len(closed),
            "rejected": len(rejected),
            "profitable": len(profitable),
            "losses": len(losses),
            "win_rate": win_rate,
            "total_pnl_pct": total_pnl,
            "strate_performance": strate_performance,
            "timestamp": datetime.now(TAHITI_TZ).isoformat(),
        }

    def get_open_issues(self) -> List[TradeIssue]:
        """Retourne les Issues ouvertes (positions actives)."""
        return [i for i in self._issues.values() if i.status in ("open", "in_progress")]

    def format_stats_rich(self) -> str:
        """Retourne un résumé texte pour la console / Telegram."""
        s = self.get_stats()
        wr = s["win_rate"]
        pnl = s["total_pnl_pct"]
        return (
            f"📊 ORACLE Tracker [{s['workspace_id']}] | "
            f"Total: {s['total_issues']} issues | "
            f"Fermées: {s['closed']} ({s['profitable']}✅/{s['losses']}❌) | "
            f"Win Rate: {wr:.0%} | PnL total: {pnl:+.2%}"
        )
