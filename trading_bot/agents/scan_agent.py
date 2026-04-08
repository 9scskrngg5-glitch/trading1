"""
Agent 1 — Scanner de Marché
Surveille en continu les marchés crypto + forex pour détecter les opportunités.
Calcule RSI, MACD, Bollinger, ATR avec des POIDS ADAPTATIFS issus de l'apprentissage ML.
Vault : vault/technique/  — notes riches avec métriques financières détaillées.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from core.base_agent import BaseAgent
from core.learning_engine import LearningEngine
from core.llm_client import LLMClient
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient
from models.learning import AgentMemory, MarketRegime
from models.signals import SignalType, MarketType, TechnicalSignal

logger = logging.getLogger(__name__)

TIMEFRAMES    = ["1h", "4h", "1d"]
CANDLES_LIMIT = 150
MIN_CONFIDENCE = 20
FOREX_CCY = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"}


class ScanAgent(BaseAgent):
    """
    Scanner de marché avec apprentissage adaptatif.

    Innovation ML :
    - Les poids RSI/MACD/BB/Volume sont ajustés après chaque trade selon le succès réel
    - Mémorisés dans vault/config/ScanAgent_memory.md
    - Performance par asset + timeframe affichée dans chaque note Obsidian
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        learning: LearningEngine,
        config: dict,
        market_data=None,          # MarketDataManager (WebSocket + REST)
        llm: "LLMClient | None" = None,
    ):
        super().__init__("ScanAgent", "technique", bus, obsidian, config)
        self.learning       = learning
        self.memory: AgentMemory = None
        self._exchanges: dict    = {}
        self._market_data   = market_data   # source de données temps réel
        self._llm           = llm

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        self.memory = self.learning.load_memory("ScanAgent")

        try:
            import ccxt.async_support as ccxt
            if "binance" in self.config.get("exchanges", []):
                self._exchanges["binance"] = ccxt.binance({
                    "apiKey": self.config.get("binance_api_key", ""),
                    "secret": self.config.get("binance_secret", ""),
                    "enableRateLimit": True,
                })
        except ImportError:
            logger.warning("[%s] ccxt absent — mode simulation", self.name)

        logger.info(
            "[%s] Mémoire chargée : %d trades, WR=%.1f%%, SL mult=%.2f",
            self.name, self.memory.total_trades, self.memory.win_rate * 100,
            self.memory.adaptive_params.get("sl_atr_multiplier", 1.5),
        )

    # ── Cycle principal ───────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        tasks = [
            self._process(pair, tf)
            for pair in self.config.get("pairs", [])
            for tf in TIMEFRAMES
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process(self, pair: str, timeframe: str) -> None:
        signal = await self._analyze(pair, timeframe)
        if signal:
            signal_dict = signal.to_dict()
            # Enrichissement GPT-4o si confiance suffisante et LLM disponible
            if self._llm and signal.confidence >= MIN_CONFIDENCE:
                regime = self._get_current_regime(pair)
                llm_comment = await self._enrich_with_llm(
                    pair=pair,
                    timeframe=timeframe,
                    direction=str(signal.signal.value) if hasattr(signal.signal, "value") else str(signal.signal),
                    confidence=signal.confidence,
                    rsi=signal_dict.get("rsi", 0.0),
                    macd_hist=signal_dict.get("macd_hist", 0.0),
                    bb_position=signal_dict.get("bb_position", 0.0),
                    regime=regime,
                )
                if llm_comment:
                    signal_dict["llm_comment"] = llm_comment
            await self.bus.publish(CHANNELS["signals_technical"], signal_dict)
            self._write_vault_note(signal)

    async def _enrich_with_llm(
        self,
        pair: str,
        timeframe: str,
        direction: str,
        confidence: int,
        rsi: float,
        macd_hist: float,
        bb_position: float,
        regime: str = "unknown",
    ) -> str:
        """Enrichit le signal avec un commentaire GPT-4o en 2 phrases. Retourne '' si indisponible."""
        if not self._llm or self._llm.budget_exceeded:
            return ""

        prompt = f"""\
Tu es un analyste technique senior. En 2 phrases courtes, dis si ce setup \
est techniquement valide ou douteux et pourquoi.

Asset: {pair} | Timeframe: {timeframe}
Direction: {direction} | Confiance algo: {confidence}/100
RSI: {rsi:.1f} | MACD hist: {macd_hist:.4f} | BB position: {bb_position:.2f}
Régime de marché: {regime}"""

        resp = await self._llm.complete("gpt-4o", prompt, max_tokens=100, timeout=5.0)
        return resp.text if resp else ""

    def _get_current_regime(self, pair: str) -> str:
        """Récupère le régime courant depuis la mémoire adaptive de l'agent."""
        return self.memory.adaptive_params.get(f"regime:{pair}", "unknown") if self.memory else "unknown"

    # ── Analyse avec poids adaptatifs ────────────────────────────────────────

    async def _analyze(self, pair: str, timeframe: str) -> Optional[TechnicalSignal]:
        df = await self._fetch_ohlcv(pair, timeframe)
        if df is None or len(df) < 60:
            return None

        close = df["close"]
        high  = df["high"]
        low   = df["low"]
        vol   = df["volume"]

        rsi              = self._rsi(close)
        _, _, macd_hist  = self._macd(close)
        bb_up, _, bb_lo  = self._bollinger(close)
        atr              = self._atr(high, low, close)

        last_close   = float(close.iloc[-1])
        last_rsi     = float(rsi.iloc[-1])
        last_hist    = float(macd_hist.iloc[-1])
        prev_hist    = float(macd_hist.iloc[-2])
        bb_rng       = float(bb_up.iloc[-1]) - float(bb_lo.iloc[-1])
        bb_pos       = (last_close - float(bb_lo.iloc[-1])) / max(bb_rng, 1e-9)
        vol_ratio    = float(vol.iloc[-1] / vol.iloc[-21:-1].mean())
        last_atr     = float(atr.iloc[-1])

        # ── Poids adaptatifs depuis la mémoire ML ──
        w_rsi  = self.memory.indicator_weights.get(f"rsi:{timeframe}:{pair}",   1.0)
        w_macd = self.memory.indicator_weights.get(f"macd:{timeframe}:{pair}",  1.0)
        w_bb   = self.memory.indicator_weights.get(f"bb:{timeframe}:{pair}",    1.0)
        w_vol  = self.memory.indicator_weights.get(f"volume:{timeframe}:{pair}", 1.0)

        direction, confidence = self._adaptive_score(
            rsi=last_rsi, macd_hist=last_hist, prev_macd_hist=prev_hist,
            bb_position=bb_pos, vol_ratio=vol_ratio,
            w_rsi=w_rsi, w_macd=w_macd, w_bb=w_bb, w_vol=w_vol,
        )

        # ── Enrichissement temps réel (order book + VWAP + order flow + AVWAP) ──
        rt = self._enrich_with_realtime(pair)
        ob_imbalance = rt["ob_imbalance"]

        # Ajustement de la confiance selon l'imbalance order book
        if direction == SignalType.BULLISH and ob_imbalance > 0.15:
            confidence = min(confidence + 8, 100)
        elif direction == SignalType.BULLISH and ob_imbalance < -0.15:
            confidence = max(confidence - 8, 0)
        elif direction == SignalType.BEARISH and ob_imbalance < -0.15:
            confidence = min(confidence + 8, 100)
        elif direction == SignalType.BEARISH and ob_imbalance > 0.15:
            confidence = max(confidence - 8, 0)

        # ── Order Flow confirmation (CVD) ──
        # Si le signal est bull et le delta 5m est fortement positif → confirmation
        delta_5m = rt["delta_5m"]
        if direction == SignalType.BULLISH and delta_5m > 0:
            confidence = min(confidence + 5, 100)
        elif direction == SignalType.BULLISH and delta_5m < 0:
            confidence = max(confidence - 5, 0)
        elif direction == SignalType.BEARISH and delta_5m < 0:
            confidence = min(confidence + 5, 100)
        elif direction == SignalType.BEARISH and delta_5m > 0:
            confidence = max(confidence - 5, 0)

        # ── Delta divergence = signal d'alerte → réduire confiance ──
        if rt["delta_divergence"]:
            confidence = max(confidence - 10, 0)

        # ── Absorption = smart money absorbe → réduire confiance ──
        if rt["absorption"]:
            confidence = max(confidence - 8, 0)

        # ── Anchored VWAP support/résistance ──
        avwap_dist = rt["avwap_dist_pct"]
        # Prix proche de l'AVWAP (< 0.3%) et direction alignée → confirmation
        if abs(avwap_dist) < 0.3:
            if direction == SignalType.BULLISH and avwap_dist > 0:
                confidence = min(confidence + 5, 100)  # rebond au-dessus de l'AVWAP
            elif direction == SignalType.BEARISH and avwap_dist < 0:
                confidence = min(confidence + 5, 100)  # rejet sous l'AVWAP

        return TechnicalSignal(
            asset            = pair,
            signal           = direction,
            confidence       = confidence,
            timeframe        = timeframe,
            market           = MarketType.FOREX if self._is_forex(pair) else MarketType.CRYPTO,
            rsi              = round(last_rsi, 2),
            macd_hist        = round(last_hist, 6),
            bb_position      = round(bb_pos, 3),
            volume_ratio     = round(vol_ratio, 2),
            entry_price      = round(last_close, 6),
            atr              = round(last_atr, 6),
            ob_imbalance     = ob_imbalance,
            vwap_dist_pct    = rt["vwap_dist_pct"],
            trend_slope      = rt["trend_slope"],
            cvd              = rt["cvd"],
            delta_5m         = rt["delta_5m"],
            delta_divergence = rt["delta_divergence"],
            absorption       = rt["absorption"],
            avwap_dist_pct   = avwap_dist,
        )

    # ── Scoring adaptatif ─────────────────────────────────────────────────────

    @staticmethod
    def _adaptive_score(
        rsi: float, macd_hist: float, prev_macd_hist: float,
        bb_position: float, vol_ratio: float,
        w_rsi: float, w_macd: float, w_bb: float, w_vol: float,
    ) -> tuple[SignalType, int]:
        """
        Scoring adaptatif multi-indicateur.

        Deux strategies coherentes :
          TREND     : RSI confirme la direction + MACD dans le meme sens
          REVERSAL  : BB extremes + MACD crossover (mean reversion)

        Chaque indicateur vote independamment, le score final est la somme
        ponderee. Le volume amplifie quand il confirme.
        """
        import math
        bull_points = 0.0
        bear_points = 0.0

        # ── RSI ──
        if rsi is not None and not math.isnan(rsi):
            if rsi > 55:
                bull_points += min((rsi - 50) / 30 * 25, 25) * w_rsi   # 55→8, 70→17, 80→25
            elif rsi < 45:
                bear_points += min((50 - rsi) / 30 * 25, 25) * w_rsi

        # ── MACD ──
        macd_cross_bull = (macd_hist > 0 and prev_macd_hist <= 0)
        macd_cross_bear = (macd_hist < 0 and prev_macd_hist >= 0)

        if macd_cross_bull:
            bull_points += 30 * w_macd       # crossover = signal fort
        elif macd_cross_bear:
            bear_points += 30 * w_macd
        elif macd_hist > 0:
            bull_points += 10 * w_macd       # continuation
        elif macd_hist < 0:
            bear_points += 10 * w_macd

        # ── Bollinger — coherent avec la direction ──
        # Trend haussier : prix au-dessus du milieu (bb > 0.5) = confirmation
        # Reversal : prix en bas de bande (bb < 0.15) + MACD cross = rebond
        if bb_position > 0.6:
            bull_points += 15 * w_bb         # prix en force (trend)
        elif bb_position < 0.15 and macd_cross_bull:
            bull_points += 20 * w_bb         # rebond mean-reversion
        elif bb_position < 0.4:
            bear_points += 15 * w_bb         # prix en faiblesse
        elif bb_position > 0.85 and macd_cross_bear:
            bear_points += 20 * w_bb         # rejet haut de bande

        # ── Volume — amplifie le signal dominant ──
        if vol_ratio > 1.3:
            boost = min(vol_ratio - 1.0, 1.0) * 15 * w_vol  # max +15 pts
            if bull_points > bear_points:
                bull_points += boost
            elif bear_points > bull_points:
                bear_points += boost

        # ── Alignement bonus : +10 si au moins 3 indicateurs dans le meme sens ──
        bull_count = sum([
            rsi is not None and not math.isnan(rsi) and rsi > 55,
            macd_hist > 0,
            bb_position > 0.5,
        ])
        bear_count = sum([
            rsi is not None and not math.isnan(rsi) and rsi < 45,
            macd_hist < 0,
            bb_position < 0.5,
        ])
        if bull_count >= 3:
            bull_points += 10
        if bear_count >= 3:
            bear_points += 10

        # ── Score final ──
        net = bull_points - bear_points
        confidence = int(min(max(bull_points, bear_points), 100))

        if net > 15:
            return SignalType.BULLISH, confidence
        elif net < -15:
            return SignalType.BEARISH, confidence
        return SignalType.NEUTRAL, confidence

    # ── Indicateurs ───────────────────────────────────────────────────────────

    @staticmethod
    def _rsi(s: pd.Series, p=14) -> pd.Series:
        d = s.diff()
        g = d.clip(lower=0).rolling(p).mean()
        l = (-d.clip(upper=0)).rolling(p).mean()
        # g=0,l=0 → 50 (neutre); g>0,l=0 → 100 (tout haussier); g=0,l>0 → 0 (tout baissier)
        rs = g / l.where(l > 1e-12, other=np.nan)
        rsi = 100 - 100 / (1 + rs)
        # Remplacer NaN (tout haussier) par 95, 0 exact par 5
        rsi = rsi.fillna(95.0)
        rsi = rsi.clip(5.0, 95.0)
        return rsi

    @staticmethod
    def _macd(s: pd.Series, fast=12, slow=26, sig=9):
        ef = s.ewm(span=fast, adjust=False).mean()
        es = s.ewm(span=slow, adjust=False).mean()
        line = ef - es
        signal = line.ewm(span=sig, adjust=False).mean()
        return line, signal, line - signal

    @staticmethod
    def _bollinger(s: pd.Series, p=20, n=2.0):
        m = s.rolling(p).mean()
        std = s.rolling(p).std()
        return m + n * std, m, m - n * std

    @staticmethod
    def _atr(h: pd.Series, l: pd.Series, c: pd.Series, p=14) -> pd.Series:
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        return tr.rolling(p).mean()

    # ── Données de marché ─────────────────────────────────────────────────────

    async def _fetch_ohlcv(self, pair: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Priorité des sources :
        1. MarketDataManager (WebSocket temps réel + historique REST)
        2. ccxt exchange (Binance REST direct)
        3. Simulation (fallback)
        """
        # 1. MarketDataManager — source principale (WS + REST)
        if self._market_data and self._market_data.is_ready():
            candles = self._market_data.get_candles(pair, timeframe, CANDLES_LIMIT)
            if len(candles) >= 30:  # 30 candles suffisent (RSI=14, BB=20)
                df = pd.DataFrame([
                    {"open": c.o, "high": c.h, "low": c.l, "close": c.c, "volume": c.v}
                    for c in candles
                ])
                logger.debug("[%s] MarketData %s/%s → %d candles (WS+REST)", self.name, pair, timeframe, len(df))
                return df
            else:
                logger.warning(
                    "[%s] MarketData %s/%s seulement %d candles (min 30)",
                    self.name, pair, timeframe, len(candles),
                )

        # 2. ccxt — fallback si MarketDataManager absent ou pas encore prêt
        for exchange in self._exchanges.values():
            try:
                raw = await exchange.fetch_ohlcv(pair, timeframe, limit=CANDLES_LIMIT)
                df  = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
                logger.debug("[%s] ccxt fallback %s/%s → %d candles", self.name, pair, timeframe, len(df))
                return df
            except Exception as exc:
                logger.debug("[%s] fetch_ohlcv %s/%s: %s", self.name, pair, timeframe, exc)

        # 3. Simulation — UNIQUEMENT en mode simulation
        mode = os.environ.get("TRADING_MODE", "simulation").lower()
        if mode != "simulation":
            logger.error(
                "🚨 [%s] AUCUNE donnée réelle pour %s/%s en mode %s — SIGNAL IGNORÉ",
                self.name, pair, timeframe, mode,
            )
            return None

        logger.warning(
            "⚠️  [%s] FALLBACK SIMULÉ pour %s/%s — mode simulation",
            self.name, pair, timeframe,
        )
        return self._sim_ohlcv(pair)

    def _enrich_with_realtime(self, pair: str) -> dict:
        """
        Enrichit le signal avec données temps réel du MarketDataManager.
        Retourne un dict avec toutes les métriques temps réel.
        """
        result = {
            "ob_imbalance": 0.0, "vwap_dist_pct": 0.0, "trend_slope": 0.0,
            "cvd": 0.0, "delta_5m": 0.0, "delta_divergence": False,
            "absorption": False, "avwap_dist_pct": 0.0,
        }
        if not (self._market_data and self._market_data.is_ready()):
            return result

        try:
            # Order book imbalance
            book = self._market_data.get_orderbook(pair, depth=10)
            result["ob_imbalance"] = round(book.get("imbalance", 0.0), 4)

            # VWAP intraday
            ticker = self._market_data.get_ticker(pair)
            last_price = ticker.get("lastPrice", 0.0)
            vwap = self._market_data.get_vwap(pair)
            if vwap and last_price > 0:
                result["vwap_dist_pct"] = round((last_price - vwap) / vwap * 100, 3)

            # Trend slope depuis candles 1m
            candles_1m = self._market_data.get_candles(pair, "1m", 20)
            if len(candles_1m) >= 10:
                closes = np.array([c.c for c in candles_1m[-20:]])
                if closes[-1] > 0:
                    slope = np.polyfit(range(len(closes)), closes, 1)[0]
                    result["trend_slope"] = round(slope / closes[-1] * 100, 5)

            # Order Flow / CVD
            flow = self._market_data.get_order_flow(pair)
            if flow:
                result["cvd"]              = round(flow.get("cvd", 0.0), 2)
                result["delta_5m"]         = round(flow.get("delta_5m", 0.0), 2)
                result["delta_divergence"] = flow.get("delta_divergence", False)
                result["absorption"]       = flow.get("absorption", False)

            # Anchored VWAP
            avwap = self._market_data.get_anchored_vwap(pair)
            if avwap:
                result["avwap_dist_pct"] = avwap.get("dist_pct", 0.0)

        except Exception as exc:
            logger.debug("[%s] enrich_realtime %s: %s", self.name, pair, exc)

        return result

    @staticmethod
    def _sim_ohlcv(pair: str) -> pd.DataFrame:
        """
        Simulation OHLCV réaliste avec tendance claire.
        Seed aligné sur 5 min avec SwarMode pour cohérence directionnelle.
        Génère RSI 55-70 (bull) ou 30-45 (bear) + MACD aligné.
        """
        seed = (hash(pair) + int(datetime.now().timestamp()) // 300) % 2**31
        rng  = np.random.default_rng(seed)
        n    = CANDLES_LIMIT

        BASE_PRICE = {
            "BTC/USDT": 84000.0, "ETH/USDT": 1800.0, "SOL/USDT": 125.0,
            "EUR/USD":  1.0950,  "GBP/USD":  1.2750,
        }
        base = BASE_PRICE.get(pair, 100.0)

        # Direction commune avec SwarMode (même seed → même choice)
        bull = (rng.choice([-1, 1]) == 1)

        # Phase 1 : neutre (50 bougies, RSI se stabilise autour de 50)
        neutral_returns = rng.normal(0, 0.003, 50)
        # Phase 2 : tendance marquée (100 bougies)
        drift    = 0.0025 if bull else -0.0025
        sigma    = 0.003
        trend_r  = rng.normal(drift, sigma, n - 50)

        all_returns = np.concatenate([neutral_returns, trend_r])
        closes = base * np.cumprod(1 + np.clip(all_returns, -0.05, 0.05))

        spread = closes * 0.0008
        # Volume plus fort en tendance
        vol_base = rng.uniform(300_000, 3_000_000, n)
        vol_mult = np.concatenate([np.ones(50), rng.uniform(1.2, 2.0, n - 50)])

        return pd.DataFrame({
            "ts":     range(n),
            "open":   closes * (1 - np.abs(rng.normal(0, 0.0003, n))),
            "high":   closes + np.abs(rng.normal(0, spread, n)),
            "low":    closes - np.abs(rng.normal(0, spread, n)),
            "close":  closes,
            "volume": vol_base * vol_mult,
        })

    # ── Vault Obsidian — notes riches avec données financières ────────────────

    def _write_vault_note(self, signal: TechnicalSignal) -> None:
        filename = self.obsidian.daily_filename("scan", signal.asset)

        # Récupérer les stats historiques depuis la mémoire
        asset_key = signal.asset
        ast_stats = self.memory.asset_stats.get(asset_key, {})
        ind_stats = {
            k: v for k, v in self.memory.indicator_stats.items()
            if signal.asset in k
        }

        w_rsi  = self.memory.indicator_weights.get(f"rsi:{signal.timeframe}:{signal.asset}",   1.0)
        w_macd = self.memory.indicator_weights.get(f"macd:{signal.timeframe}:{signal.asset}",  1.0)
        w_bb   = self.memory.indicator_weights.get(f"bb:{signal.timeframe}:{signal.asset}",    1.0)

        rsi_stat  = self.memory.indicator_stats.get(f"rsi:{signal.asset}",   {})
        macd_stat = self.memory.indicator_stats.get(f"macd:{signal.asset}",  {})
        bb_stat   = self.memory.indicator_stats.get(f"bb:{signal.asset}",    {})

        def wr(stat: dict) -> str:
            t = stat.get("total", 0)
            if t == 0:
                return "—"
            return f"{stat.get('wins', 0)/t:.0%} ({t} signaux)"

        rsi_icon = "🔴 Survente" if signal.rsi and signal.rsi < 30 else ("🟡 Surachat" if signal.rsi and signal.rsi > 70 else "⚪ Neutre")
        macd_icon = "📈" if signal.macd_hist and signal.macd_hist > 0 else "📉"
        vol_icon  = "🔥 Élevé" if signal.volume_ratio and signal.volume_ratio > 1.5 else "📊 Normal"

        total_signals_asset = ast_stats.get("total", 0)
        win_rate_asset = (ast_stats.get("wins", 0) / max(total_signals_asset, 1))
        avg_pnl_asset  = ast_stats.get("pnl_pct", 0.0)

        frontmatter = self._build_frontmatter(
            asset=signal.asset, signal_type=signal.signal.value,
            confidence=signal.confidence, timeframe=signal.timeframe,
            extra={
                "rsi": signal.rsi, "macd_hist": signal.macd_hist,
                "bb_position": signal.bb_position, "atr": signal.atr,
                "entry_price": signal.entry_price,
                "sl_atr_mult": self.memory.adaptive_params.get("sl_atr_multiplier", 1.5),
            },
        )

        ob_icon   = "🟢 Acheteur" if signal.ob_imbalance and signal.ob_imbalance > 0.1 else ("🔴 Vendeur" if signal.ob_imbalance and signal.ob_imbalance < -0.1 else "⚪ Neutre")
        vwap_icon = "↑ Dessus" if signal.vwap_dist_pct and signal.vwap_dist_pct > 0 else ("↓ Dessous" if signal.vwap_dist_pct else "—")
        trend_icon = "📈" if signal.trend_slope and signal.trend_slope > 0 else ("📉" if signal.trend_slope and signal.trend_slope < 0 else "—")
        data_src = "🔴 Simulation" if not (self._market_data and self._market_data.is_ready()) else "🟢 Binance WS+REST"

        content = f"""## Scan de Marché — {signal.asset} `{signal.timeframe}`

> Source données : {data_src}

### Indicateurs en Temps Réel
| Indicateur | Valeur | Statut | Poids ML | Taux succès historique |
|---|---|---|---|---|
| RSI (14) | `{signal.rsi}` | {rsi_icon} | `{w_rsi:.2f}` | {wr(rsi_stat)} |
| MACD Histogram | `{signal.macd_hist}` | {macd_icon} | `{w_macd:.2f}` | {wr(macd_stat)} |
| Bollinger Band | `{signal.bb_position:.1%}` | {'🟢 Bas' if signal.bb_position and signal.bb_position < 0.2 else '🔴 Haut' if signal.bb_position and signal.bb_position > 0.8 else '—'} | `{w_bb:.2f}` | {wr(bb_stat)} |
| Volume | `{signal.volume_ratio}x` | {vol_icon} | adaptatif | — |
| ATR (14) | `{signal.atr}` | — | — | — |
| Prix | `{signal.entry_price}` | — | — | — |

### Données Temps Réel (Order Book + VWAP)
| Indicateur | Valeur | Interprétation |
|---|---|---|
| Order Book Imbalance | `{signal.ob_imbalance or 0:.3f}` | {ob_icon} |
| VWAP Distance | `{signal.vwap_dist_pct or 0:+.2f}%` | {vwap_icon} VWAP |
| Trend Slope (1m×20) | `{signal.trend_slope or 0:+.5f}%/candle` | {trend_icon} |

### Signal Adaptatif
> **{signal.signal.value.upper()}** — Confiance : **{signal.confidence}/100**
> Seuil minimum appris : `{self.memory.adaptive_params.get('confidence_floor', 40)}/100`

### Performance Historique sur {signal.asset}
| Métrique | Valeur |
|---|---|
| Trades analysés | `{total_signals_asset}` |
| Win Rate | `{win_rate_asset:.1%}` |
| P&L moyen EMA | `{avg_pnl_asset:+.3f}%` |

### Paramètres ML Courants
| Paramètre | Valeur Apprise |
|---|---|
| SL multiplier | `{self.memory.adaptive_params.get('sl_atr_multiplier', 1.5):.2f}×ATR` |
| TP ratio | `1:{self.memory.adaptive_params.get('tp_rr_ratio', 2.5):.2f}` |
| Confidence floor | `{self.memory.adaptive_params.get('confidence_floor', 40)}/100` |

### Liens
{self.obsidian.wikilink('decisions', self.obsidian.timestamp_filename('predict', signal.asset))}
{self.obsidian.wikilink('config', 'ScanAgent_memory')}
"""
        self.obsidian.write_note("technique", filename, frontmatter, content)
        logger.info(
            "[%s] 📊 %s/%s → %s (%d/100) [RSI:%.1f MACD:%+.4f]",
            self.name, signal.asset, signal.timeframe,
            signal.signal.value, signal.confidence,
            signal.rsi or 0, signal.macd_hist or 0,
        )

    @staticmethod
    def _is_forex(pair: str) -> bool:
        return len(set(pair.replace("/", " ").upper().split()) & FOREX_CCY) >= 2