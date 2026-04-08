---
date: 2026-03-31 10:16 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: bearish
market_type: trending
phase: markdown
volatility: medium
structure: HH_HL
bos: false
bias: balanced
coherence: 50
realized_vol: 10.37
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 31/03/2026 10:16 UTC | Prix : `2018.370000` | ATR : `21.319286` (1.06%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR ETH/USDT: N/A | HistTech: 2n | HistFund: 1n | Leçons: 2n

| Paramètre Mémorisé | Valeur |
|---|---|
| Mode CompoundAgent | `STARTUP` |
| Risque/Trade actuel | `2.0%` |
| Confiance min. (RiskAgent) | `55.0` |
| Ajustement confiance mémoire | `-5 pts` |

---

### 1. RÉGIME DE MARCHÉ
| Dimension | Valeur | Détail |
|---|---|---|
| Direction | **BEARISH** | slope 20p = -2.57% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKDOWN** | EMA20 = 2047.4251 |
| Volatilité ATR% | `1.06%` | 🟡 Moyenne |
| Force de tendance | `12/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `10.4%` — 🟢 Faible (<30%) |
| Percentile session | `66e percentile` |
| POC (Point of Control) | `2072.02625` |
| Value Area High (VAH) | `2074.54` |
| Value Area Low (VAL) | `2004.155` |
| HVN (High Vol. Nodes) | `1976.5038` | `1996.6137` | `2061.9713` |
| LVN (Low Vol. Nodes) | `1991.5863` | `2026.7787` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `2009.4800` | `2085.0000` | `2049.1000` | `2092.3400` |
|---|---|
| **Swing Lows récents** | `1983.5600` | `1938.8200` | `2013.3300` | `2013.9200` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `2088.670000` | `50/100` | `2` touches |
| R2 | `2019.650000` | `25/100` | `1` touches |
| R3 | `2049.100000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `2013.625000` | `50/100` | `2` touches |
| S2 | `1983.560000` | `25/100` | `1` touches |
| S3 | `1938.820000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `2013.625` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @1972.6650 | `1938.820000` | `2006.510000` | `1972.665000` |
| 🔴 OB Bearish @2070.9150 | `2061.910000` | `2079.920000` | `2070.915000` |
| 🟢 OB Bullish @2023.4950 | `2013.920000` | `2033.070000` | `2023.495000` |
| 🔴 OB Bearish @2061.8850 | `2054.770000` | `2069.000000` | `2061.885000` |

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
> NEGATIVE — score `-21.4` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `neutral` | `27/100` |
| Fondamental | `bearish` | `18/100` |
| Régime | `bearish` | — |
| Structure | `bullish` | — |

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
**Entrée** : 2018.370000 (niveau courant)
**SL** : `2026.897714` | **TP** : `2001.314571` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Entry sur rebond vers résistance la plus proche_
**Qualité** : 🟢 Favorable

#### ⚡ Scalping Contrarian
**Direction** : `LONG`
**Entrée** : 2013.625 (support S1)
**SL** : `2005.097286` | **TP** : `2030.680429` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Rebond sur support avec volume haussier_
**Qualité** : 🟡 Contre-tendance — prudence
**Note mémoire** : _Setup complémentaire pour équilibrer le biais_

---

#### 📊 Intraday (1h–4h)
**Direction** : `SHORT`
**Entrée** : Rebond vers 2029.029643 ou OB bearish
**SL** : `2039.689286` | **TP** : `1975.731429` | **R:R** : `1:2.0`
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
| Votes LONG / SHORT / HOLD | `26%` / `33%` / `42%` |
| Probabilité haussière | `48%` |
| Probabilité baissière | `31%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+25` (-50 à +50) |
| Risque manipulation crowd | `5%` |

**Note comportementale** : _✅ Alignement foule-technique — 33% SHORT avec support structurel. Consensus comportemental renforce l'analyse primaire._

---

### Liens
[[decisions/convergence_ETH_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
