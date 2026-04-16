"""
TwitterSentimentStrate — Signal de sentiment X/Twitter pour ORACLE v2.

Rôle dans le parlement : vote externe pondéré basé sur le sentiment
crypto en temps réel sur X (ex-Twitter).

Sources :
  - X API v2 via tweepy.AsyncClient (Bearer Token)
  - Recherche : $BTC OR #bitcoin OR "bitcoin price"
  - Fallback : NEUTRAL si API indisponible ou clé absente

Architecture :
  - Cache 5 min pour respecter les rate limits (500k tweets/mois Free)
  - Scoring par dictionnaire bullish/bearish pondéré
  - Pondération par reach (followers → amplification)
  - Volume de tweets → confiance (plus il y a de signal, plus on est sûr)
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("ORACLE.Twitter")

# ── Dictionnaires de sentiment ────────────────────────────────────────────────
_BULLISH_TOKENS = {
    # Momentum fort
    "moon": 3, "ath": 3, "breakout": 3, "parabolic": 3, "explode": 2,
    "rip": 2, "rocket": 3, "pump": 2, "surge": 2, "ripping": 2,
    # Fondamentaux positifs
    "buy": 1, "long": 1, "bull": 2, "bullish": 2, "accumulate": 2,
    "dip": 1, "accumulation": 2, "hodl": 1, "hold": 1, "stack": 1,
    "institutional": 2, "etf": 2, "adoption": 2, "halving": 2,
    # Niveaux techniques
    "support": 1, "bounce": 2, "recovery": 2, "rebound": 2, "higher high": 3,
    "resistance broken": 3, "golden cross": 3, "oversold": 2,
    # Sentiment général
    "green": 1, "gains": 1, "profit": 1, "winning": 1, "rally": 2,
}

_BEARISH_TOKENS = {
    # Momentum fort négatif
    "crash": 3, "dump": 3, "rekt": 3, "liquidation": 3, "capitulation": 3,
    "collapse": 3, "spiral": 2, "freefall": 3, "plunge": 2, "tank": 2,
    # Fondamentaux négatifs
    "sell": 1, "short": 1, "bear": 2, "bearish": 2, "fud": 2,
    "ban": 2, "regulation": 1, "hack": 2, "exploit": 2, "scam": 2,
    "fraud": 2, "ponzi": 2, "bubble": 2, "overvalued": 2,
    # Niveaux techniques
    "resistance": 1, "rejection": 2, "lower low": 3, "death cross": 3,
    "overbought": 2, "breakdown": 3, "support lost": 3, "support broken": 3,
    # Sentiment général
    "red": 1, "loss": 1, "losing": 1, "panic": 2, "correction": 1,
    "pullback": 1, "dip buying failed": 2,
}

_AMPLIFICATION_KEYWORDS = {
    "btc": 1.2, "$btc": 1.5, "bitcoin": 1.1, "#bitcoin": 1.2,
    "satoshi": 1.0, "crypto": 0.8,  # crypto générique = moins pertinent
}

# ── Structures de données ─────────────────────────────────────────────────────

@dataclass
class TweetSignal:
    text: str
    score: float      # positif = bullish, négatif = bearish
    reach: float      # followers_count normalisé
    relevance: float  # pondération par mots-clés BTC


@dataclass
class TwitterSentimentResult:
    direction: str          # "LONG", "SHORT", "NEUTRAL"
    confidence: float       # 0.0 – 1.0
    reasoning: str
    tweet_count: int
    avg_score: float
    bullish_count: int
    bearish_count: int
    cached: bool = False


# ── Strate ────────────────────────────────────────────────────────────────────

class TwitterSentimentStrate:
    """
    Vote parlement basé sur le sentiment X/Twitter pour BTC.

    Utilisé dans cycle_manager.analyze_symbol() pour l'asset BTC.
    Respecte l'interface parliament.Vote (direction + confidence + reasoning).

    Rate limits X API v2 gratuit : ~500 000 tweets/mois → polling 5 min.
    Plan Basic (100$/mois) : accès temps réel complet.
    """

    SEARCH_QUERIES = [
        "$BTC lang:en -is:retweet",
        "#bitcoin lang:en -is:retweet",
        '"bitcoin price" lang:en -is:retweet',
    ]
    CACHE_TTL: int = 300          # 5 minutes
    MAX_TWEETS_PER_QUERY: int = 30
    MIN_TWEETS_FOR_SIGNAL: int = 10
    CONFIDENCE_SCALE: float = 0.8  # plafond de confiance max

    def __init__(self, bearer_token: str = ""):
        self.bearer_token = bearer_token
        self._client = None
        self._available = bool(bearer_token)

        # Cache
        self._last_result: Optional[TwitterSentimentResult] = None
        self._last_fetch: float = 0.0

        if self._available:
            self._init_client()
        else:
            logger.warning("TwitterSentimentStrate: TWITTER_BEARER_TOKEN absent — strate désactivée")

    def _init_client(self) -> None:
        """Initialise le client tweepy AsyncClient (X API v2)."""
        try:
            import tweepy
            self._client = tweepy.AsyncClient(
                bearer_token=self.bearer_token,
                wait_on_rate_limit=False,
            )
            logger.info("TwitterSentimentStrate: client X API v2 initialisé")
        except ImportError:
            logger.error("tweepy non installé — `pip install tweepy`. Strate désactivée.")
            self._available = False
        except Exception as e:
            logger.error(f"TwitterSentimentStrate: erreur init client ({e})")
            self._available = False

    # ── Scoring ───────────────────────────────────────────────────────────────

    @staticmethod
    def _score_tweet(text: str) -> TweetSignal:
        """
        Score un tweet en bullish (+) ou bearish (-).
        Utilise des boundary-checks pour éviter les faux positifs
        (ex. "ath" dans "weather").
        Retourne un TweetSignal avec score ∈ [-10, +10].
        """
        import re
        lower = text.lower()
        score = 0.0
        relevance = 1.0

        def _matches(token: str, text: str) -> bool:
            """True si le token est présent comme mot/expression entière."""
            # Tokens multi-mots (ex: "support broken") → cherche la phrase
            if " " in token:
                return token in text
            # Tokens mono-mot → boundary regex pour éviter les sous-chaînes
            return bool(re.search(r'\b' + re.escape(token) + r'\b', text))

        # Amplification par mots-clés BTC
        for kw, amp in _AMPLIFICATION_KEYWORDS.items():
            if _matches(kw, lower):
                relevance = max(relevance, amp)

        # Tokens bullish
        for token, weight in _BULLISH_TOKENS.items():
            if _matches(token, lower):
                score += weight

        # Tokens bearish
        for token, weight in _BEARISH_TOKENS.items():
            if _matches(token, lower):
                score -= weight

        # Normalisation [-1, +1]
        score = max(-10, min(10, score)) / 10.0

        return TweetSignal(
            text=text[:100],
            score=score * relevance,
            reach=1.0,  # sera mis à jour si on a les métadonnées
            relevance=relevance,
        )

    @staticmethod
    def _normalize_reach(followers: int) -> float:
        """Log-normalise les followers pour éviter l'influence excessive des gros comptes."""
        if followers <= 0:
            return 1.0
        import math
        return min(5.0, 1.0 + math.log10(max(1, followers)))

    # ── Fetch ─────────────────────────────────────────────────────────────────

    async def _fetch_tweets(self) -> list[TweetSignal]:
        """Récupère les tweets récents sur BTC via X API v2."""
        if not self._client:
            return []

        signals: list[TweetSignal] = []

        for query in self.SEARCH_QUERIES[:2]:  # 2 queries max pour économiser le quota
            try:
                import tweepy
                response = await self._client.search_recent_tweets(
                    query=query,
                    max_results=self.MAX_TWEETS_PER_QUERY,
                    tweet_fields=["text", "public_metrics", "author_id"],
                    expansions=["author_id"],
                    user_fields=["public_metrics"],
                )

                if not response or not response.data:
                    continue

                # Map author_id → followers_count
                user_map = {}
                if response.includes and response.includes.get("users"):
                    for user in response.includes["users"]:
                        followers = 0
                        if hasattr(user, "public_metrics") and user.public_metrics:
                            followers = user.public_metrics.get("followers_count", 0)
                        user_map[user.id] = followers

                for tweet in response.data:
                    sig = self._score_tweet(tweet.text)
                    followers = user_map.get(tweet.author_id, 0)
                    sig.reach = self._normalize_reach(followers)
                    signals.append(sig)

            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate limit" in err_str:
                    logger.warning("TwitterSentimentStrate: rate limit X API — cache prolongé")
                    # Prolonge le cache pour éviter de continuer à taper l'API
                    self._last_fetch = time.time() - self.CACHE_TTL + 600  # +10 min
                else:
                    logger.debug(f"TwitterSentimentStrate: erreur fetch ({e})")
                break  # arrêt sur erreur

            await asyncio.sleep(0.5)  # pause entre les requêtes

        return signals

    # ── Analyse ───────────────────────────────────────────────────────────────

    def _compute_result(self, signals: list[TweetSignal]) -> TwitterSentimentResult:
        """Agrège les signaux en un résultat de sentiment."""
        if len(signals) < self.MIN_TWEETS_FOR_SIGNAL:
            return TwitterSentimentResult(
                direction="NEUTRAL",
                confidence=0.0,
                reasoning=f"Pas assez de tweets ({len(signals)} < {self.MIN_TWEETS_FOR_SIGNAL})",
                tweet_count=len(signals),
                avg_score=0.0,
                bullish_count=0,
                bearish_count=0,
            )

        # Moyenne pondérée par reach + relevance
        total_weight = sum(s.reach * s.relevance for s in signals)
        if total_weight == 0:
            return TwitterSentimentResult(
                direction="NEUTRAL", confidence=0.0,
                reasoning="Poids nuls", tweet_count=len(signals),
                avg_score=0.0, bullish_count=0, bearish_count=0,
            )

        avg_score = sum(s.score * s.reach * s.relevance for s in signals) / total_weight

        bullish = [s for s in signals if s.score > 0.05]
        bearish = [s for s in signals if s.score < -0.05]
        neutral_count = len(signals) - len(bullish) - len(bearish)

        # Confiance = |score moyen| × sqrt(n_tweets/50) × ratio signal/bruit
        import math
        n_factor = min(1.0, math.sqrt(len(signals) / 50))
        signal_ratio = (len(bullish) + len(bearish)) / len(signals)
        raw_conf = abs(avg_score) * n_factor * signal_ratio
        confidence = min(self.CONFIDENCE_SCALE, raw_conf)

        if avg_score > 0.1 and confidence > 0.15:
            direction = "LONG"
            reasoning = (
                f"Sentiment bullish: {len(bullish)} tweets haussiers "
                f"({len(bullish)/len(signals):.0%}), "
                f"score={avg_score:+.3f}, {len(signals)} tweets analysés"
            )
        elif avg_score < -0.1 and confidence > 0.15:
            direction = "SHORT"
            reasoning = (
                f"Sentiment bearish: {len(bearish)} tweets baissiers "
                f"({len(bearish)/len(signals):.0%}), "
                f"score={avg_score:+.3f}, {len(signals)} tweets analysés"
            )
        else:
            direction = "NEUTRAL"
            confidence = 0.0
            reasoning = (
                f"Sentiment mixte: {len(bullish)}↑ {len(bearish)}↓ "
                f"{neutral_count}→ | score={avg_score:+.3f}"
            )

        return TwitterSentimentResult(
            direction=direction,
            confidence=confidence,
            reasoning=reasoning,
            tweet_count=len(signals),
            avg_score=avg_score,
            bullish_count=len(bullish),
            bearish_count=len(bearish),
        )

    # ── Interface publique ────────────────────────────────────────────────────

    async def scan(self) -> TwitterSentimentResult:
        """
        Analyse le sentiment Twitter sur BTC.
        Résultat mis en cache 5 minutes pour respecter les rate limits.
        Toujours fail-safe : retourne NEUTRAL en cas d'erreur.
        """
        if not self._available:
            return TwitterSentimentResult(
                direction="NEUTRAL", confidence=0.0,
                reasoning="Strate désactivée (token absent ou tweepy manquant)",
                tweet_count=0, avg_score=0.0, bullish_count=0, bearish_count=0,
            )

        now = time.time()

        # Cache hit
        if self._last_result and (now - self._last_fetch) < self.CACHE_TTL:
            result = TwitterSentimentResult(**{**self._last_result.__dict__, "cached": True})
            logger.debug(
                f"TwitterSentimentStrate: cache hit — "
                f"{self._last_result.direction} ({self._last_result.confidence:.0%}), "
                f"expire dans {int(self.CACHE_TTL - (now - self._last_fetch))}s"
            )
            return result

        # Fetch frais
        try:
            signals = await self._fetch_tweets()
            result = self._compute_result(signals)
            self._last_result = result
            self._last_fetch = now

            logger.info(
                f"TwitterSentimentStrate: {result.direction} "
                f"conf={result.confidence:.0%} | "
                f"{result.bullish_count}↑ {result.bearish_count}↓ "
                f"sur {result.tweet_count} tweets | score={result.avg_score:+.3f}"
            )
            return result

        except Exception as e:
            logger.error(f"TwitterSentimentStrate: erreur inattendue — {e}")
            return TwitterSentimentResult(
                direction="NEUTRAL", confidence=0.0,
                reasoning=f"Erreur interne: {e}",
                tweet_count=0, avg_score=0.0, bullish_count=0, bearish_count=0,
            )

    def generate_parliament_vote(self, result: TwitterSentimentResult):
        """
        Convertit TwitterSentimentResult en Vote pour le parlement.
        Import local pour éviter la circularité.
        """
        try:
            from oracle_v2.brain.parliament import Vote
        except ImportError:
            from brain.parliament import Vote

        return Vote(
            strate_name="TWITTER",
            direction=result.direction,
            confidence=result.confidence,
            reasoning=result.reasoning,
            polymarket_signal=None,
        )

    async def close(self) -> None:
        """Ferme le client HTTP proprement."""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
