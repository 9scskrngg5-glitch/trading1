---
date: 2026-03-31 03:14 UTC
agent: SynthesisAgent
asset: EUR/USD
regime: neutral
market_type: ranging
phase: distribution
volatility: low
structure: LH_LL
bos: false
bias: short_bias
coherence: 75
realized_vol: 0.91
manip_risk: 20.0
compound_mode: startup
tags:
- synthese
- datasheet
- eur-usd
---

## DataSheet Institutionnelle — EUR/USD

> Généré le 31/03/2026 03:14 UTC | Prix : `1.148500` | ATR : `0.001336` (0.12%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR EUR/USD: N/A

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
| Direction | **NEUTRAL** | slope 20p = -0.15% |
| Type | **RANGING** | volatilité low |
| Phase (Wyckoff) | **DISTRIBUTION** | EMA20 = 1.1480 |
| Volatilité ATR% | `0.12%` | 🟢 Faible |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `0.9%` — 🟢 Faible (<30%) |
| Percentile session | `76e percentile` |
| POC (Point of Control) | `1.149155` |
| Value Area High (VAH) | `1.15117` |
| Value Area Low (VAL) | `1.14714` |
| HVN (High Vol. Nodes) | `1.1473` | `1.1492` | `1.1501` |
| LVN (Low Vol. Nodes) | `1.1482` |

---

### 3. STRUCTURE DE MARCHÉ
> **🔴 Bearish (LH/LL)**



| Swing Highs récents | `1.1510` | `1.1510` | `1.1526` | `1.1504` |
|---|---|
| **Swing Lows récents** | `1.1502` | `1.1500` | `1.1486` | `1.1450` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `1.150991` | `100/100` | `11` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `1.145000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `1.15075` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `—` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @1.1462 | `1.145000` | `1.147300` | `1.146150` |
| 🟢 OB Bullish @1.1464 | `1.146100` | `1.146800` | `1.146450` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `20/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ⚠️ OUI |

- 🧱 Fake wall potentiel côté ASK — OB imbalance -0.58 mais prix monte

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> NEGATIVE — score `-22.5` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🟡 Cohérence MODÉRÉE (75/100) — légères divergences

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `12/100` |
| Fondamental | `bearish` | `37/100` |
| Régime | `neutral` | — |
| Structure | `bearish` | — |

✅ Pas de divergence majeure

#### Détection de Biais
> ⚠️  BIAIS SHORT DÉTECTÉ (83% des signaux) — Rechercher activement des setups LONG. Réduire la taille des positions SHORT de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `5` | `17%` |
| SHORT | `25` | `83%` |
| Sévérité | `critical` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 1.145000 | SHORT @ 1.150991
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
| Votes LONG / SHORT / HOLD | `29%` / `38%` / `33%` |
| Probabilité haussière | `45%` |
| Probabilité baissière | `38%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (29%L / 38%S / 33%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_EUR_USD]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
