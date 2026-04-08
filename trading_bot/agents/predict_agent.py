"""
Agent 3 — Prédicteur (Predict)
Fusionne les signaux Scan + Research, applique un modèle de prédiction ML,
et émet un signal de confiance combiné vers l'Agent Risk.
Vault : vault/decisions/ (prédictions) + vault/apprentissage/ (learning journal)
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from core.base_agent import BaseAgent
from core.learning_engine import LearningEngine
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient
from core.strate_0_epistemic import EpistemologicalEngine
from models.learning import AgentMemory, MarketRegime
from models.signals import (
    TechnicalSignal, FundamentalSignal, CombinedSignal, SignalType,
)

logger = logging.getLogger(__name__)

SIGNAL_TTL_SEC = 900   # 15 min : signal expiré si non convergé


class PredictAgent(BaseAgent):
    """
    Agent de prédiction — cerveau de décision.

    Modèle ML :
    - Poids tech/fond adaptatifs (appris selon le win rate par régime de marché)
    - Seuil de confiance adaptatif (relevé si win rate < 45%, abaissé si > 65%)
    - Régime de marché détecté et utilisé pour ajuster les poids
    - Toutes les prédictions loguées dans le vault pour traçabilité complète
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        learning: LearningEngine,
        telegram=None,
        config: dict = None,
    ):
        super().__init__("PredictAgent", "decisions", bus, obsidian, config or {})
        self.learning = learning
        self.telegram = telegram
        self.memory: AgentMemory = None

        # Multi-timeframe buffer : asset → {timeframe: signal_dict}
        self._pending_tech:  dict[str, dict[str, dict]] = {}
        self._pending_fund:  dict[str, dict] = {}
        self._predictions:   list[dict]      = []   # journal des prédictions
        self._last_predicted: dict[str, float] = {}  # asset → timestamp dernière prédiction
        self._prediction_cooldown = 60.0             # secondes entre deux prédictions par asset

        # DataSheet buffer : asset → dernière DataSheet reçue de SynthesisAgent
        self._market_ctx: dict[str, dict] = {}

        # Régime de marché par asset (de RegimeAgent)
        self._regime_by_asset: dict[str, str] = {}

        # Insights KnowledgeAgent par asset
        self._knowledge_insights: dict[str, dict] = {}

        # ── Strate 0 — Epistemological Gate ──────────────────────────────────
        # Buffer de prix (entry_price de chaque signal technique reçu)
        # Utilisé par le gate pour calculer entropie et SNR sans MarketDataManager
        self._price_buffers: dict[str, deque] = {}  # asset → deque[float]
        _vault = Path(config.get("vault_path", "vault")) if config else None
        self._epistemic_gate = EpistemologicalEngine(
            snr_threshold         = float((config or {}).get("epistemic_snr_threshold",   0.35)),
            uncertainty_threshold = float((config or {}).get("epistemic_unc_threshold",   0.40)),
            entropy_window        = int(  (config or {}).get("epistemic_window",           50)),
            vault_path            = _vault,
        )

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        self.memory = self.learning.load_memory("PredictAgent")
        logger.info(
            "[%s] Mémoire chargée : SL=%.2f×ATR | conf_floor=%d | tech_w=%.2f",
            self.name,
            self.memory.adaptive_params.get("sl_atr_multiplier", 1.5),
            self.memory.adaptive_params.get("confidence_floor", 55),
            self.memory.adaptive_params.get("tech_weight", 0.6),
        )

    def _register_subscriptions(self) -> None:
        self.bus.subscribe(CHANNELS["signals_technical"],   self._on_tech_signal)
        self.bus.subscribe(CHANNELS["signals_fundamental"], self._on_fund_signal)
        self.bus.subscribe(CHANNELS["market_context"],      self._on_market_context)
        self.bus.subscribe(CHANNELS["regime"],              self._on_regime_update)
        self.bus.subscribe(CHANNELS["knowledge_result"],    self._on_knowledge_result)
        self.bus.subscribe(CHANNELS["meta_directive"],      self._on_meta_directive)

    # ── Cycle principal ───────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        self._purge_stale()

    # ── Handlers bus ──────────────────────────────────────────────────────────

    async def _on_tech_signal(self, data: dict) -> None:
        asset = data.get("asset")
        tf    = data.get("timeframe", "1h")
        if asset:
            if asset not in self._pending_tech:
                self._pending_tech[asset] = {}
            self._pending_tech[asset][tf] = data

            # Accumule entry_price pour le gate épistémologique (Strate 0)
            price = data.get("entry_price")
            if price and price > 0:
                if asset not in self._price_buffers:
                    self._price_buffers[asset] = deque(maxlen=120)
                self._price_buffers[asset].append(float(price))

            await self._predict(asset)

    async def _on_fund_signal(self, data: dict) -> None:
        asset = data.get("asset")
        if asset:
            self._pending_fund[asset] = data
            await self._predict(asset)

    async def _on_market_context(self, data: dict) -> None:
        """Reçoit les DataSheets de SynthesisAgent — stocke le dernier contexte par asset."""
        asset = data.get("asset")
        if asset:
            self._market_ctx[asset] = data
            logger.debug("[%s] DataSheet reçue pour %s", self.name, asset)

    async def _on_regime_update(self, data: dict) -> None:
        """Reçoit le régime de marché de RegimeAgent — ajuste dynamiquement les poids tech/fond."""
        asset  = data.get("asset")
        regime = data.get("regime")
        if asset and regime:
            prev = self._regime_by_asset.get(asset)
            self._regime_by_asset[asset] = regime
            if prev != regime:
                logger.info("[%s] Régime %s : %s → %s", self.name, asset, prev, regime)

    async def _on_knowledge_result(self, data: dict) -> None:
        """Reçoit les insights de KnowledgeAgent — enrichit les prédictions."""
        if data.get("requester") != "PredictAgent":
            return
        asset = data.get("asset")
        if asset:
            self._knowledge_insights[asset] = data
            logger.debug("[%s] Insight KnowledgeAgent reçu pour %s (WR=%.0f%%)",
                         self.name, asset, data.get("win_rate", 0) * 100)

    async def _on_meta_directive(self, data: dict) -> None:
        """Reçoit les directives du MetaAgent (CEO) — ajuste les paramètres adaptatifs."""
        if self.memory is None:
            return
        dtype = data.get("type")
        if dtype == "weight_update":
            tw = data.get("tech_weight")
            fw = data.get("fund_weight")
            if tw is not None:
                self.memory.adaptive_params["tech_weight"] = float(tw)
                logger.info("[%s] 📋 CEO directive → tech_weight=%.2f", self.name, tw)
            if fw is not None:
                self.memory.adaptive_params["fund_weight"] = float(fw)
        elif dtype == "confidence_update":
            nc = data.get("min_confidence")
            if nc is not None:
                self.memory.adaptive_params["confidence_floor"] = int(nc)
                logger.info("[%s] 📋 CEO directive → confidence_floor=%d", self.name, nc)

    # ── Prédiction ML — Wall Street Reasoning ────────────────────────────────

    async def _predict(self, asset: str) -> None:
        """
        Moteur de décision multi-couches :
        1. Confluence multi-timeframe (1h + 4h + 1d doivent pointer dans le même sens)
        2. Score tech × poids régime + score fondamental
        3. Ajustement order book imbalance (confirmation institutionnelle)
        4. Ajustement VWAP (prix au-dessus = momentum, en-dessous = retard)
        5. Filtre divergence tech/fund : rejet si opposés
        6. Seuil adaptatif ML

        Mode dégradé : si le signal fondamental est absent, le signal technique
        seul est utilisé avec une pénalité de confiance (-15) pour compenser
        le manque de confirmation.
        """
        tf_signals = self._pending_tech.get(asset, {})
        fund_d     = self._pending_fund.get(asset)

        # Besoin d'au moins un signal technique
        if not tf_signals:
            return

        # Mode dégradé : pas de signal fondamental → créer un signal neutre
        degraded_mode = False
        if not fund_d:
            degraded_mode = True
            fund_d = {
                "type": "fundamental_signal",
                "asset": asset,
                "sentiment_score": 0,
                "signal": "neutral",
                "confidence": 0,
                "news_count": 0,
                "key_events": ["[MODE DÉGRADÉ] Signal fondamental indisponible"],
                "source": "degraded_fallback",
            }
            logger.info(
                "[%s] ⚠️ Mode dégradé pour %s — signal fondamental absent, technique seul",
                self.name, asset,
            )

        # ── Cooldown : évite les doublons ──
        now  = datetime.now(timezone.utc).timestamp()
        last = self._last_predicted.get(asset, 0)
        if now - last < self._prediction_cooldown:
            return

        # ── Choisir le signal technique de référence (priorité 1h, sinon le premier dispo) ──
        tech_d = tf_signals.get("1h") or tf_signals.get("4h") or next(iter(tf_signals.values()))
        tech   = TechnicalSignal.from_dict(tech_d)
        fund   = FundamentalSignal.from_dict(fund_d)

        # ── Confluence multi-timeframe ──
        mtf_boost, mtf_summary = self._multi_timeframe_confluence(asset, tf_signals)

        # ── Régime de marché + poids adaptatifs ──
        # Priorité : RegimeAgent externe > détection interne
        ext_regime_str = self._regime_by_asset.get(asset)
        if ext_regime_str:
            _regime_map = {
                "trending_up":   MarketRegime.BULL,
                "trending_down": MarketRegime.BEAR,
                "volatile":      MarketRegime.VOLATILE,
                "ranging":       MarketRegime.SIDEWAYS,
            }
            regime = _regime_map.get(ext_regime_str, self._detect_regime())
        else:
            regime = self._detect_regime()
        tech_w, fund_w = self._regime_weights(regime)

        # ── Score combiné de base ──
        combined_score, direction, confidence = self._combine_signals(tech, fund, tech_w, fund_w)

        if direction == SignalType.NEUTRAL:
            return

        # ── Ajout du boost multi-timeframe ──
        confidence = min(confidence + mtf_boost, 100)

        # ── Ajustement order book imbalance (confirmation institutionnelle) ──
        ob_adj, ob_reason = self._ob_adjustment(direction, tech.ob_imbalance)
        confidence = min(max(confidence + ob_adj, 0), 100)

        # ── Ajustement VWAP distance ──
        vwap_adj, vwap_reason = self._vwap_adjustment(direction, tech.vwap_dist_pct)
        confidence = min(max(confidence + vwap_adj, 0), 100)

        # ── Ajustement Order Flow / CVD (confirmation smart money) ──
        flow_adj, flow_reason = self._order_flow_adjustment(direction, tech)
        confidence = min(max(confidence + flow_adj, 0), 100)

        # ── Ajustement Anchored VWAP (support/résistance institutionnel) ──
        avwap_adj, avwap_reason = self._avwap_adjustment(direction, tech.avwap_dist_pct)
        confidence = min(max(confidence + avwap_adj, 0), 100)

        # ── Ajustement SynthesisAgent DataSheet (contexte de marché global) ──
        ctx_adj, ctx_reason = self._datasheet_adjustment(asset, direction)
        confidence = min(max(confidence + ctx_adj, 0), 100)

        # ── Pénalité mode dégradé : -15 confiance (pas de confirmation fondamentale) ──
        if degraded_mode:
            confidence = max(confidence - 15, 0)

        # ── Filtre : divergence tech/fund hard (skip en mode dégradé) ──
        if (not degraded_mode and
                tech.signal != SignalType.NEUTRAL and
                fund.signal != SignalType.NEUTRAL and
                tech.signal != fund.signal):
            logger.info(
                "[%s] ❌ Divergence dure %s : tech=%s fund=%s — rejeté",
                self.name, asset, tech.signal.value, fund.signal.value,
            )
            return

        # ── Requête KnowledgeAgent : envoyer le contexte pour enrichissement ──
        # (la réponse arrivera via _on_knowledge_result sur le prochain signal)
        await self.bus.publish(CHANNELS["knowledge_query"], {
            "requester": "PredictAgent",
            "asset":     asset,
            "context": {
                "direction":   direction.value,
                "confidence":  confidence,
                "regime":      ext_regime_str or "unknown",
                "rsi":         tech.rsi,
                "atr":         tech.atr,
                "entry_price": tech.entry_price,
            },
            "k": 5,
        })

        # ── Ajustement KnowledgeAgent : patterns similaires passés ──
        insight = self._knowledge_insights.get(asset, {})
        if insight:
            hist_wr = insight.get("win_rate", 0.5)
            if hist_wr >= 0.70:
                knowledge_boost = 5
                logger.debug("[%s] 📚 Knowledge boost +5 (WR passé=%.0f%%)", self.name, hist_wr * 100)
            elif hist_wr <= 0.30:
                knowledge_boost = -5
                logger.debug("[%s] 📚 Knowledge pénalité -5 (WR passé=%.0f%%)", self.name, hist_wr * 100)
            else:
                knowledge_boost = 0
            confidence = min(max(confidence + knowledge_boost, 0), 100)

        # ── Strate 0 — Epistemological Gate (signal vs bruit) ────────────────
        # Construit une Series de prix depuis le buffer accumulé par _on_tech_signal
        _price_buf = self._price_buffers.get(asset)
        if _price_buf and len(_price_buf) >= 10:
            _prices = pd.Series(list(_price_buf))
            # Prédictions multi-timeframe comme proxy d'incertitude
            _preds = np.array([
                float(s.get("confidence", 60))
                for s in tf_signals.values()
                if s.get("confidence")
            ])
            _allowed, _gate_info = self._epistemic_gate.should_trade(
                prices=_prices, predictions=_preds if len(_preds) > 0 else None,
                asset=asset, timeframe=tech.timeframe,
            )
            if not _allowed:
                logger.info(
                    "[%s] 🚫 Strate0 BLOQUÉ %s | SNR=%.3f unc=%.3f | %s",
                    self.name, asset,
                    _gate_info["snr"], _gate_info["uncertainty"], _gate_info["reason"],
                )
                return
        # Si buffer trop court (démarrage) → gate ignoré, signal passe normalement

        # ── Seuil adaptatif ML ──
        conf_floor = int(self.memory.adaptive_params.get("confidence_floor", 25))
        if confidence < conf_floor:
            logger.debug(
                "[%s] Confiance insuffisante %s : %d < %d (floor)",
                self.name, asset, confidence, conf_floor,
            )
            return

        self._last_predicted[asset] = now

        # ── Construire le signal combiné ──
        combined = CombinedSignal(
            asset               = asset,
            final_signal        = direction,
            combined_confidence = confidence,
            technical_weight    = tech_w,
            fundamental_weight  = fund_w,
            technical           = tech,
            fundamental         = fund,
        )

        # ── Publier vers RiskAgent ──
        await self.bus.publish(CHANNELS["decisions"], {
            "type":              "combined_signal",
            "asset":             asset,
            "direction":         direction.value,
            "confidence":        confidence,
            "tech_weight":       tech_w,
            "fund_weight":       fund_w,
            "regime":            regime.value,
            "entry_price":       tech.entry_price,
            "atr":               tech.atr,
            "tech_signal":       tech_d,
            "fund_signal":       fund_d,
            "sl_atr_multiplier": self.memory.adaptive_params.get("sl_atr_multiplier", 1.5),
            "tp_rr_ratio":       self.memory.adaptive_params.get("tp_rr_ratio", 2.5),
            "mtf_boost":         mtf_boost,
            "ob_adj":            ob_adj,
            "vwap_adj":          vwap_adj,
            "flow_adj":          flow_adj,
            "avwap_adj":         avwap_adj,
            "ctx_adj":           ctx_adj,
        })

        # ── Journal et vault ──
        pred_entry = {
            "asset": asset, "direction": direction.value,
            "confidence": confidence, "regime": regime.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mtf_boost": mtf_boost, "ob_adj": ob_adj, "vwap_adj": vwap_adj,
            "flow_adj": flow_adj, "avwap_adj": avwap_adj, "ctx_adj": ctx_adj,
        }
        self._predictions.append(pred_entry)
        # vault/decisions/ supprimé — signal déjà publié sur le bus (→ RiskAgent)
        # et envoyé sur Telegram. Aucun agent ne relisait ces notes.

        # ── Notification Telegram — convergence ──
        if self.telegram:
            try:
                await self.telegram.convergence_signal(
                    asset=asset,
                    direction=direction.value,
                    confidence=confidence,
                    tech_w=tech_w,
                    fund_w=fund_w,
                    regime=regime.value,
                    mtf_boost=mtf_boost,
                    ob_adj=ob_adj,
                    vwap_adj=vwap_adj,
                )
            except Exception as exc:
                logger.warning("[%s] Erreur Telegram convergence: %s", self.name, exc)

        # ── Nettoyage des signaux utilisés ──
        self._pending_tech.pop(asset, None)
        self._pending_fund.pop(asset, None)

        mode_tag = " [DÉGRADÉ]" if degraded_mode else ""
        logger.info(
            "[%s] 🔮 %s → %s (%d/100) | Régime:%s | MTF:%+d OB:%+d VWAP:%+d CTX:%+d | Poids %.0f/%.0f%%%s",
            self.name, asset, direction.value, confidence, regime.value,
            mtf_boost, ob_adj, vwap_adj, ctx_adj, tech_w * 100, fund_w * 100, mode_tag,
        )

    # ── Combinaison ML des signaux ────────────────────────────────────────────

    def _combine_signals(
        self,
        tech: TechnicalSignal,
        fund: FundamentalSignal,
        tech_w: float,
        fund_w: float,
    ) -> tuple[float, SignalType, int]:
        """
        Score combiné pondéré avec régularisation.
        Retourne (score_brut, direction, confiance_0_100).
        """
        t_score = tech.confidence * (1 if tech.signal == SignalType.BULLISH else -1 if tech.signal == SignalType.BEARISH else 0)
        f_score = fund.confidence * (1 if fund.signal == SignalType.BULLISH else -1 if fund.signal == SignalType.BEARISH else 0)

        # Si technique NEUTRAL mais Swarmode fort (≥35) → utiliser fond seul
        if tech.signal == SignalType.NEUTRAL and abs(f_score) >= 35:
            combined_raw = f_score * 0.90   # légère décote (pas de confirmation tech)
        else:
            combined_raw = t_score * tech_w + f_score * fund_w

        confidence = int(min(abs(combined_raw), 100))

        if combined_raw > 15:
            return combined_raw, SignalType.BULLISH, confidence
        elif combined_raw < -15:
            return combined_raw, SignalType.BEARISH, confidence
        return combined_raw, SignalType.NEUTRAL, confidence

    # ── Multi-Timeframe Confluence ────────────────────────────────────────────

    def _multi_timeframe_confluence(
        self, asset: str, tf_signals: dict[str, dict]
    ) -> tuple[int, str]:
        """
        Analyse la convergence des signaux multi-timeframe.

        Logique Wall Street :
        - 1 timeframe           → 0 bonus (pas de confirmation)
        - 2 timeframes alignés  → +10 (confirmation valide)
        - 3 timeframes alignés  → +20 (conviction élevée — setup institutionnel)
        - Timeframes divergents → -5 (signal mixte)

        Retourne (boost_int, summary_str).
        """
        if len(tf_signals) < 2:
            return 0, f"1 timeframe ({list(tf_signals.keys())[0] if tf_signals else '?'}) — pas de confluence"

        directions = {tf: sig.get("signal", "neutral") for tf, sig in tf_signals.items()}

        bulls = sum(1 for d in directions.values() if d == "bullish")
        bears = sum(1 for d in directions.values() if d == "bearish")
        total = len(directions)

        tf_list = " | ".join(f"`{tf}` {d}" for tf, d in sorted(directions.items()))

        if bulls == total:
            boost = 20 if total >= 3 else 10
            return boost, f"✅ Confluence {total}/{total} BULLISH — {tf_list} → +{boost} confiance"
        elif bears == total:
            boost = 20 if total >= 3 else 10
            return boost, f"✅ Confluence {total}/{total} BEARISH — {tf_list} → +{boost} confiance"
        elif bulls >= 2 or bears >= 2:
            return 5, f"🟡 Confluence partielle — {tf_list} → +5 confiance"
        else:
            return -5, f"🔴 Divergence multi-TF — {tf_list} → -5 confiance"

    # ── Ajustements contextuels ───────────────────────────────────────────────

    @staticmethod
    def _ob_adjustment(direction: SignalType, ob_imbalance: Optional[float]) -> tuple[int, str]:
        """
        Order Book Imbalance comme signal institutionnel.
        Seuils calibrés sur données Binance L2 :
        > +0.20 = pression acheteuse significative
        < -0.20 = pression vendeuse significative
        """
        if ob_imbalance is None:
            return 0, "Order book non disponible"

        if direction == SignalType.BULLISH:
            if ob_imbalance > 0.20:
                return 12, f"📖 OB Imbalance +{ob_imbalance:.2f} → forte pression acheteuse (+12)"
            elif ob_imbalance > 0.10:
                return 6, f"📖 OB Imbalance +{ob_imbalance:.2f} → pression acheteuse modérée (+6)"
            elif ob_imbalance < -0.20:
                return -12, f"📖 OB Imbalance {ob_imbalance:.2f} → contre-signal vendeur (-12)"
            elif ob_imbalance < -0.10:
                return -6, f"📖 OB Imbalance {ob_imbalance:.2f} → légère pression vendeuse (-6)"
        elif direction == SignalType.BEARISH:
            if ob_imbalance < -0.20:
                return 12, f"📖 OB Imbalance {ob_imbalance:.2f} → forte pression vendeuse (+12)"
            elif ob_imbalance < -0.10:
                return 6, f"📖 OB Imbalance {ob_imbalance:.2f} → pression vendeuse modérée (+6)"
            elif ob_imbalance > 0.20:
                return -12, f"📖 OB Imbalance +{ob_imbalance:.2f} → contre-signal acheteur (-12)"
            elif ob_imbalance > 0.10:
                return -6, f"📖 OB Imbalance +{ob_imbalance:.2f} → légère pression acheteuse (-6)"
        return 0, f"📖 OB Imbalance {ob_imbalance:.2f} → neutre"

    @staticmethod
    def _vwap_adjustment(direction: SignalType, vwap_dist_pct: Optional[float]) -> tuple[int, str]:
        """
        Distance VWAP comme filtre de momentum.
        Wall Street : prix au-dessus du VWAP = momentum haussier intrajournalier.
        Extension > 2% = signe d'excès potentiel.
        """
        if vwap_dist_pct is None:
            return 0, "VWAP non disponible"

        if direction == SignalType.BULLISH:
            if 0 < vwap_dist_pct < 1.0:
                return 5, f"📊 VWAP +{vwap_dist_pct:.2f}% → prix au-dessus, momentum intrajour (+5)"
            elif vwap_dist_pct >= 1.0:
                return -5, f"📊 VWAP +{vwap_dist_pct:.2f}% → extension excessive, risque retour (-5)"
            elif vwap_dist_pct < -1.5:
                return -8, f"📊 VWAP {vwap_dist_pct:.2f}% → prix sous VWAP, pas de momentum (-8)"
        elif direction == SignalType.BEARISH:
            if -1.0 < vwap_dist_pct < 0:
                return 5, f"📊 VWAP {vwap_dist_pct:.2f}% → prix sous VWAP, momentum baissier (+5)"
            elif vwap_dist_pct <= -1.0:
                return -5, f"📊 VWAP {vwap_dist_pct:.2f}% → extension basse excessive (-5)"
            elif vwap_dist_pct > 1.5:
                return -8, f"📊 VWAP +{vwap_dist_pct:.2f}% → prix au-dessus VWAP, pas de momentum baissier (-8)"
        return 0, f"📊 VWAP {vwap_dist_pct:.2f}% → neutre"

    @staticmethod
    def _order_flow_adjustment(direction: SignalType, tech) -> tuple[int, str]:
        """
        Order Flow / CVD confirmation.
        - Delta divergence = signal faible → pénalité
        - Absorption = smart money oppose la direction → pénalité
        - Delta 5m aligné avec direction → bonus
        """
        adj = 0
        parts = []

        # Delta divergence : prix et volume vont dans des directions opposées
        if getattr(tech, "delta_divergence", False):
            adj -= 12
            parts.append("delta diverge (-12)")

        # Absorption : gros volume mais prix ne bouge pas = smart money absorbe
        if getattr(tech, "absorption", False):
            adj -= 8
            parts.append("absorption détectée (-8)")

        # Delta 5 min confirmation
        delta = getattr(tech, "delta_5m", None)
        if delta is not None and abs(delta) > 1000:  # seuil en USDT
            if direction == SignalType.BULLISH and delta > 0:
                adj += 8
                parts.append(f"delta +{delta:.0f} confirmé (+8)")
            elif direction == SignalType.BULLISH and delta < 0:
                adj -= 6
                parts.append(f"delta {delta:.0f} contre-signal (-6)")
            elif direction == SignalType.BEARISH and delta < 0:
                adj += 8
                parts.append(f"delta {delta:.0f} confirmé (+8)")
            elif direction == SignalType.BEARISH and delta > 0:
                adj -= 6
                parts.append(f"delta +{delta:.0f} contre-signal (-6)")

        reason = "📈 OrderFlow: " + " | ".join(parts) if parts else "📈 OrderFlow: neutre"
        return adj, reason

    @staticmethod
    def _avwap_adjustment(direction: SignalType, avwap_dist_pct: Optional[float]) -> tuple[int, str]:
        """
        Anchored VWAP comme support/résistance institutionnel.
        - Prix proche de l'AVWAP = zone de décision (confirmation si direction alignée)
        - Prix loin de l'AVWAP = extension potentielle
        """
        if avwap_dist_pct is None:
            return 0, "AVWAP non disponible"

        if direction == SignalType.BULLISH:
            if 0 < avwap_dist_pct < 0.5:
                return 6, f"⚓ AVWAP +{avwap_dist_pct:.2f}% → rebond au-dessus, support confirmé (+6)"
            elif avwap_dist_pct > 2.0:
                return -5, f"⚓ AVWAP +{avwap_dist_pct:.2f}% → trop étendu au-dessus (-5)"
            elif avwap_dist_pct < -1.0:
                return -4, f"⚓ AVWAP {avwap_dist_pct:.2f}% → sous AVWAP, momentum faible (-4)"
        elif direction == SignalType.BEARISH:
            if -0.5 < avwap_dist_pct < 0:
                return 6, f"⚓ AVWAP {avwap_dist_pct:.2f}% → rejet sous AVWAP, résistance confirmée (+6)"
            elif avwap_dist_pct < -2.0:
                return -5, f"⚓ AVWAP {avwap_dist_pct:.2f}% → trop étendu en dessous (-5)"
            elif avwap_dist_pct > 1.0:
                return -4, f"⚓ AVWAP +{avwap_dist_pct:.2f}% → au-dessus AVWAP, pas de pression vendeuse (-4)"
        return 0, f"⚓ AVWAP {avwap_dist_pct:.2f}% → neutre"

    def _datasheet_adjustment(self, asset: str, direction: SignalType) -> tuple[int, str]:
        """
        Ajustement basé sur la DataSheet du SynthesisAgent (canal market:context).

        Utilise 3 signaux du contexte de marché :
        1. Manipulation détectée  → pénalité forte (-15) — ne pas trader dans un marché manipulé
        2. Biais extrême           → pénalité si notre direction va contre le biais (-8)
        3. Structure de marché     → bonus si notre direction est alignée avec la structure (+8)
        4. VIX crypto élevé        → pénalité (-5) — volatilité excessive = risque accru
        """
        ctx = self._market_ctx.get(asset)
        if not ctx:
            return 0, "DataSheet SynthesisAgent indisponible"

        total_adj = 0
        reasons = []

        # ── 1. Manipulation détectée → signal très dangereux ──
        manipulation = ctx.get("manipulation", {})
        if isinstance(manipulation, dict):
            alerts = manipulation.get("alerts", [])
            if alerts:
                total_adj -= 15
                reasons.append(f"⚠️ Manipulation détectée ({len(alerts)} alertes) → -15")

        # ── 2. Biais directionnel extrême ──
        bias = ctx.get("bias", {})
        if isinstance(bias, dict):
            bias_dir = bias.get("direction", "neutral")
            bias_pct = bias.get("long_pct", 0.5) if isinstance(bias.get("long_pct"), (int, float)) else 0.5
            if bias_pct > 0.75 and direction == SignalType.BULLISH:
                total_adj -= 8
                reasons.append(f"Biais LONG extrême ({bias_pct:.0%}) → contre-trade risqué (-8)")
            elif bias_pct < 0.25 and direction == SignalType.BEARISH:
                total_adj -= 8
                reasons.append(f"Biais SHORT extrême ({1-bias_pct:.0%}) → contre-trade risqué (-8)")
            elif bias_dir == "bullish" and direction == SignalType.BULLISH:
                total_adj += 3
                reasons.append(f"Biais aligné BULLISH (+3)")
            elif bias_dir == "bearish" and direction == SignalType.BEARISH:
                total_adj += 3
                reasons.append(f"Biais aligné BEARISH (+3)")

        # ── 3. Structure de marché (HH/HL = haussier, LH/LL = baissier) ──
        structure = ctx.get("structure", {})
        if isinstance(structure, dict):
            trend = structure.get("trend", "").lower()
            if trend == "bullish" and direction == SignalType.BULLISH:
                total_adj += 8
                reasons.append(f"Structure haussière confirmée (+8)")
            elif trend == "bearish" and direction == SignalType.BEARISH:
                total_adj += 8
                reasons.append(f"Structure baissière confirmée (+8)")
            elif trend == "bullish" and direction == SignalType.BEARISH:
                total_adj -= 10
                reasons.append(f"Structure haussière vs signal SHORT → contre-structure (-10)")
            elif trend == "bearish" and direction == SignalType.BULLISH:
                total_adj -= 10
                reasons.append(f"Structure baissière vs signal LONG → contre-structure (-10)")

        # ── 4. VIX crypto (volatilité réalisée) ──
        vix = ctx.get("vix", {})
        if isinstance(vix, dict):
            realized_vol = vix.get("realized_vol", 0)
            if isinstance(realized_vol, (int, float)) and realized_vol > 80:
                total_adj -= 5
                reasons.append(f"VIX crypto élevé ({realized_vol:.0f}) → excès de volatilité (-5)")

        reason_str = " | ".join(reasons) if reasons else "DataSheet: aucun ajustement"
        logger.info("[%s] 📋 CTX %s : %+d (%s)", self.name, asset, total_adj, reason_str)
        return total_adj, reason_str

    def _regime_weights(self, regime: MarketRegime) -> tuple[float, float]:
        """
        Ajuste les poids tech/fond selon le régime de marché.
        - Bull/Bear clair → plus de poids au technique
        - Volatile → plus de poids au fondamental (news dominent)
        - Sideways → équilibré
        """
        base_tech = self.memory.adaptive_params.get("tech_weight", 0.60)
        base_fund = 1.0 - base_tech

        if regime == MarketRegime.VOLATILE:
            tech_w, fund_w = max(base_tech - 0.1, 0.4), min(base_fund + 0.1, 0.6)
        elif regime in (MarketRegime.BULL, MarketRegime.BEAR):
            tech_w, fund_w = min(base_tech + 0.05, 0.75), max(base_fund - 0.05, 0.25)
        else:
            tech_w, fund_w = base_tech, base_fund

        return round(tech_w, 2), round(fund_w, 2)

    def _detect_regime(self) -> MarketRegime:
        """Régime basé sur les prédictions récentes et leur outcome."""
        recent = self._predictions[-20:]
        if len(recent) < 5:
            return MarketRegime.SIDEWAYS

        # Taux de prédictions bullish vs bearish
        bulls = sum(1 for p in recent if p["direction"] == "bullish")
        ratio = bulls / len(recent)

        avg_conf = np.mean([p["confidence"] for p in recent])

        if avg_conf > 70 and ratio > 0.7:
            return MarketRegime.BULL
        elif avg_conf > 70 and ratio < 0.3:
            return MarketRegime.BEAR
        elif avg_conf < 55:
            return MarketRegime.VOLATILE
        return MarketRegime.SIDEWAYS

    def _purge_stale(self) -> None:
        now = datetime.now(timezone.utc).timestamp()

        # Purge tech signals (dict d'asset → dict de tf → signal)
        expired_assets = []
        for asset, tf_map in self._pending_tech.items():
            expired_tfs = [
                tf for tf, sig in tf_map.items()
                if now - self._ts(sig.get("timestamp", "")) > SIGNAL_TTL_SEC
            ]
            for tf in expired_tfs:
                del tf_map[tf]
            if not tf_map:
                expired_assets.append(asset)
        for asset in expired_assets:
            del self._pending_tech[asset]

        # Purge fund signals (dict d'asset → signal)
        expired_fund = [
            k for k, v in self._pending_fund.items()
            if now - self._ts(v.get("timestamp", "")) > SIGNAL_TTL_SEC
        ]
        for k in expired_fund:
            del self._pending_fund[k]

    @staticmethod
    def _ts(ts_str: str) -> float:
        try:
            return datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            return 0.0

    # ── Vault Obsidian — prédiction détaillée ─────────────────────────────────

    def _write_prediction_note(
        self,
        combined: CombinedSignal,
        regime: MarketRegime,
        tech_w: float,
        fund_w: float,
        mtf_summary: str = "",
        ob_reason: str   = "",
        vwap_reason: str = "",
        tf_signals: dict = None,
    ) -> None:
        tech = combined.technical
        fund = combined.fundamental
        filename = self.obsidian.timestamp_filename("predict", combined.asset)

        conf_floor = int(self.memory.adaptive_params.get("confidence_floor", 25))
        sl_mult    = self.memory.adaptive_params.get("sl_atr_multiplier", 1.5)
        tp_ratio   = self.memory.adaptive_params.get("tp_rr_ratio", 2.5)

        # Estimations SL/TP
        sl_est = tp_est = "—"
        if tech.entry_price and tech.atr:
            atr_val = tech.atr
            if combined.final_signal == SignalType.BULLISH:
                sl_est = f"{tech.entry_price - sl_mult * atr_val:.4f}"
                tp_est = f"{tech.entry_price + sl_mult * atr_val * tp_ratio:.4f}"
            else:
                sl_est = f"{tech.entry_price + sl_mult * atr_val:.4f}"
                tp_est = f"{tech.entry_price - sl_mult * atr_val * tp_ratio:.4f}"

        # Tableau multi-timeframe
        tf_rows = ""
        if tf_signals:
            for tf, sig in sorted(tf_signals.items()):
                d = sig.get("signal", "neutral")
                c = sig.get("confidence", 0)
                icon = "🟢" if d == "bullish" else ("🔴" if d == "bearish" else "⚪")
                tf_rows += f"| `{tf}` | {icon} {d} | {c}/100 |\n"
        if not tf_rows:
            tf_rows = "| — | — | — |\n"

        frontmatter = self._build_frontmatter(
            asset=combined.asset, signal_type=combined.final_signal.value,
            confidence=combined.combined_confidence,
            extra={
                "regime":      regime.value,
                "tech_weight": tech_w, "fund_weight": fund_w,
                "sl_estimate": sl_est, "tp_estimate": tp_est,
                "ob_imbalance": tech.ob_imbalance or 0,
                "vwap_dist":    tech.vwap_dist_pct or 0,
            },
        )

        content = f"""## Prédiction ML — {combined.asset}

> **{combined.final_signal.value.upper()}** — Confiance finale : **{combined.combined_confidence}/100**
> Régime détecté : **{regime.value.upper()}**

---

### 1. Confluence Multi-Timeframe
| Timeframe | Direction | Confiance |
|---|---|---|
{tf_rows}
> {mtf_summary}

### 2. Convergence des Agents
| Agent | Signal | Confiance | Poids |
|---|---|---|---|
| ScanAgent (Technique) | `{tech.signal.value}` `{tech.timeframe}` | {tech.confidence}/100 | **{tech_w:.0%}** |
| ResearchAgent (Fondamental) | `{fund.signal.value}` | {fund.confidence}/100 | **{fund_w:.0%}** |
| **PredictAgent** | **`{combined.final_signal.value.upper()}`** | **{combined.combined_confidence}/100** | — |

### 3. Contexte Institutionnel (Order Book + VWAP)
> {ob_reason}
> {vwap_reason}

| Indicateur | Valeur |
|---|---|
| Order Book Imbalance | `{tech.ob_imbalance or 0:.3f}` |
| Distance VWAP | `{tech.vwap_dist_pct or 0:.2f}%` |

### 4. Paramètres ML
| Paramètre | Valeur |
|---|---|
| Confidence Floor | `{conf_floor}/100` |
| SL Multiplier | `{sl_mult:.2f}×ATR` |
| TP Ratio | `1:{tp_ratio:.2f}` |
| SL estimé | `{sl_est}` |
| TP estimé | `{tp_est}` |

### Liens
{self.obsidian.wikilink('technique', self.obsidian.timestamp_filename('scan', combined.asset))}
{self.obsidian.wikilink('config', 'PredictAgent_memory')}
"""
        self.obsidian.write_note("decisions", filename, frontmatter, content)