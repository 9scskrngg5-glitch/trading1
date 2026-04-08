---
date: 2026-03-31 09:44 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: bearish
market_type: trending
phase: markdown
volatility: medium
structure: HH_HL
bos: false
bias: long_bias
coherence: 50
realized_vol: 9.87
manip_risk: 20.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 31/03/2026 09:44 UTC | Prix : `82.250000` | ATR : `0.850000` (1.03%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR SOL/USDT: N/A | HistTech: 2n | HistFund: 1n | Leçons: 1n

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
| Direction | **BEARISH** | slope 20p = -2.10% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKDOWN** | EMA20 = 83.2403 |
| Volatilité ATR% | `1.03%` | 🟡 Moyenne |
| Force de tendance | `10/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.9%` — 🟢 Faible (<30%) |
| Percentile session | `66e percentile` |
| POC (Point of Control) | `83.3565` |
| Value Area High (VAH) | `84.52` |
| Value Area Low (VAL) | `82.372` |
| HVN (High Vol. Nodes) | `82.4615` | `82.6405` | `83.3565` |
| LVN (Low Vol. Nodes) | `81.5665` | `82.9985` | `83.5355` |

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
| R2 | `82.840000` | `25/100` | `1` touches |
| R3 | `83.240000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `82.050000` | `50/100` | `2` touches |
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
| 🔴 OB Bearish @82.0800 | `81.720000` | `82.440000` | `82.080000` |
| 🟢 OB Bullish @80.5550 | `78.960000` | `82.150000` | `80.555000` |
| 🔴 OB Bearish @84.3200 | `83.880000` | `84.760000` | `84.320000` |
| 🔴 OB Bearish @83.6100 | `82.600000` | `84.620000` | `83.610000` |
| 🔴 OB Bearish @83.3350 | `82.900000` | `83.770000` | `83.335000` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `20/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ⚠️ OUI |

- 🧱 Fake wall potentiel côté BID — OB imbalance +0.44 mais prix baisse

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> NEGATIVE — score `-26.0` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `neutral` | `28/100` |
| Fondamental | `bearish` | `40/100` |
| Régime | `bearish` | — |
| Structure | `bullish` | — |

✅ Pas de divergence majeure

#### Détection de Biais
> ⚠️  BIAIS LONG DÉTECTÉ (83% des signaux) — Rechercher activement des setups SHORT. Réduire la taille des positions LONG de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `25` | `83%` |
| SHORT | `5` | `17%` |
| Sévérité | `critical` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `SHORT`
**Entrée** : 82.250000 (niveau courant)
**SL** : `82.59` | **TP** : `81.57` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Entry sur rebond vers résistance la plus proche_
**Qualité** : 🟢 Favorable

#### ⚡ Scalping Contrarian
**Direction** : `LONG`
**Entrée** : 82.05 (support S1)
**SL** : `81.71` | **TP** : `82.73` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Rebond sur support avec volume haussier_
**Qualité** : 🟡 Contre-tendance — prudence
**Note mémoire** : _Setup complémentaire pour équilibrer le biais_

---

#### 📊 Intraday (1h–4h)
**Direction** : `SHORT`
**Entrée** : Rebond vers 82.675 ou OB bearish
**SL** : `83.1` | **TP** : `80.55` | **R:R** : `1:2.0`
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
| Votes LONG / SHORT / HOLD | `15%` / `32%` / `54%` |
| Probabilité haussière | `43%` |
| Probabilité baissière | `30%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+25` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _✅ Alignement foule-technique — 32% SHORT avec support structurel. Consensus comportemental renforce l'analyse primaire._

---

### Liens
[[decisions/convergence_SOL_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
