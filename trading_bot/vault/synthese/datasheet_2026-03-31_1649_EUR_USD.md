---
date: 2026-03-31 16:49 UTC
agent: SynthesisAgent
asset: EUR/USD
regime: neutral
market_type: ranging
phase: distribution
volatility: low
structure: mixed
bos: true
bias: balanced
coherence: 25
realized_vol: 1.37
manip_risk: 25.0
compound_mode: startup
tags:
- synthese
- datasheet
- eur-usd
---

## DataSheet Institutionnelle — EUR/USD

> Généré le 31/03/2026 16:49 UTC | Prix : `1.152400` | ATR : `0.001614` (0.14%)

---

### 0. CONTEXTE MÉMOIRE (Vault)
> Mode: STARTUP | Risque: 2.0% | Confiance min: 55 | WR EUR/USD: N/A | HistTech: 2n | HistFund: 0n | Leçons: 1n

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
| Direction | **NEUTRAL** | slope 20p = +0.48% |
| Type | **RANGING** | volatilité low |
| Phase (Wyckoff) | **DISTRIBUTION** | EMA20 = 1.1495 |
| Volatilité ATR% | `0.14%` | 🟢 Faible |
| Force de tendance | `0/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `1.4%` — 🟢 Faible (<30%) |
| Percentile session | `96e percentile` |
| POC (Point of Control) | `1.147317` |
| Value Area High (VAH) | `1.15076` |
| Value Area Low (VAL) | `1.1459` |
| HVN (High Vol. Nodes) | `1.1473` | `1.1489` | `1.1502` |
| LVN (Low Vol. Nodes) | `1.1485` | `1.1497` | `1.1522` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟡 Structure mixte**
> 🔔 **BREAK OF STRUCTURE** détecté à `1.1498`
> 🔄 **CHoCH** — potentiel retournement

| Swing Highs récents | `1.1510` | `1.1526` | `1.1504` | `1.1498` |
|---|---|
| **Swing Lows récents** | `1.1450` | `1.1456` | `1.1469` | `1.1463` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `1.152600` | `25/100` | `1` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `1.147067` | `100/100` | `6` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `—` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `1.1493` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🟢 OB Bullish @1.1462 | `1.145000` | `1.147300` | `1.146150` |
| 🟢 OB Bullish @1.1464 | `1.146100` | `1.146800` | `1.146450` |
| 🟢 OB Bullish @1.1472 | `1.146600` | `1.147800` | `1.147200` |

---

### 6. DÉTECTION DE MANIPULATION
> Risque global : `25/75`

| Signal | Détecté |
|---|---|
| Stop-Hunt | ✅ Non |
| Wash Trading | ⚠️ OUI |
| Fake Wall OB | ✅ Non |

- 🔄 Wash trading probable — volume 3.0×avg, mouvement 0.095%
- ⚡ Risque de manipulation modéré — surveiller les niveaux de liquidité

---

### 7. SENTIMENT & COHÉRENCE
#### Sentiment Global
> NEUTRAL — score `+0.0` sur 1 signaux fondamentaux

#### Cohérence Inter-Agents
> 🔴 Cohérence FAIBLE (25/100) — divergences inter-agents, prudence

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bullish` | `27/100` |
| Fondamental | `neutral` | `0/100` |
| Régime | `neutral` | — |
| Structure | `neutral` | — |

**Divergences :**
- 🔔 Break of Structure à 1.1498 — recalibrage recommandé
- 🔔 CHoCH — potentiel retournement de tendance

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
**Entrée** : LONG @ 1.147067 | SHORT @ 1.152600
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
| Votes LONG / SHORT / HOLD | `43%` / `24%` / `33%` |
| Probabilité haussière | `62%` |
| Probabilité baissière | `22%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+0` (-50 à +50) |
| Risque manipulation crowd | `0%` |

**Note comportementale** : _📊 Distribution équilibrée (43%L / 24%S / 33%H). Pas de consensus clair — marché indécis selon le crowd._

---

### Liens
[[decisions/convergence_EUR_USD]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
