---
date: 2026-03-31 02:52 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: neutral
market_type: trending
phase: transition
volatility: medium
structure: mixed
bos: true
bias: long_bias
coherence: 25
realized_vol: 9.94
manip_risk: 20.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 31/03/2026 02:52 UTC | Prix : `2073.000000` | ATR : `23.675000` (1.14%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR ETH/USDT: N/A

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
| Direction | **NEUTRAL** | slope 20p = +1.50% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **TRANSITION** | EMA20 = 2042.1428 |
| Volatilité ATR% | `1.14%` | 🟡 Moyenne |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.9%` — 🟢 Faible (<30%) |
| Percentile session | `73e percentile` |
| POC (Point of Control) | `2072.02625` |
| Value Area High (VAH) | `2074.54` |
| Value Area Low (VAL) | `2004.155` |
| HVN (High Vol. Nodes) | `1976.5038` | `1996.6137` | `2061.9713` |
| LVN (Low Vol. Nodes) | `1991.5863` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟡 Structure mixte**
> 🔔 **BREAK OF STRUCTURE** détecté à `2049.1`
> 🔄 **CHoCH** — potentiel retournement

| Swing Highs récents | `2003.6100` | `2009.4800` | `2085.0000` | `2049.1000` |
|---|---|
| **Swing Lows récents** | `1997.6700` | `1983.5600` | `1938.8200` | `2013.3300` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `2085.000000` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `1997.670000` | `25/100` | `1` touches |
| S2 | `1986.600000` | `50/100` | `2` touches |
| S3 | `1938.820000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `—` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @1972.6650 | `1938.820000` | `2006.510000` | `1972.665000` |
| 🟢 OB Bullish @2058.5000 | `2053.870000` | `2063.130000` | `2058.500000` |
| 🔴 OB Bearish @2070.9150 | `2061.910000` | `2079.920000` | `2070.915000` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `20/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ✅ Non |
| Fake Wall OB | ⚠️ OUI |

- 🧱 Fake wall potentiel côté ASK — OB imbalance -0.56 mais prix monte

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> POSITIVE — score `+33.4` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (25/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `18/100` |
| Fondamental | `bullish` | `28/100` |
| Régime | `neutral` | — |
| Structure | `neutral` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Fondamental bullish
- 🔔 Break of Structure à 2049.1 — recalibrage recommandé
- 🔔 CHoCH — potentiel retournement de tendance

#### Détection de Biais
> ⚠️  BIAIS LONG DÉTECTÉ (77% des signaux) — Rechercher activement des setups SHORT. Réduire la taille des positions LONG de 20%.

| Direction | Signaux | % |
|---|---|---|
| LONG | `23` | `77%` |
| SHORT | `7` | `23%` |
| Sévérité | `moderate` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `RANGE`
**Entrée** : LONG @ 1997.670000 | SHORT @ 2085.000000
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
| Votes LONG / SHORT / HOLD | `33%` / `43%` / `24%` |
| Probabilité haussière | `47%` |
| Probabilité baissière | `41%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `22%` |

**Note comportementale** : _📊 Distribution équilibrée (33%L / 43%S / 24%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_ETH_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
