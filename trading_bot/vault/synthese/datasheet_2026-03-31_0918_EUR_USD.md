---
date: 2026-03-31 09:18 UTC
agent: SynthesisAgent
asset: EUR/USD
regime: neutral
market_type: ranging
phase: distribution
volatility: low
structure: LH_LL
bos: false
bias: long_bias
coherence: 75
realized_vol: 0.94
manip_risk: 20.0
compound_mode: startup
tags:
- synthese
- datasheet
- eur-usd
---

## DataSheet Institutionnelle — EUR/USD

> Généré le 31/03/2026 09:18 UTC | Prix : `1.147500` | ATR : `0.001071` (0.09%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR EUR/USD: N/A | HistTech: 2n | HistFund: 0n | Leçons: 1n

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
| Direction | **NEUTRAL** | slope 20p = +0.03% |
| Type | **RANGING** | volatilité low |
| Phase (Wyckoff) | **DISTRIBUTION** | EMA20 = 1.1479 |
| Volatilité ATR% | `0.09%` | 🟢 Faible |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `0.9%` — 🟢 Faible (<30%) |
| Percentile session | `60e percentile` |
| POC (Point of Control) | `1.149155` |
| Value Area High (VAH) | `1.15055` |
| Value Area Low (VAL) | `1.1459` |
| HVN (High Vol. Nodes) | `1.1473` | `1.1492` | `1.1501` |
| LVN (Low Vol. Nodes) | `1.1485` | `1.1495` | `1.1498` |

---

### 3. STRUCTURE DE MARCHÉ
> **🔴 Bearish (LH/LL)**



| Swing Highs récents | `1.1510` | `1.1526` | `1.1504` | `1.1498` |
|---|---|
| **Swing Lows récents** | `1.1500` | `1.1486` | `1.1450` | `1.1456` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `1.150900` | `100/100` | `11` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `1.145300` | `50/100` | `2` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `1.1507` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `1.1471` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @1.1462 | `1.145000` | `1.147300` | `1.146150` |
| 🟢 OB Bullish @1.1464 | `1.146100` | `1.146800` | `1.146450` |
| 🔴 OB Bearish @1.1486 | `1.148200` | `1.148900` | `1.148550` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `20/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ⚠️ OUI |

- 🧱 Fake wall potentiel côté BID — OB imbalance +0.43 mais prix baisse

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> NEGATIVE — score `-33.5` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🟡 Cohérence MODÉRÉE (75/100) — légères divergences

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `23/100` |
| Fondamental | `bearish` | `55/100` |
| Régime | `neutral` | — |
| Structure | `bearish` | — |

✅ Pas de divergence majeure

#### Détection de Biais
> ⚠️  BIAIS LONG DÉTECTÉ (100% des signaux) — Rechercher activement des setups SHORT. Réduire la taille des positions LONG de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `30` | `100%` |
| SHORT | `0` | `0%` |
| Sévérité | `critical` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 1.145300 | SHORT @ 1.150900
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
| Direction crowd | `BEARISH` |
| Votes LONG / SHORT / HOLD | `26%` / `52%` / `22%` |
| Probabilité haussière | `41%` |
| Probabilité baissière | `48%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `-25` (-50 à +50) |
| Risque manipulation crowd | `4%` |

**Note comportementale** : _🔀 Divergence comportementale — foule bearish mais technique opposé. Crowd est contre-tendance (26%/52%). Prudence : la foule a souvent tort contre la structure._

---

### Liens
[[decisions/convergence_EUR_USD]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
