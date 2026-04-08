---
date: 2026-04-06 03:54 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: bullish
market_type: trending
phase: markup
volatility: medium
structure: mixed
bos: false
bias: balanced
coherence: 0
realized_vol: 8.32
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 06/04/2026 03:54 UTC | Prix : `81.990000` | ATR : `0.831429` (1.01%)

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
| Direction | **BULLISH** | slope 20p = +2.98% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKUP** | EMA20 = 80.7809 |
| Volatilité ATR% | `1.01%` | 🟡 Moyenne |
| Force de tendance | `14/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `8.3%` — 🟢 Faible (<30%) |
| Percentile session | `100e percentile` |
| POC (Point of Control) | `80.27875` |
| Value Area High (VAH) | `81.2165` |
| Value Area Low (VAL) | `79.5115` |
| HVN (High Vol. Nodes) | `79.5968` | `80.1082` | `80.2788` |
| LVN (Low Vol. Nodes) | `79.4262` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟡 Structure mixte**



| Swing Highs récents | `81.6100` | `80.2400` | `80.3300` | `82.9700` |
|---|---|
| **Swing Lows récents** | `79.5700` | `79.4100` | `78.5200` | `79.1000` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `82.970000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `79.574000` | `100/100` | `5` touches |
| S2 | `78.520000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `79.895` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @79.8950 | `79.410000` | `80.380000` | `79.895000` |
| 🟢 OB Bullish @79.3750 | `78.800000` | `79.950000` | `79.375000` |
| 🟢 OB Bullish @79.8500 | `79.510000` | `80.190000` | `79.850000` |

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
**Entrée** : 81.990000 (niveau courant)
**SL** : `81.657429` | **TP** : `82.655143` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Entry sur pull-back vers support le plus proche_
**Qualité** : 🟢 Favorable

#### ⚡ Scalping Contrarian
**Direction** : `SHORT`
**Entrée** : 82.97 (résistance R1)
**SL** : `83.302571` | **TP** : `82.304857` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Rejet sur résistance avec volume baissier_
**Qualité** : 🟡 Contre-tendance — prudence
**Note mémoire** : _Setup complémentaire pour équilibrer le biais_

---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 81.574286 ou OB bullish
**SL** : `81.158571` | **TP** : `83.652857` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture au-dessus de l'EMA20_
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
| Direction crowd | `BULLISH` |
| Votes LONG / SHORT / HOLD | `45%` / `36%` / `18%` |
| Probabilité haussière | `56%` |
| Probabilité baissière | `35%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (45%L / 36%S / 18%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_SOL_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
