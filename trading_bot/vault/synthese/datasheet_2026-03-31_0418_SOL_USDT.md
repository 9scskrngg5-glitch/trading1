---
date: 2026-03-31 04:18 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: neutral
market_type: trending
phase: distribution
volatility: medium
structure: HH_HL
bos: false
bias: short_bias
coherence: 50
realized_vol: 9.58
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 31/03/2026 04:18 UTC | Prix : `83.600000` | ATR : `0.897143` (1.07%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR SOL/USDT: N/A

| Paramètre Mémorisé | Valeur |
|---|---|
| Mode CompoundAgent | `STARTUP` |
| Risque/Trade actuel | `2.0%` |
| Confiance min. (RiskAgent) | `55.0` |
| Ajustement confiance mémoire | `+0 pts` |

---

### 1. RÉGIME DE MARCHÉ
| Dimension | Valeur | Détail |
|---|---|---|
| Direction | **NEUTRAL** | slope 20p = -1.09% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **DISTRIBUTION** | EMA20 = 83.3250 |
| Volatilité ATR% | `1.07%` | 🟡 Moyenne |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.6%` — 🟢 Faible (<30%) |
| Percentile session | `66e percentile` |
| POC (Point of Control) | `84.4305` |
| Value Area High (VAH) | `84.52` |
| Value Area Low (VAL) | `82.372` |
| HVN (High Vol. Nodes) | `82.4615` | `82.6405` | `83.3565` |
| LVN (Low Vol. Nodes) | `81.5665` | `82.2825` | `82.9985` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `82.2300` | `84.8800` | `84.9900` | `83.6800` |
|---|---|
| **Swing Lows récents** | `81.1200` | `78.9600` | `81.9600` | `82.1400` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `84.935000` | `50/100` | `2` touches |
| R2 | `83.680000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `81.930000` | `75/100` | `3` touches |
| S2 | `81.120000` | `25/100` | `1` touches |
| S3 | `78.960000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `84.935` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `82.05` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @82.2450 | `81.690000` | `82.800000` | `82.245000` |
| 🟢 OB Bullish @80.5550 | `78.960000` | `82.150000` | `80.555000` |
| 🔴 OB Bearish @84.3200 | `83.880000` | `84.760000` | `84.320000` |

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
> POSITIVE — score `+34.5` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `17/100` |
| Fondamental | `bullish` | `29/100` |
| Régime | `neutral` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Structure bullish
- ⚠️  Technique bearish ≠ Fondamental bullish

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
**Entrée** : LONG @ 81.930000 | SHORT @ 84.935000
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `ATTENTE`
**Entrée** : Pas de setup intraday clair
**SL** : `—` | **TP** : `—` | **R:R** : `1:0.0`
**Timeframe** : `1h–4h`
**Condition** : _Attendre confirmation de direction sur 1h_
**Qualité** : 🔴 Non favorable — marché indécis

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
| Direction crowd | `BULLISH` |
| Votes LONG / SHORT / HOLD | `46%` / `31%` / `23%` |
| Probabilité haussière | `52%` |
| Probabilité baissière | `36%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+25` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _✅ Alignement foule-technique — 46% LONG avec support structurel. Consensus comportemental renforce l'analyse primaire._

---

### Liens
[[decisions/convergence_SOL_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
