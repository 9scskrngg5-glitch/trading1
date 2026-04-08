"""
Obsidian Client — Lecture/Écriture du vault Markdown
Aucune API Obsidian : manipulation directe des fichiers .md avec frontmatter YAML.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

VAULT_DIRS = [
    # ── Agents core ──
    "technique",         # ScanAgent — analyses techniques
    "fondamental",       # ResearchAgent — sentiment / news
    "decisions",         # PredictAgent — convergences
    "risque",            # RiskAgent — décisions de risque + journal
    "execution",         # ExecuteAgent — rapports d'exécution
    "retrospectives",    # RiskAgent — post-trade
    "synthese",          # SynthesisAgent — DataSheets
    # ── Agents avancés ──
    "market_conditions", # RegimeAgent — détection de régime
    "patterns",          # KnowledgeAgent — patterns découverts
    "experiments",       # ShadowAgent — stratégies shadow
    "behavior",          # BehaviorAgent — discipline
    "reports",           # MetaAgent — rapports CEO
    "supervision",       # SupervisorAgent — santé système
    # ── Infrastructure ──
    "apprentissage",     # LearningEngine — leçons ML
    "config",            # Mémoires agents + état CompoundAgent
    "agents",            # Pages agents (VaultInitializer)
]


class ObsidianNote:
    """Représentation d'une note Obsidian parsée."""

    def __init__(self, frontmatter: dict, content: str, filepath: Path | None = None):
        self.frontmatter = frontmatter
        self.content = content
        self.filepath = filepath

    @property
    def filename(self) -> str:
        return self.filepath.stem if self.filepath else ""

    def __repr__(self) -> str:
        return f"<ObsidianNote {self.filepath}>"


class ObsidianClient:
    """
    Interface de bas niveau pour le vault Obsidian.

    Chaque agent dispose de son propre dossier (séparation stricte en écriture).
    Les agents peuvent lire les dossiers des autres pour créer des liens.
    """

    # Séparateurs YAML frontmatter
    _FM_PATTERN = re.compile(r"^---\n(.*?)\n---\n?(.*)", re.DOTALL)

    def __init__(self, vault_path: str | Path):
        self.vault_path = Path(vault_path).resolve()
        self._init_structure()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_structure(self) -> None:
        for folder in VAULT_DIRS:
            (self.vault_path / folder).mkdir(parents=True, exist_ok=True)
        logger.info("Vault Obsidian prêt : %s", self.vault_path)

    # ── Écriture ──────────────────────────────────────────────────────────────

    def write_note(
        self,
        folder: str,
        filename: str,
        frontmatter: dict[str, Any],
        content: str,
    ) -> Path:
        """
        Écrit (ou écrase) une note .md avec frontmatter YAML.

        Args:
            folder:      Sous-dossier du vault (ex: "technique")
            filename:    Nom du fichier sans extension
            frontmatter: Dictionnaire YAML (metadata)
            content:     Corps Markdown de la note

        Returns:
            Path absolu du fichier créé.
        """
        filepath = self.vault_path / folder / f"{filename}.md"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        fm_block = yaml.dump(
            frontmatter,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        text = f"---\n{fm_block}---\n\n{content}"
        # Écriture atomique : .tmp puis rename pour éviter corruption en cas de crash
        tmp_path = filepath.with_suffix(".md.tmp")
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(filepath)
        logger.debug("📝  Note écrite : %s", filepath.relative_to(self.vault_path))
        return filepath

    # ── Lecture ───────────────────────────────────────────────────────────────

    def read_note(self, folder: str, filename: str) -> ObsidianNote | None:
        """Lit une note unique. Retourne None si le fichier n'existe pas."""
        filepath = self.vault_path / folder / f"{filename}.md"
        if not filepath.exists():
            return None
        return self._parse(filepath)

    def read_latest(self, folder: str, limit: int = 10) -> list[ObsidianNote]:
        """Retourne les `limit` notes les plus récentes d'un dossier."""
        folder_path = self.vault_path / folder
        files = sorted(
            folder_path.glob("*.md"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        notes = []
        for f in files[:limit]:
            note = self._parse(f)
            if note:
                notes.append(note)
        return notes

    def read_by_asset(self, folder: str, asset: str, limit: int = 5) -> list[ObsidianNote]:
        """Filtre les notes d'un dossier pour un asset donné (via frontmatter)."""
        all_notes = self.read_latest(folder, limit=50)
        return [
            n for n in all_notes
            if n.frontmatter.get("asset") == asset
        ][:limit]

    # ── Parsing interne ───────────────────────────────────────────────────────

    def _parse(self, filepath: Path) -> ObsidianNote | None:
        try:
            text = filepath.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Lecture impossible : %s — %s", filepath, exc)
            return None

        match = self._FM_PATTERN.match(text)
        if not match:
            return ObsidianNote(frontmatter={}, content=text, filepath=filepath)

        try:
            fm = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            logger.error("YAML invalide dans %s : %s", filepath.name, exc)
            fm = {}

        return ObsidianNote(
            frontmatter=fm,
            content=match.group(2).strip(),
            filepath=filepath,
        )

    # ── Helpers Obsidian ──────────────────────────────────────────────────────

    @staticmethod
    def wikilink(folder: str, filename: str) -> str:
        """Génère un wikilink Obsidian : [[folder/filename]]"""
        return f"[[{folder}/{filename}]]"

    @staticmethod
    def daily_filename(agent_prefix: str, asset: str, dt: datetime | None = None) -> str:
        """
        Génère un nom de fichier normalisé avec date.
        Ex: 2024-01-15_technique_BTC-USDT
        """
        dt = dt or datetime.now(timezone.utc)
        safe_asset = asset.replace("/", "-").replace(" ", "_")
        return f"{dt.strftime('%Y-%m-%d')}_{agent_prefix}_{safe_asset}"

    @staticmethod
    def timestamp_filename(prefix: str, asset: str, dt: datetime | None = None) -> str:
        """Nom de fichier avec timestamp complet (pour les ordres/exécutions)."""
        dt = dt or datetime.now(timezone.utc)
        safe_asset = asset.replace("/", "-").replace(" ", "_")
        return f"{dt.strftime('%Y-%m-%d_%H%M%S')}_{prefix}_{safe_asset}"
