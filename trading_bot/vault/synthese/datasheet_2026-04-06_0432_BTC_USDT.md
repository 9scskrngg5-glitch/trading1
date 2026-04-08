---
date: 2026-04-06 04:32 UTC
agent: SynthesisAgent
asset: BTC/USDT
regime: bullish
market_type: trending
phase: markup
volatility: low
structure: HH_HL
bos: false
bias: balanced
coherence: 0
realized_vol: 5.02
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- btc-usdt
---

## DataSheet Institutionnelle — BTC/USDT

> Généré le 06/04/2026 04:32 UTC | Prix : `69046.550000` | ATR : `459.793571` (0.67%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR BTC/USDT: N/A | HistTech: 3n | HistFund: 1n | Leçons: 2n

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
| Direction | **BULLISH** | slope 20p = +3.00% |
| Type | **TRENDING** | volatilité low |
| Phase (Wyckoff) | **MARKUP** | EMA20 = 68109.9588 |
| Volatilité ATR% | `0.67%` | 🟢 Faible |
| Force de tendance | `30/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `5.0%` — 🟢 Faible (<30%) |
| Percentile session | `100e percentile` |
| POC (Point of Control) | `66844.19025` |
| Value Area High (VAH) | `68359.4465` |
| Value Area Low (VAL) | `66783.58` |
| HVN (High Vol. Nodes) | `66844.1902` | `66965.4107` | `67329.0722` |
| LVN (Low Vol. Nodes) | — |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `67543.6000` | `67150.0000` | `67856.1600` | `69588.0000` |
|---|---|
| **Swing Lows récents** | `67029.0700` | `67186.6200` | `66611.6600` | `66680.5700` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `69588.000000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `66866.971667` | `100/100` | `6` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `66846.955` | Stops de vendeurs — cible de stop-hunt |

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
**Entrée** : 69046.550000 (niveau courant)
**SL** : `68862.632571` | **TP** : `69414.384857` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Entry sur pull-back vers support le plus proche_
**Qualité** : 🟢 Favorable

#### ⚡ Scalping Contrarian
**Direction** : `SHORT`
**Entrée** : 69588.0 (résistance R1)
**SL** : `69771.917429` | **TP** : `69220.165143` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Rejet sur résistance avec volume baissier_
**Qualité** : 🟡 Contre-tendance — prudence
**Note mémoire** : _Setup complémentaire pour équilibrer le biais_

---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 68816.653214 ou OB bullish
**SL** : `68586.756429` | **TP** : `69966.137143` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture au-dessus de l'EMA20_
**Qualité** : 🟢 Favorable

---

#### 🌊 Swing (1d+)
**Direction** : `LONG`
**Entrée** : Achat sur correction ≥ 38.2% du dernier swing haussier
**SL** : `68126.962857` | **TP** : `71345.517857` | **R:R** : `1:2.5`
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
| Votes LONG / SHORT / HOLD | `35%` / `22%` / `44%` |
| Probabilité haussière | `58%` |
| Probabilité baissière | `21%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `-25` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _🔀 Divergence comportementale — foule neutral mais technique opposé. Crowd est contre-tendance (35%/22%). Prudence : la foule a souvent tort contre la structure._

---

### Liens
[[decisions/2026-04-06_predict_BTC-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
