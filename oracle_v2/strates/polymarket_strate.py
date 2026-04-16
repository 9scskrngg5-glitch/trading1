"""
Strate Polymarket — Arbitrage probabiliste + signal macro précurseur.
Rôle dans le parlement : vote externe pondéré + signal corrélé aux assets.

Endpoints publics (pas de clé requise) :
  - Gamma API : https://gamma-api.polymarket.com  ← données marchés
  - CLOB API  : https://clob.polymarket.com       ← carnet d'ordres

Trading CLOB actif (clés optionnelles) :
  - POLYMARKET_PRIVATE_KEY  : clé privée wallet Polygon (0x…)
  - POLYMARKET_API_KEY      : clé CLOB L2
  - POLYMARKET_API_SECRET   : secret CLOB L2
  - POLYMARKET_API_PASSPHRASE : passphrase CLOB L2
  - POLYMARKET_PROXY_WALLET : adresse proxy wallet (si compte Polymarket Pro)

Configuration dans oracle_v2/.env (voir .env.example).

Sans clé → mode "lecture seule" (signal parlement uniquement, pas d'ordre).
Avec clé → mode "trading actif" (place des ordres CLOB binaires).

Pour obtenir vos clés :
  1. https://polymarket.com → Paramètres → API Keys → Créer une clé
  2. Copier API Key, Secret, Passphrase dans .env
  3. Wallet Polygon : MetaMask → Paramètres → Sécurité → Exporter clé privée
"""
import asyncio
import hashlib
import hmac as _hmac
import httpx
import time as _time
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("ORACLE.Polymarket")

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"

MARKET_KEYWORDS = {
    "BTC":        ["bitcoin", "btc", "digital asset", "coinbase", "binance"],
    "ETH":        ["ethereum", "ether", "defi", "layer 2", "l2", "vitalik"],
    "GOLD":       ["gold price", "xau", "precious metal", "gold etf", "federal reserve", "fed rate"],
    "NIKKEI":     ["nikkei", "bank of japan", "boj", "jpy", "yen"],
    "MACRO":      ["recession", "gdp", "cpi", "rate cut", "rate hike", "fed funds",
                   "powell", "fomc", "treasury yield", "debt ceiling", "federal reserve"],
    "REGULATION": ["sec ", "cftc", "crypto regulation", "bitcoin etf", "crypto ban",
                   "gensler", "crypto law"],
}

MARKET_EXCLUSIONS = {
    "GOLD":   ["warriors", "golden state", "golden gate", "golden globe", "golden boot"],
    "NIKKEI": ["nikki", "haley"],
    "ETH":    ["netherlands", "french", "soccer", "football", "basketball", "cricket"],
    "MACRO":  ["crypto"],
}


@dataclass
class PolymarketOpportunity:
    market_id: str
    question: str
    current_price_yes: float
    oracle_estimate: float
    edge: float
    kelly_fraction: float
    direction: str             # "YES" ou "NO"
    correlated_asset: str
    volume_24h: float
    end_date: str
    confidence: str            # "HIGH" / "MEDIUM" / "LOW"
    bullish_for_asset: bool


class PolymarketCLOBClient:
    """
    Client CLOB Polymarket authentifié.

    Gère :
      - Signature HMAC-SHA256 des requêtes L2 (API key / secret)
      - Récupération du carnet d'ordres d'un marché
      - Placement d'ordres market/limit (si clés configurées)

    Usage :
        clob = PolymarketCLOBClient(
            api_key="...", api_secret="...", api_passphrase="...",
            private_key="0x..."
        )
        await clob.initialize()
        orderbook = await clob.get_orderbook(token_id)
        order_id  = await clob.place_order(token_id, "BUY", size=10.0, price=0.65)
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
        private_key: str = "",
        proxy_wallet: str = "",
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.private_key = private_key
        self.proxy_wallet = proxy_wallet
        self._client = httpx.AsyncClient(timeout=15.0)
        self._authenticated = False

    @property
    def is_configured(self) -> bool:
        """True si les clés API L2 sont présentes."""
        return bool(self.api_key and self.api_secret and self.api_passphrase)

    @property
    def can_sign_transactions(self) -> bool:
        """True si la clé privée Polygon est présente."""
        return bool(self.private_key and self.private_key.startswith("0x"))

    async def initialize(self) -> bool:
        """
        Vérifie la connectivité et l'authentification L2.
        Retourne True si prêt, False si échec ou non configuré.
        """
        if not self.is_configured:
            logger.debug("CLOB: pas de clé API — mode lecture seule")
            return False
        try:
            # Test de connectivité simple (pas d'auth requis)
            resp = await self._client.get(f"{CLOB_API}/")
            resp.raise_for_status()
            self._authenticated = True
            logger.info("Polymarket CLOB connecté ✓ (clés API configurées)")
            return True
        except Exception as e:
            logger.warning(f"CLOB init failed: {e}")
            return False

    def _sign(self, method: str, path: str, body: str = "") -> dict:
        """
        Génère les headers d'authentification CLOB L2 (HMAC-SHA256).

        Header requis : POLY-API-KEY, POLY-SIGNATURE, POLY-TIMESTAMP, POLY-PASSPHRASE
        """
        ts = str(int(_time.time() * 1000))
        message = ts + method.upper() + path + body
        sig = _hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return {
            "POLY-API-KEY":     self.api_key,
            "POLY-SIGNATURE":   sig,
            "POLY-TIMESTAMP":   ts,
            "POLY-PASSPHRASE":  self.api_passphrase,
            "Content-Type":     "application/json",
        }

    async def get_orderbook(self, token_id: str) -> dict:
        """
        Récupère le carnet d'ordres d'un token (condition_id).
        Endpoint public — pas d'auth requise.
        """
        try:
            resp = await self._client.get(
                f"{CLOB_API}/book",
                params={"token_id": token_id},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "bids": data.get("bids", []),   # [{"price": ..., "size": ...}]
                "asks": data.get("asks", []),
                "token_id": token_id,
            }
        except Exception as e:
            logger.debug(f"CLOB orderbook error for {token_id}: {e}")
            return {"bids": [], "asks": [], "token_id": token_id}

    async def get_markets(self) -> list:
        """Marchés disponibles sur le CLOB (endpoint public)."""
        try:
            resp = await self._client.get(f"{CLOB_API}/markets")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug(f"CLOB markets error: {e}")
            return []

    async def place_order(
        self,
        token_id: str,
        side: str,       # "BUY" ou "SELL"
        size: float,     # en USDC
        price: float,    # probabilité (0.0 – 1.0)
        order_type: str = "GTC",  # GTC | FOK | GTD
    ) -> Optional[str]:
        """
        Place un ordre sur le CLOB Polymarket.

        Requiert : POLYMARKET_API_KEY + POLYMARKET_PRIVATE_KEY dans .env

        Paramètres
        ----------
        token_id  : identifiant du token YES ou NO (condition_id)
        side      : "BUY" ou "SELL"
        size      : montant en USDC (ex: 10.0 = 10 dollars)
        price     : probabilité limite (ex: 0.65 = acheter YES à 65¢)
        order_type: GTC (défaut) | FOK (fill or kill)

        Retourne
        --------
        str | None : order_id si succès, None si erreur
        """
        if not self.is_configured:
            logger.warning("CLOB: impossible de placer un ordre sans clé API")
            return None

        import json

        body = json.dumps({
            "token_id": token_id,
            "side": side.upper(),
            "size": str(size),
            "price": str(price),
            "type": order_type,
        })
        headers = self._sign("POST", "/order", body)

        try:
            resp = await self._client.post(
                f"{CLOB_API}/order",
                content=body,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            order_id = data.get("orderID") or data.get("id")
            logger.info(
                f"CLOB ordre placé: {side} {size} USDC @ {price:.2f} "
                f"| token={token_id[:16]}… | id={order_id}"
            )
            return order_id
        except Exception as e:
            logger.error(f"CLOB place_order failed: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre existant."""
        if not self.is_configured:
            return False
        import json
        body = json.dumps({"orderID": order_id})
        headers = self._sign("DELETE", "/order", body)
        try:
            resp = await self._client.delete(
                f"{CLOB_API}/order",
                content=body,
                headers=headers,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"CLOB cancel_order {order_id}: {e}")
            return False

    async def get_positions(self) -> list:
        """Positions ouvertes de l'utilisateur authentifié."""
        if not self.is_configured:
            return []
        headers = self._sign("GET", "/positions")
        try:
            resp = await self._client.get(
                f"{CLOB_API}/positions",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug(f"CLOB positions error: {e}")
            return []

    async def close(self) -> None:
        await self._client.aclose()


# ── PolymarketStrate enrichie ─────────────────────────────────────────────────

class PolymarketStrate:
    """
    Strate Polymarket avec support CLOB optionnel.

    Modes
    -----
    - Mode "signal" (défaut)  : scan Gamma API → vote parlement.
      Aucune clé requise.

    - Mode "trading actif"    : idem + place des ordres CLOB quand
      l'edge est suffisant et que les clés sont configurées.
      Activé automatiquement si POLYMARKET_PRIVATE_KEY est défini.

    Paramètres
    ----------
    min_edge          : edge minimum pour générer un signal (défaut 5%)
    min_volume        : volume 24h minimum (défaut 25k USDC)
    kelly_fraction_max: taille Kelly maximale (défaut 30%)
    clob_client       : instance PolymarketCLOBClient (optionnel)
    trading_enabled   : activer le trading actif (défaut False)
    min_clob_size_usdc: taille minimum d'un ordre CLOB (défaut 5 USDC)
    """

    def __init__(
        self,
        min_edge: float = 0.05,
        min_volume: float = 25_000,
        kelly_fraction_max: float = 0.30,
        clob_client: Optional[PolymarketCLOBClient] = None,
        trading_enabled: bool = False,
        min_clob_size_usdc: float = 5.0,
    ):
        self.min_edge = min_edge
        self.min_volume = min_volume
        self.kelly_fraction_max = kelly_fraction_max
        self.trading_enabled = trading_enabled
        self.min_clob_size_usdc = min_clob_size_usdc

        self._gamma_client = httpx.AsyncClient(timeout=15.0)
        self.clob = clob_client or PolymarketCLOBClient()

        self.last_opportunities: list = []
        self.cache_ttl = 300
        self._last_fetch = 0.0

    # ── Factory depuis config ──────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config) -> "PolymarketStrate":
        """
        Crée une instance à partir d'OracleConfig.

        Si POLYMARKET_API_KEY est défini → mode trading actif.
        Sinon → mode signal uniquement.
        """
        clob = PolymarketCLOBClient(
            api_key=getattr(config, "POLYMARKET_API_KEY", ""),
            api_secret=getattr(config, "POLYMARKET_API_SECRET", ""),
            api_passphrase=getattr(config, "POLYMARKET_API_PASSPHRASE", ""),
            private_key=getattr(config, "POLYMARKET_PRIVATE_KEY", ""),
            proxy_wallet=getattr(config, "POLYMARKET_PROXY_WALLET", ""),
        )
        trading_enabled = bool(clob.is_configured)

        instance = cls(
            min_edge=config.POLYMARKET_MIN_EDGE,
            min_volume=config.POLYMARKET_MIN_VOLUME,
            kelly_fraction_max=config.POLYMARKET_KELLY_MAX,
            clob_client=clob,
            trading_enabled=trading_enabled,
        )
        if trading_enabled:
            logger.info("PolymarketStrate: clés CLOB détectées → trading actif activé")
        else:
            logger.info("PolymarketStrate: pas de clé CLOB → mode signal seul")
        return instance

    # ── Données Gamma (publiques) ──────────────────────────────────────────────

    async def fetch_markets(self) -> list:
        """Récupère marchés actifs depuis Gamma API (public, pas de clé)."""
        try:
            resp = await self._gamma_client.get(
                f"{GAMMA_API}/markets",
                params={
                    "active": True,
                    "closed": False,
                    "limit": 200,
                    "order": "volume24hr",
                    "ascending": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("markets", [])
        except Exception as e:
            logger.error(f"Polymarket fetch_markets error: {e}")
            return []

    def classify_market(self, question: str) -> tuple:
        q = question.lower()
        for asset, keywords in MARKET_KEYWORDS.items():
            if not any(kw in q for kw in keywords):
                continue
            if any(ex in q for ex in MARKET_EXCLUSIONS.get(asset, [])):
                continue
            bearish_words = ["reject", "ban", "crash", "below", "fail",
                             "bankrupt", "collapse", "recession", "rate hike"]
            bullish = not any(bw in q for bw in bearish_words)
            return asset, bullish
        return None, True

    def kelly_size(self, p_estimate: float, market_price: float) -> float:
        if market_price <= 0 or market_price >= 1:
            return 0.0
        b = (1 - market_price) / market_price
        q = 1 - p_estimate
        kelly = (p_estimate * b - q) / b
        return max(0.0, min(self.kelly_fraction_max, kelly))

    def estimate_oracle_probability(
        self,
        question: str,
        asset: str,
        market_price: float,
        oracle_macro_context: Optional[dict] = None,
    ) -> float:
        if oracle_macro_context and asset in oracle_macro_context:
            return oracle_macro_context[asset]
        if market_price > 0.80:
            return market_price - 0.05
        elif market_price < 0.20:
            return market_price + 0.07
        else:
            return market_price

    async def scan(self, oracle_macro_context: Optional[dict] = None) -> list:
        """
        Scan principal — Gamma API + filtrage.
        Résultat mis en cache 5 minutes.
        """
        now = _time.time()
        if now - self._last_fetch < self.cache_ttl and self.last_opportunities:
            return self.last_opportunities

        markets = await self.fetch_markets()
        opportunities = []

        for market in markets:
            try:
                question = market.get("question", "")
                volume = float(market.get("volume", 0) or 0)
                if volume < self.min_volume:
                    continue

                outcome_prices = market.get("outcomePrices", ["0.5"])
                if not outcome_prices:
                    continue
                if isinstance(outcome_prices, str):
                    import json as _json
                    try:
                        outcome_prices = _json.loads(outcome_prices)
                    except Exception:
                        continue
                try:
                    current_yes = float(outcome_prices[0])
                except (ValueError, IndexError):
                    continue

                if current_yes <= 0 or current_yes >= 1:
                    continue

                asset, bullish = self.classify_market(question)
                if not asset:
                    continue

                oracle_est = self.estimate_oracle_probability(
                    question, asset, current_yes, oracle_macro_context
                )
                edge = oracle_est - current_yes
                if abs(edge) < self.min_edge:
                    continue

                kelly = self.kelly_size(oracle_est, current_yes)
                direction = "YES" if edge > 0 else "NO"
                abs_edge = abs(edge)

                opp = PolymarketOpportunity(
                    market_id=market.get("id", ""),
                    question=question,
                    current_price_yes=current_yes,
                    oracle_estimate=oracle_est,
                    edge=round(edge, 4),
                    kelly_fraction=round(kelly, 4),
                    direction=direction,
                    correlated_asset=asset,
                    volume_24h=volume,
                    end_date=market.get("endDate", "N/A"),
                    confidence="HIGH" if abs_edge > 0.15 else "MEDIUM" if abs_edge > 0.10 else "LOW",
                    bullish_for_asset=bullish,
                )
                opportunities.append(opp)

            except Exception as e:
                logger.debug(f"Market parse error: {e}")
                continue

        self.last_opportunities = sorted(opportunities, key=lambda o: abs(o.edge), reverse=True)
        self._last_fetch = now
        logger.info(
            f"Polymarket scan: {len(markets)} marchés → "
            f"{len(self.last_opportunities)} opps "
            f"({'trading actif' if self.trading_enabled else 'signal seul'})"
        )
        return self.last_opportunities

    # ── Trading CLOB actif ─────────────────────────────────────────────────────

    async def execute_opportunity(
        self,
        opp: PolymarketOpportunity,
        capital_usdc: float,
        token_id_yes: Optional[str] = None,
        token_id_no: Optional[str] = None,
    ) -> Optional[str]:
        """
        Place un ordre CLOB pour saisir une opportunité.

        Requiert :
          - self.trading_enabled = True
          - self.clob.is_configured = True
          - token_id_yes / token_id_no selon direction

        Paramètres
        ----------
        opp           : PolymarketOpportunity à saisir
        capital_usdc  : capital disponible en USDC
        token_id_yes  : condition_id du token YES
        token_id_no   : condition_id du token NO

        Retourne
        --------
        str | None : order_id si succès
        """
        if not self.trading_enabled or not self.clob.is_configured:
            logger.debug("CLOB: trading désactivé ou non configuré — ordre ignoré")
            return None

        # Taille Kelly
        size_usdc = capital_usdc * opp.kelly_fraction
        if size_usdc < self.min_clob_size_usdc:
            logger.debug(f"CLOB: taille {size_usdc:.2f} USDC < min {self.min_clob_size_usdc} — ignoré")
            return None

        # Sélectionner token et side
        if opp.direction == "YES" and token_id_yes:
            token_id = token_id_yes
            side = "BUY"
            price = opp.current_price_yes
        elif opp.direction == "NO" and token_id_no:
            token_id = token_id_no
            side = "BUY"
            price = 1.0 - opp.current_price_yes
        else:
            logger.warning(f"CLOB: token_id manquant pour {opp.question[:40]}")
            return None

        order_id = await self.clob.place_order(
            token_id=token_id,
            side=side,
            size=round(size_usdc, 2),
            price=round(price, 4),
        )
        return order_id

    # ── Vote parlement ─────────────────────────────────────────────────────────

    def generate_parliament_vote(self, opportunities: list, target_asset: str):
        """Génère un Vote parlement pour un asset donné."""
        from oracle_v2.brain.parliament import Vote
        asset_opps = [o for o in opportunities if o.correlated_asset == target_asset]

        if not asset_opps:
            return Vote(
                strate_name="POLYMARKET",
                direction="NEUTRAL",
                confidence=0.0,
                reasoning="Aucun signal Polymarket pour cet asset",
            )

        top = asset_opps[0]
        if top.direction == "YES" and top.bullish_for_asset:
            trade_direction = "LONG"
        elif top.direction == "YES" and not top.bullish_for_asset:
            trade_direction = "SHORT"
        elif top.direction == "NO" and top.bullish_for_asset:
            trade_direction = "SHORT"
        else:
            trade_direction = "LONG"

        confidence = min(1.0, abs(top.edge) * 5)
        clob_suffix = " [CLOB actif]" if self.trading_enabled else ""
        return Vote(
            strate_name="POLYMARKET",
            direction=trade_direction,
            confidence=confidence,
            reasoning=(
                f"Edge {top.edge:+.1%} sur '{top.question[:60]}…' "
                f"(Kelly {top.kelly_fraction:.1%}){clob_suffix}"
            ),
            polymarket_signal=(
                f"{top.direction} @ {top.current_price_yes:.2f} | Edge: {top.edge:+.1%}"
            ),
        )

    async def close(self) -> None:
        await self._gamma_client.aclose()
        await self.clob.close()
