---
date: 2026-04-07 04:58 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: neutral
market_type: trending
phase: accumulation
volatility: medium
structure: mixed
bos: false
bias: balanced
coherence: 25
realized_vol: 8.86
manip_risk: 20.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 07/04/2026 04:58 UTC | Prix : `2108.370000` | ATR : `18.585714` (0.88%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 1.5% | Confiance min: 55 | WR ETH/USDT: N/A | HistTech: 3n | HistFund: 1n | Leçons: 2n

| Paramètre Mémorisé | Valeur |
|---|---|
| Mode CompoundAgent | `STARTUP` |
| Risque/Trade actuel | `1.5%` |
| Confiance min. (RiskAgent) | `55.0` |
| Ajustement confiance mémoire | `-5 pts` |

---

### 1. RÉGIME DE MARCHÉ
| Dimension | Valeur | Détail |
|---|---|---|
| Direction | **NEUTRAL** | slope 20p = -1.41% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **ACCUMULATION** | EMA20 = 2121.9614 |
| Volatilité ATR% | `0.88%` | 🟡 Moyenne |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `8.9%` — 🟢 Faible (<30%) |
| Percentile session | `70e percentile` |
| POC (Point of Control) | `2147.61375` |
| Value Area High (VAH) | `2164.65` |
| Value Area Low (VAL) | `2103.3195` |
| HVN (High Vol. Nodes) | `2106.7267` | `2113.5413` | `2133.9848` |
| LVN (Low Vol. Nodes) | `2031.7673` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟡 Structure mixte**



| Swing Highs récents | `2147.2400` | `2174.7900` | `2169.6000` | `2155.0600` |
|---|---|
| **Swing Lows récents** | `2050.0000` | `2120.0400` | `2123.6000` | `2087.5000` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `2151.150000` | `50/100` | `2` touches |
| R2 | `2172.195000` | `50/100` | `2` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `2087.500000` | `25/100` | `1` touches |
| S2 | `2050.000000` | `25/100` | `1` touches |
| S3 | `2024.625000` | `50/100` | `2` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `2172.195` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `—` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @2038.5350 | `2034.480000` | `2042.590000` | `2038.535000` |
| 🟢 OB Bullish @2031.9050 | `2021.500000` | `2042.310000` | `2031.905000` |
| 🟢 OB Bullish @2062.9250 | `2056.730000` | `2069.120000` | `2062.925000` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `20/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ⚠️ OUI |

- 🧱 Fake wall potentiel côté ASK — OB imbalance -0.66 mais prix monte

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> NEGATIVE — score `-30.2` sur 4 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (25/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bullish` | `29/100` |
| Fondamental | `bearish` | `40/100` |
| Régime | `neutral` | — |
| Structure | `neutral` | — |

**Divergences :**
- ⚠️  Technique bullish ≠ Fondamental bearish

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
**Direction** : `RANGE`
**Entrée** : LONG @ 2087.500000 | SHORT @ 2151.150000
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
| Votes LONG / SHORT / HOLD | `41%` / `40%` / `19%` |
| Probabilité haussière | `50%` |
| Probabilité baissière | `40%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `14%` |

**Note comportementale** : _📊 Distribution équilibrée (41%L / 40%S / 19%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/2026-04-07_predict_ETH-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
