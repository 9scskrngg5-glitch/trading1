---
date: 2026-03-31 08:11 UTC
agent: SynthesisAgent
asset: SOL/USDT
regime: bearish
market_type: trending
phase: markdown
volatility: medium
structure: HH_HL
bos: false
bias: short_bias
coherence: 75
realized_vol: 9.76
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- sol-usdt
---

## DataSheet Institutionnelle — SOL/USDT

> Généré le 31/03/2026 08:11 UTC | Prix : `83.100000` | ATR : `0.840714` (1.01%)

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
| Direction | **BEARISH** | slope 20p = -1.65% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKDOWN** | EMA20 = 83.3465 |
| Volatilité ATR% | `1.01%` | 🟡 Moyenne |
| Force de tendance | `8/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.8%` — 🟢 Faible (<30%) |
| Percentile session | `66e percentile` |
| POC (Point of Control) | `83.3565` |
| Value Area High (VAH) | `84.52` |
| Value Area Low (VAL) | `82.372` |
| HVN (High Vol. Nodes) | `82.4615` | `82.6405` | `83.3565` |
| LVN (Low Vol. Nodes) | `81.5665` | `82.2825` | `82.9985` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**



| Swing Highs récents | `84.8800` | `84.9900` | `83.6800` | `84.6200` |
|---|---|
| **Swing Lows récents** | `81.1200` | `78.9600` | `81.9600` | `82.1400` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `84.830000` | `75/100` | `3` touches |
| R2 | `83.240000` | `25/100` | `1` touches |
| R3 | `83.680000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `81.930000` | `75/100` | `3` touches |
| S2 | `81.120000` | `25/100` | `1` touches |
| S3 | `78.960000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `84.935` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `82.05` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🔴 OB Bearish @82.9700 | `82.700000` | `83.240000` | `82.970000` |
| 🟢 OB Bullish @80.5550 | `78.960000` | `82.150000` | `80.555000` |
| 🔴 OB Bearish @84.3200 | `83.880000` | `84.760000` | `84.320000` |
| 🔴 OB Bearish @83.6100 | `82.600000` | `84.620000` | `83.610000` |

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
> NEGATIVE — score `-20.1` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🟡 Cohérence MODÉRÉE (75/100) — légères divergences

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `36/100` |
| Fondamental | `bearish` | `17/100` |
| Régime | `bearish` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Structure bullish

#### Détection de Biais
> ⚠️  BIAIS SHORT DÉTECTÉ (73% des signaux) — Rechercher activement des setups LONG. Réduire la taille des positions SHORT de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `8` | `27%` |
| SHORT | `22` | `73%` |
| Sévérité | `moderate` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 81.930000 | SHORT @ 84.830000
**SL** : `En dehors du range` | **TP** : `Extrémité opposée du range` | **R:R** : `1:1.5`
**Timeframe** : `5m–15m`
**Condition** : _Marché en range — jouer les extrémités_
**Qualité** : 🟡 Range confirmé requis



---

#### 📊 Intraday (1h–4h)
**Direction** : `SHORT`
**Entrée** : Rebond vers 83.520357 ou OB bearish
**SL** : `83.940714` | **TP** : `81.418571` | **R:R** : `1:2.0`
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
| Votes LONG / SHORT / HOLD | `21%` / `46%` / `33%` |
| Probabilité haussière | `39%` |
| Probabilité baissière | `44%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `5%` |

**Note comportementale** : _📊 Distribution équilibrée (21%L / 46%S / 33%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_SOL_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
