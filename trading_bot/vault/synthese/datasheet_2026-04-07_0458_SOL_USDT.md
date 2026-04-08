---
date: 2026-04-07 04:58 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: bearish
market_type: trending
phase: markdown
volatility: low
structure: HH_HL
bos: false
bias: balanced
coherence: 0
realized_vol: 9.38
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 07/04/2026 04:58 UTC | Prix : `79.940000` | ATR : `0.612857` (0.77%)

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
| Direction | **BEARISH** | slope 20p = -3.07% |
| Type | **TRENDING** | volatilité low |
| Phase (Wyckoff) | **MARKDOWN** | EMA20 = 80.8116 |
| Volatilité ATR% | `0.77%` | 🟢 Faible |
| Force de tendance | `30/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.4%` — 🟢 Faible (<30%) |
| Percentile session | `66e percentile` |
| POC (Point of Control) | `82.404` |
| Value Area High (VAH) | `82.68` |
| Value Area Low (VAL) | `79.92` |
| HVN (High Vol. Nodes) | `79.6440` | `79.8280` | `81.8520` |
| LVN (Low Vol. Nodes) | `80.3800` | `80.7480` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `80.3300` | `82.9700` | `83.2000` | `82.8100` |
|---|---|
| **Swing Lows récents** | `79.1000` | `80.9700` | `81.1900` | `79.3800` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `82.993333` | `75/100` | `3` touches |
| R2 | `80.285000` | `50/100` | `2` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `79.296667` | `75/100` | `3` touches |
| S2 | `78.520000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `80.285` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `79.395` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🔴 OB Bearish @82.2300 | `81.660000` | `82.800000` | `82.230000` |
| 🔴 OB Bearish @81.9800 | `81.810000` | `82.150000` | `81.980000` |
| 🟢 OB Bullish @79.7600 | `79.380000` | `80.140000` | `79.760000` |

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
> NEUTRAL — score `+0.0` sur 0 signaux fondamentaux

#### Cohérence Inter-Agents
> Pas de signaux disponibles

| Source | Direction | Confiance |
|---|---|---|
| Technique | `neutral` | `0/100` |
| Fondamental | `neutral` | `0/100` |
| Régime | `neutral` | — |
| Structure | `neutral` | — |

✅ Pas de divergence majeure

#### Détection de Biais
> Données insuffisantes — biais non calculable

| Direction | Signaux | % |
|---|---|---|
| LONG | `0` | `50%` |
| SHORT | `0` | `50%` |
| Sévérité | `none` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `SHORT`
**Entrée** : 79.940000 (niveau courant)
**SL** : `80.185143` | **TP** : `79.449714` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Entry sur rebond vers résistance la plus proche_
**Qualité** : 🟢 Favorable

#### ⚡ Scalping Contrarian
**Direction** : `LONG`
**Entrée** : 79.296667 (support S1)
**SL** : `79.051524` | **TP** : `79.786953` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Rebond sur support avec volume haussier_
**Qualité** : 🟡 Contre-tendance — prudence
**Note mémoire** : _Setup complémentaire pour équilibrer le biais_

---

#### 📊 Intraday (1h–4h)
**Direction** : `SHORT`
**Entrée** : Rebond vers 80.246429 ou OB bearish
**SL** : `80.552857` | **TP** : `78.714286` | **R:R** : `1:2.0`
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
| Votes LONG / SHORT / HOLD | `36%` / `23%` / `41%` |
| Probabilité haussière | `59%` |
| Probabilité baissière | `20%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+25` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _✅ Alignement foule-technique — 36% LONG avec support structurel. Consensus comportemental renforce l'analyse primaire._

---

### Liens
[[decisions/2026-04-07_predict_SOL-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
