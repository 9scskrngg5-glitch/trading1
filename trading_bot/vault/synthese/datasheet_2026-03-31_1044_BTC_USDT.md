---
date: 2026-03-31 10:44 UTC
agent: SynthesisAgent
asset: BTC/USDT
regime: bearish
market_type: trending
phase: markdown
volatility: medium
structure: HH_HL
bos: true
bias: balanced
coherence: 75
realized_vol: 7.9
manip_risk: 0.0
compound_mode: startup
tags:
- synthese
- datasheet
- btc-usdt
---

## DataSheet Institutionnelle — BTC/USDT

> Généré le 31/03/2026 10:44 UTC | Prix : `66124.990000` | ATR : `538.905000` (0.81%)

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
| Direction | **BEARISH** | slope 20p = -2.47% |
| Type | **TRENDING** | volatilité medium |
| Phase (Wyckoff) | **MARKDOWN** | EMA20 = 67174.8440 |
| Volatilité ATR% | `0.81%` | 🟡 Moyenne |
| Force de tendance | `12/100` | |

---

### 2. VIX CRYPTO & VOLUME PROFILE
| Indicateur | Valeur |
|---|---|
| Volatilité réalisée (VIX) | `7.9%` — 🟢 Faible (<30%) |
| Percentile session | `66e percentile` |
| POC (Point of Control) | `67578.884` |
| Value Area High (VAH) | `67943.43` |
| Value Area Low (VAL) | `66589.402` |
| HVN (High Vol. Nodes) | `66641.4800` | `66745.6360` | `67578.8840` |
| LVN (Low Vol. Nodes) | `66433.1680` | `66953.9480` |

---

### 3. STRUCTURE DE MARCHÉ
> **🟢 Bullish (HH/HL)**
> 🔔 **BREAK OF STRUCTURE** détecté à `66419.79`
> 🔄 **CHoCH** — potentiel retournement

| Swing Highs récents | `66988.0100` | `66793.8300` | `68169.6500` | `68408.3700` |
|---|---|
| **Swing Lows récents** | `66158.2600` | `65000.0000` | `66233.1300` | `66419.7900` |

---

### 4. ZONES CLÉS
#### Résistances
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| R1 | `66970.780000` | `75/100` | `3` touches |
| R2 | `68289.010000` | `50/100` | `2` touches |

#### Supports
| Niveau | Prix | Force | Validations |
|---|---|---|---|
| S1 | `65000.000000` | `25/100` | `1` touches |

#### Zones de Liquidité
| Type | Prix | Description |
|---|---|---|
| BSL (Buy-Side) | `67059.255` | Stops d'acheteurs — cible de stop-hunt |
| SSL (Sell-Side) | `—` | Stops de vendeurs — cible de stop-hunt |

---

### 5. ORDER BLOCKS INSTITUTIONNELS
| OB | Low | High | Mid |
|---|---|---|---|
| 🔴 OB Bearish @66629.0050 | `66461.000000` | `66797.010000` | `66629.005000` |
| 🟢 OB Bullish @65855.0600 | `65000.000000` | `66710.120000` | `65855.060000` |
| 🔴 OB Bearish @67476.6100 | `67088.730000` | `67864.490000` | `67476.610000` |
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
> NEUTRAL — score `-18.8` sur 5 signaux fondamentaux

#### Cohérence Inter-Agents
> 🟡 Cohérence MODÉRÉE (75/100) — légères divergences

| Source | Direction | Confiance |
|---|---|---|
| Technique | `bearish` | `10/100` |
| Fondamental | `bearish` | `16/100` |
| Régime | `bearish` | — |
| Structure | `bullish` | — |

**Divergences :**
- ⚠️  Technique bearish ≠ Structure bullish
- 🔔 Break of Structure à 66419.79 — recalibrage recommandé
- 🔔 CHoCH — potentiel retournement de tendance

#### Détection de Biais
> ✅ Équilibré : 45% long / 55% short sur 22 signaux

| Direction | Signaux | % |
|---|---|---|
| LONG | `10` | `46%` |
| SHORT | `12` | `55%` |
| Sévérité | `none` | |

---

### 8. STRATÉGIES MULTI-HORIZON

#### ⚡ Scalping (5m–15m)
**Direction** : `SHORT`
**Entrée** : 66124.990000 (niveau courant)
**SL** : `66340.552` | **TP** : `65693.866` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Entry sur rebond vers résistance la plus proche_
**Qualité** : 🟢 Favorable

#### ⚡ Scalping Contrarian
**Direction** : `LONG`
**Entrée** : 65000.0 (support S1)
**SL** : `64784.438` | **TP** : `65431.124` | **R:R** : `1:2.0`
**Timeframe** : `5m–15m`
**Condition** : _Rebond sur support avec volume haussier_
**Qualité** : 🟡 Contre-tendance — prudence
**Note mémoire** : _Setup complémentaire pour équilibrer le biais_

---

#### 📊 Intraday (1h–4h)
**Direction** : `SHORT`
**Entrée** : Rebond vers 66394.4425 ou OB bearish
**SL** : `66663.895` | **TP** : `65047.18` | **R:R** : `1:2.0`
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
| Direction crowd | `NEUTRAL` |
| Votes LONG / SHORT / HOLD | `37%` / `34%` / `29%` |
| Probabilité haussière | `55%` |
| Probabilité baissière | `30%` |
| Signal Contrarian (>75%) | Non |
| Divergence vs Technique | `+25` (-50 à +50) |
| Risque manipulation crowd | `14%` |

**Note comportementale** : _✅ Alignement foule-technique — 37% LONG avec support structurel. Consensus comportemental renforce l'analyse primaire._

---

### Liens
[[decisions/convergence_BTC_USDT]]
[[config/SynthesisAgent_memory]]
[[config/CompoundAgent_state]]
