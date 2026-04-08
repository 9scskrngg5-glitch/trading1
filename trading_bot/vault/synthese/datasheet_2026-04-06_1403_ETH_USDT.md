---
date: 2026-04-06 14:03 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: bullish
market_type: trending
phase: markup
volatility: low
structure: HH_HL
bos: false
bias: long_bias
coherence: 75
realized_vol: 6.73
manip_risk: 20.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 06/04/2026 14:03 UTC | Prix : `2145.990000` | ATR : `15.955000` (0.74%)

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
| Direction | **BULLISH** | slope 20p = +4.02% |
| Type | **TRENDING** | volatilité low |
| Phase (Wyckoff) | **MARKUP** | EMA20 = 2120.7423 |
| Volatilité ATR% | `0.74%` | 🟢 Faible |
| Force de tendance | `40/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `6.7%` — 🟢 Faible (<30%) |
| Percentile session | `90e percentile` |
| POC (Point of Control) | `2056.46475` |
| Value Area High (VAH) | `2134.5335` |
| Value Area Low (VAL) | `2028.36` |
| HVN (High Vol. Nodes) | `2056.4648` | `2062.7103` | `2131.4108` |
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
| R1 | `2147.240000` | `25/100` | `1` touches |
| R2 | `2174.790000` | `25/100` | `1` touches |

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
> Risque global : `20/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ⚠️ OUI |

- 🧱 Fake wall potentiel côté BID — OB imbalance +0.42 mais prix baisse

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> NEUTRAL — score `-19.9` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🟡 Cohérence MODÉRÉE (75/100) — légères divergences

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bullish` | `67/100` |
| Fondamental | `bearish` | `21/100` |
| Régime | `bullish` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bullish ≠ Fondamental bearish

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
**Entrée** : LONG @ 2120.040000 | SHORT @ 2147.240000
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 2138.0125 ou OB bullish
**SL** : `2130.035` | **TP** : `2177.9` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture au-dessus de l'EMA20_
**Qualité** : 🟢 Favorable

---

#### 🌊 Swing (1d+)
**Direction** : `LONG`
**Entrée** : Achat sur correction ≥ 38.2% du dernier swing haussier
**SL** : `2114.08` | **TP** : `2225.765` | **R:R** : `1:2.5`
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
| Votes LONG / SHORT / HOLD | `45%` / `23%` / `32%` |
| Probabilité haussière | `57%` |
| Probabilité baissière | `27%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `25%` |

**Note comportementale** : _📊 Distribution équilibrée (45%L / 23%S / 32%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/2026-04-06_predict_ETH-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
