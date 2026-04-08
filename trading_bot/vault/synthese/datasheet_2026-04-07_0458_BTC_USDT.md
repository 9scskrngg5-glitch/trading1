---
date: 2026-04-07 04:58 UTC
agent: SynthesisAgent
asset: BTC/USDT
regime: neutral
market_type: ranging
phase: accumulation
volatility: low
structure: HH_HL
bos: true
bias: balanced
coherence: 25
realized_vol: 6.67
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- btc-usdt
---

## DataSheet Institutionnelle — BTC/USDT

> Généré le 07/04/2026 04:58 UTC | Prix : `68779.210000` | ATR : `479.222143` (0.70%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 1.5% | Confiance min: 55 | WR BTC/USDT: N/A | HistTech: 3n | HistFund: 1n | Leçons: 2n

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
| Direction | **NEUTRAL** | slope 20p = -0.64% |
| Type | **RANGING** | volatilité low |
| Phase (Wyckoff) | **ACCUMULATION** | EMA20 = 69063.2546 |
| Volatilité ATR% | `0.70%` | 🟢 Faible |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `6.7%` — 🟢 Faible (<30%) |
| Percentile session | `66e percentile` |
| POC (Point of Control) | `69729.97325` |
| Value Area High (VAH) | `69968.87` |
| Value Area Low (VAL) | `68216.9605` |
| HVN (High Vol. Nodes) | `67341.0057` | `68774.3862` | `69092.9153` |
| LVN (Low Vol. Nodes) | `67659.5348` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**
> 🔔 **BREAK OF STRUCTURE** détecté à `69163.86`
> 🔄 **CHoCH** — potentiel retournement

| Swing Highs récents | `69588.0000` | `70283.3200` | `70351.4600` | `69974.0800` |
|---|---|
| **Swing Lows récents** | `66611.6600` | `66680.5700` | `68806.5300` | `69163.8600` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `70317.390000` | `50/100` | `2` touches |
| R2 | `69588.000000` | `25/100` | `1` touches |
| R3 | `69974.080000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `67186.620000` | `25/100` | `1` touches |
| S2 | `66646.115000` | `50/100` | `2` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `70317.39` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `66646.115` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @66775.8300 | `66611.660000` | `66940.000000` | `66775.830000` |
| 🟢 OB Bullish @66839.7850 | `66680.570000` | `66999.000000` | `66839.785000` |
| 🟢 OB Bullish @67545.2450 | `67408.070000` | `67682.420000` | `67545.245000` |

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
> NEUTRAL — score `-15.0` sur 4 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (25/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `neutral` | `33/100` |
| Fondamental | `bearish` | `19/100` |
| Régime | `neutral` | — |
| Structure | `bullish` | — |

**Divergences :**
- 🔔 Break of Structure à 69163.86 — recalibrage recommandé
- 🔔 CHoCH — potentiel retournement de tendance

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
**Entrée** : LONG @ 67186.620000 | SHORT @ 70317.390000
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
| Votes LONG / SHORT / HOLD | `42%` / `26%` / `33%` |
| Probabilité haussière | `59%` |
| Probabilité baissière | `24%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `21%` |

**Note comportementale** : _📊 Distribution équilibrée (42%L / 26%S / 33%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/2026-04-07_predict_BTC-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
