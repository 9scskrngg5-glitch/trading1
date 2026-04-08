---
date: 2026-04-06 16:20 UTC
agent: SynthesisAgent
asset: BTC/USDT
regime: bullish
market_type: trending
phase: markup
volatility: low
structure: HH_HL
bos: false
bias: long_bias
coherence: 100
realized_vol: 5.55
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- btc-usdt
---

## DataSheet Institutionnelle — BTC/USDT

> Généré le 06/04/2026 16:20 UTC | Prix : `69968.870000` | ATR : `405.074286` (0.58%)

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
| Direction | **BULLISH** | slope 20p = +3.42% |
| Type | **TRENDING** | volatilité low |
| Phase (Wyckoff) | **MARKUP** | EMA20 = 69058.3518 |
| Volatilité ATR% | `0.58%` | 🟢 Faible |
| Force de tendance | `34/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `5.5%` — 🟢 Faible (<30%) |
| Percentile session | `100e percentile` |
| POC (Point of Control) | `69092.91525` |
| Value Area High (VAH) | `69968.87` |
| Value Area Low (VAL) | `67261.3735` |
| HVN (High Vol. Nodes) | `66863.2122` | `67341.0057` | `69092.9153` |
| LVN (Low Vol. Nodes) | — |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `67150.0000` | `67856.1600` | `69588.0000` | `70283.3200` |
|---|---|
| **Swing Lows récents** | `67186.6200` | `66611.6600` | `66680.5700` | `68806.5300` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `70283.320000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `68806.530000` | `25/100` | `1` touches |
| S2 | `66885.184000` | `100/100` | `5` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `66973.535` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @66775.8300 | `66611.660000` | `66940.000000` | `66775.830000` |
| 🟢 OB Bullish @66839.7850 | `66680.570000` | `66999.000000` | `66839.785000` |
| 🟢 OB Bullish @67545.2450 | `67408.070000` | `67682.420000` | `67545.245000` |
| 🟢 OB Bullish @69080.3950 | `68806.530000` | `69354.260000` | `69080.395000` |
| 🟢 OB Bullish @69482.5500 | `69329.230000` | `69635.870000` | `69482.550000` |

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
> POSITIVE — score `+42.4` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> ✅ Cohérence FORTE (100/100) — tous les agents alignés bullish

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bullish` | `67/100` |
| Fondamental | `bullish` | `36/100` |
| Régime | `bullish` | — |
| Structure | `bullish` | — |

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
**Entrée** : LONG @ 68806.530000 | SHORT @ 70283.320000
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 69766.332857 ou OB bullish
**SL** : `69563.795714` | **TP** : `70779.018571` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture au-dessus de l'EMA20_
**Qualité** : 🟢 Favorable

---

#### 🌊 Swing (1d+)
**Direction** : `LONG`
**Entrée** : Achat sur correction ≥ 38.2% du dernier swing haussier
**SL** : `69158.721429` | **TP** : `71994.241429` | **R:R** : `1:2.5`
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
| Votes LONG / SHORT / HOLD | `45%` / `26%` / `29%` |
| Probabilité haussière | `59%` |
| Probabilité baissière | `26%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `-25` (-50 à +50) |
| Risque manipulation crowd | `24%` |

**Note comportementale** : _🔀 Divergence comportementale — foule neutral mais technique opposé. Crowd est contre-tendance (45%/26%). Prudence : la foule a souvent tort contre la structure._

---

### Liens
[[decisions/2026-04-06_predict_BTC-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
