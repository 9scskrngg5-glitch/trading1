"""
Predictive Layer — XGBoost + Hebbian weighting pour signaux prédictifs.
Équivalent cortex préfrontal : planification et prédiction.
"""
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("ORACLE.PredictiveLayer")


@dataclass
class Prediction:
    symbol: str
    direction: str       # "LONG", "SHORT", "NEUTRAL"
    probability: float   # 0.0 - 1.0
    confidence: float    # calibrated confidence
    features_used: list
    model_version: str


# Mapping classe → direction pour multi:softprob
_CLASS_TO_DIR = {0: "SHORT", 1: "NEUTRAL", 2: "LONG"}
_DIR_TO_CLASS = {"SHORT": 0, "NEUTRAL": 1, "LONG": 2}


class PredictiveLayer:
    """
    Couche prédictive XGBoost multiclass (LONG / NEUTRAL / SHORT).

    Modèle : multi:softprob, 3 classes :
      0 = SHORT  (-1 dans les labels d'entraînement)
      1 = NEUTRAL ( 0)
      2 = LONG   (+1)

    Retourne la probabilité de chaque classe ; la direction gagnante
    n'est retenue que si sa confiance dépasse 40 %.
    En l'absence de modèle entraîné → heuristiques calibrées.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path
        self._model_type: str = "multiclass"   # "multiclass" | "binary" (legacy)
        self.feature_names = [
            "rsi", "macd", "volume_ratio", "bb_position",
            "price_change_pct", "trend_score", "orderbook_imbalance"
        ]
        if model_path:
            self._load_model(model_path)

    def _load_model(self, path: str) -> None:
        try:
            import xgboost as xgb
            self.model = xgb.Booster()
            self.model.load_model(path)
            # Détecter le type de modèle via les attributs du booster
            cfg = self.model.save_config()
            self._model_type = "binary" if "binary:logistic" in cfg else "multiclass"
            logger.info(f"PredictiveLayer: modèle chargé depuis {path} (type={self._model_type})")
        except Exception as e:
            logger.warning(f"PredictiveLayer: impossible de charger le modèle ({e}) — mode heuristique")

    def predict_heuristic(self, features: dict) -> Prediction:
        """Heuristique calibrée quand XGBoost n'est pas disponible."""
        rsi = features.get("rsi", 50.0)
        macd = features.get("macd", 0.0)
        bb_pos = features.get("bb_position", 0.0)
        trend_score = features.get("trend_score", 0.0)
        ob_imbalance = features.get("orderbook_imbalance", 0.0)

        long_score = 0.0
        short_score = 0.0

        if rsi < 35:
            long_score += 0.30
        elif rsi > 65:
            short_score += 0.30

        if macd > 0:
            long_score += 0.20
        elif macd < 0:
            short_score += 0.20

        if bb_pos < -0.6:
            long_score += 0.20
        elif bb_pos > 0.6:
            short_score += 0.20

        if trend_score > 0:
            long_score += 0.15 * trend_score
        elif trend_score < 0:
            short_score += 0.15 * abs(trend_score)

        if ob_imbalance > 0.3:
            long_score += 0.15
        elif ob_imbalance < -0.3:
            short_score += 0.15

        if long_score > short_score and long_score > 0.4:
            direction = "LONG"
            prob = min(0.95, long_score)
        elif short_score > long_score and short_score > 0.4:
            direction = "SHORT"
            prob = min(0.95, short_score)
        else:
            direction = "NEUTRAL"
            prob = 0.5

        confidence = min(1.0, max(long_score, short_score))
        return Prediction(
            symbol=features.get("symbol", "UNKNOWN"),
            direction=direction, probability=prob,
            confidence=confidence, features_used=list(features.keys()),
            model_version="heuristic_v1"
        )

    def train(self, features_list: list, labels: list, save_path: str = None) -> bool:
        """
        Entraîne XGBoost multiclass sur des données historiques labelisées.

        features_list : liste de dicts (mêmes clés que self.feature_names)
        labels        : liste de int/float
                          +1  → LONG  (classe 2)
                           0  → NEUTRAL (classe 1)
                          -1  → SHORT (classe 0)
        save_path     : chemin de sauvegarde (remplace self.model_path si fourni)
        Retourne True si l'entraînement a réussi.
        """
        try:
            import xgboost as xgb
            import numpy as np
        except ImportError:
            logger.error("PredictiveLayer.train(): xgboost non installé (pip install xgboost)")
            return False

        if len(features_list) != len(labels) or len(features_list) < 10:
            logger.warning(f"PredictiveLayer.train(): données insuffisantes ({len(features_list)} exemples)")
            return False

        try:
            X = np.array(
                [[f.get(feat, 0.0) for feat in self.feature_names] for f in features_list],
                dtype=float,
            )
            # Labels : -1→0 (SHORT), 0→1 (NEUTRAL), +1→2 (LONG)
            y = np.array(
                [2 if lbl > 0 else (0 if lbl < 0 else 1) for lbl in labels],
                dtype=int,
            )

            dtrain = xgb.DMatrix(X, label=y, feature_names=self.feature_names)
            params = {
                "objective": "multi:softprob",
                "num_class": 3,
                "eval_metric": "merror",
                "max_depth": 4,
                "eta": 0.1,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "seed": 42,
            }
            self.model = xgb.train(
                params, dtrain,
                num_boost_round=100,
                verbose_eval=False,
            )
            self._model_type = "multiclass"

            path = save_path or self.model_path
            if path:
                self.model.save_model(path)
                logger.info(f"PredictiveLayer: modèle sauvegardé → {path}")

            counts = {d: int((y == c).sum()) for d, c in _DIR_TO_CLASS.items()}
            logger.info(
                f"PredictiveLayer: entraînement OK — {len(features_list)} exemples | "
                f"LONG={counts['LONG']} NEUTRAL={counts['NEUTRAL']} SHORT={counts['SHORT']}"
            )
            return True
        except Exception as e:
            logger.error(f"PredictiveLayer.train(): erreur XGBoost — {e}")
            return False

    def predict(self, features: dict) -> Prediction:
        if self.model is None:
            return self.predict_heuristic(features)
        try:
            import xgboost as xgb
            import numpy as np
            feature_vec = [features.get(f, 0.0) for f in self.feature_names]
            dmatrix = xgb.DMatrix(np.array([feature_vec]), feature_names=self.feature_names)

            if self._model_type == "multiclass":
                # multi:softprob → tableau [p_SHORT, p_NEUTRAL, p_LONG] par sample
                probs = self.model.predict(dmatrix).reshape(-1, 3)[0]
                pred_class = int(np.argmax(probs))
                direction = _CLASS_TO_DIR[pred_class]
                confidence = float(probs[pred_class])
                # Si la meilleure classe est NEUTRAL et faible confiance → NEUTRAL
                if pred_class == 1 or confidence < 0.40:
                    direction = "NEUTRAL"
                    confidence = float(probs[1])
                prob = float(probs[2])  # p(LONG) pour compatibilité
            else:
                # Legacy binary:logistic
                prob = float(self.model.predict(dmatrix)[0])
                if prob > 0.60:
                    direction = "LONG"
                elif prob < 0.40:
                    direction = "SHORT"
                else:
                    direction = "NEUTRAL"
                confidence = abs(prob - 0.5) * 2

            return Prediction(
                symbol=features.get("symbol", "UNKNOWN"),
                direction=direction, probability=prob,
                confidence=confidence,
                features_used=self.feature_names,
                model_version=f"xgboost_{self._model_type}",
            )
        except Exception as e:
            logger.error(f"PredictiveLayer XGBoost error: {e} — fallback heuristique")
            return self.predict_heuristic(features)
