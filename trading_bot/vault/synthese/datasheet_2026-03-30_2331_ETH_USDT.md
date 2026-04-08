---
date: 2026-03-30 23:31 UTC
agent: SynthesisAgent
asset: ETH/USDT
regime: neutral
market_type: ranging
phase: accumulation
volatility: medium
structure: mixed
bos: false
bias: balanced
coherence: 25
realized_vol: 9.43
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- eth-usdt
---

## DataSheet Institutionnelle — ETH/USDT

> Généré le 30/03/2026 23:31 UTC | Prix : `2033.080000` | ATR : `19.340000` (0.95%)

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
| Direction | **NEUTRAL** | slope 20p = -0.14% |
| Type | **RANGING** | volatilité medium |
| Phase (Wyckoff) | **ACCUMULATION** | EMA20 = 2040.3951 |
| Volatilité ATR% | `0.95%` | 🟡 Moyenne |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `9.4%` — 🟢 Faible (<30%) |
| Percentile session | `76e percentile` |
| POC (Point of Control) | `2072.02625` |
| Value Area High (VAH) | `2074.54` |
| Value Area Low (VAL) | `1999.1275` |
| HVN (High Vol. Nodes) | `1996.6137` | `2026.7787` | `2061.9713` |
| LVN (Low Vol. Nodes) | `1991.5863` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟡 Structure mixte**



| Swing Highs récents | `2008.1600` | `2003.6100` | `2009.4800` | `2085.0000` |
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
| 🔴 OB Bearish @2070.9150 | `2061.910000` | `2079.920000` | `2070.915000` |

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
> POSITIVE — score `+35.2` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (25/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `31/100` |
| Fondamental | `bullish` | `30/100` |
| Régime | `neutral` | — |
| Structure | `neutral` | — |

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
| Votes LONG / SHORT / HOLD | `30%` / `32%` / `38%` |
| Probabilité haussière | `51%` |
| Probabilité baissière | `30%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `12%` |

**Note comportementale** : _📊 Distribution équilibrée (30%L / 32%S / 38%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_ETH_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
