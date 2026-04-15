"""
ORACLE v2 — Setup Wizard
Wizard Textual 8 écrans : Welcome → 5 APIs → BugScan → Summary
Lance via : python -m ui.setup_wizard  (depuis oracle_v2/)
"""
from __future__ import annotations
import importlib
import os
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Log, Static

from ui.styles import ORACLE_CSS

# ── Paths ──────────────────────────────────────────────────────────────────
ORACLE_DIR = Path(__file__).parent.parent   # .../oracle_v2/
ENV_PATH = ORACLE_DIR / ".env"

# ── CSS ────────────────────────────────────────────────────────────────────
WIZARD_CSS = ORACLE_CSS + """
.wizard-screen {
    align: center middle;
}

.wizard-box {
    background: #0d1b2a;
    border: solid #00d4ff;
    padding: 2 4;
    width: 84;
    max-height: 92%;
}

.step-indicator {
    color: #4a5568;
    text-align: center;
    padding-bottom: 0;
}

.wizard-title {
    color: #00d4ff;
    text-style: bold;
    text-align: center;
    padding-bottom: 1;
}

.wizard-desc {
    color: #8899aa;
    text-align: center;
    padding-bottom: 1;
}

Input {
    background: #060d1a;
    border: solid #1e3a5f;
    color: #e0e8ff;
    padding: 0 1;
    margin-bottom: 1;
}

Input:focus {
    border: solid #00d4ff;
}

.field-label {
    color: #4a9eff;
    margin-bottom: 0;
}

.btn-row {
    align: center middle;
    height: 3;
    margin-top: 1;
}

Button {
    margin: 0 1;
}

Button.primary {
    background: #00d4ff;
    color: #0a0e1a;
    text-style: bold;
}

Button.skip {
    background: #1e3a5f;
    color: #4a9eff;
}

Button.launch {
    background: #00ff88;
    color: #0a0e1a;
    text-style: bold;
}

.scan-log {
    background: #060d1a;
    border: solid #1e3a5f;
    height: 22;
    padding: 1;
    margin-bottom: 1;
}

.scan-summary {
    color: #4a9eff;
    text-align: center;
    padding-top: 1;
}
"""

ORACLE_ASCII = r"""
 ██████╗ ██████╗  █████╗  ██████╗██╗     ███████╗    ██╗   ██╗██████╗
██╔═══██╗██╔══██╗██╔══██╗██╔════╝██║     ██╔════╝    ██║   ██║╚════██╗
██║   ██║██████╔╝███████║██║     █████╗  █████╗      ██║   ██║ █████╔╝
██║   ██║██╔══██╗██╔══██║██║     ██╔══╝  ██╔══╝      ╚██╗ ██╔╝██╔═══╝
╚██████╔╝██║  ██║██║  ██║╚██████╗███████╗███████╗     ╚████╔╝ ███████╗
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝╚══════╝      ╚═══╝  ╚══════╝
"""

# ── .env helpers ───────────────────────────────────────────────────────────

def read_env() -> dict[str, str]:
    """Lit le .env existant, retourne dict key→value."""
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


def write_env(new_values: dict[str, str]) -> None:
    """Fusionne new_values dans .env (crée ou met à jour les clés existantes)."""
    existing_raw: dict[str, str] = {}   # key → original raw line
    ordered: list[str] = []              # keys in file order (or plain lines)

    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=")[0].strip()
                existing_raw[key] = line
                ordered.append(f"\x00key\x00{key}")
            else:
                ordered.append(line)

    output: list[str] = []
    inserted: set[str] = set()

    for entry in ordered:
        if entry.startswith("\x00key\x00"):
            key = entry[6:]
            if key in new_values:
                output.append(f"{key}={new_values[key]}")
                inserted.add(key)
            else:
                output.append(existing_raw[key])
        else:
            output.append(entry)

    # Append brand-new keys that weren't in the file yet
    for key, val in new_values.items():
        if key not in inserted and val:
            output.append(f"{key}={val}")

    ENV_PATH.write_text("\n".join(output) + "\n", encoding="utf-8")


# ── WelcomeScreen ──────────────────────────────────────────────────────────

class WelcomeScreen(Screen):
    """Écran d'accueil : ASCII art + détection .env existant."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(classes="wizard-screen"):
            with Vertical(classes="wizard-box"):
                yield Static(ORACLE_ASCII, id="ascii-banner")
                yield Static("SETUP WIZARD", classes="wizard-title")
                yield Static(
                    "Configuration guidée point par point — API keys + diagnostic complet du code",
                    classes="wizard-desc",
                )
                yield Static("", id="env-status")
                with Horizontal(classes="btn-row"):
                    yield Button("Commencer →", id="btn-start", classes="primary")
        yield Footer()

    def on_mount(self) -> None:
        existing = read_env()
        status = self.query_one("#env-status", Static)
        if existing:
            filled = [k for k, v in existing.items() if v]
            status.update(
                f"[green]● .env détecté[/] — {len(filled)} clé(s) existante(s) "
                "seront [cyan]pré-remplies[/] automatiquement."
            )
        else:
            status.update(
                "[yellow]● Aucun .env trouvé[/] — configuration from scratch."
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            self.app.push_screen("binance")
