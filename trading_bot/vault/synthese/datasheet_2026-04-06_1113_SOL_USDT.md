---
date: 2026-04-06 11:13 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: bullish
market_type: trending
phase: markup
volatility: medium
structure: mixed
bos: false
bias: long_bias
coherence: 50
realized_vol: 8.34
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 06/04/2026 11:13 UTC | Prix : `82.680000` | ATR : `0.862857` (1.04%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR SOL/USDT: N/A | HistTech: 3n | HistFund: 1n | Leçons: 1n

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
| Direction | **BULLISH** | slope 20p = +3.56% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKUP** | EMA20 = 80.9713 |
| Volatilité ATR% | `1.04%` | 🟡 Moyenne |
| Force de tendance | `35/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `8.3%` — 🟢 Faible (<30%) |
| Percentile session | `100e percentile` |
| POC (Point of Control) | `80.196` |
| Value Area High (VAH) | `81.208` |
| Value Area Low (VAL) | `79.368` |
| HVN (High Vol. Nodes) | `79.6440` | `80.1960` | `80.9320` |
| LVN (Low Vol. Nodes) | `79.4600` |

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
| S1 | `79.920000` | `25/100` | `1` touches |
| S2 | `79.360000` | `75/100` | `3` touches |
| S3 | `78.520000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `79.49` | Stops de vendeurs — cible de stop-hunt |

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
> NEUTRAL — score `-17.6` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bullish` | `31/100` |
| Fondamental | `bearish` | `21/100` |
| Régime | `bullish` | — |
| Structure | `neutral` | — |

**Divergences :**
- ⚠️  Technique bullish ≠ Fondamental bearish

#### Détection de Biais
> ⚠️  BIAIS LONG DÉTECTÉ (100% des signaux) — Rechercher activement des setups SHORT. Réduire la taille des positions LONG de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `16` | `100%` |
| SHORT | `0` | `0%` |
| Sévérité | `critical` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 79.920000 | SHORT @ 82.970000
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 82.248571 ou OB bullish
**SL** : `81.817143` | **TP** : `84.405714` | **R:R** : `1:2.0`
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
| Direction crowd | `NEUTRAL` |
| Votes LONG / SHORT / HOLD | `32%` / `35%` / `33%` |
| Probabilité haussière | `47%` |
| Probabilité baissière | `36%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `-25` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _🔀 Divergence comportementale — foule neutral mais technique opposé. Crowd est contre-tendance (32%/35%). Prudence : la foule a souvent tort contre la structure._

---

### Liens
[[decisions/2026-04-06_predict_SOL-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
