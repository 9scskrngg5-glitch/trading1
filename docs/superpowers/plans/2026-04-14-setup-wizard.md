# ORACLE v2 Setup Wizard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a standalone Textual TUI wizard (`SETUP_ORACLE.bat`) that guides the user through API key configuration step by step, writes a `.env` file, then runs a full diagnostic scan of the entire codebase.

**Architecture:** A Textual App with 8 sequential Screens (Welcome → 5 API screens → BugScan → Summary). API values are collected in-memory and written atomically to `oracle_v2/.env` before the scan. The bug scan runs async checks and streams results line by line using Textual's `@work` decorator.

**Tech Stack:** Python 3.10+, Textual ≥0.61, Rich ≥13.7, httpx (async HTTP), subprocess (pytest runner), python-dotenv ≥1.0.0

---

### Task 1: Add python-dotenv dependency

**Files:**
- Modify: `oracle_v2/requirements.txt`
- Modify: `oracle_v2/main.py`

- [ ] **Step 1: Add python-dotenv to requirements**

In `oracle_v2/requirements.txt`, after the `rich>=13.7.0` line, add:
```
python-dotenv>=1.0.0
```

- [ ] **Step 2: Add load_dotenv() to main.py**

In `oracle_v2/main.py`, after `import sys`, add:
```python
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
```

- [ ] **Step 3: Install the dependency**

```bash
cd oracle_v2 && pip install "python-dotenv>=1.0.0"
```
Expected: `Successfully installed python-dotenv-...`

- [ ] **Step 4: Commit**

```bash
git add oracle_v2/requirements.txt oracle_v2/main.py
git commit -m "feat: add python-dotenv for .env loading"
```

---

### Task 2: Create SETUP_ORACLE.bat

**Files:**
- Create: `SETUP_ORACLE.bat` (at repo root `C:\Users\gille\OneDrive\Bureau\bot\trading\`)

- [ ] **Step 1: Create the bat file**

Create `SETUP_ORACLE.bat`:

```bat
@echo off
chcp 65001 > nul
title ORACLE v2 — Setup Wizard
cls

echo.
echo  +======================================+
echo  ^|        ORACLE v2 ^| SETUP WIZARD     ^|
echo  +======================================+
echo.

:: Check Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Python introuvable. Installe Python 3.10+ depuis python.org
    pause
    exit /b 1
)

:: Activate venv if present (oracle_v2/venv or root venv)
if exist "%~dp0oracle_v2\venv\Scripts\activate.bat" (
    call "%~dp0oracle_v2\venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

:: Run wizard from oracle_v2 directory (imports are relative to oracle_v2/)
cd /d "%~dp0oracle_v2"
python -m ui.setup_wizard
if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] Le wizard a plante. Lance manuellement :
    echo   cd oracle_v2 ^&^& python -m ui.setup_wizard
    pause
)
```

- [ ] **Step 2: Commit**

```bash
git add SETUP_ORACLE.bat
git commit -m "feat: add SETUP_ORACLE.bat dedicated launcher"
```

---

### Task 3: setup_wizard.py — helpers + WelcomeScreen

**Files:**
- Create: `oracle_v2/ui/setup_wizard.py`

- [ ] **Step 1: Create the file with imports, CSS, helpers, and WelcomeScreen**

Create `oracle_v2/ui/setup_wizard.py` with this exact content:

```python
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
```

- [ ] **Step 2: Verify import**

```bash
cd oracle_v2 && python -c "from ui.setup_wizard import WelcomeScreen; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add oracle_v2/ui/setup_wizard.py
git commit -m "feat(wizard): skeleton + WelcomeScreen + .env helpers"
```

---

### Task 4: ApiScreen base class + 5 API screens

**Files:**
- Modify: `oracle_v2/ui/setup_wizard.py` (append after WelcomeScreen)

- [ ] **Step 1: Append ApiField descriptor and ApiScreen base**

Append to `oracle_v2/ui/setup_wizard.py`:

```python
# ── ApiScreen — base ───────────────────────────────────────────────────────

class ApiField:
    """Describes one Input field on an API screen."""
    def __init__(
        self,
        key: str,
        label: str,
        placeholder: str = "",
        password: bool = False,
        optional: bool = False,
    ):
        self.key = key
        self.label = label
        self.placeholder = placeholder
        self.password = password
        self.optional = optional


class ApiScreen(Screen):
    """Base class for API configuration screens.

    Subclasses set class attributes:
        SCREEN_TITLE, DESCRIPTION, FIELDS, NEXT_SCREEN, STEP, OPTIONAL
    """

    SCREEN_TITLE: str = "API Configuration"
    DESCRIPTION: str = ""
    FIELDS: list[ApiField] = []
    NEXT_SCREEN: str = ""
    STEP: str = "? / 5"
    OPTIONAL: bool = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(classes="wizard-screen"):
            with Vertical(classes="wizard-box"):
                yield Static(f"Étape {self.STEP}", classes="step-indicator")
                yield Static(self.SCREEN_TITLE, classes="wizard-title")
                if self.DESCRIPTION:
                    yield Static(self.DESCRIPTION, classes="wizard-desc")
                for field in self.FIELDS:
                    opt = "  [dim](optionnel)[/]" if field.optional else ""
                    yield Label(f"[bold #4a9eff]{field.label}[/]{opt}", markup=True)
                    yield Input(
                        placeholder=field.placeholder,
                        password=field.password,
                        id=f"input_{field.key}",
                    )
                with Horizontal(classes="btn-row"):
                    if self.OPTIONAL:
                        yield Button("Passer ›", id="btn-skip", classes="skip")
                    yield Button("Suivant →", id="btn-next", classes="primary")
        yield Footer()

    def on_mount(self) -> None:
        """Pre-fill fields from existing .env."""
        existing = read_env()
        for field in self.FIELDS:
            val = existing.get(field.key, "")
            if val:
                self.query_one(f"#input_{field.key}", Input).value = val

    def _collect(self) -> dict[str, str]:
        return {
            field.key: self.query_one(f"#input_{field.key}", Input).value.strip()
            for field in self.FIELDS
        }

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-skip":
            self.app.push_screen(self.NEXT_SCREEN)
        elif event.button.id == "btn-next":
            self.app.config_values.update(self._collect())
            self.app.push_screen(self.NEXT_SCREEN)
```

- [ ] **Step 2: Append the 5 concrete API screens**

Append to `oracle_v2/ui/setup_wizard.py`:

```python
class BinanceScreen(ApiScreen):
    SCREEN_TITLE = "⟨1⟩  BINANCE"
    DESCRIPTION  = "Clés API Binance — requises pour le trading BTC/USDT"
    STEP         = "1 / 5"
    NEXT_SCREEN  = "telegram"
    OPTIONAL     = False
    FIELDS = [
        ApiField("BINANCE_API_KEY", "API Key",    placeholder="Votre Binance API key"),
        ApiField("BINANCE_SECRET",  "Secret Key", placeholder="Votre Binance secret", password=True),
    ]

    def on_mount(self) -> None:
        super().on_mount()
        existing = read_env()
        testnet = existing.get("BINANCE_TESTNET", "True")
        self.notify(
            f"BINANCE_TESTNET={testnet}  (modifiable dans .env après setup)",
            severity="information",
            timeout=5,
        )


class TelegramScreen(ApiScreen):
    SCREEN_TITLE = "⟨2⟩  TELEGRAM"
    DESCRIPTION  = "Alertes trading en temps réel"
    STEP         = "2 / 5"
    NEXT_SCREEN  = "anthropic"
    OPTIONAL     = True
    FIELDS = [
        ApiField("TELEGRAM_TOKEN",   "Bot Token", placeholder="123456:ABC-DEF...",   optional=True),
        ApiField("TELEGRAM_CHAT_ID", "Chat ID",   placeholder="-100123456789",       optional=True),
    ]


class AnthropicScreen(ApiScreen):
    SCREEN_TITLE = "⟨3⟩  ANTHROPIC"
    DESCRIPTION  = "Claude Haiku — narration enrichie des décisions Oracle"
    STEP         = "3 / 5"
    NEXT_SCREEN  = "twitter"
    OPTIONAL     = True
    FIELDS = [
        ApiField(
            "ANTHROPIC_API_KEY", "API Key",
            placeholder="sk-ant-api03-...",
            password=True, optional=True,
        ),
    ]


class TwitterScreen(ApiScreen):
    SCREEN_TITLE = "⟨4⟩  TWITTER / X"
    DESCRIPTION  = "Sentiment BTC temps réel — plan Free : 500k tweets/mois"
    STEP         = "4 / 5"
    NEXT_SCREEN  = "capital"
    OPTIONAL     = True
    FIELDS = [
        ApiField(
            "TWITTER_BEARER_TOKEN", "Bearer Token",
            placeholder="AAAA...",
            password=True, optional=True,
        ),
    ]


class CapitalScreen(ApiScreen):
    SCREEN_TITLE = "⟨5⟩  CAPITAL.COM"
    DESCRIPTION  = "Connector CFD alternatif (Forex / indices)"
    STEP         = "5 / 5"
    NEXT_SCREEN  = "bugscan"
    OPTIONAL     = True
    FIELDS = [
        ApiField("CAPITAL_API_KEY",  "API Key",  placeholder="Votre Capital.com key",  optional=True),
        ApiField("CAPITAL_PASSWORD", "Password", placeholder="Votre mot de passe", password=True, optional=True),
    ]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Override: write .env before navigating to BugScan."""
        if event.button.id == "btn-next":
            self.app.config_values.update(self._collect())
        # Both next and skip trigger .env write + navigation
        if event.button.id in ("btn-next", "btn-skip"):
            write_env(self.app.config_values)
            self.notify("✅ .env sauvegardé", severity="information", timeout=2)
            self.app.push_screen("bugscan")
```

- [ ] **Step 3: Verify**

```bash
cd oracle_v2 && python -c "from ui.setup_wizard import BinanceScreen, CapitalScreen; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add oracle_v2/ui/setup_wizard.py
git commit -m "feat(wizard): ApiScreen base + 5 API screens (Binance/Telegram/Anthropic/Twitter/Capital)"
```

---

### Task 5: BugScanScreen

**Files:**
- Modify: `oracle_v2/ui/setup_wizard.py` (append)

- [ ] **Step 1: Append BugScanScreen**

Append to `oracle_v2/ui/setup_wizard.py`:

```python
# ── BugScanScreen ──────────────────────────────────────────────────────────

CRITICAL_DEPS = [
    "ccxt", "pandas", "numpy", "textual", "rich",
    "anthropic", "xgboost", "ta", "httpx", "dotenv",
    "telegram", "websockets", "sklearn", "langchain",
]

ORACLE_MODULES: list[tuple[str, str]] = [
    ("config",                "Config"),
    ("brain.brainstem",       "Brainstem"),
    ("brain.safety_kernel",   "SafetyKernel"),
    ("brain.parliament",      "Parliament"),
    ("brain.working_memory",  "WorkingMemory"),
    ("brain.narrator",        "Narrator"),
    ("strates.amd_strate",    "AMD Strate"),
    ("strates.momentum_strate","Momentum"),
    ("strates.legacy_bridge", "LegacyBridge"),
    ("telegram.alert_queue",  "AlertQueue"),
    ("execution_engine",      "ExecutionEngine"),
]

LEGACY_MODULES = [
    "trading_bot.core.strate_0_epistemic",
    "trading_bot.core.strate_2_minsky",
    "trading_bot.core.strate_4_reflexivity",
    "trading_bot.core.strate_5_behavioral_bias",
    "trading_bot.core.strate_7_fractal_risk",
]


class BugScanScreen(Screen):
    """Scan complet en streaming : deps → imports → pytest → API pings."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(classes="wizard-screen"):
            with Vertical(classes="wizard-box"):
                yield Static("DIAGNOSTIC COMPLET", classes="wizard-title")
                yield Static("Scan en cours…", id="scan-status", classes="wizard-desc")
                yield Log(id="scan-log", classes="scan-log", auto_scroll=True)
                yield Static("", id="scan-summary", classes="scan-summary")
                with Horizontal(classes="btn-row"):
                    yield Button(
                        "Voir le résumé →", id="btn-summary",
                        classes="primary", disabled=True,
                    )
        yield Footer()

    def on_mount(self) -> None:
        self.run_scan()

    @work(exclusive=True)
    async def run_scan(self) -> None:
        log = self.query_one("#scan-log", Log)
        passes = 0
        fails = 0

        async for label, ok, detail in self._all_checks():
            icon = "[green]✅[/]" if ok else "[red]❌[/]"
            suffix = f"  [dim]{detail}[/]" if detail else ""
            log.write_markup(f"{icon}  {label}{suffix}")
            if ok:
                passes += 1
            else:
                fails += 1

        color = "green" if fails == 0 else ("yellow" if fails <= 3 else "red")
        self.query_one("#scan-status", Static).update(
            f"[bold {color}]Scan terminé[/]"
        )
        self.query_one("#scan-summary", Static).update(
            f"[green]{passes} passés[/]  ·  [red]{fails} échoués[/]  "
            f"·  {passes + fails} checks au total"
        )
        self.app.scan_passes = passes
        self.app.scan_fails = fails
        self.query_one("#btn-summary", Button).disabled = False

    async def _all_checks(self) -> AsyncIterator[tuple[str, bool, str]]:
        """Yields (label, ok, detail) for every diagnostic check."""

        # ── 1. Python version ─────────────────────────────────────────────
        vi = sys.version_info
        ok = vi >= (3, 10)
        yield "Python >= 3.10", ok, f"{vi.major}.{vi.minor}.{vi.micro}"

        # ── 2. Pip dependencies ───────────────────────────────────────────
        for pkg in CRITICAL_DEPS:
            try:
                importlib.import_module(pkg)
                yield f"dep: {pkg}", True, "OK"
            except ImportError as e:
                yield f"dep: {pkg}", False, str(e)[:55]

        # ── 3. oracle_v2 modules ──────────────────────────────────────────
        for mod, name in ORACLE_MODULES:
            try:
                importlib.import_module(mod)
                yield f"oracle_v2 · {name}", True, "OK"
            except Exception as e:
                yield f"oracle_v2 · {name}", False, str(e)[:55]

        # ── 4. trading_bot legacy strates ─────────────────────────────────
        repo_root = str(ORACLE_DIR.parent)
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        for mod in LEGACY_MODULES:
            strate_name = mod.split(".")[-1]
            try:
                importlib.import_module(mod)
                yield f"legacy · {strate_name}", True, "OK"
            except Exception as e:
                yield f"legacy · {strate_name}", False, str(e)[:55]

        # ── 5. pytest ─────────────────────────────────────────────────────
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "--tb=line", "-q", "--no-header"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(ORACLE_DIR),
            )
            ok = result.returncode == 0
            output = (result.stdout + result.stderr).strip()
            last = output.split("\n")[-1] if output else "(no output)"
            yield "pytest oracle_v2/tests/", ok, last[:60]
        except subprocess.TimeoutExpired:
            yield "pytest oracle_v2/tests/", False, "timeout >120s"
        except Exception as e:
            yield "pytest oracle_v2/tests/", False, str(e)[:55]

        # ── 6. Binance public ping (no auth) ──────────────────────────────
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get("https://api.binance.com/api/v3/ping")
            yield "Binance API ping", r.status_code == 200, f"HTTP {r.status_code}"
        except Exception as e:
            yield "Binance API ping", False, str(e)[:55]

        # ── 7. Telegram getMe (only if token configured) ──────────────────
        token = (
            self.app.config_values.get("TELEGRAM_TOKEN")
            or os.getenv("TELEGRAM_TOKEN", "")
        )
        if token:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(
                        f"https://api.telegram.org/bot{token}/getMe"
                    )
                data = r.json()
                ok = data.get("ok", False)
                username = data.get("result", {}).get("username", "?")
                yield "Telegram getMe", ok, (
                    f"@{username}" if ok else r.text[:40]
                )
            except Exception as e:
                yield "Telegram getMe", False, str(e)[:55]

        # ── 8. Anthropic API (only if key configured) ─────────────────────
        api_key = (
            self.app.config_values.get("ANTHROPIC_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY", "")
        )
        if api_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                models = client.models.list()
                yield "Anthropic API", True, f"{len(models.data)} models disponibles"
            except Exception as e:
                yield "Anthropic API", False, str(e)[:55]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-summary":
            self.app.push_screen("summary")
```

- [ ] **Step 2: Commit**

```bash
git add oracle_v2/ui/setup_wizard.py
git commit -m "feat(wizard): BugScanScreen — full async streaming diagnostic"
```

---

### Task 6: SummaryScreen + SetupWizard App wire-up

**Files:**
- Modify: `oracle_v2/ui/setup_wizard.py` (append)

- [ ] **Step 1: Append SummaryScreen**

Append to `oracle_v2/ui/setup_wizard.py`:

```python
# ── SummaryScreen ──────────────────────────────────────────────────────────

class SummaryScreen(Screen):
    """Résumé final : config sauvegardée + résultats scan + lancement."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(classes="wizard-screen"):
            with Vertical(classes="wizard-box"):
                yield Static("RÉSUMÉ", classes="wizard-title")

                yield Static(
                    "[bold #4a9eff]Configuration sauvegardée dans .env[/]",
                    classes="wizard-desc",
                )
                yield Static("", id="config-recap")

                yield Static("", id="scan-recap", classes="scan-summary")

                with Horizontal(classes="btn-row"):
                    yield Button("↩ Refaire le scan", id="btn-rescan", classes="skip")
                    yield Button("🚀  Lancer ORACLE v2", id="btn-launch", classes="launch")
        yield Footer()

    def on_mount(self) -> None:
        # Config recap — mask secrets
        values = self.app.config_values
        lines: list[str] = []
        for key, val in values.items():
            if val:
                if len(val) > 8:
                    display = val[:4] + "·" * 4 + val[-2:]
                else:
                    display = "·" * len(val)
                lines.append(f"  [cyan]{key}[/] = {display}")
        recap = self.query_one("#config-recap", Static)
        recap.update("\n".join(lines) if lines else "  [dim]Aucune valeur saisie[/]")

        # Scan recap
        passes = getattr(self.app, "scan_passes", 0)
        fails = getattr(self.app, "scan_fails", 0)
        color = "green" if fails == 0 else ("yellow" if fails <= 3 else "red")
        msg = "✅ Tous les checks sont passés." if fails == 0 else (
            f"⚠️  {fails} erreur(s) détectée(s) — consulte le scan pour les détails."
        )
        self.query_one("#scan-recap", Static).update(
            f"[bold {color}]Diagnostic : {passes} ✅  {fails} ❌[/]\n[dim]{msg}[/]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-rescan":
            self.app.push_screen("bugscan")
        elif event.button.id == "btn-launch":
            self.app.exit(0)
```

- [ ] **Step 2: Append the main SetupWizard App and entry point**

Append to `oracle_v2/ui/setup_wizard.py`:

```python
# ── SetupWizard App ────────────────────────────────────────────────────────

class SetupWizard(App):
    """Application Textual principale du wizard de configuration."""

    CSS = WIZARD_CSS
    TITLE = "ORACLE v2 — Setup Wizard"
    BINDINGS = [
        Binding("q", "quit", "Quitter"),
        Binding("ctrl+c", "quit", "Quitter"),
    ]

    SCREENS = {
        "welcome":   WelcomeScreen,
        "binance":   BinanceScreen,
        "telegram":  TelegramScreen,
        "anthropic": AnthropicScreen,
        "twitter":   TwitterScreen,
        "capital":   CapitalScreen,
        "bugscan":   BugScanScreen,
        "summary":   SummaryScreen,
    }

    def __init__(self) -> None:
        super().__init__()
        self.config_values: dict[str, str] = {}
        self.scan_passes: int = 0
        self.scan_fails: int = 0

    def on_mount(self) -> None:
        self.push_screen("welcome")

    def action_quit(self) -> None:
        self.exit(0)


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Pre-load existing .env so read_env() and os.getenv() both see old values
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_PATH)
    except ImportError:
        pass

    SetupWizard().run()

    print(
        "\n[ORACLE v2] Setup terminé.\n"
        "Lance le bot : python main.py --mode paper\n"
    )
```

- [ ] **Step 3: Full import check**

```bash
cd oracle_v2 && python -c "from ui.setup_wizard import SetupWizard; print('SetupWizard OK')"
```
Expected: `SetupWizard OK`

- [ ] **Step 4: Verify SCREENS keys match screen classes**

```bash
cd oracle_v2 && python -c "
from ui.setup_wizard import SetupWizard
app = SetupWizard()
print('Screens:', list(app.SCREENS.keys()))
"
```
Expected:
```
Screens: ['welcome', 'binance', 'telegram', 'anthropic', 'twitter', 'capital', 'bugscan', 'summary']
```

- [ ] **Step 5: Final commit**

```bash
git add oracle_v2/ui/setup_wizard.py
git commit -m "feat(wizard): SummaryScreen + SetupWizard app — wizard complet"
```

---

## Self-Review

**Spec coverage:**
- ✅ `.bat` dédié → `SETUP_ORACLE.bat` (Task 2)
- ✅ Saisie directe dans le terminal → `Input` Textual fields (Task 4)
- ✅ Configuration point par point → 5 écrans `ApiScreen` séquentiels (Task 4)
- ✅ Écriture `.env` → `write_env()` appelé dans `CapitalScreen.on_button_pressed` (Task 4)
- ✅ Tour des bugs — ensemble du code → deps + imports `oracle_v2` (11 modules) + imports `trading_bot` legacy (5 strates) + pytest + Binance ping + Telegram ping + Anthropic ping (Task 5)
- ✅ Thème cyberpunk → `WIZARD_CSS` extends `ORACLE_CSS`, couleurs `#00d4ff`/`#4a9eff`/`#00ff88` (Task 3)
- ✅ Pré-remplissage `.env` existant → `read_env()` + `on_mount()` dans `ApiScreen` (Tasks 3-4)
- ✅ Résumé avec masquage des secrets → `SummaryScreen.on_mount()` (Task 6)

**Placeholder scan:** Aucun TBD/TODO/placeholder — tous les blocs de code sont complets et exécutables.

**Type consistency:**
- `read_env() → dict[str, str]` ✅
- `write_env(new_values: dict[str, str]) → None` ✅ appelé avec `self.app.config_values` qui est `dict[str, str]`
- `ApiField.key: str` → utilisé comme `f"input_{field.key}"` cohéremment dans `compose()`, `on_mount()`, `_collect()` ✅
- `NEXT_SCREEN: str` → correspond aux clés de `SetupWizard.SCREENS` dans toutes les sous-classes ✅
- `self.app.scan_passes / scan_fails: int` → initialisés dans `SetupWizard.__init__()`, lus dans `SummaryScreen.on_mount()` ✅
