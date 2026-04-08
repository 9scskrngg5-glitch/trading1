---
date: 2026-04-06 15:39 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: bullish
market_type: trending
phase: markup
volatility: low
structure: HH_HL
bos: false
bias: long_bias
coherence: 100
realized_vol: 6.8
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 06/04/2026 15:39 UTC | Prix : `2156.710000` | ATR : `16.152143` (0.75%)

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
| Direction | **BULLISH** | slope 20p = +4.57% |
| Type | **TRENDING** | volatilité low |
| Phase (Wyckoff) | **MARKUP** | EMA20 = 2124.1676 |
| Volatilité ATR% | `0.75%` | 🟢 Faible |
| Force de tendance | `45/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `6.8%` — 🟢 Faible (<30%) |
| Percentile session | `90e percentile` |
| POC (Point of Control) | `2153.50125` |
| Value Area High (VAH) | `2156.71` |
| Value Area Low (VAL) | `2060.4475` |
| HVN (High Vol. Nodes) | `2050.8212` | `2063.6562` | `2134.2488` |
| LVN (Low Vol. Nodes) | — |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `2052.5300` | `2069.8900` | `2147.2400` | `2174.7900` |
|---|---|
| **Swing Lows récents** | `2027.7500` | `2021.5000` | `2050.0000` | `2120.0400` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `2174.790000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `2120.040000` | `25/100` | `1` touches |
| S2 | `2047.506667` | `75/100` | `3` touches |
| S3 | `2024.625000` | `50/100` | `2` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `2046.26` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @2038.5350 | `2034.480000` | `2042.590000` | `2038.535000` |
| 🟢 OB Bullish @2031.9050 | `2021.500000` | `2042.310000` | `2031.905000` |
| 🟢 OB Bullish @2062.9250 | `2056.730000` | `2069.120000` | `2062.925000` |
| 🟢 OB Bullish @2129.5200 | `2120.040000` | `2139.000000` | `2129.520000` |

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
> POSITIVE — score `+39.4` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> ✅ Cohérence FORTE (100/100) — tous les agents alignés bullish

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bullish` | `57/100` |
| Fondamental | `bullish` | `34/100` |
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
**Entrée** : LONG @ 2120.040000 | SHORT @ 2174.790000
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 2148.633929 ou OB bullish
**SL** : `2140.557857` | **TP** : `2189.014286` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture au-dessus de l'EMA20_
**Qualité** : 🟢 Favorable

---

#### 🌊 Swing (1d+)
**Direction** : `LONG`
**Entrée** : Achat sur correction ≥ 38.2% du dernier swing haussier
**SL** : `2124.405714` | **TP** : `2237.470714` | **R:R** : `1:2.5`
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
| Votes LONG / SHORT / HOLD | `44%` / `25%` / `31%` |
| Probabilité haussière | `58%` |
| Probabilité baissière | `27%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `-25` (-50 à +50) |
| Risque manipulation crowd | `9%` |

**Note comportementale** : _🔀 Divergence comportementale — foule neutral mais technique opposé. Crowd est contre-tendance (44%/25%). Prudence : la foule a souvent tort contre la structure._

---

### Liens
[[decisions/2026-04-06_predict_ETH-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
