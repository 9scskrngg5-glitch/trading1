---
date: 2026-03-31 05:05 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: neutral
market_type: ranging
phase: distribution
volatility: medium
structure: HH_HL
bos: false
bias: short_bias
coherence: 25
realized_vol: 9.59
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 31/03/2026 05:05 UTC | Prix : `83.340000` | ATR : `0.871429` (1.05%)

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
| Direction | **NEUTRAL** | slope 20p = -0.95% |
| Type | **RANGING** | volatilité medium |
| Phase (Wyckoff) | **DISTRIBUTION** | EMA20 = 83.3258 |
| Volatilité ATR% | `1.05%` | 🟡 Moyenne |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.6%` — 🟢 Faible (<30%) |
| Percentile session | `66e percentile` |
| POC (Point of Control) | `83.3565` |
| Value Area High (VAH) | `84.52` |
| Value Area Low (VAL) | `82.372` |
| HVN (High Vol. Nodes) | `82.4615` | `82.6405` | `83.3565` |
| LVN (Low Vol. Nodes) | `81.5665` | `82.2825` | `82.9985` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `84.8800` | `84.9900` | `83.6800` | `84.6200` |
|---|---|
| **Swing Lows récents** | `81.1200` | `78.9600` | `81.9600` | `82.1400` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `84.830000` | `75/100` | `3` touches |
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
| 🟢 OB Bullish @80.5550 | `78.960000` | `82.150000` | `80.555000` |
| 🔴 OB Bearish @84.3200 | `83.880000` | `84.760000` | `84.320000` |
| 🔴 OB Bearish @83.6100 | `82.600000` | `84.620000` | `83.610000` |

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
> NEUTRAL — score `-1.8` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (25/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `18/100` |
| Fondamental | `neutral` | `33/100` |
| Régime | `neutral` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Structure bullish

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
**Entrée** : LONG @ 81.930000 | SHORT @ 84.830000
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
| Direction crowd | `NEUTRAL` |
| Votes LONG / SHORT / HOLD | `32%` / `34%` / `34%` |
| Probabilité haussière | `51%` |
| Probabilité baissière | `32%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (32%L / 34%S / 34%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_SOL_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
