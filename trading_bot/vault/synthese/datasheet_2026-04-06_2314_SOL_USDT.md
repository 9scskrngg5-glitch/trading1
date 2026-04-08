---
date: 2026-04-06 23:14 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: bearish
market_type: trending
phase: markdown
volatility: medium
structure: HH_HL
bos: true
bias: short_bias
coherence: 50
realized_vol: 9.68
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 06/04/2026 23:14 UTC | Prix : `80.170000` | ATR : `0.669286` (0.83%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 1.5% | Confiance min: 55 | WR SOL/USDT: N/A | HistTech: 3n | HistFund: 1n | Leçons: 1n

| Paramètre Mémorisé | Valeur |
|---|---|
| Mode CompoundAgent | `STARTUP` |
| Risque/Trade actuel | `1.5%` |
| Confiance min. (RiskAgent) | `55.0` |
| Ajustement confiance mémoire | `+0 pts` |

---

### 1. RÉGIME DE MARCHÉ
| Dimension | Valeur | Détail |
|---|---|---|
| Direction | **BEARISH** | slope 20p = -2.36% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKDOWN** | EMA20 = 81.6262 |
| Volatilité ATR% | `0.83%` | 🟡 Moyenne |
| Force de tendance | `11/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.7%` — 🟢 Faible (<30%) |
| Percentile session | `86e percentile` |
| POC (Point of Control) | `82.404` |
| Value Area High (VAH) | `82.68` |
| Value Area Low (VAL) | `80.472` |
| HVN (High Vol. Nodes) | `79.6440` | `80.9320` | `81.8520` |
| LVN (Low Vol. Nodes) | `79.0920` | `79.4600` | `82.5880` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**
> 🔔 **BREAK OF STRUCTURE** détecté à `81.19`
> 🔄 **CHoCH** — potentiel retournement

| Swing Highs récents | `80.3300` | `82.9700` | `83.2000` | `82.8100` |
|---|---|
| **Swing Lows récents** | `78.5200` | `79.1000` | `80.9700` | `81.1900` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `82.993333` | `75/100` | `3` touches |
| R2 | `80.285000` | `50/100` | `2` touches |
| R3 | `81.610000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `79.360000` | `75/100` | `3` touches |
| S2 | `78.520000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `80.285` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `79.49` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @79.3750 | `78.800000` | `79.950000` | `79.375000` |
| 🟢 OB Bullish @79.8500 | `79.510000` | `80.190000` | `79.850000` |
| 🔴 OB Bearish @82.2300 | `81.660000` | `82.800000` | `82.230000` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `0/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ✅ Non |

- ✅ Aucun signal de manipulation détecté

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> POSITIVE — score `+32.1` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `40/100` |
| Fondamental | `bullish` | `19/100` |
| Régime | `bearish` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Structure bullish
- ⚠️  Technique bearish ≠ Fondamental bullish
- 🔔 Break of Structure à 81.19 — recalibrage recommandé
- 🔔 CHoCH — potentiel retournement de tendance

#### Détection de Biais
> ⚠️  BIAIS SHORT DÉTECTÉ (100% des signaux) — Rechercher activement des setups LONG. Réduire la taille des positions SHORT de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `0` | `0%` |
| SHORT | `30` | `100%` |
| Sévérité | `critical` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 79.360000 | SHORT @ 82.993333
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `SHORT`
**Entrée** : Rebond vers 80.504643 ou OB bearish
**SL** : `80.839286` | **TP** : `78.831429` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture sous l'EMA20_
**Qualité** : 🟡 Modéré

---

#### 🌊 Swing (1d+)
**Direction** : `ATTENTE / OBSERVATION`
**Entrée** : Structure de marché non confirmée pour un swing
**SL** : `—` | **TP** : `—` | **R:R** : `1:0.0`
**Timeframe** : `1d+`
**Condition** : _Attendre un BOS / CHoCH propre avant d'entrer_
**Qualité** : 🟡 Prudence — structure ambiguë

---

### 9. MIROFISH — SOURCE SECONDAIRE
> ⚠️ **ATTENTION** : Section secondaire de confirmation comportementale.
> Les données Mirofish ne remplacent JAMAIS l'analyse des sections 1-8.
> Priorité 4/4 dans la hiérarchie des sources.

> ⚠️ Source secondaire — ne remplace pas l'analyse primaire

| Métrique Mirofish | Valeur |
|---|---|
| Direction crowd | `NEUTRAL` |
| Votes LONG / SHORT / HOLD | `30%` / `40%` / `30%` |
| Probabilité haussière | `46%` |
| Probabilité baissière | `39%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+25` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _✅ Alignement foule-technique — 40% SHORT avec support structurel. Consensus comportemental renforce l'analyse primaire._

---

### Liens
[[decisions/2026-04-06_predict_SOL-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
