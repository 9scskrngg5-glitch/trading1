---
date: 2026-03-31 16:49 UTC
agent: SynthesisAgent
asset: BTC/USDT
regime: neutral
market_type: trending
phase: transition
volatility: medium
structure: HH_HL
bos: false
bias: balanced
coherence: 0
realized_vol: 9.16
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- btc-usdt
---

## DataSheet Institutionnelle — BTC/USDT

> Généré le 31/03/2026 16:49 UTC | Prix : `67585.350000` | ATR : `672.631429` (0.99%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR BTC/USDT: N/A | HistTech: 2n | HistFund: 1n | Leçons: 2n

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
| Direction | **NEUTRAL** | slope 20p = +1.16% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **TRANSITION** | EMA20 = 67035.5949 |
| Volatilité ATR% | `0.99%` | 🟡 Moyenne |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.2%` — 🟢 Faible (<30%) |
| Percentile session | `76e percentile` |
| POC (Point of Control) | `67578.884` |
| Value Area High (VAH) | `67943.43` |
| Value Area Low (VAL) | `66589.402` |
| HVN (High Vol. Nodes) | `66641.4800` | `66745.6360` | `67578.8840` |
| LVN (Low Vol. Nodes) | `66433.1680` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `66988.0100` | `66793.8300` | `68169.6500` | `68408.3700` |
|---|---|
| **Swing Lows récents** | `65000.0000` | `66233.1300` | `66419.7900` | `65998.0500` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `68289.010000` | `50/100` | `2` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `66245.446000` | `100/100` | `5` touches |
| S2 | `65000.000000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `66325.565` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @65855.0600 | `65000.000000` | `66710.120000` | `65855.060000` |
| 🔴 OB Bearish @67476.6100 | `67088.730000` | `67864.490000` | `67476.610000` |
| 🟢 OB Bullish @66836.4100 | `66683.720000` | `66989.100000` | `66836.410000` |
| 🔴 OB Bearish @67590.1700 | `67400.000000` | `67780.340000` | `67590.170000` |

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
**Direction** : `RANGE`
**Entrée** : LONG @ 66245.446000 | SHORT @ 68289.010000
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
| Votes LONG / SHORT / HOLD | `42%` / `22%` / `36%` |
| Probabilité haussière | `57%` |
| Probabilité baissière | `25%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (42%L / 22%S / 36%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_BTC_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
