---
date: 2026-03-31 10:36 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: bearish
market_type: volatile
phase: transition
volatility: medium
structure: HH_HL
bos: true
bias: short_bias
coherence: 75
realized_vol: 11.11
manip_risk: 20.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 31/03/2026 10:36 UTC | Prix : `80.550000` | ATR : `0.967857` (1.20%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR SOL/USDT: N/A | HistTech: 2n | HistFund: 1n | Leçons: 1n

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
| Direction | **BEARISH** | slope 20p = -4.55% |
| Type | **VOLATILE** | volatilité medium |
| Phase (Wyckoff) | **TRANSITION** | EMA20 = 82.9843 |
| Volatilité ATR% | `1.20%` | 🟡 Moyenne |
| Force de tendance | `45/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `11.1%` — 🟢 Faible (<30%) |
| Percentile session | `76e percentile` |
| POC (Point of Control) | `83.82525` |
| Value Area High (VAH) | `84.52` |
| Value Area Low (VAL) | `82.138` |
| HVN (High Vol. Nodes) | `82.6342` | `83.4283` | `83.8252` |
| LVN (Low Vol. Nodes) | `81.6418` | `83.0312` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**
> 🔔 **BREAK OF STRUCTURE** détecté à `82.14`
> 🔄 **CHoCH** — potentiel retournement

| Swing Highs récents | `84.8800` | `84.9900` | `83.6800` | `84.6200` |
|---|---|
| **Swing Lows récents** | `81.1200` | `78.9600` | `81.9600` | `82.1400` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `84.830000` | `75/100` | `3` touches |
| R2 | `82.230000` | `25/100` | `1` touches |
| R3 | `82.840000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `78.960000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `84.935` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `—` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🔴 OB Bearish @82.0800 | `81.720000` | `82.440000` | `82.080000` |
| 🟢 OB Bullish @80.5550 | `78.960000` | `82.150000` | `80.555000` |
| 🔴 OB Bearish @84.3200 | `83.880000` | `84.760000` | `84.320000` |
| 🔴 OB Bearish @83.6100 | `82.600000` | `84.620000` | `83.610000` |
| 🔴 OB Bearish @83.3350 | `82.900000` | `83.770000` | `83.335000` |

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
> NEGATIVE — score `-29.0` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🟡 Cohérence MODÉRÉE (75/100) — légères divergences

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `18/100` |
| Fondamental | `bearish` | `25/100` |
| Régime | `bearish` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Structure bullish
- 🔔 Break of Structure à 82.14 — recalibrage recommandé
- 🔔 CHoCH — potentiel retournement de tendance

#### Détection de Biais
> ⚠️  BIAIS SHORT DÉTECTÉ (100% des signaux) — Rechercher activement des setups LONG. Réduire la taille des positions SHORT de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `0` | `0%` |
| SHORT | `7` | `100%` |
| Sévérité | `critical` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 78.960000 | SHORT @ 84.830000
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `SHORT`
**Entrée** : Rebond vers 81.033929 ou OB bearish
**SL** : `81.517857` | **TP** : `78.614286` | **R:R** : `1:2.0`
**Timeframe** : `1h–4h`
**Condition** : _Confirmation sur 1h : clôture sous l'EMA20_
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
| Direction crowd | `BEARISH` |
| Votes LONG / SHORT / HOLD | `22%` / `46%` / `31%` |
| Probabilité haussière | `39%` |
| Probabilité baissière | `45%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (22%L / 46%S / 31%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_SOL_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
