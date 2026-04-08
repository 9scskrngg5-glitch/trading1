---
date: 2026-03-30 22:20 UTC
agent: SynthesisAgent
asset: BTC/USDT
regime: neutral
market_type: ranging
phase: accumulation
volatility: low
structure: LH_LL
bos: false
bias: balanced
coherence: 50
realized_vol: 6.68
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- btc-usdt
---

## DataSheet Institutionnelle — BTC/USDT

> Généré le 30/03/2026 22:20 UTC | Prix : `66809.300000` | ATR : `448.105000` (0.67%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR BTC/USDT: N/A

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
| Direction | **NEUTRAL** | slope 20p = -0.46% |
| Type | **RANGING** | volatilité low |
| Phase (Wyckoff) | **ACCUMULATION** | EMA20 = 67075.9809 |
| Volatilité ATR% | `0.67%` | 🟢 Faible |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `6.7%` — 🟢 Faible (<30%) |
| Percentile session | `86e percentile` |
| POC (Point of Control) | `67644.68` |
| Value Area High (VAH) | `67695.662` |
| Value Area Low (VAL) | `66472.094` |
| HVN (High Vol. Nodes) | `66625.0400` | `66828.9680` | `67542.7160` |
| LVN (Low Vol. Nodes) | `67440.7520` |

---

### 3. STRUCTURE DE MARCHÉ
> **🔴 Bearish (LH/LL)**



| Swing Highs récents | `67130.5000` | `66988.0100` | `66793.8300` | `68169.6500` |
|---|---|
| **Swing Lows récents** | `66281.4000` | `66418.0000` | `66158.2600` | `65000.0000` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `67104.362500` | `100/100` | `4` touches |
| R2 | `68169.650000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `66285.886667` | `75/100` | `3` touches |
| S2 | `65000.000000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `67209.72` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `66349.7` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @66519.6300 | `66283.380000` | `66755.880000` | `66519.630000` |
| 🟢 OB Bullish @65855.0600 | `65000.000000` | `66710.120000` | `65855.060000` |
| 🔴 OB Bearish @67476.6100 | `67088.730000` | `67864.490000` | `67476.610000` |

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
> POSITIVE — score `+28.9` sur 3 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `20/100` |
| Fondamental | `bullish` | `29/100` |
| Régime | `neutral` | — |
| Structure | `bearish` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Fondamental bullish

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
**Entrée** : LONG @ 66285.886667 | SHORT @ 67104.362500
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
| Votes LONG / SHORT / HOLD | `17%` / `40%` / `43%` |
| Probabilité haussière | `41%` |
| Probabilité baissière | `38%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `20%` |

**Note comportementale** : _📊 Distribution équilibrée (17%L / 40%S / 43%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_BTC_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
