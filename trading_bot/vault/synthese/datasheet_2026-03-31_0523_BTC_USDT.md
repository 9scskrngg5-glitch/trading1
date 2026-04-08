---
date: 2026-03-31 05:23 UTC
agent: SynthesisAgent
asset: BTC/USDT
regime: neutral
market_type: ranging
phase: distribution
volatility: low
structure: HH_HL
bos: false
bias: long_bias
coherence: 50
realized_vol: 7.17
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- btc-usdt
---

## DataSheet Institutionnelle — BTC/USDT

> Généré le 31/03/2026 05:23 UTC | Prix : `67544.010000` | ATR : `514.870714` (0.76%)

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
| Direction | **NEUTRAL** | slope 20p = +0.07% |
| Type | **RANGING** | volatilité low |
| Phase (Wyckoff) | **DISTRIBUTION** | EMA20 = 67281.3359 |
| Volatilité ATR% | `0.76%` | 🟢 Faible |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `7.2%` — 🟢 Faible (<30%) |
| Percentile session | `66e percentile` |
| POC (Point of Control) | `67578.884` |
| Value Area High (VAH) | `67943.43` |
| Value Area Low (VAL) | `66589.402` |
| HVN (High Vol. Nodes) | `66537.3240` | `66641.4800` | `67578.8840` |
| LVN (Low Vol. Nodes) | `66433.1680` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `66988.0100` | `66793.8300` | `68169.6500` | `68408.3700` |
|---|---|
| **Swing Lows récents** | `66158.2600` | `65000.0000` | `66233.1300` | `66419.7900` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `68289.010000` | `50/100` | `2` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `66302.116000` | `100/100` | `5` touches |
| S2 | `65000.000000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `66349.7` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @66519.6300 | `66283.380000` | `66755.880000` | `66519.630000` |
| 🟢 OB Bullish @65855.0600 | `65000.000000` | `66710.120000` | `65855.060000` |
| 🔴 OB Bearish @67476.6100 | `67088.730000` | `67864.490000` | `67476.610000` |
| 🟢 OB Bullish @66836.4100 | `66683.720000` | `66989.100000` | `66836.410000` |

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
> POSITIVE — score `+27.3` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (50/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `12/100` |
| Fondamental | `bullish` | `23/100` |
| Régime | `neutral` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Structure bullish
- ⚠️  Technique bearish ≠ Fondamental bullish

#### Détection de Biais
> ⚠️  BIAIS LONG DÉTECTÉ (80% des signaux) — Rechercher activement des setups SHORT. Réduire la taille des positions LONG de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `24` | `80%` |
| SHORT | `6` | `20%` |
| Sévérité | `moderate` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 66302.116000 | SHORT @ 68289.010000
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
| Votes LONG / SHORT / HOLD | `29%` / `33%` / `38%` |
| Probabilité haussière | `51%` |
| Probabilité baissière | `30%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (29%L / 33%S / 38%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_BTC_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
