"""
Watchdog — Relance automatique du bot en cas de crash.

Usage : python watchdog.py
Le mode de trading est lu depuis la variable d'environnement TRADING_MODE.

Comportement :
- Lance run_demo.py en sous-process
- Si le process crash (exit code != 0), attend 10s et relance
- Envoie une alerte Telegram à chaque crash et chaque restart
- Log tout dans watchdog.log
- Ctrl+C arrête proprement le bot ET le watchdog
"""

import os
import sys
import time
import subprocess
import logging
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# ── Logging ──────────────────────────────────────────────────────────────────

LOG_PATH = Path(__file__).parent / "watchdog.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("watchdog")

# ── Config ───────────────────────────────────────────────────────────────────

RESTART_DELAY  = 10      # secondes entre crash et restart
MAX_FAST_CRASHES = 5     # si 5 crashes en < 2min chacun → arrêt total
FAST_CRASH_SEC = 120     # un crash en < 2min = "fast crash"


def send_telegram(message: str) -> None:
    """Envoie un message Telegram sans dépendance async."""
    token   = os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        import httpx
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        httpx.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }, timeout=10)
    except Exception as exc:
        log.warning("Telegram send failed: %s", exc)


def run_watchdog() -> None:
    python = sys.executable
    script = str(Path(__file__).parent / "run_demo.py")
    fast_crashes = 0
    restart_count = 0

    log.info("=" * 60)
    log.info("WATCHDOG DEMARRÉ — surveille run_demo.py")
    log.info("Mode: %s", os.environ.get("TRADING_MODE", "simulation"))
    log.info("=" * 60)

    send_telegram("🐕 *Watchdog démarré*\nSurveillance active du bot.")

    while True:
        start_time = time.time()
        restart_count += 1

        log.info("Lancement #%d de run_demo.py ...", restart_count)

        try:
            proc = subprocess.run(
                [python, script],
                cwd=str(Path(__file__).parent),
                env={**os.environ},
            )
            exit_code = proc.returncode
        except KeyboardInterrupt:
            log.info("Ctrl+C reçu — arrêt du watchdog.")
            send_telegram("🛑 *Watchdog arrêté* (Ctrl+C)")
            break

        elapsed = time.time() - start_time

        if exit_code == 0:
            log.info("Bot terminé normalement (exit 0). Arrêt du watchdog.")
            send_telegram("✅ *Bot arrêté normalement* (exit 0)")
            break

        # Crash détecté
        log.error(
            "CRASH détecté ! exit_code=%d, durée=%.0fs",
            exit_code, elapsed,
        )

        crash_msg = (
            f"💥 *CRASH #{restart_count}*\n"
            f"Exit code : `{exit_code}`\n"
            f"Durée : `{elapsed:.0f}s`\n"
            f"Restart dans `{RESTART_DELAY}s`..."
        )
        send_telegram(crash_msg)

        # Protection contre les crash loops
        if elapsed < FAST_CRASH_SEC:
            fast_crashes += 1
            if fast_crashes >= MAX_FAST_CRASHES:
                log.critical(
                    "STOP — %d crashes rapides consécutifs. Intervention manuelle requise.",
                    MAX_FAST_CRASHES,
                )
                send_telegram(
                    f"🚨 *WATCHDOG ARRÊTÉ*\n"
                    f"{MAX_FAST_CRASHES} crashes en < {FAST_CRASH_SEC}s chacun.\n"
                    f"Intervention manuelle requise."
                )
                break
        else:
            fast_crashes = 0  # reset si le bot a tenu > 2min

        log.info("Attente %ds avant restart...", RESTART_DELAY)
        try:
            time.sleep(RESTART_DELAY)
        except KeyboardInterrupt:
            log.info("Ctrl+C pendant attente — arrêt.")
            send_telegram("🛑 *Watchdog arrêté* (Ctrl+C)")
            break

        send_telegram(f"🔄 *Restart #{restart_count + 1}* en cours...")


if __name__ == "__main__":
    run_watchdog()
