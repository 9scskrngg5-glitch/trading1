"""
Agent 9 — Détecteur de Régime de Marché
Classifie le régime (trending/ranging/volatile) via ADX, ATR, volume anomaly.
Publie sur market:regime → consommé par PredictAgent, RiskAgent, SynthesisAgent, CompoundAgent.
Vault : vault/market_conditions/
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone

import numpy as np

from core.base_agent import BaseAgent
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)

# ── Régimes possibles ─────────────────────────────────────────────────────────
REGIME_TRENDING_UP   = "trending_up"
REGIME_TRENDING_DOWN = "trending_down"
REGIME_RANGING       = "ranging"
REGIME_VOLATILE      = "volatile"
REGIME_UNKNOWN       = "unknown"

REGIME_EMOJI = {
    REGIME_TRENDING_UP:   "📈",
    REGIME_TRENDING_DOWN: "📉",
    REGIME_RANGING:       "↔️",
    REGIME_VOLATILE:      "⚡",
    REGIME_UNKNOWN:       "❓",
}


class RegimeAgent(BaseAgent):
    """
    Agent de détection du régime de marché.

    Indicateurs utilisés :
    - ADX  : force de la tendance (> 25 = trend fort, < 20 = range)
    - ATR% : volatilité relative (> 4% = volatile)
    - Volume anomaly : spike > 2× moyenne rolling = événement majeur
    - Linear regression slope sur 20 périodes → direction

    Publie sur market:regime → consommé par PredictAgent, RiskAgent,
    SynthesisAgent et CompoundAgent pour ajuster leurs décisions.
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        config: dict,
        market_data=None,
        telegram=None,
    ):
        super().__init__("RegimeAgent", "market_conditions", bus, obsidian, config)
        self.market_data = market_data
        self.telegram    = telegram
        self.assets      = config.get("assets", ["BTC/USDT", "ETH/USDT", "SOL/USDT", "EUR/USD"])

        # Dernier régime connu par asset (pour détecter les changements)
        self._regimes: dict[str, str] = {}
        self._regime_history: dict[str, deque] = {
            a: deque(maxlen=20) for a in self.assets
        }

        # Buffers de prix/volumes alimentés par les signaux techniques du bus
        self._price_buf:  dict[str, deque] = {a: deque(maxlen=100) for a in self.assets}
        self._high_buf:   dict[str, deque] = {a: deque(maxlen=100) for a in self.assets}
        self._low_buf:    dict[str, deque] = {a: deque(maxlen=100) for a in self.assets}
        self._volume_buf: dict[str, deque] = {a: deque(maxlen=50)  for a in self.assets}

        # Cache du dernier régime complet (asset → dict)
        self._last_regime_data: dict[str, dict] = {}

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        (self.obsidian.vault_path / "market_conditions").mkdir(exist_ok=True)
        logger.info(
            "[%s] Actif | assets : %s | seuils : ADX>25=trend, ATR>4%%=volatile",
            self.name, self.assets,
        )

    def _register_subscriptions(self) -> None:
        # Enrichit les buffers de prix depuis les signaux techniques
        self.bus.subscribe(CHANNELS["signals_technical"], self._on_technical_signal)

    # ── Handler bus ───────────────────────────────────────────────────────────

    async def _on_technical_signal(self, data: dict) -> None:
        """Accumule les prix/volumes dans les buffers rolling."""
        asset = data.get("asset")
        if not asset:
            return

        price  = data.get("close") or data.get("price")
        high   = data.get("high", price)
        low    = data.get("low",  price)
        volume = data.get("volume")

        if price:
            p = float(price)
            if asset not in self._price_buf:
                self._price_buf[asset]  = deque(maxlen=100)
                self._high_buf[asset]   = deque(maxlen=100)
                self._low_buf[asset]    = deque(maxlen=100)
                self._volume_buf[asset] = deque(maxlen=50)
            self._price_buf[asset].append(p)
            self._high_buf[asset].append(float(high)   if high   else p * 1.002)
            self._low_buf[asset].append(float(low)    if low    else p * 0.998)
            if volume:
                self._volume_buf[asset].append(float(volume))

    # ── Cycle principal ───────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        for asset in self.assets:
            try:
                regime_data = self._detect_regime(asset)
                if not regime_data:
                    continue

                prev_regime = self._regimes.get(asset)
                new_regime  = regime_data["regime"]

                # Détecter et notifier les changements de régime
                if prev_regime and prev_regime != new_regime:
                    await self._on_regime_shift(asset, prev_regime, new_regime, regime_data)

                self._regimes[asset]          = new_regime
                self._last_regime_data[asset] = regime_data
                self._regime_history[asset].append({
                    "regime": new_regime,
                    "adx":    regime_data.get("adx", 0),
                    "ts":     datetime.now(timezone.utc).isoformat(),
                })

                # Publier sur le bus
                await self.bus.publish(CHANNELS["regime"], {
                    "type":  "regime_update",
                    "asset": asset,
                    **regime_data,
                })

                emoji = REGIME_EMOJI.get(new_regime, "❓")
                logger.info(
                    "[%s] %s %s → %s | ADX=%.1f ATR%%=%.2f%% Vol=%s",
                    self.name, emoji, asset, new_regime.upper(),
                    regime_data.get("adx", 0),
                    regime_data.get("atr_pct", 0),
                    "⚠️ SPIKE" if regime_data.get("volume_anomaly") else "normal",
                )

            except Exception as exc:
                logger.warning("[%s] Erreur régime %s: %s", self.name, asset, exc)

    # ── Détection du régime ───────────────────────────────────────────────────

    def _detect_regime(self, asset: str) -> dict | None:
        """
        Calcule ADX, ATR%, volume anomaly et classifie le régime.
        Prend les données depuis MarketDataManager si dispo, sinon buffers internes.
        """
        prices = highs = lows = volumes = None

        # Priorité : MarketDataManager (données exchange réelles)
        if self.market_data and hasattr(self.market_data, "is_ready"):
            # is_ready() takes no arguments (checks global ready flag)
            if self.market_data.is_ready():
                try:
                    df = self.market_data.get_ohlcv(asset, "1h", limit=50)
                    if df is not None and len(df) >= 20:
                        prices  = df["close"].values.astype(float)
                        highs   = df["high"].values.astype(float)
                        lows    = df["low"].values.astype(float)
                        volumes = df["volume"].values.astype(float)
                except Exception:
                    pass

        # Fallback : buffers internes alimentés par le bus
        if prices is None:
            p_buf = list(self._price_buf.get(asset, []))
            if len(p_buf) < 14:
                return None
            prices  = np.array(p_buf, dtype=float)
            h_buf   = list(self._high_buf.get(asset, []))
            l_buf   = list(self._low_buf.get(asset,  []))
            highs   = np.array(h_buf,  dtype=float) if h_buf  else prices * 1.002
            lows    = np.array(l_buf,  dtype=float) if l_buf  else prices * 0.998
            v_buf   = list(self._volume_buf.get(asset, []))
            volumes = np.array(v_buf, dtype=float)  if v_buf  else np.ones(len(prices))

        if len(prices) < 14:
            return None

        adx          = self._compute_adx(highs, lows, prices, period=14)
        atr_pct      = self._compute_atr_pct(highs, lows, prices, period=14)
        vol_anomaly  = self._detect_volume_anomaly(volumes)
        trend_dir    = self._detect_trend_direction(prices)

        # ── Classification ────────────────────────────────────────────────────
        if atr_pct > 4.0 or vol_anomaly:
            regime = REGIME_VOLATILE
        elif adx >= 25:
            regime = REGIME_TRENDING_UP if trend_dir > 0 else REGIME_TRENDING_DOWN
        elif adx < 20:
            regime = REGIME_RANGING
        else:
            # Zone grise 20-25 : tendance faible
            regime = REGIME_TRENDING_UP if trend_dir > 0 else REGIME_TRENDING_DOWN

        return {
            "regime":           regime,
            "adx":              round(float(adx), 2),
            "atr_pct":          round(float(atr_pct), 3),
            "volume_anomaly":   bool(vol_anomaly),
            "trend_direction":  int(trend_dir),
            "timestamp":        datetime.now(timezone.utc).isoformat(),
        }

    # ── Indicateurs techniques ────────────────────────────────────────────────

    def _compute_adx(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14,
    ) -> float:
        """
        Average Directional Index (ADX) — mesure la FORCE de la tendance.
        > 25 = trend fort, < 20 = range, 20-25 = zone grise.
        Méthode de Wilder (EMA adaptée).
        """
        n = len(close)
        if n < period + 1:
            return 15.0

        tr       = np.zeros(n)
        dm_plus  = np.zeros(n)
        dm_minus = np.zeros(n)

        for i in range(1, n):
            # True Range
            tr[i] = max(
                float(high[i])  - float(low[i]),
                abs(float(high[i]) - float(close[i - 1])),
                abs(float(low[i])  - float(close[i - 1])),
            )
            # Directional Movement
            up_move   = float(high[i]) - float(high[i - 1])
            down_move = float(low[i - 1]) - float(low[i])
            if up_move > down_move and up_move > 0:
                dm_plus[i]  = up_move
            if down_move > up_move and down_move > 0:
                dm_minus[i] = down_move

        atr14 = self._wilder_smooth(tr[1:],       period)
        dmp14 = self._wilder_smooth(dm_plus[1:],  period)
        dmm14 = self._wilder_smooth(dm_minus[1:], period)

        if atr14 == 0:
            return 15.0

        di_plus  = 100.0 * dmp14 / atr14
        di_minus = 100.0 * dmm14 / atr14
        di_sum   = di_plus + di_minus

        if di_sum == 0:
            return 15.0

        dx = 100.0 * abs(di_plus - di_minus) / di_sum
        return float(dx)

    def _wilder_smooth(self, data: np.ndarray, period: int) -> float:
        """Lissage de Wilder (EMA avec alpha = 1/period)."""
        if len(data) == 0:
            return 0.0
        if len(data) < period:
            return float(np.mean(data))
        result = float(np.mean(data[:period]))
        for val in data[period:]:
            result = (result * (period - 1) + float(val)) / period
        return result

    def _compute_atr_pct(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14,
    ) -> float:
        """ATR exprimé en % du prix courant — mesure la volatilité relative."""
        n = len(close)
        if n < 2:
            return 1.0
        tr_vals = []
        for i in range(1, min(n, period + 1)):
            tr = max(
                float(high[i]) - float(low[i]),
                abs(float(high[i]) - float(close[i - 1])),
                abs(float(low[i])  - float(close[i - 1])),
            )
            tr_vals.append(tr)
        if not tr_vals or float(close[-1]) == 0:
            return 1.0
        atr = float(np.mean(tr_vals))
        return (atr / float(close[-1])) * 100.0

    def _detect_volume_anomaly(
        self,
        volumes: np.ndarray,
        threshold: float = 2.0,
    ) -> bool:
        """Spike de volume > threshold × moyenne rolling → événement majeur."""
        if len(volumes) < 5:
            return False
        avg = float(np.mean(volumes[:-1]))
        if avg == 0:
            return False
        return float(volumes[-1]) > avg * threshold

    def _detect_trend_direction(self, prices: np.ndarray) -> int:
        """
        Direction via régression linéaire sur les 20 dernières périodes.
        Returns +1 (haussier), -1 (baissier), 0 (indéterminé).
        """
        n = min(len(prices), 20)
        if n < 5:
            return 0
        y = prices[-n:].astype(float)
        x = np.arange(n, dtype=float)
        slope = float(np.polyfit(x, y, 1)[0])
        # Seuil minimal : pente > 0.01% du prix pour être significative
        price_threshold = float(y[-1]) * 0.0001
        if slope > price_threshold:
            return 1
        if slope < -price_threshold:
            return -1
        return 0

    # ── Changement de régime ──────────────────────────────────────────────────

    async def _on_regime_shift(
        self,
        asset: str,
        prev: str,
        new: str,
        data: dict,
    ) -> None:
        """
        Notifie d'un changement de régime :
        1. Log structuré
        2. Telegram (regime_shift)
        3. Vault market_conditions/
        """
        emoji_prev = REGIME_EMOJI.get(prev, "❓")
        emoji_new  = REGIME_EMOJI.get(new,  "❓")
        logger.info(
            "[%s] 🔄 REGIME SHIFT %s : %s %s → %s %s | ADX=%.1f ATR%%=%.2f%%",
            self.name, asset,
            emoji_prev, prev.upper(),
            emoji_new,  new.upper(),
            data.get("adx", 0), data.get("atr_pct", 0),
        )

        if self.telegram:
            try:
                await self.telegram.regime_shift(
                    asset         = asset,
                    prev_regime   = prev,
                    new_regime    = new,
                    adx           = data.get("adx",   0.0),
                    atr_pct       = data.get("atr_pct", 0.0),
                    volume_anomaly= data.get("volume_anomaly", False),
                )
            except Exception as exc:
                logger.warning("[%s] Telegram regime_shift: %s", self.name, exc)

        self._write_regime_shift_note(asset, prev, new, data)

    def _write_regime_shift_note(
        self,
        asset: str,
        prev: str,
        new: str,
        data: dict,
    ) -> None:
        """Écrit la note de changement de régime dans vault/market_conditions/."""
        date_str     = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        asset_safe   = asset.replace("/", "_")
        emoji_new    = REGIME_EMOJI.get(new, "❓")

        frontmatter = {
            "date":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "agent":    "RegimeAgent",
            "asset":    asset,
            "type":     "regime_shift",
            "from":     prev,
            "to":       new,
            "adx":      data.get("adx"),
            "atr_pct":  data.get("atr_pct"),
            "tags":     ["régime", "marché", asset_safe, new],
        }

        impact_risk = {
            REGIME_VOLATILE:      "⬇️ Sizing réduit ×0.7 (ATR élevé)",
            REGIME_TRENDING_UP:   "✅ Biais LONG favorisé",
            REGIME_TRENDING_DOWN: "✅ Biais SHORT favorisé",
            REGIME_RANGING:       "⚠️ Signaux de trend ignorés, range-trading seulement",
        }.get(new, "Aucun ajustement")

        content = f"""## {emoji_new} Changement de Régime — {asset}

| Paramètre | Valeur |
|---|---|
| Asset | `{asset}` |
| Ancien régime | `{prev.upper()}` |
| **Nouveau régime** | **`{new.upper()}`** |
| ADX | `{data.get('adx', 0):.1f}` _(> 25 = trend fort, < 20 = range)_ |
| ATR % | `{data.get('atr_pct', 0):.2f}%` |
| Volume anomaly | `{'OUI ⚠️' if data.get('volume_anomaly') else 'Non'}` |
| Direction | `{'HAUSSIER 📈' if data.get('trend_direction', 0) > 0 else 'BAISSIER 📉' if data.get('trend_direction', 0) < 0 else 'NEUTRE'}` |

### Impact sur le Système
{impact_risk}

### Agents Notifiés
- [[agents/PredictAgent]] — ajuste les poids modèles au régime
- [[agents/RiskAgent]] — ajuste le sizing selon volatilité
- [[agents/CompoundAgent]] — bloque le scaling si volatile
- [[agents/SynthesisAgent]] — intègre le régime dans la DataSheet

### Liens
[[agents/RegimeAgent]] | [[market_conditions/index]]
"""
        self.obsidian.write_note(
            "market_conditions",
            f"shift_{asset_safe}_{date_str}",
            frontmatter,
            content,
        )

    # ── API publique ──────────────────────────────────────────────────────────

    def get_regime(self, asset: str) -> str:
        """Retourne le dernier régime connu pour un asset."""
        return self._regimes.get(asset, REGIME_UNKNOWN)

    def get_regime_data(self, asset: str) -> dict:
        """Retourne les indicateurs complets du dernier régime."""
        return self._last_regime_data.get(asset, {"regime": REGIME_UNKNOWN})

    def get_regime_history(self, asset: str, n: int = 10) -> list[dict]:
        """Retourne les N derniers régimes enregistrés."""
        hist = list(self._regime_history.get(asset, []))
        return hist[-n:]
