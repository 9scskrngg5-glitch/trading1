"""
Agent 7 — Synthèse & Contexte de Marché (SynthesisAgent)
Couche analytique institutionnelle qui transforme des signaux bruts en DataSheet exploitable.

Rôle dans l'écosystème :
  - NE PREND PAS DE DÉCISION DE TRADING
  - Agrège tous les signaux du pipeline (Scan + Research + Predict + Risk)
  - LIT activement le vault avant chaque analyse (mémoire active, pas passive)
  - Analyse la structure de marché (HH/HL/LH/LL, BOS, Order Blocks)
  - Détecte zones S/R, liquidité (BSL/SSL), Order Blocks institutionnels
  - Identifie les biais systémiques (ex : 78% de longs → alerte)
  - Intègre Mirofish comme SOURCE SECONDAIRE de confirmation comportementale
  - Calcule la volatilité réalisée (équivalent crypto-VIX) et le volume profile
  - Détecte la manipulation de marché (stop-hunt, wash trading, fake walls)
  - Produit des stratégies multi-horizon : Scalping / Intraday / Swing
  - Publie la DataSheet sur le canal market:context
  - Effectue des rétrospectives et des propositions d'auto-amélioration

Priorisation des sources (ordre décroissant) :
  1. Données réelles de marché (MarketDataManager)
  2. Signaux du pipeline (ScanAgent, PredictAgent)
  3. Mémoire du vault (patterns historiques, erreurs récurrentes)
  4. Mirofish (simulation probabiliste — JAMAIS prioritaire sur les vraies données)

Vault : vault/synthese/
Canal sortant : market:context
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from core.base_agent import BaseAgent
from core.learning_engine import LearningEngine
from core.message_bus import MessageBus, CHANNELS
from core.obsidian_client import ObsidianClient
from data.mirofish_client import MirofishClient
from models.learning import AgentMemory

logger = logging.getLogger(__name__)

# Nombre de signaux conservés dans les buffers par asset
SIGNAL_BUFFER = 30
# Nombre de candles 1h analysées pour la structure de marché
STRUCTURE_LOOKBACK = 60
# Seuil de biais (% de longs au-delà duquel c'est un biais détecté)
BIAS_THRESHOLD = 0.65
# Fréquence du health check (cycles)
HEALTH_CHECK_EVERY = 10
# Bins pour le volume profile
VOL_PROFILE_BINS = 20


# ── MemoryContext — données vault lues avant chaque analyse ──────────────────

@dataclass
class MemoryContext:
    """
    Contexte extrait du vault avant chaque analyse.
    Influence directement les seuils et la qualité des stratégies.
    """
    # Mode du CompoundAgent (capital_preservation / progressive_compound / aggressive_scaling)
    compound_mode:      str   = "normal"
    current_risk_pct:   float = 2.0

    # Paramètres adaptatifs du RiskAgent
    confidence_floor:   float = 55.0
    sl_atr_multiplier:  float = 1.5

    # Performances historiques par asset (win rate)
    asset_win_rates:    dict  = field(default_factory=dict)

    # Erreurs récurrentes détectées par les rétrospectives
    recurring_errors:   list  = field(default_factory=list)

    # Résumé contextuel (affiché dans la DataSheet)
    summary:            str   = "Mémoire non chargée"

    # Ajustement de confiance suggéré par la mémoire
    confidence_boost:   int   = 0   # peut être négatif (mode preservation)

    @property
    def is_preservation_mode(self) -> bool:
        return self.compound_mode == "capital_preservation"

    @property
    def confidence_threshold_for_bullish(self) -> float:
        """Seuil de confiance requis pour valider une stratégie bullish."""
        base = self.confidence_floor
        if self.is_preservation_mode:
            base += 10   # Plus strict quand le capital est sous pression
        return base


class SynthesisAgent(BaseAgent):
    """
    Agent de synthèse institutionnelle.

    À chaque cycle :
    1. Lit le vault pour charger le contexte mémoire (MemoryContext)
    2. Collecte les derniers signaux de tous les agents
    3. Récupère les candles 1h depuis MarketDataManager (ou estimation)
    4. Calcule VIX crypto (volatilité réalisée) et volume profile
    5. Analyse structure de marché, S/R, liquidité, Order Blocks
    6. Détecte manipulation (stop-hunt, wash trading, fake walls)
    7. Détecte les biais directionnels et la cohérence inter-agents
    8. Lance Mirofish comme confirmation secondaire
    9. Émet des stratégies Scalping / Intraday / Swing (ajustées par la mémoire)
    10. Publie une DataSheet complète sur market:context
    11. Écrit une note riche dans vault/synthese/
    12. Exécute un vault health check périodique
    """

    def __init__(
        self,
        bus: MessageBus,
        obsidian: ObsidianClient,
        learning: LearningEngine,
        config: dict,
        market_data=None,
        telegram=None,
    ):
        super().__init__("SynthesisAgent", "synthese", bus, obsidian, config)
        self.learning     = learning
        self._market_data  = market_data
        self.telegram      = telegram
        self.memory: AgentMemory = None
        self._mirofish    = MirofishClient(n_agents=2000)

        # Buffers de signaux par asset
        self._tech_buf:  dict[str, deque] = defaultdict(lambda: deque(maxlen=SIGNAL_BUFFER))

        # Anti-spam Telegram : ne renvoyer que quand le biais change
        self._last_tg_bias: dict[str, str] = {}
        self._fund_buf:  dict[str, deque] = defaultdict(lambda: deque(maxlen=SIGNAL_BUFFER))
        self._dec_buf:   dict[str, deque] = defaultdict(lambda: deque(maxlen=SIGNAL_BUFFER))
        self._outcomes:  deque            = deque(maxlen=100)

        # DataSheets les plus récentes
        self._last_sheets: dict[str, dict] = {}

        # Régimes externes de RegimeAgent (asset → regime string)
        self._ext_regime: dict[str, str] = {}

        # Compteur de cycles pour le health check
        self._cycle_count: int = 0

    # ── Setup ─────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        self.memory = self.learning.load_memory("SynthesisAgent")
        (self.obsidian.vault_path / "synthese").mkdir(exist_ok=True)
        logger.info("[%s] ✅ Démarré — couche analytique institutionnelle", self.name)

    def _register_subscriptions(self) -> None:
        self.bus.subscribe(CHANNELS["signals_technical"],   self._on_tech)
        self.bus.subscribe(CHANNELS["signals_fundamental"], self._on_fund)
        self.bus.subscribe(CHANNELS["decisions"],           self._on_decision)
        self.bus.subscribe(CHANNELS["portfolio_update"],    self._on_outcome)
        self.bus.subscribe(CHANNELS["regime"],              self._on_regime_update)

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _on_regime_update(self, data: dict) -> None:
        """Reçoit le régime de RegimeAgent — enrichit la DataSheet avec l'info externe."""
        asset  = data.get("asset")
        regime = data.get("regime")
        if asset and regime:
            self._ext_regime[asset] = regime
            logger.debug("[%s] Régime externe %s : %s", self.name, asset, regime)

    async def _on_tech(self, data: dict) -> None:
        asset = data.get("asset")
        if asset:
            self._tech_buf[asset].append(data)

    async def _on_fund(self, data: dict) -> None:
        asset = data.get("asset")
        if asset:
            self._fund_buf[asset].append(data)

    async def _on_decision(self, data: dict) -> None:
        asset = data.get("asset")
        if asset:
            self._dec_buf[asset].append(data)

    async def _on_outcome(self, data: dict) -> None:
        if data.get("type") == "trade_closed":
            self._outcomes.append(data)

    # ── Cycle principal ───────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        self._cycle_count += 1
        assets = self.config.get("assets", self.config.get("pairs", []))

        for asset in assets:
            try:
                sheet = await self._build_datasheet(asset)
                if sheet:
                    self._last_sheets[asset] = sheet
                    await self.bus.publish(CHANNELS["market_context"], sheet)
                    self._write_vault_note(asset, sheet)

                    # ── Notification Telegram — DataSheet (seulement si le biais change) ──
                    if self.telegram:
                        try:
                            bias_info = sheet.get("bias", {})
                            bias_str = bias_info.get("direction", "neutre") if isinstance(bias_info, dict) else str(bias_info)
                            prev_bias = self._last_tg_bias.get(asset)
                            if bias_str != prev_bias:
                                self._last_tg_bias[asset] = bias_str
                                vix_data = sheet.get("vix", {})
                                vix_val = vix_data.get("realized_vol", 0) if isinstance(vix_data, dict) else 0
                                structure = sheet.get("structure", {})
                                struct_str = structure.get("trend", "?") if isinstance(structure, dict) else str(structure)
                                strats = sheet.get("strategies", {})
                                if isinstance(strats, dict):
                                    strat_parts = []
                                    for horizon, s in strats.items():
                                        if isinstance(s, dict):
                                            strat_parts.append(f"{horizon}: {s.get('direction', '?')}")
                                        else:
                                            strat_parts.append(f"{horizon}: {s}")
                                    strats_str = " | ".join(strat_parts) if strat_parts else "—"
                                else:
                                    strats_str = str(strats)[:80]
                                await self.telegram.datasheet_summary(
                                    asset=asset,
                                    bias=bias_str,
                                    vix=float(vix_val),
                                    structure=struct_str,
                                    strategies=strats_str,
                                )
                        except Exception as tg_exc:
                            logger.warning("[%s] Erreur Telegram DataSheet: %s", self.name, tg_exc)
            except Exception as exc:
                logger.warning("[%s] Erreur datasheet %s: %s", self.name, asset, exc, exc_info=True)

        # Rétrospective + auto-amélioration
        self._write_retrospective_note()

        # Health check périodique du vault
        if self._cycle_count % HEALTH_CHECK_EVERY == 0:
            self._vault_health_check()

    # ── Chargement Actif de la Mémoire (AVANT l'analyse) ─────────────────────

    def _load_active_memory(self, asset: str) -> MemoryContext:
        """
        Lit le vault AVANT l'analyse pour construire un MemoryContext.

        Sources lues :
        1. vault/config/CompoundAgent_state.md → mode actuel, risk_pct
        2. vault/config/RiskAgent_memory.md     → sl_multiplier, confidence_floor
        3. vault/retrospectives/ (5 dernières)  → win rates par asset, erreurs récurrentes
        4. vault/config/SynthesisAgent_memory.md → patterns d'erreur historiques
        5. vault/technique/ (3 dernières par asset) → tendance RSI/MACD/signal historique
        6. vault/fondamental/ (3 dernières par asset) → tendance sentiment historique
        7. vault/apprentissage/ (3 dernières par asset) → leçons ML: exits récurrents

        Retourne un MemoryContext qui influencera les seuils et stratégies.
        """
        ctx = MemoryContext()

        # ── 1. CompoundAgent memory ───────────────────────────────────────────
        compound_note = self.obsidian.read_note("config", "CompoundAgent_state")
        if compound_note:
            fm = compound_note.frontmatter
            ctx.compound_mode    = fm.get("current_mode", "normal")
            ctx.current_risk_pct = float(fm.get("current_risk_pct", 2.0))
            if ctx.is_preservation_mode:
                ctx.confidence_boost = -10   # Mode préservation → on exige plus

        # ── 2. RiskAgent memory ───────────────────────────────────────────────
        risk_note = self.obsidian.read_note("config", "RiskAgent_memory")
        if risk_note:
            fm = risk_note.frontmatter
            adaptive = fm.get("adaptive_params", {})
            if isinstance(adaptive, dict):
                ctx.confidence_floor  = float(adaptive.get("confidence_floor",  55.0))
                ctx.sl_atr_multiplier = float(adaptive.get("sl_atr_multiplier", 1.5))

        # ── 3. Rétrospectives récentes → win rates par asset ──────────────────
        retros = self.obsidian.read_latest("retrospectives", limit=5)
        asset_wins   = defaultdict(int)
        asset_totals = defaultdict(int)
        for note in retros:
            fm = note.frontmatter
            a  = fm.get("asset", "")
            if a:
                asset_totals[a] += fm.get("total_trades", 0)
                wins = int(fm.get("total_trades", 0) * fm.get("win_rate", 0.5))
                asset_wins[a] += wins
        for a, total in asset_totals.items():
            if total > 0:
                ctx.asset_win_rates[a] = round(asset_wins[a] / total, 3)

        # ── 4. SynthesisAgent retrospectives → erreurs récurrentes ───────────
        synth_retros = self.obsidian.read_latest("synthese", limit=3)
        errors_seen: set = set()
        for note in synth_retros:
            fm = note.frontmatter
            if fm.get("type") == "system_retrospective":
                patterns = fm.get("error_patterns", [])
                if isinstance(patterns, list):
                    errors_seen.update(patterns)
        ctx.recurring_errors = list(errors_seen)

        # ── 5. Historique technique (ScanAgent) → tendance RSI/signal récente ──
        tech_notes = self.obsidian.read_by_asset("technique", asset, limit=3)
        if tech_notes:
            signals = [n.frontmatter.get("signal_type", "neutral") for n in tech_notes]
            bulls = signals.count("bullish")
            bears = signals.count("bearish")
            # Tendance technique : majorité = momentum
            if bulls > bears:
                ctx.confidence_boost += 5
            elif bears > bulls:
                ctx.confidence_boost -= 5
            # RSI moyen sur les 3 derniers scans
            rsi_vals = [n.frontmatter.get("rsi") for n in tech_notes if isinstance(n.frontmatter.get("rsi"), (int, float))]
            if rsi_vals:
                avg_rsi = sum(rsi_vals) / len(rsi_vals)
                ctx.summary = getattr(ctx, "summary", "") + f" | RSI moy: {avg_rsi:.0f}"
            logger.debug("[%s] Technique vault %s: %d haussier/%d baissier sur %d notes",
                         self.name, asset, bulls, bears, len(tech_notes))

        # ── 6. Historique fondamental (ResearchAgent) → tendance sentiment ──
        fund_notes = self.obsidian.read_by_asset("fondamental", asset, limit=3)
        if fund_notes:
            sentiments = [n.frontmatter.get("sentiment_score", 0) for n in fund_notes
                          if isinstance(n.frontmatter.get("sentiment_score"), (int, float))]
            if sentiments:
                avg_sent = sum(sentiments) / len(sentiments)
                # Sentiment positif/négatif persistant → ajustement léger
                if avg_sent > 20:
                    ctx.confidence_boost += 3
                elif avg_sent < -20:
                    ctx.confidence_boost -= 3
            logger.debug("[%s] Fondamental vault %s: sentiment moyen %.1f sur %d notes",
                         self.name, asset, avg_sent if sentiments else 0, len(fund_notes))

        # ── 7. Leçons ML (LearningEngine) → patterns d'échec récents ──
        learn_notes = self.obsidian.read_by_asset("apprentissage", asset, limit=3)
        if learn_notes:
            exit_reasons = [n.frontmatter.get("exit_reason", "") for n in learn_notes]
            losses = [n for n in learn_notes if not n.frontmatter.get("is_win", True)]
            # Ajouter les raisons d'échec récurrentes aux erreurs connues
            for note in losses:
                reason = note.frontmatter.get("exit_reason", "")
                if reason and reason not in ctx.recurring_errors:
                    ctx.recurring_errors.append(f"{asset}:{reason}")
            # Si 2 pertes sur 3 derniers trades → pénalité confiance
            if len(losses) >= 2:
                ctx.confidence_boost -= 8
                logger.info("[%s] ⚠️ %s : %d pertes sur %d derniers trades (vault) → confiance -8",
                            self.name, asset, len(losses), len(learn_notes))
            logger.debug("[%s] Apprentissage vault %s: %d pertes / %d trades, exits: %s",
                         self.name, asset, len(losses), len(learn_notes), exit_reasons)

        # ── Résumé contextuel ─────────────────────────────────────────────────
        asset_wr = ctx.asset_win_rates.get(asset)
        wr_str = f"{asset_wr:.0%}" if asset_wr is not None else "N/A"

        parts = [f"Mode: {ctx.compound_mode.upper()}", f"Risque: {ctx.current_risk_pct}%",
                 f"Confiance min: {ctx.confidence_floor:.0f}", f"WR {asset}: {wr_str}",
                 f"HistTech: {len(tech_notes)}n", f"HistFund: {len(fund_notes)}n",
                 f"Leçons: {len(learn_notes)}n"]
        ctx.summary = " | ".join(parts)

        return ctx

    # ── Construction de la DataSheet ──────────────────────────────────────────

    async def _build_datasheet(self, asset: str) -> Optional[dict]:
        """
        Point d'entrée principal — assemble toutes les couches analytiques.
        La mémoire est chargée EN PREMIER pour influencer l'analyse.
        """
        # ── ÉTAPE 0 : Charger la mémoire active ──
        mem_ctx = self._load_active_memory(asset)

        closes, highs, lows, volumes = self._get_price_series(asset)
        if len(closes) < 10:
            return None

        price = closes[-1]
        atr   = self._atr(highs, lows, closes, 14)

        # ── 1. Régime de marché ──
        # Si RegimeAgent a publié un régime pour cet asset, il prend priorité
        _ext = self._ext_regime.get(asset)
        if _ext:
            _ext_map = {
                "trending_up":   "trending_bullish",
                "trending_down": "trending_bearish",
                "volatile":      "volatile",
                "ranging":       "ranging",
            }
            regime = _ext_map.get(_ext, self._detect_regime(closes, highs, lows, volumes, atr, price))
        else:
            regime = self._detect_regime(closes, highs, lows, volumes, atr, price)

        # ── 2. Structure de marché ──
        structure = self._analyze_structure(closes, highs, lows)

        # ── 3. Zones clés (S/R + liquidité) ──
        levels = self._find_key_levels(highs, lows, closes, price, atr)

        # ── 4. Order Blocks institutionnels ──
        order_blocks = self._find_order_blocks(closes, highs, lows)

        # ── 5. VIX crypto (volatilité réalisée) ──
        vix_data = self._compute_realized_vol(closes)

        # ── 6. Volume Profile (heatmap de prix) ──
        vol_profile = self._compute_volume_profile(closes, volumes)

        # ── 7. Détection de manipulation ──
        manipulation = self._detect_manipulation(highs, lows, closes, volumes, levels)

        # ── 8. Détection de biais directionnel ──
        bias = self._detect_bias(asset)

        # ── 9. Cohérence inter-agents ──
        coherence = self._check_coherence(asset, regime, structure)

        # ── 10. Stratégies multi-horizon (ajustées par la mémoire) ──
        strategies = self._build_strategies(
            asset, price, atr, regime, structure, levels, bias, mem_ctx
        )

        # ── 11. Sentiment global ──
        sentiment = self._compute_sentiment(asset)

        # ── 12. Mirofish — SOURCE SECONDAIRE ──
        mirofish_result = await self._run_mirofish(
            asset, price, regime, structure, sentiment
        )

        sheet = {
            "type":         "market_context",
            "asset":        asset,
            "price":        round(price, 6),
            "atr":          round(atr, 6),
            "atr_pct":      round(atr / price * 100, 3) if price > 0 else 0,
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "memory_ctx":   {
                "compound_mode":    mem_ctx.compound_mode,
                "confidence_floor": mem_ctx.confidence_floor,
                "confidence_boost": mem_ctx.confidence_boost,
                "risk_pct":         mem_ctx.current_risk_pct,
                "summary":          mem_ctx.summary,
            },
            "regime":       regime,
            "structure":    structure,
            "levels":       levels,
            "order_blocks": order_blocks,
            "vix":          vix_data,
            "vol_profile":  vol_profile,
            "manipulation": manipulation,
            "bias":         bias,
            "coherence":    coherence,
            "strategies":   strategies,
            "sentiment":    sentiment,
            "mirofish":     mirofish_result,   # SOURCE SECONDAIRE — toujours en dernier
        }
        return sheet

    # ── Mirofish — Simulation Comportementale Secondaire ─────────────────────

    async def _run_mirofish(
        self,
        asset: str,
        price: float,
        regime: dict,
        structure: dict,
        sentiment: dict,
    ) -> dict:
        """
        Exécute la simulation Mirofish comme SOURCE SECONDAIRE de confirmation.

        Important : ce résultat NE REMPLACE JAMAIS les données réelles.
        Il est utilisé uniquement pour détecter des divergences comportementales
        et des signaux contrarians (>75% consensus → piège potentiel).

        Les paramètres sont extraits des analyses déjà calculées sur vraies données.
        """
        # Extraire les indicateurs tech les plus récents pour cet asset
        tech_buf = list(self._tech_buf.get(asset, []))
        last_tech = tech_buf[-1] if tech_buf else {}

        rsi          = float(last_tech.get("rsi",          50.0) or 50.0)
        macd_hist    = float(last_tech.get("macd_hist",    0.0)  or 0.0)
        bb_position  = float(last_tech.get("bb_position",  0.5)  or 0.5)
        vol_ratio    = float(last_tech.get("vol_ratio",    1.0)  or 1.0)
        ob_imbalance = float(last_tech.get("ob_imbalance", 0.0)  or 0.0)

        try:
            result = await self._mirofish.simulate_market(
                asset            = asset,
                price            = price,
                rsi              = rsi,
                macd_hist        = macd_hist,
                bb_position      = bb_position,
                vol_ratio        = vol_ratio,
                sentiment_score  = sentiment.get("score", 0.0),
                regime_dir       = regime.get("direction", "neutral"),
                structure_pattern = structure.get("pattern", "unclear"),
                ob_imbalance     = ob_imbalance,
            )
            return {
                "source":            "🎯 Mirofish (simulation probabiliste — SOURCE SECONDAIRE)",
                "direction":         result.direction,
                "long_pct":          result.long_pct,
                "short_pct":         result.short_pct,
                "hold_pct":          result.hold_pct,
                "bull_probability":  result.bull_probability,
                "bear_probability":  result.bear_probability,
                "contrarian_signal": result.contrarian_signal,
                "divergence_score":  result.divergence_score,
                "manipulation_risk": result.manipulation_risk,
                "behavioral_note":   result.behavioral_note,
                "disclaimer":        "⚠️ Source secondaire — ne remplace pas l'analyse primaire",
            }
        except Exception as exc:
            logger.debug("[%s] Mirofish erreur pour %s: %s", self.name, asset, exc)
            return {
                "source":    "🎯 Mirofish",
                "error":     str(exc),
                "disclaimer": "⚠️ Simulation non disponible — analyse primaire suffisante",
            }

    # ── VIX Crypto — Volatilité Réalisée ─────────────────────────────────────

    @staticmethod
    def _compute_realized_vol(closes: np.ndarray) -> dict:
        """
        Calcule l'équivalent crypto-VIX : volatilité réalisée annualisée.

        Méthode : écart-type des log-rendements journaliers × sqrt(365)
        Interprétation :
          < 30%  : volatilité faible (marché stable)
          30-60% : volatilité modérée
          60-100%: volatilité élevée
          > 100% : volatilité extrême (crypto typique en bull run)
        """
        if len(closes) < 10:
            return {"realized_vol": 0.0, "label": "N/A", "percentile": 50}

        returns = np.log(closes[1:] / closes[:-1])
        # Volatilité journalière × annualisée (365 jours pour crypto)
        daily_vol = float(np.std(returns))
        annualized = daily_vol * np.sqrt(365) * 100

        # Rolling percentile sur la session (contexte)
        n_hist = min(len(returns), 30)
        hist_vols = [
            np.std(returns[max(0, i-10):i]) * np.sqrt(365) * 100
            for i in range(10, n_hist + 10)
        ]
        pct = 50
        if hist_vols:
            current_rank = sum(1 for v in hist_vols if v <= annualized)
            pct = int(current_rank / len(hist_vols) * 100)

        if annualized < 30:
            label = "🟢 Faible (<30%)"
        elif annualized < 60:
            label = "🟡 Modérée (30-60%)"
        elif annualized < 100:
            label = "🟠 Élevée (60-100%)"
        else:
            label = "🔴 Extrême (>100%)"

        return {
            "realized_vol":      round(float(annualized), 2),
            "label":             label,
            "percentile":        int(pct),
            "daily_vol_pct":     round(float(daily_vol * 100), 4),
            "interpretation":    f"Volatilité réalisée {annualized:.1f}% — {pct}e percentile session",
        }

    # ── Volume Profile — Heatmap de Prix ─────────────────────────────────────

    @staticmethod
    def _compute_volume_profile(closes: np.ndarray, volumes: np.ndarray) -> dict:
        """
        Calcule le volume profile (distribution des volumes par niveaux de prix).

        Outputs :
        - POC (Point of Control) : niveau où s'est échangé le plus de volume
        - VAH (Value Area High)  : borne haute de la zone de valeur (70% du volume)
        - VAL (Value Area Low)   : borne basse de la zone de valeur (70% du volume)
        - HVN (High Volume Node) : zones de congestion → magnétiques pour le prix
        - LVN (Low Volume Node)  : zones de peu de volume → le prix les traverse vite
        """
        if len(closes) < 5 or len(volumes) < 5:
            return {"poc": None, "vah": None, "val": None, "hvn": [], "lvn": []}

        price_min = float(closes.min())
        price_max = float(closes.max())
        if price_max <= price_min:
            return {"poc": None, "vah": None, "val": None, "hvn": [], "lvn": []}

        n_bins  = min(VOL_PROFILE_BINS, len(closes))
        bins    = np.linspace(price_min, price_max, n_bins + 1)
        bin_vol = np.zeros(n_bins)

        for close, vol in zip(closes, volumes):
            idx = int((close - price_min) / (price_max - price_min) * n_bins)
            idx = min(idx, n_bins - 1)
            bin_vol[idx] += vol

        # POC = bin avec le plus de volume
        poc_idx = int(np.argmax(bin_vol))
        poc     = round(float((bins[poc_idx] + bins[poc_idx + 1]) / 2), 6)

        # Value Area (70% du volume total)
        total_vol = bin_vol.sum()
        target    = total_vol * 0.70
        accumulated = bin_vol[poc_idx]
        lo_idx, hi_idx = poc_idx, poc_idx

        while accumulated < target and (lo_idx > 0 or hi_idx < n_bins - 1):
            lo_add = bin_vol[lo_idx - 1] if lo_idx > 0 else 0
            hi_add = bin_vol[hi_idx + 1] if hi_idx < n_bins - 1 else 0
            if lo_add >= hi_add and lo_idx > 0:
                lo_idx    -= 1
                accumulated += lo_add
            elif hi_idx < n_bins - 1:
                hi_idx    += 1
                accumulated += hi_add
            else:
                break

        vah = round(float(bins[hi_idx + 1]), 6)
        val = round(float(bins[lo_idx]), 6)

        # HVN et LVN (seuil = 80th percentile et 20th percentile du volume)
        threshold_hvn = np.percentile(bin_vol, 80)
        threshold_lvn = np.percentile(bin_vol, 20)
        hvn = [
            round(float((bins[i] + bins[i+1]) / 2), 6)
            for i in range(n_bins) if bin_vol[i] >= threshold_hvn
        ][:3]
        lvn = [
            round(float((bins[i] + bins[i+1]) / 2), 6)
            for i in range(n_bins) if bin_vol[i] <= threshold_lvn and bin_vol[i] > 0
        ][:3]

        return {
            "poc":  poc,
            "vah":  vah,
            "val":  val,
            "hvn":  hvn,
            "lvn":  lvn,
            "note": f"POC={poc:.4f} | VAH={vah:.4f} | VAL={val:.4f}",
        }

    # ── Détection de Manipulation ─────────────────────────────────────────────

    def _detect_manipulation(
        self,
        highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
        volumes: np.ndarray, levels: dict,
    ) -> dict:
        """
        Détecte 3 types de manipulation institutionnelle :

        1. Stop-Hunt (liquidation de stops)
           - Spike rapide vers une zone BSL/SSL suivie d'une réversion
           - Détecté via : wick > 1.5× ATR + clôture dans la direction opposée

        2. Wash Trading (volume artificiel)
           - Volume anormalement élevé (>3× moyenne) avec mouvement de prix minimal (<0.1%)
           - Corrélation volume/prix cassée

        3. Fake Wall (mur fictif dans l'order book)
           - Utilise ob_imbalance des signaux tech récents
           - Si imbalance élevé (>0.4) mais price ne suit pas → potentiel fake wall
        """
        signals = {
            "stop_hunt":    False,
            "wash_trading": False,
            "fake_wall":    False,
            "risk_score":   0,
            "notes":        [],
        }

        if len(closes) < 5 or len(volumes) < 5:
            return signals

        atr = self._atr(highs, lows, closes, 14)
        if atr <= 0:
            return signals

        # ── 1. Stop-Hunt ──────────────────────────────────────────────────────
        # Chercher des wicks extrêmes sur les 5 dernières bougies
        for i in range(max(0, len(closes)-5), len(closes)-1):
            upper_wick = highs[i] - max(closes[i], closes[i-1] if i > 0 else closes[i])
            lower_wick = min(closes[i], closes[i-1] if i > 0 else closes[i]) - lows[i]

            bsl = levels.get("bsl")
            ssl = levels.get("ssl")

            # Spike haussier vers BSL puis réversion
            if bsl and upper_wick > atr * 1.5 and closes[i+1] < closes[i]:
                if highs[i] >= bsl * 0.998 and highs[i] <= bsl * 1.002:
                    signals["stop_hunt"] = True
                    signals["notes"].append(
                        f"🎯 Stop-hunt BSL détecté — wick de {upper_wick/atr:.1f}×ATR vers {bsl:.4f}"
                    )

            # Spike baissier vers SSL puis réversion
            if ssl and lower_wick > atr * 1.5 and closes[i+1] > closes[i]:
                if lows[i] >= ssl * 0.998 and lows[i] <= ssl * 1.002:
                    signals["stop_hunt"] = True
                    signals["notes"].append(
                        f"🎯 Stop-hunt SSL détecté — wick de {lower_wick/atr:.1f}×ATR vers {ssl:.4f}"
                    )

        # ── 2. Wash Trading ───────────────────────────────────────────────────
        if len(volumes) >= 10:
            avg_vol = float(np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes))
            for i in range(max(1, len(volumes)-5), len(volumes)):
                vol_ratio   = volumes[i] / max(avg_vol, 1e-9)
                price_chg   = abs(closes[i] - closes[i-1]) / closes[i-1] * 100
                # Volume 3× la moyenne mais mouvement de prix < 0.1%
                if vol_ratio > 3.0 and price_chg < 0.1:
                    signals["wash_trading"] = True
                    signals["notes"].append(
                        f"🔄 Wash trading probable — volume {vol_ratio:.1f}×avg, mouvement {price_chg:.3f}%"
                    )

        # ── 3. Fake Wall ──────────────────────────────────────────────────────
        # Si les signaux tech récents montrent un OB imbalance fort mais que le prix
        # ne confirme pas la direction attendue
        tech_recent = list(self._tech_buf.get("", []))
        all_obs = []
        for buf in self._tech_buf.values():
            if buf:
                last = list(buf)[-1]
                ob = float(last.get("ob_imbalance", 0) or 0)
                all_obs.append(ob)

        if all_obs:
            avg_ob = float(np.mean(all_obs))
            price_dir = 1 if closes[-1] > closes[-5] else -1  # direction dernières 5 bougies
            # OB fortement bid mais prix descend → potentiel fake wall côté bid
            if avg_ob > 0.4 and price_dir < 0:
                signals["fake_wall"] = True
                signals["notes"].append(
                    f"🧱 Fake wall potentiel côté BID — OB imbalance +{avg_ob:.2f} mais prix baisse"
                )
            elif avg_ob < -0.4 and price_dir > 0:
                signals["fake_wall"] = True
                signals["notes"].append(
                    f"🧱 Fake wall potentiel côté ASK — OB imbalance {avg_ob:.2f} mais prix monte"
                )

        # ── Score de risque global ────────────────────────────────────────────
        risk = (
            (30 if signals["stop_hunt"]  else 0) +
            (25 if signals["wash_trading"] else 0) +
            (20 if signals["fake_wall"]  else 0)
        )
        signals["risk_score"] = risk

        if risk > 50:
            signals["notes"].append("⚠️  RISQUE DE MANIPULATION ÉLEVÉ — réduire la taille des positions")
        elif risk > 20:
            signals["notes"].append("⚡ Risque de manipulation modéré — surveiller les niveaux de liquidité")

        return signals

    # ── Données de prix ────────────────────────────────────────────────────────

    def _get_price_series(self, asset: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Récupère les séries OHLCV depuis MarketDataManager (1h) ou reconstitue
        une série approximative à partir des prix d'entrée des signaux.
        """
        if self._market_data and self._market_data.is_ready():
            candles = self._market_data.get_candles(asset, "1h", STRUCTURE_LOOKBACK)
            if len(candles) >= 10:
                return (
                    np.array([c.c for c in candles]),
                    np.array([c.h for c in candles]),
                    np.array([c.l for c in candles]),
                    np.array([c.v for c in candles]),
                )

        # Fallback : reconstituer depuis les prix des signaux tech
        prices = [
            s.get("entry_price") for s in self._tech_buf.get(asset, [])
            if s.get("entry_price")
        ]
        if len(prices) >= 3:
            arr    = np.array(prices)
            spread = arr.mean() * 0.008
            return arr, arr + spread, arr - spread, np.ones(len(arr)) * 1_000_000
        return np.array([]), np.array([]), np.array([]), np.array([])

    # ── Régime de Marché ──────────────────────────────────────────────────────

    def _detect_regime(
        self,
        closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
        volumes: np.ndarray, atr: float, price: float,
    ) -> dict:
        """
        Classifie le régime de marché selon 3 axes :
        - Direction (bullish / bearish / neutral)
        - Type (trending / ranging / volatile)
        - Phase Wyckoff simplifiée (accumulation / markup / distribution / markdown)
        - Niveau de volatilité (low / medium / high / extreme)
        """
        n = len(closes)
        if n < 20:
            return {"direction": "neutral", "type": "ranging", "phase": "unknown",
                    "volatility": "medium", "strength": 0}

        ema20 = self._ema(closes, 20)
        ema50 = self._ema(closes, min(50, n))

        slope_20 = (closes[-1] - closes[-20]) / closes[-20] * 100 if closes[-20] > 0 else 0
        slope_5  = (closes[-1] - closes[-5])  / closes[-5]  * 100 if closes[-5]  > 0 else 0

        atr_pct = atr / price * 100 if price > 0 else 0
        if atr_pct < 0.8:
            vol_label = "low"
        elif atr_pct < 2.0:
            vol_label = "medium"
        elif atr_pct < 4.0:
            vol_label = "high"
        else:
            vol_label = "extreme"

        above_ema20 = price > ema20
        above_ema50 = price > ema50

        if slope_20 > 3 and above_ema20 and above_ema50:
            direction = "bullish"
            strength  = min(int(abs(slope_20) * 10), 100)
        elif slope_20 < -3 and not above_ema20 and not above_ema50:
            direction = "bearish"
            strength  = min(int(abs(slope_20) * 10), 100)
        elif abs(slope_20) > 1.5:
            direction = "bullish" if slope_20 > 0 else "bearish"
            strength  = min(int(abs(slope_20) * 5), 60)
        else:
            direction = "neutral"
            strength  = 0

        range_20  = highs[-20:].max() - lows[-20:].min() if len(highs) >= 20 else 0
        avg_price = closes[-20:].mean() if len(closes) >= 20 else price
        range_pct = range_20 / avg_price * 100 if avg_price > 0 else 0

        if atr_pct > 3.5 or abs(slope_5) > 2.5:
            market_type = "volatile"
        elif range_pct < 3 or abs(slope_20) < 1:
            market_type = "ranging"
        else:
            market_type = "trending"

        vol_trend = (volumes[-5:].mean() / volumes[-20:].mean()) if len(volumes) >= 20 else 1.0
        if direction == "neutral" and slope_20 < 0.5:
            phase = "accumulation" if closes[-1] <= np.percentile(closes[-20:], 30) else "distribution"
        elif direction == "bullish" and market_type == "trending":
            phase = "markup"
        elif direction == "bearish" and market_type == "trending":
            phase = "markdown"
        else:
            phase = "transition"

        return {
            "direction":  direction,
            "type":       market_type,
            "phase":      phase,
            "volatility": vol_label,
            "strength":   strength,
            "atr_pct":    round(atr_pct, 3),
            "slope_20":   round(slope_20, 3),
            "ema20":      round(float(ema20), 6),
        }

    # ── Structure de Marché ───────────────────────────────────────────────────

    def _analyze_structure(
        self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray
    ) -> dict:
        """
        Identifie :
        - Pattern : HH/HL (bullish) | LH/LL (bearish) | mixte
        - Break of Structure (BOS) : rupture d'un swing précédent
        - Change of Character (CHoCH) : premier signe de retournement
        """
        if len(highs) < 15:
            return {"pattern": "unknown", "label": "Indéterminé",
                    "bos": False, "bos_level": None, "choch": False,
                    "swing_highs": [], "swing_lows": []}

        sh = self._find_swings(highs, mode="high", window=3)
        sl = self._find_swings(lows,  mode="low",  window=3)

        last_sh = sh[-4:] if len(sh) >= 4 else sh
        last_sl = sl[-4:] if len(sl) >= 4 else sl

        hh_count = hl_count = lh_count = ll_count = 0
        for i in range(1, len(last_sh)):
            if last_sh[i]["price"] > last_sh[i-1]["price"]:
                hh_count += 1
            else:
                lh_count += 1
        for i in range(1, len(last_sl)):
            if last_sl[i]["price"] > last_sl[i-1]["price"]:
                hl_count += 1
            else:
                ll_count += 1

        if hh_count > lh_count and hl_count > ll_count:
            pattern = "HH_HL"
            label   = "🟢 Bullish (HH/HL)"
        elif lh_count > hh_count and ll_count > hl_count:
            pattern = "LH_LL"
            label   = "🔴 Bearish (LH/LL)"
        elif hh_count > 0 and ll_count > 0:
            pattern = "mixed"
            label   = "🟡 Structure mixte"
        else:
            pattern = "unclear"
            label   = "⚪ Indéterminée"

        bos = False
        bos_level = None
        choch = False

        current = float(closes[-1])
        if len(last_sh) >= 2 and current > last_sh[-1]["price"]:
            if pattern in ("LH_LL", "mixed"):
                bos   = True
                choch = True
            else:
                bos = True
            bos_level = last_sh[-1]["price"]
        elif len(last_sl) >= 2 and current < last_sl[-1]["price"]:
            if pattern in ("HH_HL", "mixed"):
                bos   = True
                choch = True
            else:
                bos = True
            bos_level = last_sl[-1]["price"]

        return {
            "pattern":     pattern,
            "label":       label,
            "bos":         bos,
            "bos_level":   round(bos_level, 6) if bos_level else None,
            "choch":       choch,
            "swing_highs": [{"idx": s["idx"], "price": round(s["price"], 6)} for s in last_sh],
            "swing_lows":  [{"idx": s["idx"], "price": round(s["price"], 6)} for s in last_sl],
        }

    # ── Zones Clés ───────────────────────────────────────────────────────────

    def _find_key_levels(
        self,
        highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
        price: float, atr: float,
    ) -> dict:
        """
        Identifie résistances, supports, BSL (Buy-Side Liq.) et SSL (Sell-Side Liq.).
        """
        sh = self._find_swings(highs, "high", window=3)
        sl = self._find_swings(lows,  "low",  window=3)

        resistances = self._cluster_levels(
            [s["price"] for s in sh if s["price"] > price], threshold_pct=0.4,
        )[:3]
        supports = self._cluster_levels(
            [s["price"] for s in sl if s["price"] < price], threshold_pct=0.4,
        )[:3]
        supports.sort(key=lambda x: -x["price"])

        all_highs = [s["price"] for s in sh]
        all_lows  = [s["price"] for s in sl]
        bsl = self._find_liquidity_zone(all_highs, threshold_pct=0.3, above_price=price)
        ssl = self._find_liquidity_zone(all_lows,  threshold_pct=0.3, above_price=None, below_price=price)

        return {
            "resistances":        resistances,
            "supports":           supports,
            "bsl":                round(bsl, 6) if bsl else None,
            "ssl":                round(ssl, 6) if ssl else None,
            "nearest_resistance": round(resistances[0]["price"], 6) if resistances else None,
            "nearest_support":    round(supports[0]["price"], 6) if supports else None,
        }

    def _find_order_blocks(
        self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray
    ) -> list[dict]:
        """
        Identifie les Order Blocks institutionnels :
        - OB Bullish : dernière bougie rouge avant fort mouvement haussier
        - OB Bearish : dernière bougie verte avant fort mouvement baissier
        """
        if len(closes) < 6:
            return []

        opens = np.roll(closes, 1)
        opens[0] = closes[0]
        blocks = []

        for i in range(2, len(closes) - 3):
            next3_bull = all(closes[i+j] > closes[i+j-1] for j in range(1, 4) if i+j < len(closes))
            next3_bear = all(closes[i+j] < closes[i+j-1] for j in range(1, 4) if i+j < len(closes))

            is_bear_candle = closes[i] < opens[i]
            is_bull_candle = closes[i] > opens[i]

            if is_bear_candle and next3_bull:
                blocks.append({
                    "type":  "bullish",
                    "idx":   i,
                    "high":  round(float(highs[i]), 6),
                    "low":   round(float(lows[i]), 6),
                    "mid":   round(float((highs[i] + lows[i]) / 2), 6),
                    "label": f"🟢 OB Bullish @{(highs[i]+lows[i])/2:.4f}",
                })
            elif is_bull_candle and next3_bear:
                blocks.append({
                    "type":  "bearish",
                    "idx":   i,
                    "high":  round(float(highs[i]), 6),
                    "low":   round(float(lows[i]), 6),
                    "mid":   round(float((highs[i] + lows[i]) / 2), 6),
                    "label": f"🔴 OB Bearish @{(highs[i]+lows[i])/2:.4f}",
                })

        recent  = blocks[-5:] if len(blocks) >= 5 else blocks
        current = float(closes[-1])
        valid   = [
            b for b in recent
            if not (b["type"] == "bullish" and current < b["low"])
            and not (b["type"] == "bearish" and current > b["high"])
        ]
        return valid

    # ── Détection de Biais ────────────────────────────────────────────────────

    def _detect_bias(self, asset: str) -> dict:
        """
        Analyse les N dernières décisions pour détecter un biais directionnel.
        Biais détecté si > BIAS_THRESHOLD des décisions sont dans la même direction.
        """
        decisions = list(self._dec_buf.get(asset, []))
        if not decisions:
            all_decisions = [d for buf in self._dec_buf.values() for d in buf]
            decisions = all_decisions[-30:] if all_decisions else []

        if len(decisions) < 3:
            return {
                "detected": False, "type": "balanced",
                "long_pct": 0.5, "short_pct": 0.5,
                "long_count": 0, "short_count": 0,
                "recommendation": "Données insuffisantes — biais non calculable",
                "severity": "none",
            }

        long_count  = sum(1 for d in decisions if d.get("direction") == "bullish")
        short_count = sum(1 for d in decisions if d.get("direction") == "bearish")
        total       = long_count + short_count

        long_pct  = long_count  / total if total > 0 else 0.5
        short_pct = short_count / total if total > 0 else 0.5

        if long_pct >= BIAS_THRESHOLD:
            bias_type = "long_bias"
            severity  = "critical" if long_pct > 0.80 else "moderate"
            rec = (
                f"⚠️  BIAIS LONG DÉTECTÉ ({long_pct:.0%} des signaux) — "
                "Rechercher activement des setups SHORT. "
                "Réduire la taille des positions LONG de 20%."
            )
        elif short_pct >= BIAS_THRESHOLD:
            bias_type = "short_bias"
            severity  = "critical" if short_pct > 0.80 else "moderate"
            rec = (
                f"⚠️  BIAIS SHORT DÉTECTÉ ({short_pct:.0%} des signaux) — "
                "Rechercher activement des setups LONG. "
                "Réduire la taille des positions SHORT de 20%."
            )
        else:
            bias_type = "balanced"
            severity  = "none"
            rec = f"✅ Équilibré : {long_pct:.0%} long / {short_pct:.0%} short sur {total} signaux"

        return {
            "detected":       bias_type != "balanced",
            "type":           bias_type,
            "long_pct":       round(long_pct, 3),
            "short_pct":      round(short_pct, 3),
            "long_count":     long_count,
            "short_count":    short_count,
            "total_analyzed": total,
            "recommendation": rec,
            "severity":       severity,
        }

    # ── Cohérence Inter-Agents ────────────────────────────────────────────────

    def _check_coherence(self, asset: str, regime: dict, structure: dict) -> dict:
        """
        Vérifie la cohérence entre tous les agents et le contexte de marché.
        Score 0-100 : 100 = tous alignés, 0 = contradiction totale.
        """
        tech_signals = list(self._tech_buf.get(asset, []))
        fund_signals = list(self._fund_buf.get(asset, []))

        if not tech_signals:
            return {
                "score": 0, "verdict": "Pas de signaux disponibles", "details": [],
                "tech_dir": "neutral", "tech_conf": 0, "fund_dir": "neutral",
                "fund_conf": 0, "regime_dir": "neutral", "struct_dir": "neutral",
            }

        recent_tech = tech_signals[-5:]
        tech_bull = sum(1 for s in recent_tech if s.get("signal") == "bullish")
        tech_bear = sum(1 for s in recent_tech if s.get("signal") == "bearish")
        tech_dir  = "bullish" if tech_bull > tech_bear else ("bearish" if tech_bear > tech_bull else "neutral")
        tech_conf = sum(s.get("confidence", 0) for s in recent_tech) / len(recent_tech)

        recent_fund = fund_signals[-3:] if fund_signals else []
        fund_dir    = "neutral"
        fund_conf   = 0
        if recent_fund:
            fund_bull = sum(1 for s in recent_fund if s.get("signal") == "bullish")
            fund_bear = sum(1 for s in recent_fund if s.get("signal") == "bearish")
            fund_dir  = "bullish" if fund_bull > fund_bear else ("bearish" if fund_bear > fund_bull else "neutral")
            fund_conf = sum(s.get("confidence", 0) for s in recent_fund) / len(recent_fund)

        regime_dir = regime.get("direction", "neutral")
        struct_dir = (
            "bullish" if structure.get("pattern") == "HH_HL"
            else "bearish" if structure.get("pattern") == "LH_LL"
            else "neutral"
        )

        all_dirs   = [tech_dir, fund_dir, regime_dir, struct_dir]
        bull_votes = all_dirs.count("bullish")
        bear_votes = all_dirs.count("bearish")
        max_votes  = max(bull_votes, bear_votes)
        score      = int((max_votes / len(all_dirs)) * 100)

        details = []
        if tech_dir != "neutral" and struct_dir != "neutral" and tech_dir != struct_dir:
            details.append(f"⚠️  Technique {tech_dir} ≠ Structure {struct_dir}")
        if tech_dir != "neutral" and fund_dir != "neutral" and tech_dir != fund_dir:
            details.append(f"⚠️  Technique {tech_dir} ≠ Fondamental {fund_dir}")
        if regime_dir != "neutral" and tech_dir != "neutral" and regime_dir != tech_dir:
            details.append(f"⚠️  Régime {regime_dir} ≠ Technique {tech_dir}")
        if structure.get("bos"):
            details.append(f"🔔 Break of Structure à {structure.get('bos_level')} — recalibrage recommandé")
        if structure.get("choch"):
            details.append("🔔 CHoCH — potentiel retournement de tendance")

        if score >= 80:
            verdict = f"✅ Cohérence FORTE ({score}/100) — tous les agents alignés {tech_dir}"
        elif score >= 60:
            verdict = f"🟡 Cohérence MODÉRÉE ({score}/100) — légères divergences"
        else:
            verdict = f"🔴 Cohérence FAIBLE ({score}/100) — divergences inter-agents, prudence"

        return {
            "score":     score,
            "verdict":   verdict,
            "tech_dir":  tech_dir,
            "tech_conf": round(tech_conf, 1),
            "fund_dir":  fund_dir,
            "fund_conf": round(fund_conf, 1),
            "regime_dir": regime_dir,
            "struct_dir": struct_dir,
            "details":   details,
        }

    # ── Stratégies Multi-Horizon ──────────────────────────────────────────────

    def _build_strategies(
        self,
        asset: str,
        price: float,
        atr: float,
        regime: dict,
        structure: dict,
        levels: dict,
        bias: dict,
        mem_ctx: MemoryContext,
    ) -> dict:
        """
        Génère TOUJOURS des stratégies pour les 3 horizons.
        La mémoire (MemoryContext) influence les seuils et qualité.

        Scalping  : horizon 5m–15m, R:R 1:1.5, SL serré (0.5×ATR)
        Intraday  : horizon 1h–4h,  R:R 1:2,   SL normal (1×ATR)
        Swing     : horizon 1d+,    R:R 1:3,   SL large  (2×ATR)
        """
        direction   = regime.get("direction", "neutral")
        volatility  = regime.get("volatility", "medium")
        market_type = regime.get("type", "ranging")
        struct_bias = structure.get("pattern", "unclear")

        # ── Ajustements mémoire ────────────────────────────────────────────────
        mem_notes = []
        if mem_ctx.is_preservation_mode:
            mem_notes.append(
                "🛡️ [Mémoire] Mode Capital Preservation actif — "
                "seuil de confiance augmenté de +10pts, tailles réduites recommandées"
            )
        asset_wr = mem_ctx.asset_win_rates.get(asset)
        if asset_wr is not None and asset_wr < 0.40:
            mem_notes.append(
                f"⚠️ [Mémoire] Win rate historique sur {asset}: {asset_wr:.0%} — extra prudence recommandée"
            )
        if "TP too conservative" in mem_ctx.recurring_errors or "wins trop petits" in " ".join(mem_ctx.recurring_errors).lower():
            mem_notes.append("📌 [Mémoire] Erreur récurrente : TP trop conservateur — envisager TP plus large")
        if "SL too wide" in mem_ctx.recurring_errors or "losses trop larges" in " ".join(mem_ctx.recurring_errors).lower():
            mem_notes.append("📌 [Mémoire] Erreur récurrente : SL trop large — réduire le multiplicateur ATR")

        mem_note = " | ".join(mem_notes) if mem_notes else ""

        # Anti-biais directionnel
        bias_adj_dir = direction
        bias_note    = ""
        if bias.get("type") == "long_bias" and direction == "bullish":
            bias_adj_dir = "neutral"
            bias_note    = " ⚠️ [Biais long corrigé — setup short exploré]"
        elif bias.get("type") == "short_bias" and direction == "bearish":
            bias_adj_dir = "neutral"
            bias_note    = " ⚠️ [Biais short corrigé — setup long exploré]"

        r1  = levels.get("nearest_resistance", price * 1.02)
        s1  = levels.get("nearest_support",    price * 0.98)
        bsl = levels.get("bsl")
        ssl = levels.get("ssl")

        # SL ajusté si mémoire indique que les stops sont trop larges
        sl_mult_adj = 0.9 if "SL trop large" in " ".join(mem_ctx.recurring_errors).lower() else 1.0

        # ── Scalping ──────────────────────────────────────────────────────────
        scalp_sl_mult = (0.4 if volatility in ("low", "medium") else 0.6) * sl_mult_adj
        scalp_tp_mult = 0.8

        if direction == "bullish" and bias_adj_dir != "neutral":
            scalp = {
                "direction":    "LONG",
                "entry":        f"{price:.6f} (niveau courant)",
                "stop_loss":    round(price - atr * scalp_sl_mult, 6),
                "take_profit":  round(price + atr * scalp_tp_mult, 6),
                "rr":           round(scalp_tp_mult / scalp_sl_mult, 2),
                "timeframe":    "5m–15m",
                "condition":    "Entry sur pull-back vers support le plus proche",
                "invalidation": f"Close < {round(price - atr * 0.5, 6)}",
                "quality":      "🟢 Favorable" if market_type == "trending" else "🟡 Acceptable",
                "note":         (bias_note + " | " + mem_note) if mem_note else bias_note,
            }
            scalp_short = {
                "direction":  "SHORT",
                "entry":      f"{r1 or round(price*1.015, 6)} (résistance R1)",
                "stop_loss":  round((r1 or price*1.015) + atr * scalp_sl_mult, 6),
                "take_profit":round((r1 or price*1.015) - atr * scalp_tp_mult, 6),
                "rr":         round(scalp_tp_mult / scalp_sl_mult, 2),
                "timeframe":  "5m–15m",
                "condition":  "Rejet sur résistance avec volume baissier",
                "quality":    "🟡 Contre-tendance — prudence",
                "note":       "Setup complémentaire pour équilibrer le biais",
            }
        elif direction == "bearish" and bias_adj_dir != "neutral":
            scalp = {
                "direction":    "SHORT",
                "entry":        f"{price:.6f} (niveau courant)",
                "stop_loss":    round(price + atr * scalp_sl_mult, 6),
                "take_profit":  round(price - atr * scalp_tp_mult, 6),
                "rr":           round(scalp_tp_mult / scalp_sl_mult, 2),
                "timeframe":    "5m–15m",
                "condition":    "Entry sur rebond vers résistance la plus proche",
                "invalidation": f"Close > {round(price + atr * 0.5, 6)}",
                "quality":      "🟢 Favorable" if market_type == "trending" else "🟡 Acceptable",
                "note":         (bias_note + " | " + mem_note) if mem_note else bias_note,
            }
            scalp_short = {
                "direction":  "LONG",
                "entry":      f"{s1 or round(price*0.985, 6)} (support S1)",
                "stop_loss":  round((s1 or price*0.985) - atr * scalp_sl_mult, 6),
                "take_profit":round((s1 or price*0.985) + atr * scalp_tp_mult, 6),
                "rr":         round(scalp_tp_mult / scalp_sl_mult, 2),
                "timeframe":  "5m–15m",
                "condition":  "Rebond sur support avec volume haussier",
                "quality":    "🟡 Contre-tendance — prudence",
                "note":       "Setup complémentaire pour équilibrer le biais",
            }
        else:
            scalp = {
                "direction":  "RANGE",
                "entry":      f"LONG @ {s1:.6f} | SHORT @ {r1:.6f}" if s1 and r1 else "—",
                "stop_loss":  "En dehors du range",
                "take_profit":"Extrémité opposée du range",
                "rr":         1.5,
                "timeframe":  "5m–15m",
                "condition":  "Marché en range — jouer les extrémités",
                "quality":    "🟡 Range confirmé requis",
                "note":       mem_note,
            }
            scalp_short = None

        # ── Intraday ──────────────────────────────────────────────────────────
        intra_sl = 1.0 * sl_mult_adj
        intra_tp = 2.0

        if direction == "bullish":
            intra = {
                "direction":  "LONG",
                "entry":      f"Pull-back vers {round(price - atr*0.5, 6)} ou OB bullish",
                "stop_loss":  round(price - atr * intra_sl, 6),
                "take_profit":round(price + atr * intra_tp, 6),
                "rr":         intra_tp,
                "timeframe":  "1h–4h",
                "condition":  "Confirmation sur 1h : clôture au-dessus de l'EMA20",
                "target":     f"R1 : {r1:.6f}" + (f" | BSL : {bsl:.6f}" if bsl else ""),
                "quality":    "🟢 Favorable" if struct_bias == "HH_HL" else "🟡 Modéré",
                "note":       mem_note,
            }
        elif direction == "bearish":
            intra = {
                "direction":  "SHORT",
                "entry":      f"Rebond vers {round(price + atr*0.5, 6)} ou OB bearish",
                "stop_loss":  round(price + atr * intra_sl, 6),
                "take_profit":round(price - atr * intra_tp, 6),
                "rr":         intra_tp,
                "timeframe":  "1h–4h",
                "condition":  "Confirmation sur 1h : clôture sous l'EMA20",
                "target":     f"S1 : {s1:.6f}" + (f" | SSL : {ssl:.6f}" if ssl else ""),
                "quality":    "🟢 Favorable" if struct_bias == "LH_LL" else "🟡 Modéré",
                "note":       mem_note,
            }
        else:
            intra = {
                "direction":  "ATTENTE",
                "entry":      "Pas de setup intraday clair",
                "stop_loss":  "—",
                "take_profit":"—",
                "rr":         0,
                "timeframe":  "1h–4h",
                "condition":  "Attendre confirmation de direction sur 1h",
                "quality":    "🔴 Non favorable — marché indécis",
            }

        # ── Swing ─────────────────────────────────────────────────────────────
        swing_sl = 2.0 * sl_mult_adj
        swing_tp = 5.0

        if direction == "bullish" and struct_bias == "HH_HL":
            swing = {
                "direction":    "LONG",
                "entry":        "Achat sur correction ≥ 38.2% du dernier swing haussier",
                "stop_loss":    round(price - atr * swing_sl, 6),
                "take_profit":  round(price + atr * swing_tp, 6),
                "rr":           swing_tp / swing_sl,
                "timeframe":    "1d–1W",
                "condition":    "Structure HH/HL intacte, volume confirmé",
                "invalidation": "Cassure sous le dernier HL",
                "quality":      "🟢 Favorable — structure bullish validée",
                "note":         mem_note,
            }
        elif direction == "bearish" and struct_bias == "LH_LL":
            swing = {
                "direction":    "SHORT",
                "entry":        "Short sur rebond ≤ 61.8% du dernier swing baissier",
                "stop_loss":    round(price + atr * swing_sl, 6),
                "take_profit":  round(price - atr * swing_tp, 6),
                "rr":           swing_tp / swing_sl,
                "timeframe":    "1d–1W",
                "condition":    "Structure LH/LL intacte, volume confirmé",
                "invalidation": "Cassure au-dessus du dernier LH",
                "quality":      "🟢 Favorable — structure bearish validée",
                "note":         mem_note,
            }
        else:
            swing = {
                "direction":  "ATTENTE / OBSERVATION",
                "entry":      "Structure de marché non confirmée pour un swing",
                "stop_loss":  "—",
                "take_profit":"—",
                "rr":         0,
                "timeframe":  "1d+",
                "condition":  "Attendre un BOS / CHoCH propre avant d'entrer",
                "quality":    "🟡 Prudence — structure ambiguë",
            }

        result = {"scalping": scalp, "intraday": intra, "swing": swing}
        if scalp_short:
            result["scalping_contrarian"] = scalp_short
        return result

    # ── Sentiment Global ──────────────────────────────────────────────────────

    def _compute_sentiment(self, asset: str) -> dict:
        """Agrège le sentiment des signaux fondamentaux récents."""
        fund_sigs = list(self._fund_buf.get(asset, []))
        if not fund_sigs:
            return {"overall": "neutral", "score": 0, "count": 0}

        recent = fund_sigs[-5:]
        scores = [s.get("sentiment_score", 0) for s in recent if "sentiment_score" in s]
        if not scores:
            return {"overall": "neutral", "score": 0, "count": len(recent)}

        avg = np.mean(scores)
        overall = "positive" if avg > 20 else ("negative" if avg < -20 else "neutral")
        return {"overall": overall, "score": round(float(avg), 1), "count": len(recent)}

    # ── Vault Health Check ────────────────────────────────────────────────────

    def _vault_health_check(self) -> None:
        """
        Analyse la santé du vault et écrit un rapport dans vault/synthese/.

        Problèmes détectés :
        - Dossiers manquants
        - Notes sans frontmatter valide
        - Notes > 7 jours sans mise à jour (staleness)
        - Mémoires agents avec 0 trade (jamais initialisées)
        - Mémoires corrompues (YAML invalide)
        - Déséquilibre de volume (un dossier trop chargé)
        """
        issues   = []
        warnings = []
        stats    = {}

        vault = self.obsidian.vault_path
        expected_dirs = [
            "technique", "fondamental", "risque", "execution",
            "decisions", "retrospectives", "config", "synthese",
            "compound", "apprentissage",
        ]

        # ── Vérification des dossiers ─────────────────────────────────────────
        for d in expected_dirs:
            p = vault / d
            if not p.exists():
                issues.append(f"❌ Dossier manquant : vault/{d}/")
                p.mkdir(exist_ok=True)
                issues.append(f"  → Créé automatiquement")
            else:
                files = list(p.glob("*.md"))
                stats[d] = len(files)

        # ── Vérification des mémoires agents ─────────────────────────────────
        config_dir = vault / "config"
        expected_memories = [
            "CompoundAgent_state", "RiskAgent_memory",
            "PredictAgent_memory", "ScanAgent_memory",
        ]
        for mem_name in expected_memories:
            note = self.obsidian.read_note("config", mem_name)
            if note is None:
                warnings.append(f"⚠️  Mémoire absente : config/{mem_name}.md (agent non encore initialisé)")
            elif note.frontmatter.get("total_trades", -1) == 0:
                warnings.append(f"⚠️  Mémoire vide : {mem_name} — aucun trade enregistré (normal si démo récente)")

        # ── Vérification des notes récentes (staleness) ───────────────────────
        import time
        now_ts = time.time()
        stale_threshold = 7 * 24 * 3600  # 7 jours

        for folder in ["technique", "fondamental", "risque"]:
            p = vault / folder
            if not p.exists():
                continue
            files = sorted(p.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
            if files:
                most_recent_age = now_ts - files[0].stat().st_mtime
                if most_recent_age > stale_threshold:
                    days = int(most_recent_age / 86400)
                    warnings.append(
                        f"⏰ Dossier vault/{folder}/ inactif depuis {days} jours — "
                        "agent correspondant peut-être arrêté ?"
                    )

        # ── Notes avec frontmatter manquant ───────────────────────────────────
        malformed = 0
        for folder in list(stats.keys()):
            for f in (vault / folder).glob("*.md"):
                try:
                    text = f.read_text(encoding="utf-8")
                    if not text.startswith("---"):
                        malformed += 1
                except Exception:
                    malformed += 1
        if malformed > 0:
            warnings.append(f"⚠️  {malformed} note(s) avec frontmatter YAML manquant")

        # ── Rapport ───────────────────────────────────────────────────────────
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        health_score = max(0, 100 - len(issues) * 20 - len(warnings) * 5)

        nl = "\n"
        issues_md   = nl.join(f"- {i}" for i in issues)   if issues   else "- ✅ Aucun problème critique"
        warnings_md = nl.join(f"- {w}" for w in warnings) if warnings else "- ✅ Aucun avertissement"
        stats_md    = nl.join(f"| `{k}` | `{v}` notes |" for k, v in sorted(stats.items()))

        frontmatter = {
            "date":         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "agent":        "SynthesisAgent",
            "type":         "vault_health_check",
            "health_score": health_score,
            "issues":       len(issues),
            "warnings":     len(warnings),
            "tags":         ["health", "vault", "diagnostic"],
        }

        content = f"""## Vault Health Check — {date_str}

### Score de Santé : {health_score}/100

### Problèmes Critiques
{issues_md}

### Avertissements
{warnings_md}

### Statistiques du Vault
| Dossier | Volume |
|---|---|
{stats_md}
"""
        self.obsidian.write_note("synthese", f"health_check_{date_str}", frontmatter, content)
        logger.info(
            "[%s] 🏥 Vault health check — score:%d/100 | %d issues | %d warnings",
            self.name, health_score, len(issues), len(warnings),
        )

    # ── Rétrospective & Auto-Amélioration ─────────────────────────────────────

    def _write_retrospective_note(self) -> None:
        """
        Analyse les patterns d'erreurs récurrentes, incohérences inter-agents,
        et génère des propositions d'auto-amélioration concrètes.
        """
        outcomes = list(self._outcomes)
        if len(outcomes) < 5:
            return

        total  = len(outcomes)
        wins   = sum(1 for o in outcomes if o.get("is_win"))
        losses = total - wins
        avg_pnl_win  = float(np.mean([o.get("pnl_pct", 0) for o in outcomes if o.get("is_win")])) if wins else 0
        avg_pnl_loss = float(np.mean([o.get("pnl_pct", 0) for o in outcomes if not o.get("is_win")])) if losses else 0

        all_decisions = [d for buf in self._dec_buf.values() for d in buf]
        total_dir   = len(all_decisions)
        long_count  = sum(1 for d in all_decisions if d.get("direction") == "bullish")
        short_count = sum(1 for d in all_decisions if d.get("direction") == "bearish")
        long_pct    = long_count / total_dir if total_dir > 0 else 0.5

        # Patterns d'erreur
        patterns = []
        if wins > 0 and avg_pnl_win < 0.5:
            patterns.append("wins trop petits — TP trop conservateur ou sorties prématurées")
        if losses > 0 and abs(avg_pnl_loss) > 1.5:
            patterns.append("losses trop larges — SL trop large ou tenu trop longtemps")
        if long_pct > BIAS_THRESHOLD:
            patterns.append(f"biais long systémique ({long_pct:.0%}) — pipeline favorise trop les achats")
        if wins / total < 0.4 and total >= 10:
            patterns.append("win rate < 40% — revoir les seuils de confiance ou la logique de PredictAgent")

        # Suggestions d'auto-amélioration
        suggestions = []
        if long_pct > 0.70:
            suggestions.append(
                "Ajouter un multiplicateur de confiance ×0.9 pour signaux LONG pendant biais détecté"
            )
        if wins / total < 0.45 and total >= 10:
            suggestions.append(
                "Relever le confidence_floor de +5 points dans RiskAgent_memory.md"
            )
        if abs(avg_pnl_loss) > abs(avg_pnl_win) * 2:
            suggestions.append(
                "Réduire sl_atr_multiplier de 0.1 dans RiskAgent_memory.md — stops trop larges"
            )

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fname    = f"retrospective_system_{date_str}"

        nl = "\n"
        verdict_str  = "⚠️ BIAIS LONG" if long_pct > 0.65 else ("⚠️ BIAIS SHORT" if long_pct < 0.35 else "✅ Équilibré")
        patterns_md  = nl.join(f"- ⚠️  {p}" for p in patterns)  if patterns  else "- ✅ Aucun pattern d'erreur significatif"
        suggest_md   = nl.join(f"- 📌 {s}" for s in suggestions) if suggestions else "- ✅ Paramètres dans les normes"
        ratio_str    = f"{abs(avg_pnl_win / avg_pnl_loss):.2f}" if avg_pnl_loss != 0 else "∞"

        frontmatter = {
            "date":          date_str,
            "agent":         "SynthesisAgent",
            "type":          "system_retrospective",
            "win_rate":      round(wins / total, 3),
            "long_pct":      round(long_pct, 3),
            "total_trades":  total,
            "error_patterns": patterns,   # utilisé par _load_active_memory()
            "tags":          ["retrospective", "system", "biais", "auto-amelioration"],
        }

        content = f"""## Rétrospective Système — {date_str}

### Performance Globale (session)
| Métrique | Valeur |
|---|---|
| Total trades analysés | `{total}` |
| Wins | `{wins}` ({wins/total:.0%}) |
| Losses | `{losses}` ({losses/total:.0%}) |
| Gain moyen (wins) | `+{avg_pnl_win:.3f}%` |
| Perte moyenne (losses) | `{avg_pnl_loss:.3f}%` |
| Ratio Gain/Perte | `{ratio_str}` |

### Biais Directionnel Systémique
| Direction | Count | % |
|---|---|---|
| LONG (Bullish) | `{long_count}` | `{long_pct:.0%}` |
| SHORT (Bearish) | `{short_count}` | `{1-long_pct:.0%}` |
| **Verdict** | {verdict_str} | — |

### Patterns d'Erreur Identifiés
{patterns_md}

### Propositions d'Auto-Amélioration
{suggest_md}

### Liens
{self.obsidian.wikilink('config', 'RiskAgent_memory')}
{self.obsidian.wikilink('config', 'PredictAgent_memory')}
{self.obsidian.wikilink('config', 'CompoundAgent_state')}
"""
        self.obsidian.write_note("synthese", fname, frontmatter, content)

    # ── Vault Obsidian — DataSheet ────────────────────────────────────────────

    def _write_vault_note(self, asset: str, sheet: dict) -> None:
        """Écrit la DataSheet complète dans vault/synthese/ avec toutes les sections."""
        ts    = datetime.now(timezone.utc)
        fname = f"datasheet_{ts.strftime('%Y-%m-%d_%H%M')}_{asset.replace('/','_')}"

        r    = sheet["regime"]
        s    = sheet["structure"]
        lv   = sheet["levels"]
        b    = sheet["bias"]
        c    = sheet["coherence"]
        st   = sheet["strategies"]
        sent = sheet["sentiment"]
        obs  = sheet.get("order_blocks", [])
        vix  = sheet.get("vix", {})
        vp   = sheet.get("vol_profile", {})
        manip = sheet.get("manipulation", {})
        mf   = sheet.get("mirofish", {})
        mc   = sheet.get("memory_ctx", {})

        # Résistances et supports
        res_rows = "\n".join(
            f"| R{i+1} | `{v['price']:.6f}` | `{v['strength']}/100` | `{v['touches']}` touches |"
            for i, v in enumerate(lv["resistances"])
        ) or "| — | — | — | — |"
        sup_rows = "\n".join(
            f"| S{i+1} | `{v['price']:.6f}` | `{v['strength']}/100` | `{v['touches']}` touches |"
            for i, v in enumerate(lv["supports"])
        ) or "| — | — | — | — |"

        # Order Blocks
        ob_rows = "\n".join(
            f"| {ob['label']} | `{ob['low']:.6f}` | `{ob['high']:.6f}` | `{ob['mid']:.6f}` |"
            for ob in obs
        ) or "| — | — | — | — |"

        # Stratégies
        def fmt_strategy(strat: dict) -> str:
            if not strat:
                return "_Non disponible_"
            lines = [
                f"**Direction** : `{strat.get('direction','—')}`",
                f"**Entrée** : {strat.get('entry','—')}",
                f"**SL** : `{strat.get('stop_loss','—')}` | **TP** : `{strat.get('take_profit','—')}` | **R:R** : `1:{strat.get('rr',0):.1f}`",
                f"**Timeframe** : `{strat.get('timeframe','—')}`",
                f"**Condition** : _{strat.get('condition','—')}_",
                f"**Qualité** : {strat.get('quality','—')}",
            ]
            if strat.get("note"):
                lines.append(f"**Note mémoire** : _{strat['note']}_")
            return "\n".join(lines)

        sh_str = " | ".join(f"`{sh['price']:.4f}`" for sh in s.get("swing_highs", []))
        sl_str = " | ".join(f"`{sl['price']:.4f}`" for sl in s.get("swing_lows", []))

        # Volume profile nodes
        hvn_str = " | ".join(f"`{v:.4f}`" for v in vp.get("hvn", [])) or "—"
        lvn_str = " | ".join(f"`{v:.4f}`" for v in vp.get("lvn", [])) or "—"

        # Manipulation notes
        manip_notes_md = "\n".join(f"- {n}" for n in manip.get("notes", [])) or "- ✅ Aucun signal de manipulation détecté"

        # Mirofish
        if mf.get("error"):
            mf_section = f"> ⚠️ Simulation Mirofish non disponible : {mf.get('error')}"
        else:
            mf_dir     = mf.get("direction", "—")
            mf_long    = mf.get("long_pct", 0)
            mf_short   = mf.get("short_pct", 0)
            mf_hold    = mf.get("hold_pct", 0)
            mf_bull_p  = mf.get("bull_probability", 0)
            mf_bear_p  = mf.get("bear_probability", 0)
            mf_contr   = "⚠️ OUI" if mf.get("contrarian_signal") else "Non"
            mf_diverg  = mf.get("divergence_score", 0)
            mf_manip   = mf.get("manipulation_risk", 0)
            mf_note    = mf.get("behavioral_note", "—")
            mf_section = f"""> {mf.get('disclaimer', '')}

| Métrique Mirofish | Valeur |
|---|---|
| Direction crowd | `{mf_dir.upper()}` |
| Votes LONG / SHORT / HOLD | `{mf_long:.0%}` / `{mf_short:.0%}` / `{mf_hold:.0%}` |
| Probabilité haussière | `{mf_bull_p:.0%}` |
| Probabilité baissière | `{mf_bear_p:.0%}` |
| Signal Contrarian (>75%) | {mf_contr} |
| Divergence vs Technique | `{mf_diverg:+d}` (-50 à +50) |
| Risque manipulation crowd | `{mf_manip:.0%}` |

**Note comportementale** : _{mf_note}_"""

        # Convertir numpy scalars en types Python natifs pour YAML
        def _py(v):
            if hasattr(v, 'item'):
                return v.item()
            return v

        frontmatter = {
            "date":        ts.strftime("%Y-%m-%d %H:%M UTC"),
            "agent":       "SynthesisAgent",
            "asset":       asset,
            "regime":      r.get("direction","?"),
            "market_type": r.get("type","?"),
            "phase":       r.get("phase","?"),
            "volatility":  r.get("volatility","?"),
            "structure":   s.get("pattern","?"),
            "bos":         bool(s.get("bos", False)),
            "bias":        b.get("type","?"),
            "coherence":   int(_py(c.get("score", 0))),
            "realized_vol": float(_py(vix.get("realized_vol", 0))),
            "manip_risk":   float(_py(manip.get("risk_score", 0))),
            "compound_mode": mc.get("compound_mode", "normal"),
            "tags":        ["synthese", "datasheet", asset.replace("/","-").lower()],
        }

        content = f"""## DataSheet Institutionnelle — {asset}

> Généré le {ts.strftime('%d/%m/%Y %H:%M UTC')} | Prix : `{sheet['price']:.6f}` | ATR : `{sheet['atr']:.6f}` ({sheet['atr_pct']:.2f}%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> {mc.get('summary', 'Non chargé')}

| Paramètre Mémorisé | Valeur |
|---|---|
| Mode CompoundAgent | `{mc.get('compound_mode', 'normal').upper()}` |
| Risque/Trade actuel | `{mc.get('risk_pct', 2.0)}%` |
| Confiance min. (RiskAgent) | `{mc.get('confidence_floor', 55)}` |
| Ajustement confiance mémoire | `{mc.get('confidence_boost', 0):+d} pts` |

---

### 1. RÉGIME DE MARCHÉ
| Dimension | Valeur | Détail |
|---|---|---|
| Direction | **{r['direction'].upper()}** | slope 20p = {r.get('slope_20',0):+.2f}% |
| Type | **{r['type'].upper()}** | volatilité {r['volatility']} |
| Phase (Wyckoff) | **{r['phase'].upper()}** | EMA20 = {r.get('ema20',0):.4f} |
| Volatilité ATR% | `{r['atr_pct']:.2f}%` | {'🔴 Extrême' if r['volatility']=='extreme' else '🟠 Haute' if r['volatility']=='high' else '🟡 Moyenne' if r['volatility']=='medium' else '🟢 Faible'} |
| Force de tendance | `{r.get('strength',0)}/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `{vix.get('realized_vol', 0):.1f}%` — {vix.get('label', '—')} |
| Percentile session | `{vix.get('percentile', 50)}e percentile` |
| POC (Point of Control) | `{vp.get('poc') or '—'}` |
| Value Area High (VAH) | `{vp.get('vah') or '—'}` |
| Value Area Low (VAL) | `{vp.get('val') or '—'}` |
| HVN (High Vol. Nodes) | {hvn_str} |
| LVN (Low Vol. Nodes) | {lvn_str} |

---

### 3. STRUCTURE DE MARCHÉ
> **{s['label']}**
{'> 🔔 **BREAK OF STRUCTURE** détecté à `' + str(s.get('bos_level','?')) + '`' if s.get('bos') else ''}
{'> 🔄 **CHoCH** — potentiel retournement' if s.get('choch') else ''}

| Swing Highs récents | {sh_str or "—"} |
|---|---|
| **Swing Lows récents** | {sl_str or "—"} |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
{res_rows}

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
{sup_rows}

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `{lv.get('bsl') or '—'}` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `{lv.get('ssl') or '—'}` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
{ob_rows}

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `{manip.get('risk_score', 0)}/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | {'⚠️ OUI' if manip.get('stop_hunt') else '✅ Non'} |
| Wash Trading | {'⚠️ OUI' if manip.get('wash_trading') else '✅ Non'} |
| Fake Wall OB | {'⚠️ OUI' if manip.get('fake_wall') else '✅ Non'} |

{manip_notes_md}

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> {sent['overall'].upper()} — score `{sent['score']:+.1f}` sur {sent['count']} signaux fondamentaux

#### Cohérence Inter-Agents
> {c['verdict']}

| Source | Direction | Confiance |
|---|---|---|
| Technique | `{c['tech_dir']}` | `{c['tech_conf']:.0f}/100` |
| Fondamental | `{c['fund_dir']}` | `{c['fund_conf']:.0f}/100` |
| Régime | `{c['regime_dir']}` | — |
| Structure | `{c['struct_dir']}` | — |

{"**Divergences :**" + chr(10) + chr(10).join("- " + d for d in c['details']) if c['details'] else "✅ Pas de divergence majeure"}

#### Détection de Biais
> {b['recommendation']}

| Direction | Signaux | % |
|---|---|---|
| LONG | `{b['long_count']}` | `{b['long_pct']:.0%}` |
| SHORT | `{b['short_count']}` | `{b['short_pct']:.0%}` |
| Sévérité | `{b['severity']}` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
{fmt_strategy(st.get('scalping'))}

{"#### ⚡ Scalping Contrarian" + chr(10) + fmt_strategy(st.get('scalping_contrarian')) if st.get('scalping_contrarian') else ""}

---

#### 📊 Intraday (1h–4h)
{fmt_strategy(st.get('intraday'))}

---

#### 🌊 Swing (1d+)
{fmt_strategy(st.get('swing'))}

---

### 9. MIROFISH — SOURCE SECONDAIRE
> ⚠️ **ATTENTION** : Section secondaire de confirmation comportementale.
> Les données Mirofish ne remplacent JAMAIS l'analyse des sections 1-8.
> Priorité 4/4 dans la hiérarchie des sources.

{mf_section}

---

### Liens
{self.obsidian.wikilink('decisions', self.obsidian.daily_filename('predict', asset))}
{self.obsidian.wikilink('config', 'SynthesisAgent_memory')}
{self.obsidian.wikilink('config', 'CompoundAgent_state')}
"""
        self.obsidian.write_note("synthese", fname, frontmatter, content)
        logger.info(
            "[%s] 📊 DataSheet %s → %s | %s | Cohérence:%d/100 | VIX:%.1f%% | Manip:%d/75 | Biais:%s",
            self.name, asset, r["direction"].upper(), s["label"],
            c["score"], vix.get("realized_vol", 0), manip.get("risk_score", 0), b["type"],
        )

    # ── Algorithmes Techniques ────────────────────────────────────────────────

    @staticmethod
    def _find_swings(series: np.ndarray, mode: str, window: int = 3) -> list[dict]:
        """Détecte les swing highs ou swing lows."""
        results = []
        for i in range(window, len(series) - window):
            if mode == "high":
                if series[i] == max(series[i-window:i+window+1]):
                    results.append({"idx": i, "price": float(series[i])})
            else:
                if series[i] == min(series[i-window:i+window+1]):
                    results.append({"idx": i, "price": float(series[i])})
        return results

    @staticmethod
    def _cluster_levels(prices: list[float], threshold_pct: float = 0.5) -> list[dict]:
        """Regroupe les prix proches (±threshold_pct%) en zones."""
        if not prices:
            return []
        sorted_prices = sorted(prices)
        clusters = []
        current_cluster = [sorted_prices[0]]

        for p in sorted_prices[1:]:
            ref = current_cluster[-1]
            if abs(p - ref) / ref * 100 <= threshold_pct:
                current_cluster.append(p)
            else:
                avg = float(np.mean(current_cluster))
                clusters.append({
                    "price":    round(avg, 6),
                    "low":      round(float(np.min(current_cluster)), 6),
                    "high":     round(float(np.max(current_cluster)), 6),
                    "touches":  len(current_cluster),
                    "strength": min(len(current_cluster) * 25, 100),
                })
                current_cluster = [p]

        if current_cluster:
            avg = float(np.mean(current_cluster))
            clusters.append({
                "price":    round(avg, 6),
                "low":      round(float(np.min(current_cluster)), 6),
                "high":     round(float(np.max(current_cluster)), 6),
                "touches":  len(current_cluster),
                "strength": min(len(current_cluster) * 25, 100),
            })

        return sorted(clusters, key=lambda x: -x["strength"])

    @staticmethod
    def _find_liquidity_zone(
        prices: list[float],
        threshold_pct: float = 0.3,
        above_price: Optional[float] = None,
        below_price: Optional[float] = None,
    ) -> Optional[float]:
        """Trouve une zone de liquidité (equal highs ou equal lows)."""
        if len(prices) < 2:
            return None
        for i, p1 in enumerate(prices):
            for p2 in prices[i+1:]:
                if abs(p1 - p2) / max(p1, 1e-9) * 100 <= threshold_pct:
                    mid = (p1 + p2) / 2
                    if above_price is not None and mid <= above_price:
                        continue
                    if below_price is not None and mid >= below_price:
                        continue
                    return mid
        return None

    @staticmethod
    def _ema(series: np.ndarray, period: int) -> float:
        """EMA simple."""
        if len(series) < period:
            return float(np.mean(series)) if len(series) > 0 else 0.0
        k, result = 2 / (period + 1), series[0]
        for v in series[1:]:
            result = v * k + result * (1 - k)
        return float(result)

    @staticmethod
    def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Average True Range."""
        if len(closes) < 2:
            return 0.0
        tr = np.maximum(highs[1:] - lows[1:],
             np.maximum(abs(highs[1:] - closes[:-1]),
                        abs(lows[1:]  - closes[:-1])))
        return float(np.mean(tr[-period:]))
