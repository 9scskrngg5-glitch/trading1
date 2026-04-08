---
date: 2026-03-31 16:50 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: bullish
market_type: trending
phase: markup
volatility: medium
structure: HH_HL
bos: false
bias: balanced
coherence: 50
realized_vol: 11.43
manip_risk: 20.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 31/03/2026 16:50 UTC | Prix : `2054.850000` | ATR : `22.956429` (1.12%)

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
| Direction | **BULLISH** | slope 20p = +1.56% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKUP** | EMA20 = 2048.5946 |
| Volatilité ATR% | `1.12%` | 🟡 Moyenne |
| Force de tendance | `7/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `11.4%` — 🟢 Faible (<30%) |
| Percentile session | `73e percentile` |
| POC (Point of Control) | `2072.8355` |
| Value Area High (VAH) | `2075.37` |
| Value Area Low (VAL) | `2019.611` |
| HVN (High Vol. Nodes) | `2042.4215` | `2047.4905` | `2062.6975` |
| LVN (Low Vol. Nodes) | `1991.7315` | `2001.8695` | `2012.0075` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `2009.4800` | `2085.0000` | `2049.1000` | `2092.3400` |
|---|---|
| **Swing Lows récents** | `1938.8200` | `2013.3300` | `2013.9200` | `2012.6400` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `2088.670000` | `50/100` | `2` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `2013.296667` | `75/100` | `3` touches |
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
| 🟢 OB Bullish @2058.5000 | `2053.870000` | `2063.130000` | `2058.500000` |
| 🔴 OB Bearish @2070.9150 | `2061.910000` | `2079.920000` | `2070.915000` |
| 🟢 OB Bullish @2023.4950 | `2013.920000` | `2033.070000` | `2023.495000` |
| 🔴 OB Bearish @2061.8850 | `2054.770000` | `2069.000000` | `2061.885000` |
| 🟢 OB Bullish @2028.5700 | `2012.640000` | `2044.500000` | `2028.570000` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `20/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ⚠️ OUI |

- 🧱 Fake wall potentiel côté ASK — OB imbalance -0.52 mais prix monte

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> NEGATIVE — score `-20.8` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `33/100` |
| Fondamental | `bearish` | `18/100` |
| Régime | `bullish` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Structure bullish
- ⚠️  Régime bullish ≠ Technique bearish

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
**Direction** : `LONG`
**Entrée** : 2054.850000 (niveau courant)
**SL** : `2045.667429` | **TP** : `2073.215143` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Entry sur pull-back vers support le plus proche_
**Qualité** : 🟢 Favorable

#### ⚡ Scalping Contrarian
**Direction** : `SHORT`
**Entrée** : 2088.67 (résistance R1)
**SL** : `2097.852571` | **TP** : `2070.304857` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Rejet sur résistance avec volume baissier_
**Qualité** : 🟡 Contre-tendance — prudence
**Note mémoire** : _Setup complémentaire pour équilibrer le biais_

---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 2043.371786 ou OB bullish
**SL** : `2031.893571` | **TP** : `2100.762857` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture au-dessus de l'EMA20_
**Qualité** : 🟢 Favorable

---

#### 🌊 Swing (1d+)
**Direction** : `LONG`
**Entrée** : Achat sur correction ≥ 38.2% du dernier swing haussier
**SL** : `2008.937143` | **TP** : `2169.632143` | **R:R** : `1:2.5`
**Timeframe** : `1d–1W`
**Condition** : _Structure HH/HL intacte, volume confirmé_
**Qualité** : 🟢 Favorable — structure bullish validée

---

### 9. MIROFISH — SOURCE SECONDAIRE
> ⚠️ **ATTENTION** : Section secondaire de confirmation comportementale.
> Les données Mirofish ne remplacent JAMAIS l'analyse des sections 1-8.
> Priorité 4/4 dans la hiérarchie des sources.

> ⚠️ Source secondaire — ne remplace pas l'analyse primaire

| Métrique Mirofish | Valeur |
|---|---|
| Direction crowd | `NEUTRAL` |
| Votes LONG / SHORT / HOLD | `32%` / `26%` / `42%` |
| Probabilité haussière | `51%` |
| Probabilité baissière | `28%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `-25` (-50 à +50) |
| Risque manipulation crowd | `12%` |

**Note comportementale** : _🔀 Divergence comportementale — foule neutral mais technique opposé. Crowd est contre-tendance (32%/26%). Prudence : la foule a souvent tort contre la structure._

---

### Liens
[[decisions/convergence_ETH_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
