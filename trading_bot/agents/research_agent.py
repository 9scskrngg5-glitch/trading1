"""
Agent 2 — Chercheur (Research)
Analyse en profondeur le sentiment, les fondamentaux et les données on-chain.
Apprend la corrélation news → mouvement de prix via la mémoire ML.
Vault : vault/fondamental/
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
import numpy as np

from core.base_agent import BaseAgent
from core.learning_engine import LearningEngine
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient
from models.learning import AgentMemory
from models.signals import FundamentalSignal, SignalType

logger = logging.getLogger(__name__)

CRYPTOPANIC_URL = "https://cryptopanic.com/api/developer/v2/posts/"
NEWSAPI_URL     = "https://newsapi.org/v2/everything"
BINANCE_URL     = "https://api.binance.com/api/v3"
MIN_SCORE       = 12

# Mapping asset → symbole Binance
BINANCE_SYMBOL = {
    "BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
    "BNB": "BNBUSDT", "ADA": "ADAUSDT",
    "EUR": "EURUSDT", "GBP": "GBPUSDT",
}


class ResearchAgent(BaseAgent):
    """
    Agent de recherche fondamentale.

    Apprentissage ML :
    - Corrélation entre score de sentiment et variation de prix réelle (apprise)
    - Pondération adaptative des sources (CryptoPanic vs NewsAPI vs On-Chain)
    - Historique des événements macro et leur impact mesuré
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        learning: LearningEngine,
        config: dict,
    ):
        super().__init__("ResearchAgent", "fondamental", bus, obsidian, config)
        self.learning = learning
        self.memory: AgentMemory = None
        self._http: Optional[httpx.AsyncClient] = None

        # Corrélation apprise : sentiment_score → price_change
        self._sentiment_history: dict[str, list[tuple[float, float]]] = {}

        # Cache Binance : 60s TTL
        self._cg_cache: dict[str, dict]  = {}
        self._cg_ts:    dict[str, float] = {}
        self._cg_ttl = 300.0

        # Semaphore CryptoPanic : max 2 requêtes simultanées (free tier ~5 req/s)
        self._cp_sem = asyncio.Semaphore(2)

        # Devises forex : CryptoPanic est crypto-only, on skip pour ces bases
        self._forex_bases = {"EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "USD"}

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        self.memory   = self.learning.load_memory("ResearchAgent")
        self._http    = httpx.AsyncClient(timeout=25, headers={"User-Agent": "TradingBot/2.0"})
        logger.info(
            "[%s] Mémoire chargée : %d trades analysés",
            self.name, self.memory.total_trades,
        )

    async def cleanup(self) -> None:
        """Ferme le client HTTP proprement."""
        if self._http:
            await self._http.aclose()
            self._http = None
            logger.debug("[%s] Client HTTP fermé", self.name)

    # ── Cycle principal ───────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        # Binance supporte 1200 req/min → on peut lancer tous les assets en parallèle
        tasks = [self._process(asset) for asset in self.config.get("assets", [])]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process(self, asset: str) -> None:
        signal = await self._research(asset)
        if signal:
            await self.bus.publish(CHANNELS["signals_fundamental"], signal.to_dict())
            self._write_vault_note(signal)

    # ── Recherche fondamentale ────────────────────────────────────────────────

    async def _research(self, asset: str) -> Optional[FundamentalSignal]:
        base = asset.split("/")[0].upper()

        # Collecte parallèle multi-sources
        cp_task   = self._fetch_cryptopanic(base)
        nws_task  = self._fetch_newsapi(base)
        cg_task   = self._fetch_binance(base)       # Binance remplace CoinGecko

        cp, news, cg = await asyncio.gather(cp_task, nws_task, cg_task, return_exceptions=True)

        cp   = cp   if isinstance(cp,   list) else []
        news = news if isinstance(news, list) else []
        cg   = cg   if isinstance(cg,   dict) else {}

        all_items = cp + news
        if not all_items and not cg:
            return None

        # Scores par source avec poids adaptatifs ML
        w_cp  = self.memory.adaptive_params.get("weight_cryptopanic", 1.2)
        w_nws = self.memory.adaptive_params.get("weight_newsapi",     0.8)

        score_cp  = self._score_cryptopanic(cp)  * w_cp
        score_nws = self._score_lexical(news)    * w_nws
        score_cg  = self._score_onchain(cg)

        # Score composite
        n_sources = sum([bool(cp), bool(news), bool(cg)])
        raw_score = (score_cp + score_nws + score_cg) / max(n_sources, 1)

        # Correction via la corrélation apprise
        corr = self._learned_correlation(asset, raw_score)
        final_score = int(max(-100, min(100, raw_score * corr)))

        signal = (
            SignalType.BULLISH if final_score >  MIN_SCORE else
            SignalType.BEARISH if final_score < -MIN_SCORE else
            SignalType.NEUTRAL
        )
        confidence = min(abs(final_score), 100)

        key_events = [
            (item.get("title") or item.get("headline", ""))[:120]
            for item in all_items[:8]
        ]

        return FundamentalSignal(
            asset           = asset,
            sentiment_score = final_score,
            signal          = signal,
            confidence      = confidence,
            news_count      = len(all_items),
            key_events      = [e for e in key_events if e],
            onchain_metrics = cg if cg else None,
        )

    # ── Sources de données ────────────────────────────────────────────────────

    async def _fetch_cryptopanic(self, currency: str) -> list[dict]:
        token = self.config.get("cryptopanic_token", "")
        # CryptoPanic = news crypto uniquement → skip les devises forex
        if not token or currency in self._forex_bases:
            return []
        async with self._cp_sem:          # max 2 requêtes simultanées
            try:
                r = await self._http.get(CRYPTOPANIC_URL, params={
                    "auth_token": token,
                    "currencies": currency,
                    "kind":       "news",
                    "public":     "true",
                    "limit":      20,
                }, timeout=8.0)
                if r.status_code == 429:
                    logger.debug("[%s] CryptoPanic 429 sur %s", self.name, currency)
                    return []
                if r.status_code != 200:
                    logger.debug("[%s] CryptoPanic HTTP %d sur %s", self.name, r.status_code, currency)
                    return []
                results = r.json().get("results", [])
                logger.debug("[%s] CryptoPanic %s → %d articles", self.name, currency, len(results))
                return results
            except Exception as exc:
                logger.debug("[%s] CryptoPanic error: %s", self.name, exc)
                return []

    async def _fetch_newsapi(self, currency: str) -> list[dict]:
        key = self.config.get("newsapi_key", "")
        if not key:
            return []
        try:
            r = await self._http.get(NEWSAPI_URL, params={
                "q": f"{currency} crypto OR market OR trading",
                "language": "en", "sortBy": "publishedAt",
                "pageSize": 15, "apiKey": key,
            })
            return r.json().get("articles", [])
        except Exception:
            return []

    async def _fetch_binance(self, currency: str) -> dict:
        """
        Données marché temps réel via Binance REST public (1200 req/min, pas de clé nécessaire).
        Remplace CoinGecko pour éviter les 429 en simulation.
        Retourne: price, volume_24h, price_change_24h_pct, high/low 24h, nb trades.
        """
        import time
        symbol = BINANCE_SYMBOL.get(currency)
        if not symbol:
            return {}

        # Cache 60s — Binance peut supporter des appels plus fréquents mais inutile
        now = time.monotonic()
        if currency in self._cg_cache and (now - self._cg_ts.get(currency, 0)) < 60.0:
            return self._cg_cache[currency]

        try:
            r = await self._http.get(
                f"{BINANCE_URL}/ticker/24hr",
                params={"symbol": symbol},
                timeout=5.0,
            )
            r.raise_for_status()
            d = r.json()

            result = {
                "price_usd":            float(d.get("lastPrice",         0)),
                "volume_24h":           float(d.get("quoteVolume",       0)),   # USDT
                "price_change_24h_pct": float(d.get("priceChangePercent", 0)),
                "high_24h":             float(d.get("highPrice",         0)),
                "low_24h":              float(d.get("lowPrice",          0)),
                "trade_count":          int(d.get("count",              0)),
                # Champ de compatibilité avec _score_onchain
                "price_change_7d_pct":  None,   # non disponible sur ce endpoint
                "sentiment_votes_up":   None,
                "sentiment_votes_down": None,
            }
            self._cg_cache[currency] = result
            self._cg_ts[currency]    = now
            logger.debug(
                "[%s] Binance %s → $%s | Δ24h: %s%% | vol: $%sM",
                self.name, currency, result["price_usd"],
                round(result["price_change_24h_pct"], 2),
                round(result["volume_24h"] / 1_000_000, 1),
            )
            return result
        except Exception as exc:
            logger.debug("[%s] Binance ticker error sur %s: %s", self.name, currency, exc)
            return self._cg_cache.get(currency, {})

    # ── Scoring multi-source ──────────────────────────────────────────────────

    @staticmethod
    def _score_cryptopanic(items: list[dict]) -> float:
        if not items:
            return 0.0
        score = 0.0
        for item in items:
            v = item.get("votes", {})
            # v2 API : "disliked" (v1 utilisait "dislike")
            pos = v.get("positive", 0) + v.get("liked", 0) + v.get("lol", 0)
            neg = v.get("negative", 0) + v.get("disliked", 0) + v.get("dislike", 0) + v.get("toxic", 0)
            score += (pos - neg) * 4
        return max(-100, min(100, score / len(items) * 10))

    @staticmethod
    def _score_lexical(items: list[dict]) -> float:
        BULL = {"surge","rally","bull","breakout","ath","adoption","upgrade","gain","soar","growth","record","buy","accumulate"}
        BEAR = {"crash","bear","drop","fall","hack","ban","fraud","selloff","dump","fear","panic","decline","warning","sell"}
        if not items:
            return 0.0
        score = 0.0
        for item in items:
            title = (item.get("title") or "").lower()
            words = set(title.split())
            score += len(words & BULL) * 6 - len(words & BEAR) * 6
        return max(-100, min(100, score / len(items)))

    @staticmethod
    def _score_onchain(cg: dict) -> float:
        if not cg:
            return 0.0
        score = 0.0
        p24h = cg.get("price_change_24h_pct")
        p7d  = cg.get("price_change_7d_pct")
        sup  = cg.get("sentiment_votes_up")
        sdn  = cg.get("sentiment_votes_down")

        if p24h:  score += np.clip(p24h * 2, -30, 30)
        if p7d:   score += np.clip(p7d  * 1, -20, 20)
        if sup and sdn:
            score += (sup - sdn) * 0.5

        return float(np.clip(score, -100, 100))

    def _learned_correlation(self, asset: str, raw_score: float) -> float:
        """
        Facteur de correction basé sur la corrélation historique
        sentiment → prix réel pour cet asset.
        Retourne 1.0 si pas encore de données.
        """
        history = self._sentiment_history.get(asset, [])
        if len(history) < 5:
            return 1.0

        sentiments = np.array([h[0] for h in history[-30:]])
        pnls       = np.array([h[1] for h in history[-30:]])

        # Corrélation de Pearson
        if sentiments.std() < 1e-6 or pnls.std() < 1e-6:
            return 1.0

        corr = float(np.corrcoef(sentiments, pnls)[0, 1])

        # Si corrélation forte → renforcer, si faible → modérer
        return max(0.5, min(1.5, 1.0 + corr * 0.3))

    def register_outcome(self, asset: str, sentiment_at_signal: float, actual_pnl: float):
        """Appelé par LearningEngine après clôture d'un trade."""
        self._sentiment_history.setdefault(asset, []).append(
            (sentiment_at_signal, actual_pnl)
        )
        # Adapter le poids des sources selon la corrélation
        history = self._sentiment_history[asset]
        if len(history) >= 10:
            recent = history[-20:]
            corr   = np.corrcoef([h[0] for h in recent], [h[1] for h in recent])[0, 1]
            logger.info(
                "[%s] Corrélation sentiment→prix sur %s : %.2f",
                self.name, asset, corr,
            )

    # ── Vault Obsidian — notes financières enrichies ──────────────────────────

    def _write_vault_note(self, signal: FundamentalSignal) -> None:
        filename = self.obsidian.daily_filename("research", signal.asset)

        cg = signal.onchain_metrics or {}
        ast_stats = self.memory.asset_stats.get(signal.asset, {})
        corr = self._learned_correlation(signal.asset, signal.sentiment_score)

        score_icon = (
            "🟢 Positif" if signal.sentiment_score > 20 else
            "🔴 Négatif" if signal.sentiment_score < -20 else
            "🟡 Neutre"
        )
        events_md = "\n".join(f"- {e}" for e in signal.key_events) or "- Aucun événement majeur"

        # On-chain data
        onchain_md = ""
        if cg:
            onchain_md = f"""
### Données On-Chain (CoinGecko)
| Métrique | Valeur |
|---|---|
| Prix USD | `${cg.get('price_usd', '—'):,}` |
| Market Cap | `${cg.get('market_cap_usd', 0):,.0f}` |
| Volume 24h | `${cg.get('volume_24h', 0):,.0f}` |
| Variation 24h | `{cg.get('price_change_24h_pct', 0):+.2f}%` |
| Variation 7j | `{cg.get('price_change_7d_pct', 0):+.2f}%` |
| % du ATH | `{cg.get('ath_change_pct', 0):.1f}%` |
| Votes Bullish | `{cg.get('sentiment_votes_up', '—')}%` |
"""

        frontmatter = self._build_frontmatter(
            asset=signal.asset, signal_type=signal.signal.value,
            confidence=signal.confidence,
            extra={
                "sentiment_score": signal.sentiment_score,
                "news_count":      signal.news_count,
                "corr_factor":     round(corr, 3),
            },
        )

        content = f"""## Recherche Fondamentale — {signal.asset}

### Score de Sentiment Composite
**{signal.sentiment_score:+d} / 100** — {score_icon}
- Sources analysées : **{signal.news_count}**
- Facteur de corrélation appris : **{corr:.2f}** ({'fiable' if corr > 1.1 else 'à calibrer' if corr < 0.8 else 'normal'})
{onchain_md}
### Événements Clés Détectés
{events_md}

### Performance Historique (mémoire ML)
| Métrique | Valeur |
|---|---|
| Trades sur cet asset | `{ast_stats.get('total', 0)}` |
| Win rate observé | `{ast_stats.get('wins', 0) / max(ast_stats.get('total', 1), 1):.0%}` |
| P&L moyen (EMA) | `{ast_stats.get('pnl_pct', 0):+.3f}%` |

### Poids Sources Adaptatifs
| Source | Poids appris |
|---|---|
| CryptoPanic | `{self.memory.adaptive_params.get('weight_cryptopanic', 1.2):.2f}` |
| NewsAPI | `{self.memory.adaptive_params.get('weight_newsapi', 0.8):.2f}` |
| On-Chain | `1.00` (fixe) |

### Conclusion
> **{signal.signal.value.upper()}** — Confiance : {signal.confidence}/100

### Liens
{self.obsidian.wikilink('decisions', self.obsidian.timestamp_filename('predict', signal.asset))}
{self.obsidian.wikilink('config', 'ResearchAgent_memory')}
"""
        self.obsidian.write_note("fondamental", filename, frontmatter, content)
        logger.info(
            "[%s] 🔍 %s → sentiment %+d | %s (%d/100) [corr=%.2f]",
            self.name, signal.asset, signal.sentiment_score,
            signal.signal.value, signal.confidence, corr,
        )
