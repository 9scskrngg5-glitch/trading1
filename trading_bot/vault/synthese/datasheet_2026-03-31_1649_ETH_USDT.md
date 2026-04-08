---
date: 2026-03-31 16:49 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: bullish
market_type: trending
phase: markup
volatility: medium
structure: HH_HL
bos: false
bias: balanced
coherence: 0
realized_vol: 12.2
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 31/03/2026 16:49 UTC | Prix : `2091.640000` | ATR : `25.710714` (1.23%)

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
| Direction | **BULLISH** | slope 20p = +2.73% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKUP** | EMA20 = 2052.6928 |
| Volatilité ATR% | `1.23%` | 🟡 Moyenne |
| Force de tendance | `13/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `12.2%` — 🟢 Faible (<30%) |
| Percentile session | `80e percentile` |
| POC (Point of Control) | `2071.05125` |
| Value Area High (VAH) | `2079.875` |
| Value Area Low (VAL) | `2015.1675` |
| HVN (High Vol. Nodes) | `1994.5787` | `2041.6388` | `2047.5213` |
| LVN (Low Vol. Nodes) | `1988.6962` | `2000.4613` | `2012.2262` |

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
| R1 | `2092.340000` | `25/100` | `1` touches |

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
| 🟢 OB Bullish @2023.4950 | `2013.920000` | `2033.070000` | `2023.495000` |
| 🟢 OB Bullish @2028.5700 | `2012.640000` | `2044.500000` | `2028.570000` |

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
**Direction** : `LONG`
**Entrée** : 2091.640000 (niveau courant)
**SL** : `2081.355714` | **TP** : `2112.208571` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Entry sur pull-back vers support le plus proche_
**Qualité** : 🟢 Favorable

#### ⚡ Scalping Contrarian
**Direction** : `SHORT`
**Entrée** : 2092.34 (résistance R1)
**SL** : `2102.624286` | **TP** : `2071.771429` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Rejet sur résistance avec volume baissier_
**Qualité** : 🟡 Contre-tendance — prudence
**Note mémoire** : _Setup complémentaire pour équilibrer le biais_

---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 2078.784643 ou OB bullish
**SL** : `2065.929286` | **TP** : `2143.061429` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture au-dessus de l'EMA20_
**Qualité** : 🟢 Favorable

---

#### 🌊 Swing (1d+)
**Direction** : `LONG`
**Entrée** : Achat sur correction ≥ 38.2% du dernier swing haussier
**SL** : `2040.218571` | **TP** : `2220.193571` | **R:R** : `1:2.5`
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
| Direction crowd | `BULLISH` |
| Votes LONG / SHORT / HOLD | `50%` / `29%` / `22%` |
| Probabilité haussière | `58%` |
| Probabilité baissière | `32%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (50%L / 29%S / 22%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_ETH_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
