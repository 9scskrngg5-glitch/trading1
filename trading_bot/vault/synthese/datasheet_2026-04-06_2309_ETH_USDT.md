---
date: 2026-04-06 23:09 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: neutral
market_type: trending
phase: accumulation
volatility: medium
structure: HH_HL
bos: true
bias: balanced
coherence: 50
realized_vol: 8.67
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 06/04/2026 23:09 UTC | Prix : `2105.410000` | ATR : `17.939286` (0.85%)

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
| Direction | **NEUTRAL** | slope 20p = -1.12% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **ACCUMULATION** | EMA20 = 2131.7592 |
| Volatilité ATR% | `0.85%` | 🟡 Moyenne |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `8.7%` — 🟢 Faible (<30%) |
| Percentile session | `86e percentile` |
| POC (Point of Control) | `2147.61375` |
| Value Area High (VAH) | `2164.65` |
| Value Area Low (VAL) | `2062.4325` |
| HVN (High Vol. Nodes) | `2065.8398` | `2133.9848` | `2147.6137` |
| LVN (Low Vol. Nodes) | — |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**
> 🔔 **BREAK OF STRUCTURE** détecté à `2123.6`
> 🔄 **CHoCH** — potentiel retournement

| Swing Highs récents | `2069.8900` | `2147.2400` | `2174.7900` | `2169.6000` |
|---|---|
| **Swing Lows récents** | `2021.5000` | `2050.0000` | `2120.0400` | `2123.6000` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `2172.195000` | `50/100` | `2` touches |
| R2 | `2147.240000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `2047.315000` | `50/100` | `2` touches |
| S2 | `2024.625000` | `50/100` | `2` touches |

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
> NEGATIVE — score `-21.4` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bullish` | `43/100` |
| Fondamental | `bearish` | `35/100` |
| Régime | `neutral` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bullish ≠ Fondamental bearish
- 🔔 Break of Structure à 2123.6 — recalibrage recommandé
- 🔔 CHoCH — potentiel retournement de tendance

#### Détection de Biais
> ✅ Équilibré : 50% long / 50% short sur 30 signaux

| Direction | Signaux | % |
|---|---|---|
| LONG | `15` | `50%` |
| SHORT | `15` | `50%` |
| Sévérité | `none` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 2047.315000 | SHORT @ 2172.195000
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
| Direction crowd | `BULLISH` |
| Votes LONG / SHORT / HOLD | `49%` / `20%` / `31%` |
| Probabilité haussière | `63%` |
| Probabilité baissière | `22%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+25` (-50 à +50) |
| Risque manipulation crowd | `22%` |

**Note comportementale** : _✅ Alignement foule-technique — 49% LONG avec support structurel. Consensus comportemental renforce l'analyse primaire._

---

### Liens
[[decisions/2026-04-06_predict_ETH-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
