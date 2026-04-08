---
date: 2026-03-30 20:13 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: neutral
market_type: volatile
phase: transition
volatility: medium
structure: mixed
bos: false
bias: short_bias
coherence: 25
realized_vol: !!python/object/apply:numpy._core.multiarray.scalar
- !!python/object/apply:numpy.dtype
  args:
  - f8
  - false
  - true
  state: !!python/tuple
  - 3
  - <
  - null
  - null
  - null
  - -1
  - -1
  - 0
- !!binary |
  9ihcj8J1IkA=
manip_risk: 20
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 30/03/2026 20:13 UTC | Prix : `82.390000` | ATR : `0.804286` (0.98%)

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
| Direction | **NEUTRAL** | slope 20p = +0.61% |
| Type | **VOLATILE** | volatilité medium |
| Phase (Wyckoff) | **TRANSITION** | EMA20 = 83.4267 |
| Volatilité ATR% | `0.98%` | 🟡 Moyenne |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.2%` — 🟢 Faible (<30%) |
| Percentile session | `93e percentile` |
| POC (Point of Control) | `83.3565` |
| Value Area High (VAH) | `84.52` |
| Value Area Low (VAL) | `82.372` |
| HVN (High Vol. Nodes) | `81.0295` | `82.4615` | `83.3565` |
| LVN (Low Vol. Nodes) | `81.5665` | `81.7455` | `82.2825` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟡 Structure mixte**



| Swing Highs récents | `82.8400` | `82.2300` | `84.8800` | `84.9900` |
|---|---|
| **Swing Lows récents** | `82.6000` | `81.6900` | `81.1200` | `78.9600` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `84.935000` | `50/100` | `2` touches |
| R2 | `82.840000` | `25/100` | `1` touches |
| R3 | `83.240000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `81.690000` | `25/100` | `1` touches |
| S2 | `81.120000` | `25/100` | `1` touches |
| S3 | `78.960000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `84.935` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `—` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @82.2450 | `81.690000` | `82.800000` | `82.245000` |
| 🔴 OB Bearish @82.9700 | `82.700000` | `83.240000` | `82.970000` |
| 🔴 OB Bearish @82.0800 | `81.720000` | `82.440000` | `82.080000` |
| 🟢 OB Bullish @80.5550 | `78.960000` | `82.150000` | `80.555000` |
| 🔴 OB Bearish @84.3200 | `83.880000` | `84.760000` | `84.320000` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `20/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ⚠️ OUI |

- 🧱 Fake wall potentiel côté BID — OB imbalance +0.47 mais prix baisse

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> POSITIVE — score `+39.0` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (25/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `14/100` |
| Fondamental | `bullish` | `33/100` |
| Régime | `neutral` | — |
| Structure | `neutral` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Fondamental bullish

#### Détection de Biais
> ⚠️  BIAIS SHORT DÉTECTÉ (100% des signaux) — Rechercher activement des setups LONG. Réduire la taille des positions SHORT de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `0` | `0%` |
| SHORT | `22` | `100%` |
| Sévérité | `critical` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 81.690000 | SHORT @ 84.935000
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
| Votes LONG / SHORT / HOLD | `35%` / `41%` / `24%` |
| Probabilité haussière | `47%` |
| Probabilité baissière | `41%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (35%L / 41%S / 24%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_SOL_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_memory]]
