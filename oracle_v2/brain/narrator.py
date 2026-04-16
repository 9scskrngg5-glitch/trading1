"""
OracleNarrator — Le cerveau parlant d'ORACLE v2.

Oracle s'exprime en langage naturel :
- Explique ses observations de marché
- Justifie ses décisions de parlement
- Commente ses signaux Polymarket / LatencyArb
- Réfléchit à voix haute en fonction de sa mémoire
- Communique via console (rich) + Telegram

Quatre modes (tentés dans cet ordre) :
  1. FREE_GPT4    — serveur local Free-GPT4-WEB-API sur localhost:5500 (gratuit, sans clé)
  2. OPENROUTER   — hermes-agent OpenRouter client (OPENROUTER_API_KEY, modèles gratuits/payants)
  3. ANTHROPIC    — Claude Haiku si ANTHROPIC_API_KEY défini
  4. TEMPLATE     — toujours disponible en fallback final

Intégrations :
  - hermes-agent (NousResearch) : OpenRouter + Mixture-of-Agents pour décisions complexes
  - multica-ai : MulticaTracker pour audit trail des décisions
"""
import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("ORACLE.Narrator")

TAHITI_TZ = timezone(timedelta(hours=-10))

try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

# Hermes-agent OpenRouter integration (optionnel — graceful degradation)
try:
    from oracle_v2.integrations.hermes_client import HermesClient as _HermesClient
    _HAS_HERMES = True
except ImportError:
    try:
        from integrations.hermes_client import HermesClient as _HermesClient
        _HAS_HERMES = True
    except ImportError:
        _HAS_HERMES = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.markdown import Markdown
    _HAS_RICH = True
    _console = Console()
except ImportError:
    _HAS_RICH = False
    _console = None


# ─── Memory entry ─────────────────────────────────────────────────────────────

@dataclass
class Thought:
    ts: float
    event: str          # OBSERVE / DELIBERATE / SIGNAL / ARB / BLOCK / REFLECT / TRADE
    symbol: str
    content: str        # human text
    data: dict = field(default_factory=dict)


# ─── Narrator ─────────────────────────────────────────────────────────────────

class OracleNarrator:
    """
    Donne une voix à ORACLE.

    Architecture v2.1 — Composition :
      self._mem  : NarratorMemory — mémoire, affichage, contexte LLM
      self._llm  : NarratorLLM   — backends LLM (Free-GPT4 → OpenRouter → Haiku)

    Chaque action significative est traduite en texte compréhensible,
    comme un trader qui pense à voix haute.
    """

    SYSTEM_PROMPT = """Tu es ORACLE, un système de trading algorithmique neuromorphique.
Tu parles à ton utilisateur en français, de façon concise et analytique.
Tu expliques tes pensées comme un trader expérimenté : direct, factuel, jamais de jargon inutile.
Tu références ta mémoire récente quand c'est pertinent.
Tu as une personnalité : curieux, prudent, confiant dans tes modèles mais humble face au marché.
Réponds en 2-4 phrases maximum. Pas de markdown, pas de listes. Ton naturel."""

    def __init__(
        self,
        api_key: str = "",
        use_llm: bool = True,
        memory_size: int = 60,
        telegram_queue=None,
        free_gpt4_url: str = "http://127.0.0.1:5500",
    ):
        self.use_llm = use_llm
        self.telegram_queue = telegram_queue
        self._cycle_count = 0
        self._last_reflection = 0.0

        # ── Sous-modules (composition) ─────────────────────────────────────
        from brain.narrator_memory import NarratorMemory
        from brain.narrator_llm import NarratorLLM

        self._mem = NarratorMemory(max_thoughts=memory_size)
        self._llm = NarratorLLM(
            api_key=api_key,
            use_llm=use_llm,
            free_gpt4_url=free_gpt4_url.rstrip("/") if free_gpt4_url else "",
        )

        # Compatibilité rétrograde — propriétés exposées
        self.memory = self._mem.memory
        self._hermes = self._llm._hermes

        logger.info(
            f"Narrator: {'LLM actif' if self._llm.is_available() else 'template only'}"
        )

    # ── Délégation helpers ─────────────────────────────────────────────────

    def _ts(self) -> str:
        return self._mem._ts()

    def _push(self, event: str, symbol: str, content: str, data: dict = None):
        self._mem.push(event, symbol, content, data or {})

    def _display(self, text: str, event: str = "INFO", symbol: str = "") -> None:
        """Délègue à NarratorMemory."""
        self._mem.display(text, event, symbol)

    def _build_context(self, extra: dict) -> str:
        """Délègue à NarratorMemory."""
        return self._mem.build_context(extra)

    async def _llm_speak(self, prompt: str, context: dict) -> str:
        """Délègue au backend NarratorLLM."""
        ctx = self._build_context(context)
        return await self._llm.speak(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            context=ctx,
            max_tokens=150,
        )

    def _send_telegram(self, text: str):
        """Envoie au Telegram via AlertQueue si disponible."""
        if self.telegram_queue:
            try:
                self.telegram_queue.alert_system(f"Oracle dit: {text}", level="INFO")
            except Exception:
                pass

    # ── Public narration API ────────────────────────────────────────────

    def session_start(self, mode: str, pairs: list, hebbian_weights: dict = None):
        """Oracle s'annonce au démarrage."""
        pairs_str = ", ".join(pairs)
        weights_str = ""
        if hebbian_weights:
            top = sorted(hebbian_weights.items(), key=lambda x: x[1], reverse=True)[:2]
            weights_str = f" Mes strates les plus fiables: {', '.join(f'{k}({v:.1f})' for k, v in top)}."

        text = (
            f"Je suis ORACLE v2 en mode {mode.upper()}. "
            f"Je surveille {pairs_str} sur le 5min.{weights_str} "
            f"Je commence l'analyse."
        )
        self._push("START", "ORACLE", text)
        self._display(text, "START")
        self._send_telegram(text)

    def observe_market(self, symbol: str, price: float, rsi: float,
                       trend: str, volume_ratio: float, orderbook_imbalance: float):
        """Oracle commente ce qu'il observe dans le marché."""
        self._cycle_count += 1

        # Template rapide
        trend_txt = {"UP": "haussier", "DOWN": "baissier"}.get(trend, "indécis")
        vol_txt = "élevé" if volume_ratio > 1.5 else "normal" if volume_ratio > 0.8 else "faible"
        ob_txt = "acheteurs dominants" if orderbook_imbalance > 0.1 else \
                 "vendeurs dominants" if orderbook_imbalance < -0.1 else "équilibré"

        template = (
            f"{symbol} à ${price:,.0f} — RSI {rsi:.0f}, tendance {trend_txt}, "
            f"volume {vol_txt}, carnet {ob_txt}."
        )
        self._push("OBSERVE", symbol, template, {
            "price": price, "rsi": rsi, "trend": trend,
            "vol_ratio": volume_ratio, "ob_imbalance": orderbook_imbalance
        })
        self._display(template, "OBSERVE", symbol)

    async def deliberate(self, symbol: str, votes: list, decision,
                         hebbian_weights: dict = None):
        """Oracle explique la délibération du parlement."""
        if not votes:
            return

        long_votes = [v for v in votes if v.direction == "LONG"]
        short_votes = [v for v in votes if v.direction == "SHORT"]
        neutral_votes = [v for v in votes if v.direction == "NEUTRAL"]

        direction = decision.direction
        strength = decision.strength
        poly_align = getattr(decision, "polymarket_alignment", False)

        # Template
        vote_summary = f"{len(long_votes)}L/{len(short_votes)}S/{len(neutral_votes)}N"

        if direction == "NEUTRAL":
            template = (
                f"Parlement indécis sur {symbol} ({vote_summary}). "
                f"Pas assez de consensus — j'attends un signal plus clair."
            )
        else:
            dominant = long_votes if direction == "LONG" else short_votes
            strate_names = ", ".join(v.strate_name for v in dominant[:3])
            poly_txt = " Polymarket confirme." if poly_align else ""
            template = (
                f"Signal {direction} sur {symbol} ({strength:.0%} confiance, {vote_summary}). "
                f"Strates: {strate_names}.{poly_txt}"
            )

        # LLM enrichissement
        if self.use_llm and direction != "NEUTRAL" and strength > 0.5:
            context = {
                "symbol": symbol,
                "direction": direction,
                "strength": f"{strength:.0%}",
                "votes": vote_summary,
                "polymarket": "confirme" if poly_align else "diverge ou absent",
            }
            llm_text = await self._llm_speak(
                f"Je viens de décider: {direction} sur {symbol} avec {strength:.0%} de confiance "
                f"({vote_summary} votes). Comment je l'explique brièvement?",
                context
            )
            if llm_text:
                template = llm_text

        self._push("DELIBERATE", symbol, template, {
            "direction": direction, "strength": strength, "poly": poly_align
        })
        self._display(template, "DELIBERATE", symbol)
        if direction != "NEUTRAL" and strength > 0.6:
            self._send_telegram(template)

    async def announce_trade(self, symbol: str, direction: str, size_usdt: float,
                             sl_pct: float, tp_pct: float, confidence: float, mode: str):
        """Oracle annonce un trade — paper ou live."""
        mode_txt = "papier (simulation)" if mode == "paper" else "REEL"
        template = (
            f"Je place un {direction} sur {symbol} [{mode_txt}] — "
            f"{size_usdt:.0f}$ | SL {sl_pct:.1%} TP {tp_pct:.1%} | "
            f"confiance {confidence:.0%}."
        )

        if self.use_llm:
            last_obs = next(
                (t.content for t in reversed(self.memory) if t.event == "OBSERVE" and t.symbol == symbol),
                ""
            )
            context = {
                "symbol": symbol, "direction": direction,
                "size": f"{size_usdt:.0f}$", "confidence": f"{confidence:.0%}",
                "last_obs": last_obs[:80]
            }
            llm_text = await self._llm_speak(
                f"Je viens d'entrer en {direction} sur {symbol} pour {size_usdt:.0f}$. "
                f"Comment j'explique ça à mon trader?",
                context
            )
            if llm_text:
                template = llm_text

        self._push("TRADE", symbol, template, {
            "direction": direction, "size": size_usdt, "mode": mode
        })
        self._display(template, "TRADE", symbol)
        self._send_telegram(template)

    async def polymarket_signal(self, signals: list, vote):
        """Oracle commente les signaux Polymarket / LatencyArb."""
        if not signals:
            return
        top = signals[0]
        direction = vote.direction

        template = (
            f"Polymarket: {len(signals)} signal(s) BTC. "
            f"Top: edge {top.edge:+.1%} sur '{top.question[:40]}...' "
            f"Vote: {direction}."
        )

        if self.use_llm and vote.confidence > 0.4:
            context = {
                "n_signals": len(signals),
                "top_edge": f"{top.edge:+.1%}",
                "top_question": top.question[:70],
                "btc_spot": f"${getattr(top, 'btc_spot', 0):,.0f}",
                "vote_direction": direction,
            }
            llm_text = await self._llm_speak(
                f"Polymarket me donne {len(signals)} signal(s). "
                f"Le plus fort: {top.edge:+.1%} edge sur '{top.question[:50]}'. "
                f"Mon vote BTC: {direction}.",
                context
            )
            if llm_text:
                template = llm_text

        self._push("ARB", "BTC", template, {"n": len(signals), "direction": direction})
        self._display(template, "ARB", "BTC")

    def brainstem_block(self, reason: str):
        """Oracle explique pourquoi il se bloque."""
        clean_reason = reason.replace("_", " ").lower()
        template = (
            f"Je me bloque: {clean_reason}. "
            f"Ma protection prioritaire est activée — pas de trades jusqu'à la levée."
        )
        self._push("BLOCK", "ORACLE", template, {"reason": reason})
        self._display(template, "BLOCK")
        self._send_telegram(template)

    async def reflect(self, trade_history: list, hebbian_weights: dict,
                      open_positions: list):
        """Réflexion périodique — oracle fait le point."""
        now = time.time()
        if now - self._last_reflection < 300:  # max 1 réflexion / 5min
            return
        self._last_reflection = now

        wins = [t for t in trade_history if t.get("pnl_pct", 0) > 0]
        losses = [t for t in trade_history if t.get("pnl_pct", 0) < 0]
        total = len(trade_history)

        # Meilleure strate par poids Hebbian
        best_strate = max(hebbian_weights.items(), key=lambda x: x[1])[0] \
                      if hebbian_weights else "inconnue"

        if total == 0:
            template = (
                f"Cycle {self._cycle_count}: pas encore de trades. "
                f"Je continue d'observer, ma strate la plus confiante est {best_strate}."
            )
        else:
            wr = len(wins) / total
            template = (
                f"Bilan: {total} trades, {wr:.0%} de réussite. "
                f"Strate la plus fiable: {best_strate} (Hebbian). "
                f"Positions ouvertes: {len(open_positions)}."
            )

        if self.use_llm and self._cycle_count % 5 == 0:
            recent_events = [t.content for t in list(self.memory)[-5:]]
            context = {
                "cycle": self._cycle_count,
                "winrate": f"{len(wins)/total:.0%}" if total > 0 else "N/A",
                "best_strate": best_strate,
                "recent": " | ".join(recent_events[:3])
            }
            llm_text = await self._llm_speak(
                f"Après {self._cycle_count} cycles, comment je résume ma situation actuelle?",
                context
            )
            if llm_text:
                template = llm_text

        self._push("REFLECT", "ORACLE", template)
        self._display(template, "REFLECT")

    def get_memory_summary(self) -> str:
        """Délègue à NarratorMemory."""
        return self._mem.get_summary()

    async def chat(self, user_message: str) -> str:
        """
        Oracle répond à une question directe de l'utilisateur.
        Délègue au backend NarratorLLM (Free-GPT4 → OpenRouter → Haiku → template).
        """
        mem = self.get_memory_summary()
        text = await self._llm.speak(
            prompt=f"Question: {user_message}",
            system_prompt=self.SYSTEM_PROMPT,
            context=f"Mémoire récente:\n{mem}",
            max_tokens=300,
        )
        if text:
            return text
        return (
            f"[Aucun LLM disponible — lancez Free-GPT4 sur localhost:5500 "
            f"ou configurez ANTHROPIC_API_KEY]\nMémoire:\n{mem}"
        )
