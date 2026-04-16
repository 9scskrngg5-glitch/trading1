"""Modèle de base ORACLE v2 avec support PyTorch, calibration et inférence temps réel."""

import numpy as np
import pandas as pd
from typing import Union, Dict, Optional, Tuple
import pickle

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class OracleModel:
    """
    Modèle de base ORACLE v2 pour classification multi-classe ou régression.
    Supporte PyTorch (S2), sauvegarde/chargement, et inférence temps réel.
    """

    def __init__(self, model_type: str = 'sklearn', name: str = 'OracleModel'):
        """
        Initialise le modèle ORACLE.

        Parameters
        ----------
        model_type : str, default 'sklearn'
            Type de modèle : 'sklearn' ou 'torch'
        name : str, default 'OracleModel'
            Nom du modèle
        """
        self.model_type = model_type
        self.name = name
        self.model = None
        self.feature_names = None
        self.is_fitted = False

        # État de calibration
        self._brier_scores = []
        self._parliament_weight = 1.0
        self._n_observations = 0

    def fit(self, X: Union[np.ndarray, pd.DataFrame], y: np.ndarray, **kwargs):
        """
        Entraîne le modèle.

        Parameters
        ----------
        X : array-like
            Features (n_samples, n_features)
        y : array-like
            Targets (n_samples,)
        **kwargs
            Arguments additionnels pour le modèle
        """
        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns.tolist()
            X = X.values
        else:
            X = np.asarray(X)

        # À implémenter par les sous-classes
        self.is_fitted = True

    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Prédiction sur un batch de samples.

        Parameters
        ----------
        X : array-like
            Features (n_samples, n_features)

        Returns
        -------
        predictions : np.ndarray
            Prédictions (n_samples,)
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction.")

        if isinstance(X, pd.DataFrame):
            X = X.values

        return np.zeros(len(X), dtype=int)  # Placeholder

    def predict_single(self, x: Union[np.ndarray, dict]) -> Union[int, float]:
        """
        Prédiction sur un unique sample (utile pour l'inférence temps réel).

        Parameters
        ----------
        x : array-like or dict
            Features d'un single sample. Si dict, clés = noms de features.

        Returns
        -------
        prediction : int or float
            Prédiction pour ce sample.
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction.")

        if isinstance(x, dict):
            # Convertir dict à array en respectant l'ordre des features
            if self.feature_names is None:
                raise ValueError("Feature names not available for dict input.")
            x = np.array([x.get(fname, 0.0) for fname in self.feature_names])
        else:
            x = np.asarray(x)

        # Ajouter dimension batch (1, n_features)
        x_batch = x.reshape(1, -1)
        prediction = self.predict(x_batch)

        return prediction[0]

    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Probabilités de classe (pour les modèles de classification).

        Parameters
        ----------
        X : array-like
            Features

        Returns
        -------
        probabilities : np.ndarray
            Probabilités (n_samples, n_classes)
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction.")

        if isinstance(X, pd.DataFrame):
            X = X.values

        return np.zeros((len(X), 3), dtype=float)  # Placeholder

    def update_calibration(self, y_true: np.ndarray, y_pred: np.ndarray):
        """
        Met à jour l'état de calibration (Brier score, parliament weight).

        Parameters
        ----------
        y_true : array-like
            Labels vrais
        y_pred : array-like
            Prédictions (probabilités ou labels)
        """
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)

        # Si y_pred sont des probabilités, utiliser Brier score
        if y_pred.ndim == 2 and y_pred.shape[1] > 1:
            # Multi-classe : Brier score
            n_classes = y_pred.shape[1]
            y_true_one_hot = np.eye(n_classes)[y_true]
            brier = np.mean((y_pred - y_true_one_hot) ** 2)
        else:
            # Binaire
            brier = np.mean((y_pred - y_true) ** 2)

        self._brier_scores.append(brier)
        self._n_observations += len(y_true)

        # Ajuster parliament_weight en fonction de la calibration
        # Brier score < 0.25 : bon (weight proche de 1.0)
        # Brier score > 0.35 : mauvais (weight doit baisser)
        mean_brier = np.mean(self._brier_scores[-100:])  # Moyenne récente

        if mean_brier < 0.25:
            self._parliament_weight = min(5.0, self._parliament_weight * 1.05)
        elif mean_brier > 0.35:
            self._parliament_weight = max(0.1, self._parliament_weight * 0.95)

    def get_calibration_status(self) -> Dict:
        """
        Retourne le statut de calibration du modèle.

        Returns
        -------
        status : dict
            Dictionnaire avec 'brier_score' (float), 'parliament_weight' (float),
            'n_observations' (int)
        """
        mean_brier = np.mean(self._brier_scores) if self._brier_scores else np.nan

        return {
            'brier_score': mean_brier,
            'parliament_weight': self._parliament_weight,
            'n_observations': self._n_observations,
        }

    def save_torch(self, path: str):
        """
        Sauvegarde le modèle PyTorch (state dict + métadonnées).

        Parameters
        ----------
        path : str
            Chemin du fichier .pt ou .pth

        Raises
        ------
        ValueError
            Si HAS_TORCH est False ou si le modèle n'est pas un nn.Module
        """
        if not HAS_TORCH:
            raise ValueError("PyTorch is not installed.")

        if not isinstance(self.model, nn.Module):
            raise ValueError(f"Model must be nn.Module instance, got {type(self.model)}")

        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'model_class': self.model.__class__.__name__,
            'feature_names': self.feature_names,
            'is_fitted': self.is_fitted,
            'brier_scores': self._brier_scores,
            'parliament_weight': self._parliament_weight,
            'n_observations': self._n_observations,
        }

        torch.save(checkpoint, path)

    def load_torch(self, path: str, model_class=None):
        """
        Charge un modèle PyTorch sauvegardé.

        Parameters
        ----------
        path : str
            Chemin du fichier .pt ou .pth
        model_class : class, optional
            Classe du modèle. Si None, essaie de recréer depuis le checkpoint.

        Raises
        ------
        ValueError
            Si HAS_TORCH est False ou si le checkpoint est invalide
        """
        if not HAS_TORCH:
            raise ValueError("PyTorch is not installed.")

        checkpoint = torch.load(path, map_location='cpu')

        # Restaurer les métadonnées
        self.feature_names = checkpoint.get('feature_names')
        self.is_fitted = checkpoint.get('is_fitted', False)
        self._brier_scores = checkpoint.get('brier_scores', [])
        self._parliament_weight = checkpoint.get('parliament_weight', 1.0)
        self._n_observations = checkpoint.get('n_observations', 0)

        # Charger le modèle
        if model_class is not None:
            self.model = model_class()
        else:
            raise ValueError(
                "model_class must be provided to load the model architecture."
            )

        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()

    def save(self, path: str):
        """
        Sauvegarde le modèle complet (pickle pour sklearn, torch.save pour PyTorch).

        Parameters
        ----------
        path : str
            Chemin du fichier
        """
        if self.model_type == 'torch' and HAS_TORCH and isinstance(self.model, nn.Module):
            self.save_torch(path)
        else:
            # Sauvegarder via pickle
            with open(path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'model_type': self.model_type,
                    'feature_names': self.feature_names,
                    'is_fitted': self.is_fitted,
                    'brier_scores': self._brier_scores,
                    'parliament_weight': self._parliament_weight,
                    'n_observations': self._n_observations,
                }, f)

    def load(self, path: str, model_class=None):
        """
        Charge un modèle sauvegardé (pickle ou torch).

        Parameters
        ----------
        path : str
            Chemin du fichier
        model_class : class, optional
            Classe du modèle (pour torch)
        """
        if path.endswith(('.pt', '.pth')) and HAS_TORCH:
            self.load_torch(path, model_class=model_class)
        else:
            # Charger depuis pickle
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.model_type = data['model_type']
                self.feature_names = data['feature_names']
                self.is_fitted = data['is_fitted']
                self._brier_scores = data.get('brier_scores', [])
                self._parliament_weight = data.get('parliament_weight', 1.0)
                self._n_observations = data.get('n_observations', 0)

    def get_params(self) -> Dict:
        """Retourne les paramètres du modèle."""
        return {
            'model_type': self.model_type,
            'name': self.name,
            'feature_names': self.feature_names,
            'is_fitted': self.is_fitted,
        }
