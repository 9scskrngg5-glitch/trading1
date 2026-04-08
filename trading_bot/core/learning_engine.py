"""
Learning Engine — Cerveau ML du système multi-agents.

Fonctions principales :
1. record_outcome()         → enregistre un trade clôturé
2. run_counterfactual()     → analyse "qu'est-ce qui aurait marché ?"
3. update_agent_memory()    → met à jour les poids adaptatifs
4. save/load_memory()       → persiste la mémoire dans le vault Obsidian

Algorithme d'apprentissage : EMA Bayésien sur les taux de succès.
Pas de dépendance sklearn pour le cœur — numpy seulement.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

from models.learning import (
    AgentMemory, CounterfactualResult, IndicatorStats,
    MarketRegime, TradeOutcome,
)
from core.obsidian_client import ObsidianClient

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────
LEARNING_RATE   = 0.10     # α pour EMA
MIN_TRADES      = 5        # trades minimum avant d'adapter les poids
WEIGHT_MIN      = 0.3      # poids minimum (évite de "tuer" un indicateur)
WEIGHT_MAX      = 2.0      # poids maximum

# Grille de recherche contrefactuelle
SL_MULTIPLIERS  = [0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0]
TP_RATIOS       = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]


class LearningEngine:
    """
    Moteur d'apprentissage central partagé par tous les agents.

    Chaque agent dispose de sa propre AgentMemory, persistée dans :
        vault/config/{agent_name}_memory.md

    Flux d'apprentissage :
        TradeOutcome → update_agent_memory() → AgentMemory (vault)
                    → run_counterfactual() → CounterfactualResult (vault)
    """

    def __init__(self, obsidian: ObsidianClient, config: dict, telegram=None):
        self.obsidian = obsidian
        self.config   = config
        self.telegram = telegram
        self._memories: dict[str, AgentMemory] = {}
        self._outcomes: list[TradeOutcome]     = []

    # ── Chargement / Sauvegarde de la mémoire ─────────────────────────────────

    def load_memory(self, agent_name: str) -> AgentMemory:
        """
        Charge la mémoire persistée du vault.
        Si c'est la première exécution, crée une mémoire par défaut.
        """
        note = self.obsidian.read_note("config", f"{agent_name}_memory")
        if note is None or not note.frontmatter:
            logger.info("[Learning] Première exécution de %s — mémoire initialisée", agent_name)
            mem = AgentMemory.default(agent_name)
            self._memories[agent_name] = mem
            self.save_memory(mem)
            return mem

        fm = note.frontmatter

        # Reconstruction depuis le frontmatter YAML + contenu JSON inline
        mem = AgentMemory(
            agent_name     = agent_name,
            version        = fm.get("version", 1),
            total_trades   = fm.get("total_trades", 0),
            total_wins     = fm.get("total_wins", 0),
            total_pnl_usd  = fm.get("total_pnl_usd", 0.0),
            total_pnl_pct  = fm.get("total_pnl_pct", 0.0),
            best_trade_pct = fm.get("best_trade_pct", 0.0),
            worst_trade_pct= fm.get("worst_trade_pct", 0.0),
            last_updated   = fm.get("last_updated", ""),
        )

        # Extraction des blocs JSON depuis le contenu markdown
        # Utilise les titres français exacts des sections
        content = note.content
        json_blocks = self._extract_all_json_blocks(content)
        # Ordre des blocs dans save_memory() : [0] adaptive_params, [1] indicator_weights, [2] indicator_stats, [3] asset_stats, [4] regime_params
        if len(json_blocks) >= 1:
            mem.adaptive_params   = json_blocks[0] or mem.adaptive_params
        if len(json_blocks) >= 2:
            mem.indicator_weights = json_blocks[1] or {}
        if len(json_blocks) >= 3:
            mem.indicator_stats   = json_blocks[2] or {}
        if len(json_blocks) >= 4:
            mem.asset_stats       = json_blocks[3] or {}
        if len(json_blocks) >= 5:
            mem.regime_params     = json_blocks[4] or mem.regime_params

        # ── Détection + nettoyage chirurgical de corruption ──
        # Les anciens fichiers vault avaient adaptive_params dupliqué dans tous les blocs
        adaptive_keys = {"sl_atr_multiplier", "tp_rr_ratio", "confidence_floor",
                         "tech_weight", "fund_weight", "learning_rate", "regime_sensitivity", "leverage"}
        for field_name in ("indicator_weights", "indicator_stats", "asset_stats"):
            data = getattr(mem, field_name)
            if data and adaptive_keys & set(data.keys()):
                removed = 0
                for k in list(adaptive_keys):
                    if k in data:
                        del data[k]
                        removed += 1
                if removed:
                    logger.warning(
                        "[Learning] CORRUPTION nettoyée dans %s.%s — %d clés parasites retirées",
                        agent_name, field_name, removed,
                    )

        self._memories[agent_name] = mem
        logger.info(
            "[Learning] Mémoire chargée pour %s : %d trades, WR=%.1f%%",
            agent_name, mem.total_trades, mem.win_rate * 100,
        )
        return mem

    def save_memory(self, mem: AgentMemory) -> None:
        """Persiste la mémoire dans vault/config/{agent}_memory.md"""
        mem.last_updated = datetime.now(timezone.utc).isoformat()
        mem.version     += 1

        frontmatter = mem.to_frontmatter()
        frontmatter.update({
            "total_pnl_usd":  round(mem.total_pnl_usd, 2),
            "total_pnl_pct":  round(mem.total_pnl_pct, 4),
            "best_trade_pct": round(mem.best_trade_pct, 4),
            "worst_trade_pct":round(mem.worst_trade_pct, 4),
            "current_streak": mem.current_streak,
        })

        content = f"""## Mémoire Apprise — {mem.agent_name}

### Paramètres Adaptatifs
```json
{json.dumps(mem.adaptive_params, indent=2, ensure_ascii=False)}
```

### Poids des Indicateurs
```json
{json.dumps(mem.indicator_weights, indent=2, ensure_ascii=False)}
```

### Statistiques par Indicateur
```json
{json.dumps(mem.indicator_stats, indent=2, ensure_ascii=False)}
```

### Statistiques par Asset
```json
{json.dumps(mem.asset_stats, indent=2, ensure_ascii=False)}
```

### Paramètres par Régime
```json
{json.dumps(mem.regime_params, indent=2, ensure_ascii=False)}
```

### Historique d'Apprentissage
- Total trades : **{mem.total_trades}**
- Win rate : **{mem.win_rate:.1%}**
- P&L total : **${mem.total_pnl_usd:+,.2f}** (`{mem.total_pnl_pct:+.2f}%`)
- Meilleur trade : **{mem.best_trade_pct:+.2f}%**
- Pire trade : **{mem.worst_trade_pct:+.2f}%**
- Série en cours : **{"+" if mem.current_streak >= 0 else ""}{mem.current_streak}**
"""
        self.obsidian.write_note("config", f"{mem.agent_name}_memory", frontmatter, content)

    def get_memory(self, agent_name: str) -> AgentMemory:
        """Retourne la mémoire en cache ou la charge depuis le vault."""
        if agent_name not in self._memories:
            return self.load_memory(agent_name)
        return self._memories[agent_name]

    # ── Enregistrement d'un résultat de trade ────────────────────────────────

    def record_outcome(self, outcome: TradeOutcome) -> None:
        """
        Point d'entrée principal.
        1. Stocke le résultat
        2. Met à jour les mémoires des agents concernés
        3. Lance l'analyse contrefactuelle si trade perdant
        4. Écrit la note de rétrospective
        """
        self._outcomes.append(outcome)
        logger.info(
            "[Learning] Trade %s : %s %+.2f%% (%s)",
            outcome.order_id, outcome.asset,
            outcome.pnl_pct,
            "✅ WIN" if outcome.is_win else "❌ LOSS",
        )

        # Mise à jour de tous les agents qui ont participé
        for agent_name in ["ScanAgent", "ResearchAgent", "PredictAgent", "RiskAgent"]:
            self._update_memory(agent_name, outcome)

        # Analyse contrefactuelle pour les trades perdants (si données OHLCV dispo)
        if not outcome.is_win:
            cf = self.run_counterfactual(outcome)
            if cf:
                self._apply_counterfactual_to_regime(cf, outcome)
                self._write_learning_note(outcome, cf)
        else:
            self._write_learning_note(outcome, None)

    def _update_memory(self, agent_name: str, outcome: TradeOutcome) -> None:
        """Met à jour la mémoire d'un agent avec le résultat du trade."""
        mem = self.get_memory(agent_name)

        # ── Stats globales ──
        mem.total_trades  += 1
        mem.total_pnl_usd += outcome.pnl_usd
        mem.total_pnl_pct += outcome.pnl_pct
        if outcome.is_win:
            mem.total_wins    += 1
            mem.current_streak = max(mem.current_streak + 1, 1)
        else:
            mem.current_streak = min(mem.current_streak - 1, -1)

        mem.best_trade_pct  = max(mem.best_trade_pct,  outcome.pnl_pct)
        mem.worst_trade_pct = min(mem.worst_trade_pct, outcome.pnl_pct)

        # ── Stats par asset ──
        asset_key = outcome.asset
        ast = mem.asset_stats.setdefault(asset_key, {
            "total": 0, "wins": 0, "pnl_pct": 0.0,
        })
        ast["total"]  += 1
        ast["wins"]   += int(outcome.is_win)
        ast["pnl_pct"] = ast["pnl_pct"] * (1 - LEARNING_RATE) + outcome.pnl_pct * LEARNING_RATE

        # ── Mise à jour des poids indicateurs (TechnicalAgent uniquement) ──
        if agent_name == "ScanAgent" and outcome.tech_signal:
            self._update_indicator_weights(mem, outcome)

        # ── Adaptation des paramètres ──
        if mem.total_trades >= MIN_TRADES:
            self._adapt_params(mem, outcome)

        # ── Sauvegarde ──
        self.save_memory(mem)

    def _update_indicator_weights(self, mem: AgentMemory, outcome: TradeOutcome) -> None:
        """
        Ajuste le poids de chaque indicateur selon le résultat du trade.
        Un indicateur qui "avait raison" voit son poids augmenter.
        """
        tech = outcome.tech_signal
        alpha = mem.adaptive_params.get("learning_rate", LEARNING_RATE)

        indicators = {
            "rsi":    self._rsi_was_correct(tech.get("rsi"), outcome),
            "macd":   self._macd_was_correct(tech.get("macd_hist"), outcome),
            "bb":     self._bb_was_correct(tech.get("bb_position"), outcome),
            "volume": outcome.is_win,  # volume élevé = signal fiable si trade gagnant
        }

        for ind_name, was_correct in indicators.items():
            key = f"{ind_name}:{tech.get('timeframe','?')}:{outcome.asset}"
            current_weight = mem.indicator_weights.get(key, 1.0)

            if was_correct:
                new_weight = current_weight + alpha * (WEIGHT_MAX - current_weight)
            else:
                new_weight = current_weight - alpha * (current_weight - WEIGHT_MIN)

            mem.indicator_weights[key] = round(
                max(WEIGHT_MIN, min(WEIGHT_MAX, new_weight)), 4
            )

            # Stats détaillées
            stats_key = f"{ind_name}:{outcome.asset}"
            stats = mem.indicator_stats.setdefault(stats_key, {
                "total": 0, "wins": 0, "avg_pnl": 0.0,
            })
            stats["total"] += 1
            stats["wins"]  += int(was_correct)
            stats["avg_pnl"] = stats["avg_pnl"] * (1 - alpha) + outcome.pnl_pct * alpha

    def _adapt_params(self, mem: AgentMemory, outcome: TradeOutcome) -> None:
        """
        Adapte les paramètres clés selon la performance récente.
        - Paramètres globaux ET régime-spécifiques
        - Si le SL est souvent touché avant le TP, élargir le SL
        - Levier ajusté selon le Sharpe récent
        """
        alpha = mem.adaptive_params.get("learning_rate", LEARNING_RATE)
        regime_key = outcome.regime.value if hasattr(outcome.regime, "value") else str(outcome.regime)

        # ── Adaptation globale ──
        if outcome.exit_reason and "stop" in str(outcome.exit_reason).lower():
            current_mult = mem.adaptive_params.get("sl_atr_multiplier", 1.5)
            mem.adaptive_params["sl_atr_multiplier"] = round(
                min(current_mult + alpha * 0.2, 3.0), 3
            )
        if outcome.exit_reason and "take" in str(outcome.exit_reason).lower() and outcome.is_win:
            current_rr = mem.adaptive_params.get("tp_rr_ratio", 2.5)
            mem.adaptive_params["tp_rr_ratio"] = round(
                min(current_rr + alpha * 0.1, 5.0), 3
            )

        # Ajuster la confidence floor selon le win rate
        win_rate = mem.win_rate
        if win_rate < 0.40 and mem.total_trades >= 20:
            mem.adaptive_params["confidence_floor"] = round(
                min(mem.adaptive_params.get("confidence_floor", 55.0) + 2.0, 80.0), 1
            )
        elif win_rate > 0.60 and mem.total_trades >= 20:
            mem.adaptive_params["confidence_floor"] = round(
                max(mem.adaptive_params.get("confidence_floor", 55.0) - 1.0, 45.0), 1
            )

        # ── Adaptation régime-spécifique ──
        rp = mem.regime_params.setdefault(regime_key, {
            "sl_atr_multiplier": 2.0, "tp_rr_ratio": 3.0,
            "confidence_floor": 55.0, "leverage": 1.0,
        })
        if outcome.exit_reason and "stop" in str(outcome.exit_reason).lower():
            rp["sl_atr_multiplier"] = round(
                min(rp.get("sl_atr_multiplier", 2.0) + alpha * 0.3, 3.5), 3
            )
        if outcome.exit_reason and "take" in str(outcome.exit_reason).lower() and outcome.is_win:
            rp["tp_rr_ratio"] = round(
                min(rp.get("tp_rr_ratio", 3.0) + alpha * 0.15, 5.0), 3
            )

        # Confidence floor par régime
        regime_trades = mem.asset_stats  # on utilise les stats globales comme proxy
        if not outcome.is_win:
            rp["confidence_floor"] = round(
                min(rp.get("confidence_floor", 55.0) + 1.0, 80.0), 1
            )
        elif outcome.pnl_pct > 1.0:
            rp["confidence_floor"] = round(
                max(rp.get("confidence_floor", 55.0) - 0.5, 40.0), 1
            )

        # ── Levier adaptatif (appris en paper) ──
        # Augmenter doucement si le Sharpe est bon, réduire sinon
        sharpe = mem.sharpe_approx
        current_lev = mem.adaptive_params.get("leverage", 1.0)
        if sharpe > 1.5 and mem.total_trades >= 30:
            mem.adaptive_params["leverage"] = round(min(current_lev + alpha * 0.1, 3.0), 2)
            rp["leverage"] = round(min(rp.get("leverage", 1.0) + alpha * 0.15, 3.0), 2)
        elif sharpe < 0.5 and mem.total_trades >= 20:
            mem.adaptive_params["leverage"] = round(max(current_lev - alpha * 0.2, 0.5), 2)
            rp["leverage"] = round(max(rp.get("leverage", 1.0) - alpha * 0.25, 0.5), 2)

    def _apply_counterfactual_to_regime(self, cf, outcome: TradeOutcome) -> None:
        """
        Applique les leçons contrefactuelles au régime spécifique du trade.
        Si la simulation montre qu'un SL/TP différent aurait été profitable,
        on déplace les paramètres du régime vers cette configuration optimale.
        """
        regime_key = outcome.regime.value if hasattr(outcome.regime, "value") else str(outcome.regime)
        alpha = LEARNING_RATE * 0.5  # plus doux que l'adaptation directe

        for agent_name in ["RiskAgent", "PredictAgent"]:
            mem = self.get_memory(agent_name)
            rp = mem.regime_params.setdefault(regime_key, {
                "sl_atr_multiplier": 2.0, "tp_rr_ratio": 3.0,
                "confidence_floor": 55.0, "leverage": 1.0,
            })

            if cf.improvement_pct > 0.5:  # seulement si amélioration significative
                # EMA vers les paramètres optimaux trouvés
                rp["sl_atr_multiplier"] = round(
                    rp["sl_atr_multiplier"] * (1 - alpha) + cf.best_sl_mult * alpha, 3
                )
                rp["tp_rr_ratio"] = round(
                    rp["tp_rr_ratio"] * (1 - alpha) + cf.best_tp_ratio * alpha, 3
                )
                logger.info(
                    "[Learning] Contrefactuel %s régime=%s → SL:%.2f TP:%.2f (amélioration: +%.1f%%)",
                    outcome.asset, regime_key,
                    rp["sl_atr_multiplier"], rp["tp_rr_ratio"], cf.improvement_pct,
                )

            self.save_memory(mem)

    # ── Analyse contrefactuelle ───────────────────────────────────────────────

    def run_counterfactual(
        self,
        outcome: TradeOutcome,
        ohlcv_data: Optional[np.ndarray] = None,
    ) -> Optional[CounterfactualResult]:
        """
        Pour un trade perdant : cherche quelle combinaison SL/TP aurait été profitable.

        ohlcv_data : array (N, 5) = [timestamp, open, high, low, close]
                     Si None, utilise la simulation basée sur les prix SL/TP connus.
        """
        if outcome.is_win:
            return None

        entry  = outcome.entry_price
        sl     = outcome.stop_loss
        tp     = outcome.take_profit
        is_buy = (outcome.side.value == "buy")

        # Distance ATR approx. = distance SL actuel / 1.5 (notre default)
        atr_approx = abs(entry - sl) / 1.5

        best_pnl   = outcome.pnl_pct
        best_sl    = 1.5
        best_tp    = 2.5
        best_exit  = outcome.exit_reason

        if ohlcv_data is not None and len(ohlcv_data) > 0:
            # Simulation réelle sur les données historiques
            for sl_mult in SL_MULTIPLIERS:
                for tp_ratio in TP_RATIOS:
                    sim_sl = entry - sl_mult * atr_approx if is_buy else entry + sl_mult * atr_approx
                    sim_tp = entry + sl_mult * atr_approx * tp_ratio if is_buy else entry - sl_mult * atr_approx * tp_ratio

                    pnl, exit_reason = self._simulate_trade(
                        ohlcv_data, entry, sim_sl, sim_tp, is_buy
                    )
                    if pnl > best_pnl:
                        best_pnl  = pnl
                        best_sl   = sl_mult
                        best_tp   = tp_ratio
                        best_exit = exit_reason
        else:
            # Simulation simplifiée sans données OHLCV
            # Heuristique : si le max_favorable était positif, un SL plus large aurait pu sauver le trade
            if outcome.max_favorable > 0:
                for sl_mult in SL_MULTIPLIERS:
                    if sl_mult > 1.5:  # si on avait un SL plus large
                        for tp_ratio in TP_RATIOS:
                            # Estimation grossière
                            sl_dist = sl_mult * atr_approx / entry * 100
                            tp_dist = sl_dist * tp_ratio
                            if outcome.max_favorable >= tp_dist * 0.7:
                                est_pnl = tp_dist * 0.8
                                if est_pnl > best_pnl:
                                    best_pnl = est_pnl
                                    best_sl  = sl_mult
                                    best_tp  = tp_ratio

        # Construire le résultat
        improvement = best_pnl - outcome.pnl_pct
        lesson      = self._generate_lesson(outcome, best_sl, best_tp, improvement)

        cf = CounterfactualResult(
            trade_outcome   = outcome,
            actual_pnl_pct  = outcome.pnl_pct,
            actual_exit     = str(outcome.exit_reason),
            best_sl_mult    = best_sl,
            best_tp_ratio   = best_tp,
            best_pnl_pct    = best_pnl,
            best_exit       = str(best_exit),
            improvement_pct = improvement,
            lesson          = lesson,
            param_updates   = {
                "sl_atr_multiplier": best_sl,
                "tp_rr_ratio":       best_tp,
            },
        )
        return cf

    @staticmethod
    def _simulate_trade(
        ohlcv: np.ndarray,
        entry: float,
        sl: float,
        tp: float,
        is_buy: bool,
    ) -> tuple[float, str]:
        """Rejoue un trade sur des données OHLCV historiques."""
        for bar in ohlcv:
            _, o, h, l, c = float(bar[0]), float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
            if is_buy:
                if l <= sl:
                    pnl = (sl - entry) / entry * 100
                    return pnl, "stop_loss"
                if h >= tp:
                    pnl = (tp - entry) / entry * 100
                    return pnl, "take_profit"
            else:
                if h >= sl:
                    pnl = (entry - sl) / entry * 100
                    return pnl, "stop_loss"
                if l <= tp:
                    pnl = (entry - tp) / entry * 100
                    return pnl, "take_profit"
        # Trade toujours ouvert à la fin
        last_close = float(ohlcv[-1][4])
        direction  = 1 if is_buy else -1
        return direction * (last_close - entry) / entry * 100, "timeout"

    @staticmethod
    def _generate_lesson(
        outcome: TradeOutcome,
        best_sl: float,
        best_tp: float,
        improvement: float,
    ) -> str:
        current_sl_mult = 1.5  # valeur par défaut
        lessons = []

        if best_sl > current_sl_mult + 0.3:
            lessons.append(
                f"Stop-Loss trop serré ({current_sl_mult}×ATR). "
                f"Un SL à {best_sl}×ATR aurait évité le stop prématuré."
            )
        if best_tp > 3.0:
            lessons.append(
                f"Take-Profit conservateur. Un ratio 1:{best_tp} aurait capturé +{improvement:.1f}%."
            )
        if improvement > 2.0:
            lessons.append(
                f"Ce trade était potentiellement gagnant avec de meilleurs paramètres "
                f"(amélioration possible : +{improvement:.1f}%)."
            )
        if not lessons:
            lessons.append(
                "Signal de marché faible. Augmenter la confiance minimale requise "
                f"pour {outcome.asset}."
            )

        return " ".join(lessons)

    # ── Vault Obsidian ────────────────────────────────────────────────────────

    def _write_learning_note(
        self,
        outcome: TradeOutcome,
        cf: Optional[CounterfactualResult],
    ) -> None:
        """Écrit la rétrospective ML dans vault/apprentissage/."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        filename = f"learning_{outcome.asset.replace('/', '-')}_{date_str}"

        result_icon = "✅ WIN" if outcome.is_win else "❌ LOSS"
        frontmatter = {
            "date":      datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "agent":     "LearningEngine",
            "asset":     outcome.asset,
            "signal":    outcome.side.value,
            "confiance": outcome.confidence,
            "tags":      ["apprentissage", "ml", outcome.asset, "retrospective"],
            "pnl_pct":   round(outcome.pnl_pct, 3),
            "is_win":    outcome.is_win,
            "exit_reason": str(outcome.exit_reason),
        }

        cf_section = cf.to_markdown() if cf else "> Aucune analyse contrefactuelle (trade gagnant)."

        content = f"""## Rétrospective ML — {outcome.asset} | {result_icon}

### Résultat du Trade
| Champ | Valeur |
|---|---|
| Asset | `{outcome.asset}` |
| Direction | {outcome.side.value.upper()} |
| Entrée | `{outcome.entry_price}` |
| Sortie | `{outcome.exit_price}` |
| P&L | `{outcome.pnl_pct:+.3f}%` (`${outcome.pnl_usd:+.2f}`) |
| Durée | `{outcome.duration_hours:.1f}h` |
| Raison sortie | `{outcome.exit_reason}` |
| Max favorable | `{outcome.max_favorable:+.2f}%` |
| Max adverse | `{outcome.max_adverse:+.2f}%` |

### Signaux au Moment de l'Entrée
**Confiance combinée : {outcome.confidence}/100**

{cf_section}

### Mise à Jour des Paramètres
```json
{json.dumps(cf.param_updates if cf else {}, indent=2)}
```

### Liens
{self.obsidian.wikilink('decisions', self.obsidian.timestamp_filename('predict', outcome.asset.replace('/', '-')))}
"""
        # Créer le dossier apprentissage si absent
        (self.obsidian.vault_path / "apprentissage").mkdir(exist_ok=True)
        self.obsidian.write_note("apprentissage", filename, frontmatter, content)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_all_json_blocks(content: str) -> list[dict]:
        """
        Extrait TOUS les blocs ```json ... ``` du contenu markdown, dans l'ordre.
        Retourne une liste de dicts correspondant à chaque bloc trouvé.
        Cela évite le bug où un regex générique retourne toujours le 1er bloc.
        """
        import re
        blocks = []
        for match in re.finditer(r'```json\s*\n(.*?)\n```', content, re.DOTALL):
            try:
                data = json.loads(match.group(1))
                blocks.append(data)
            except json.JSONDecodeError:
                blocks.append({})
        return blocks

    @staticmethod
    def _extract_json_block(content: str, key: str) -> Optional[dict]:
        """Legacy: extrait un bloc JSON par titre de section (fallback)."""
        import re
        # Chercher par titre de section français
        section_map = {
            "adaptive_params": "Param.tres Adaptatifs",
            "indicator_weights": "Poids des Indicateurs",
            "indicator_stats": "Statistiques par Indicateur",
            "asset_stats": "Statistiques par Asset",
        }
        title = section_map.get(key, key.replace('_', ' ').title())
        pattern = rf"### {re.escape(title)}\s*\n```json\s*\n(.*?)\n```"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _rsi_was_correct(rsi: Optional[float], outcome: TradeOutcome) -> bool:
        if rsi is None:
            return outcome.is_win
        if outcome.side.value == "buy":
            return (rsi < 50 and outcome.is_win) or (rsi >= 50 and not outcome.is_win)
        else:
            return (rsi > 50 and outcome.is_win) or (rsi <= 50 and not outcome.is_win)

    @staticmethod
    def _macd_was_correct(macd_hist: Optional[float], outcome: TradeOutcome) -> bool:
        if macd_hist is None:
            return outcome.is_win
        if outcome.side.value == "buy":
            return (macd_hist > 0) == outcome.is_win
        else:
            return (macd_hist < 0) == outcome.is_win

    @staticmethod
    def _bb_was_correct(bb_pos: Optional[float], outcome: TradeOutcome) -> bool:
        if bb_pos is None:
            return outcome.is_win
        if outcome.side.value == "buy":
            return (bb_pos < 0.3) == outcome.is_win
        else:
            return (bb_pos > 0.7) == outcome.is_win