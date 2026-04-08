---
date: 2026-04-06 16:09 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: bullish
market_type: trending
phase: markup
volatility: medium
structure: HH_HL
bos: false
bias: long_bias
coherence: 50
realized_vol: 8.46
manip_risk: 20.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 06/04/2026 16:09 UTC | Prix : `82.270000` | ATR : `0.662857` (0.81%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 1.5% | Confiance min: 55 | WR SOL/USDT: N/A | HistTech: 3n | HistFund: 1n | Leçons: 1n

| Paramètre Mémorisé | Valeur |
|---|---|
| Mode CompoundAgent | `STARTUP` |
| Risque/Trade actuel | `1.5%` |
| Confiance min. (RiskAgent) | `55.0` |
| Ajustement confiance mémoire | `+0 pts` |

---

### 1. RÉGIME DE MARCHÉ
| Dimension | Valeur | Détail |
|---|---|---|
| Direction | **BULLISH** | slope 20p = +2.63% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKUP** | EMA20 = 81.8013 |
| Volatilité ATR% | `0.81%` | 🟡 Moyenne |
| Force de tendance | `13/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `8.5%` — 🟢 Faible (<30%) |
| Percentile session | `90e percentile` |
| POC (Point of Control) | `82.404` |
| Value Area High (VAH) | `82.68` |
| Value Area Low (VAL) | `80.288` |
| HVN (High Vol. Nodes) | `79.6440` | `80.9320` | `81.8520` |
| LVN (Low Vol. Nodes) | `79.0920` | `79.4600` | `82.5880` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `80.2400` | `80.3300` | `82.9700` | `83.2000` |
|---|---|
| **Swing Lows récents** | `79.4100` | `78.5200` | `79.1000` | `80.9700` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `83.085000` | `50/100` | `2` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `79.920000` | `25/100` | `1` touches |
| S2 | `79.360000` | `75/100` | `3` touches |
| S3 | `78.520000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `83.085` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `79.49` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @79.8950 | `79.410000` | `80.380000` | `79.895000` |
| 🟢 OB Bullish @79.3750 | `78.800000` | `79.950000` | `79.375000` |
| 🟢 OB Bullish @79.8500 | `79.510000` | `80.190000` | `79.850000` |
| 🔴 OB Bearish @82.2300 | `81.660000` | `82.800000` | `82.230000` |
| 🟢 OB Bullish @81.5550 | `80.970000` | `82.140000` | `81.555000` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `20/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ⚠️ OUI |

- 🧱 Fake wall potentiel côté BID — OB imbalance +0.63 mais prix baisse

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> NEGATIVE — score `-21.4` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `neutral` | `49/100` |
| Fondamental | `bearish` | `24/100` |
| Régime | `bullish` | — |
| Structure | `bullish` | — |

✅ Pas de divergence majeure

#### Détection de Biais
> ⚠️  BIAIS LONG DÉTECTÉ (70% des signaux) — Rechercher activement des setups SHORT. Réduire la taille des positions LONG de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `21` | `70%` |
| SHORT | `9` | `30%` |
| Sévérité | `moderate` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 79.920000 | SHORT @ 83.085000
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `LONG`
**Entrée** : Pull-back vers 81.938571 ou OB bullish
**SL** : `81.607143` | **TP** : `83.595714` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture au-dessus de l'EMA20_
**Qualité** : 🟢 Favorable

---

#### 🌊 Swing (1d+)
**Direction** : `LONG`
**Entrée** : Achat sur correction ≥ 38.2% du dernier swing haussier
**SL** : `80.944286` | **TP** : `85.584286` | **R:R** : `1:2.5`
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
| Votes LONG / SHORT / HOLD | `39%` / `32%` / `29%` |
| Probabilité haussière | `55%` |
| Probabilité baissière | `30%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `-25` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _🔀 Divergence comportementale — foule neutral mais technique opposé. Crowd est contre-tendance (39%/32%). Prudence : la foule a souvent tort contre la structure._

---

### Liens
[[decisions/2026-04-06_predict_SOL-USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
