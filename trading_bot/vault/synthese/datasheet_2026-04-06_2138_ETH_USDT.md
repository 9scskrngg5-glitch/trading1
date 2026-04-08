---
date: 2026-04-06 21:38 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: bullish
market_type: ranging
phase: transition
volatility: low
structure: HH_HL
bos: false
bias: long_bias
coherence: 100
realized_vol: 7.54
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 06/04/2026 21:38 UTC | Prix : `2148.810000` | ATR : `16.945000` (0.79%)

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
| Direction | **BULLISH** | slope 20p = +1.59% |
| Type | **RANGING** | volatilité low |
| Phase (Wyckoff) | **TRANSITION** | EMA20 = 2134.0026 |
| Volatilité ATR% | `0.79%` | 🟢 Faible |
| Force de tendance | `7/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `7.5%` — 🟢 Faible (<30%) |
| Percentile session | `86e percentile` |
| POC (Point of Control) | `2147.61375` |
| Value Area High (VAH) | `2164.65` |
| Value Area Low (VAL) | `2062.4325` |
| HVN (High Vol. Nodes) | `2052.2108` | `2133.9848` | `2147.6137` |
| LVN (Low Vol. Nodes) | — |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `2069.8900` | `2147.2400` | `2174.7900` | `2169.6000` |
|---|---|
| **Swing Lows récents** | `2021.5000` | `2050.0000` | `2120.0400` | `2123.6000` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `2172.195000` | `50/100` | `2` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `2121.820000` | `50/100` | `2` touches |
| S2 | `2047.315000` | `50/100` | `2` touches |
| S3 | `2024.625000` | `50/100` | `2` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `2172.195` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `2047.315` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @2038.5350 | `2034.480000` | `2042.590000` | `2038.535000` |
| 🟢 OB Bullish @2031.9050 | `2021.500000` | `2042.310000` | `2031.905000` |
| 🟢 OB Bullish @2062.9250 | `2056.730000` | `2069.120000` | `2062.925000` |
| 🟢 OB Bullish @2129.5200 | `2120.040000` | `2139.000000` | `2129.520000` |
| 🟢 OB Bullish @2148.4150 | `2142.310000` | `2154.520000` | `2148.415000` |

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
> POSITIVE — score `+36.5` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> ✅ Cohérence FORTE (100/100) — tous les agents alignés bullish

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bullish` | `46/100` |
| Fondamental | `bullish` | `31/100` |
| Régime | `bullish` | — |
| Structure | `bullish` | — |

✅ Pas de divergence majeure

#### Détection de Biais
> ⚠️  BIAIS LONG DÉTECTÉ (100% des signaux) — Rechercher activement des setups SHORT. Réduire la taille des positions LONG de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `21` | `100%` |
| SHORT | `0` | `0%` |
| Sévérité | `critical` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 2121.820000 | SHORT @ 2172.195000
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 2140.3375 ou OB bullish
**SL** : `2131.865` | **TP** : `2182.7` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture au-dessus de l'EMA20_
**Qualité** : 🟢 Favorable

---

#### 🌊 Swing (1d+)
**Direction** : `LONG`
**Entrée** : Achat sur correction ≥ 38.2% du dernier swing haussier
**SL** : `2114.92` | **TP** : `2233.535` | **R:R** : `1:2.5`
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
| Votes LONG / SHORT / HOLD | `52%` / `15%` / `34%` |
| Probabilité haussière | `64%` |
| Probabilité baissière | `19%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `22%` |

**Note comportementale** : _📊 Distribution équilibrée (52%L / 15%S / 34%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/2026-04-06_predict_ETH-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
