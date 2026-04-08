---
date: 2026-04-06 11:19 UTC
agent: SynthesisAgent
asset: EUR/USD
regime: neutral
market_type: ranging
phase: distribution
volatility: low
structure: mixed
bos: false
bias: balanced
coherence: 50
realized_vol: 0.9
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- eur-usd
---

## DataSheet Institutionnelle — EUR/USD

> Généré le 06/04/2026 11:19 UTC | Prix : `1.154900` | ATR : `0.001271` (0.11%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR EUR/USD: N/A | HistTech: 3n | HistFund: 0n | Leçons: 1n

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
| Direction | **NEUTRAL** | slope 20p = +0.29% |
| Type | **RANGING** | volatilité low |
| Phase (Wyckoff) | **DISTRIBUTION** | EMA20 = 1.1532 |
| Volatilité ATR% | `0.11%` | 🟢 Faible |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `0.9%` — 🟢 Faible (<30%) |
| Percentile session | `100e percentile` |
| POC (Point of Control) | `1.15165` |
| Value Area High (VAH) | `1.1524` |
| Value Area Low (VAL) | `1.1512` |
| HVN (High Vol. Nodes) | `1.1514` | `1.1517` | `1.1522` |
| LVN (Low Vol. Nodes) | — |

---

### 3. STRUCTURE DE MARCHÉ
> **🟡 Structure mixte**



| Swing Highs récents | `1.1517` | `1.1516` | `1.1523` | `1.1572` |
|---|---|
| **Swing Lows récents** | `1.1513` | `1.1513` | `1.1507` | `1.1507` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `1.157200` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `1.151347` | `100/100` | `15` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `1.1515` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @1.1516 | `1.151500` | `1.151700` | `1.151600` |
| 🟢 OB Bullish @1.1511 | `1.150700` | `1.151400` | `1.151050` |
| 🟢 OB Bullish @1.1522 | `1.152000` | `1.152500` | `1.152250` |
| 🔴 OB Bearish @1.1551 | `1.153000` | `1.157200` | `1.155100` |

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
> NEUTRAL — score `+19.0` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bullish` | `20/100` |
| Fondamental | `bullish` | `16/100` |
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
**Direction** : `RANGE`
**Entrée** : LONG @ 1.151347 | SHORT @ 1.157200
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
| Votes LONG / SHORT / HOLD | `40%` / `34%` / `27%` |
| Probabilité haussière | `53%` |
| Probabilité baissière | `33%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (40%L / 34%S / 27%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/2026-04-06_predict_EUR-USD]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
