"""
CycleManager — Analyse par paire et cycle principal ORACLE v2.

Extrait de OracleSystem pour isoler la logique d'analyse :
  - run_cycle()      : un cycle 60s complet sur toutes les paires
  - analyze_symbol() : une passe neuromorphique complète sur un symbole

Améliorations v2.1 :
  - Émission d'événements ParliamentDecidedEvent sur le bus global
  - Enregistrement des signaux dans MetricsTracker (corrélation inter-strates)
  - Vérification connecteur dégradé avant chaque cycle
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oracle_system import OracleSystem

logger = logging.getLogger("ORACLE.Cycle")


class CycleManager:
    """
    Délégué d'analyse de cycle d'OracleSystem.

    Pattern « Context Object » : self._s est une référence directe au
    système parent.  Ce choix évite de passer ~15 dépendances explicites
    en constructeur tout en gardant OracleSystem comme source de vérité
    unique pour tout l'état partagé (brainstem, parliament, strates…).

    Durée de vie : identique à OracleSystem.
    """

    def __init__(self, system: "OracleSystem"):
        self._s = system

    async def run_cycle(self) -> None:
        """Un cycle complet pour toutes les paires configurées."""
        s = self._s

        # 0. Vérifier connecteurs dégradés
        if s._connector_degraded:
            degraded = ", ".join(s._connector_degraded)
            logger.warning(f"Cycle ignoré — connecteurs dégradés: {degraded}")
            return

        # 1. Vérification brainstem AVANT tout
        alive, reason = s.brainstem.is_alive()
        if not alive:
            logger.warning(f"Brainstem BLOQUE: {reason}")
            if s.alert_queue:
                s.alert_queue.alert_brainstem(reason)
            if s.narrator:
                s.narrator.brainstem_block(reason)
            return

        # 2. Paper monitor — vérifie SL/TP des positions ouvertes en paper
        #    Exécuté EN DÉBUT de cycle pour que le Brainstem voit les pertes
        #    AVANT d'analyser de nouveaux signaux.
        if s.mode == "paper" and hasattr(s, "paper_monitor") and s.binance:
            await s.paper_monitor.check_positions(s.binance, s._execution_engine)

        # 3. Scan Polymarket (async, mise en cache 5min)
        poly_opps = []
        try:
            poly_opps = await s.polymarket_strate.scan()
        except Exception as e:
            logger.warning(f"Polymarket scan failed: {e}")

        # 4. Cycle par paire
        for symbol in s.config.TRADING_PAIRS:
            try:
                await self.analyze_symbol(symbol, poly_opps)
            except Exception as e:
                logger.error(f"Erreur analyse {symbol}: {e}")

    async def analyze_symbol(self, symbol: str, poly_opps: list) -> None:
        """Analyse complète d'un symbole — une passe neuromorphique complète."""
        s = self._s
        asset = symbol.replace("USDT", "").replace("USD", "")

        # ── Fetch données ──────────────────────────────────────────────
        candles_by_tf = {}
        orderbook = {}
        if s.binance:
            for tf in [s.config.PRIMARY_TIMEFRAME] + s.config.SECONDARY_TIMEFRAMES:
                candles_by_tf[tf] = await s.binance.fetch_ohlcv(symbol, tf, limit=100)
            orderbook = await s.binance.fetch_orderbook(symbol, limit=20)
        else:
            logger.debug(f"{symbol}: pas de connecteur — skip")
            return

        if not candles_by_tf.get(s.config.PRIMARY_TIMEFRAME):
            return

        # ── Sensory layer ──────────────────────────────────────────────
        sensory_input = s.sensory.build_sensory_input(
            symbol=symbol,
            candles_by_tf=candles_by_tf,
            orderbook=orderbook,
        )

        # ── Feature extraction + cascade ──────────────────────────────
        primary_ohlcv = [c for c in sensory_input.ohlcv if c.timeframe == s.config.PRIMARY_TIMEFRAME]

        features_by_tf = {}
        for tf in [s.config.PRIMARY_TIMEFRAME] + s.config.SECONDARY_TIMEFRAMES:
            tf_ohlcv = [c for c in sensory_input.ohlcv if c.timeframe == tf]
            features_by_tf[tf] = s.feature_layer.extract(tf_ohlcv, symbol, tf)

        cascade = s.feature_layer.cascade_analysis(features_by_tf)
        primary_fv = features_by_tf.get(s.config.PRIMARY_TIMEFRAME)

        # ── Predictive layer ──────────────────────────────────────────
        predict_features = {
            "symbol": symbol,
            "rsi": primary_fv.rsi if primary_fv else 50.0,
            "macd": primary_fv.macd if primary_fv else 0.0,
            "volume_ratio": primary_fv.volume_ratio if primary_fv else 1.0,
            "bb_position": primary_fv.bb_position if primary_fv else 0.0,
            "price_change_pct": primary_fv.price_change_pct if primary_fv else 0.0,
            "trend_score": (1.0 if cascade.get("dominant_trend") == "UP"
                            else -1.0 if cascade.get("dominant_trend") == "DOWN" else 0.0),
            "orderbook_imbalance": sensory_input.orderbook_imbalance,
        }
        prediction = s.predictive.predict(predict_features)

        # ── Strates → Votes ───────────────────────────────────────────
        strate_data = {
            "ohlcv": [{"open": c.open, "high": c.high, "low": c.low,
                       "close": c.close, "volume": c.volume}
                      for c in primary_ohlcv],
            "features": {
                "rsi": predict_features["rsi"],
                "macd": predict_features["macd"],
                "macd_signal": primary_fv.macd_signal if primary_fv else 0.0,
                "volume_ratio": predict_features["volume_ratio"],
                "bb_position": predict_features["bb_position"],
                "price_change_pct": predict_features["price_change_pct"],
            },
            "cascade": cascade,
            "macro": {},
        }

        from brain.parliament import Vote
        votes = []

        # Strates natives
        for strate_name, strate_obj in [
            ("AMD", s.amd_strate),
            ("MOMENTUM", s.momentum_strate),
            ("STRUCTURE", s.structure_strate),
            ("MACRO", s.macro_strate),
        ]:
            res = strate_obj.safe_analyze(strate_data)
            if res.confidence > 0.3:
                votes.append(Vote(strate_name, res.direction, res.confidence, res.reasoning))
            # Enregistrer dans MetricsTracker pour corrélation inter-strates
            if hasattr(s, "_metrics"):
                s._metrics.record_signal(strate_name, res.direction, res.confidence)

        # Predictive vote
        if prediction.confidence > 0.3:
            votes.append(Vote(
                "PREDICTIVE", prediction.direction, prediction.confidence,
                f"Model: {prediction.model_version} p={prediction.probability:.2f}",
            ))

        # Polymarket vote
        poly_vote = s.polymarket_strate.generate_parliament_vote(poly_opps, asset)
        if poly_vote.confidence > 0:
            votes.append(poly_vote)

        # BTC Latency Arb vote
        if asset == "BTC" and s.config.BTC_LATENCY_ARB_ENABLED:
            latency_signals = s.latency_arb.last_signals
            if latency_signals:
                lat_vote = s.latency_arb.generate_parliament_vote(latency_signals)
                if lat_vote.confidence > 0:
                    votes.append(lat_vote)

        # Twitter / X sentiment vote — BTC uniquement (signal externe)
        if asset == "BTC" and s.twitter_strate and s.twitter_strate._available:
            try:
                tw_result = await s.twitter_strate.scan()
                if tw_result.confidence > 0.15:
                    tw_vote = s.twitter_strate.generate_parliament_vote(tw_result)
                    votes.append(tw_vote)
                    logger.info(
                        f"Twitter vote: {tw_result.direction} "
                        f"conf={tw_result.confidence:.0%} "
                        f"({'cache' if tw_result.cached else 'frais'}) | "
                        f"{tw_result.bullish_count}↑ {tw_result.bearish_count}↓ "
                        f"/ {tw_result.tweet_count} tweets"
                    )
            except Exception as e:
                logger.debug(f"Twitter vote ignoré ({e})")

        # Strates cognitives (Épistémique, Minsky, Réflexivité, Comportemental, Fractal)
        if s.cognitive_mgr.available:
            try:
                cog_votes = s.cognitive_mgr.generate_votes(
                    symbol, primary_ohlcv,
                    features=predict_features,
                    trade_history=s._trade_history,
                )
                n_cog = sum(1 for v in cog_votes if v.confidence > 0.3)
                for v in cog_votes:
                    if v.confidence > 0.3:
                        votes.append(v)
                if n_cog:
                    logger.debug(f"{symbol}: {n_cog} vote(s) cognitif(s) ajouté(s)")
            except Exception as e:
                logger.debug(f"CognitiveStrates error pour {symbol}: {e}")

        if not votes:
            return

        # ── Narrator — observe features AVANT délibération ────────────
        if s.narrator and primary_fv:
            price = primary_ohlcv[-1].close if primary_ohlcv else 0
            s.narrator.observe_market(
                symbol=symbol,
                price=price,
                rsi=primary_fv.rsi,
                trend=cascade.get("dominant_trend", "NEUTRAL"),
                volume_ratio=primary_fv.volume_ratio,
                orderbook_imbalance=sensory_input.orderbook_imbalance,
            )

        # ── Parliament deliberation (via Council when available) ───────
        import numpy as np

        if hasattr(s, "parliament_council") and s.parliament_council is not None:
            # Build agent context from available market data
            try:
                ohlcv_list = [c for c in primary_ohlcv if hasattr(c, "close")]
                closes = np.array([c.close for c in ohlcv_list[-50:]], dtype=float)
                volumes = np.array([c.volume for c in ohlcv_list[-50:]], dtype=float)
                returns = np.diff(np.log(closes + 1e-10)) if len(closes) > 1 else np.zeros(1)
                ctx = s.parliament_council.build_context(
                    symbol=symbol,
                    returns=returns,
                    close=closes,
                    volume=volumes,
                    rsi=predict_features.get("rsi", 50.0),
                    macd=predict_features.get("macd", 0.0),
                    bb_pos=predict_features.get("bb_position", 0.0),
                    vol_ratio=predict_features.get("volume_ratio", 1.0),
                    trend=cascade.get("dominant_trend", "NEUTRAL"),
                )
            except Exception:
                ctx = None

            decision = await s.parliament_council.deliberate(symbol, votes, context=ctx)
        else:
            decision = s.parliament.deliberate(votes)

        s.last_parliament_decision = decision

        logger.info(f"{symbol}: {decision.direction} ({decision.strength:.0%}) | {len(votes)} votes")

        # ── Émettre événement ParliamentDecidedEvent ───────────────────
        from events import get_event_bus, ParliamentDecidedEvent
        await get_event_bus().emit(ParliamentDecidedEvent(
            symbol=symbol,
            direction=decision.direction,
            strength=decision.strength,
            n_votes=len(votes),
            polymarket_aligned=bool(decision.polymarket_alignment),
        ))

        # ── Narrator — explique la délibération ───────────────────────
        if s.narrator:
            hw = {n: s.hebbian.get_weight(n) for n in ["AMD", "MOMENTUM", "POLYMARKET", "LATENCY_ARB"]}
            await s.narrator.deliberate(symbol, votes, decision, hw)

        # ── Working Memory consensus ───────────────────────────────────
        if decision.direction != "NEUTRAL":
            s.working_memory.push(decision.direction, decision.strength, "PARLIAMENT")

        consensus = s.working_memory.get_consensus()
        self._update_active_signal(symbol, decision, s.config.PRIMARY_TIMEFRAME)

        # ── Réflexion périodique ───────────────────────────────────────
        if s.narrator:
            all_strates = [
                "AMD", "MOMENTUM", "STRUCTURE", "MACRO", "POLYMARKET", "LATENCY_ARB",
                "EPISTEMIQUE", "MINSKY", "REFLEXIVITE", "COMPORTEMENTAL", "FRACTAL",
            ]
            await s.narrator.reflect(
                s._trade_history,
                {n: s.hebbian.get_weight(n) for n in all_strates},
                s._open_positions,
            )

        # ── Exécution si consensus atteint ────────────────────────────
        if consensus and s.mode in ["paper", "live"]:
            direction, confidence = consensus
            await s._execution_engine.try_execute(symbol, direction, confidence, decision, primary_fv)

    def _update_active_signal(self, symbol: str, decision, timeframe: str) -> None:
        s = self._s
        s._active_signals = [sig for sig in s._active_signals if sig["symbol"] != symbol]
        if decision.direction != "NEUTRAL" and decision.strength > 0.4:
            s._active_signals.append({
                "symbol": symbol,
                "direction": decision.direction,
                "confidence": decision.strength,
                "timeframe": timeframe,
                "source": "PARLIAMENT",
                "polymarket": decision.polymarket_alignment,
            })
