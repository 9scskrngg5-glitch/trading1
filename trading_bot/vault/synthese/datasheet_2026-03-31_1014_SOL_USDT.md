---
date: 2026-03-31 10:14 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: bearish
market_type: volatile
phase: transition
volatility: medium
structure: HH_HL
bos: true
bias: balanced
coherence: 0
realized_vol: 10.95
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 31/03/2026 10:14 UTC | Prix : `80.770000` | ATR : `0.958571` (1.19%)

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
| Direction | **BEARISH** | slope 20p = -4.43% |
| Type | **VOLATILE** | volatilité medium |
| Phase (Wyckoff) | **TRANSITION** | EMA20 = 82.7716 |
| Volatilité ATR% | `1.19%` | 🟡 Moyenne |
| Force de tendance | `44/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `10.9%` — 🟢 Faible (<30%) |
| Percentile session | `73e percentile` |
| POC (Point of Control) | `83.82525` |
| Value Area High (VAH) | `84.52` |
| Value Area Low (VAL) | `82.138` |
| HVN (High Vol. Nodes) | `82.6342` | `83.4283` | `83.8252` |
| LVN (Low Vol. Nodes) | `81.6418` | `83.0312` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**
> 🔔 **BREAK OF STRUCTURE** détecté à `82.14`
> 🔄 **CHoCH** — potentiel retournement

| Swing Highs récents | `84.8800` | `84.9900` | `83.6800` | `84.6200` |
|---|---|
| **Swing Lows récents** | `81.1200` | `78.9600` | `81.9600` | `82.1400` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `84.830000` | `75/100` | `3` touches |
| R2 | `82.230000` | `25/100` | `1` touches |
| R3 | `82.840000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `78.960000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `84.935` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `—` | Stops de vendeurs — cible de stop-hunt |

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
**Entrée** : 80.770000 (niveau courant)
**SL** : `81.153429` | **TP** : `80.003143` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Entry sur rebond vers résistance la plus proche_
**Qualité** : 🟡 Acceptable

#### ⚡ Scalping Contrarian
**Direction** : `LONG`
**Entrée** : 78.96 (support S1)
**SL** : `78.576571` | **TP** : `79.726857` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Rebond sur support avec volume haussier_
**Qualité** : 🟡 Contre-tendance — prudence
**Note mémoire** : _Setup complémentaire pour équilibrer le biais_

---

#### 📊 Intraday (1h–4h)
**Direction** : `SHORT`
**Entrée** : Rebond vers 81.249286 ou OB bearish
**SL** : `81.728571` | **TP** : `78.852857` | **R:R** : `1:2.0`
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
| Votes LONG / SHORT / HOLD | `25%` / `38%` / `37%` |
| Probabilité haussière | `44%` |
| Probabilité baissière | `37%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+25` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _✅ Alignement foule-technique — 38% SHORT avec support structurel. Consensus comportemental renforce l'analyse primaire._

---

### Liens
[[decisions/convergence_SOL_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
