"""XGBoost model wrapper for maker/taker predictions."""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import xgboost as xgb

from app.core.config import AIConfig
from app.core.logging import get_logger

logger = get_logger(__name__)


class TradingModel:
    """XGBoost model for predicting maker vs taker order decisions."""

    def __init__(self, config: Optional[AIConfig] = None) -> None:
        """
        Initialize trading model.

        Args:
            config: AI configuration
        """
        self.config = config or AIConfig()
        self.model: Optional[xgb.XGBClassifier] = None
        self.feature_names: list[str] = []

    def load(self, model_path: Optional[str] = None) -> bool:
        """
        Load trained model from file.

        Args:
            model_path: Path to model file (uses config default if not provided)

        Returns:
            True if loaded successfully
        """
        path = Path(model_path or self.config.model_path)

        if not path.exists():
            logger.warning(f"Model file not found: {path}")
            return False

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
                if isinstance(data, dict):
                    self.model = data.get("model")
                    self.feature_names = data.get("feature_names", [])
                else:
                    # Assume it's just the model
                    self.model = data
                    self.feature_names = []

            logger.info(f"Model loaded from {path}")
            return True
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def save(self, model_path: Optional[str] = None) -> bool:
        """
        Save trained model to file.

        Args:
            model_path: Path to save model (uses config default if not provided)

        Returns:
            True if saved successfully
        """
        if self.model is None:
            logger.error("No model to save")
            return False

        path = Path(model_path or self.config.model_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                "model": self.model,
                "feature_names": self.feature_names,
            }
            with open(path, "wb") as f:
                pickle.dump(data, f)

            logger.info(f"Model saved to {path}")
            return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    def predict(
        self,
        features: np.ndarray,
        threshold: Optional[float] = None,
    ) -> tuple[bool, float]:
        """
        Predict whether to use maker order.

        Args:
            features: Feature vector (1D or 2D array)
            threshold: Prediction threshold (uses config default if not provided)

        Returns:
            Tuple of (is_maker: bool, probability: float)
        """
        if self.model is None:
            logger.warning("Model not loaded, defaulting to taker")
            return False, 0.0

        # Ensure features are 2D
        if features.ndim == 1:
            features = features.reshape(1, -1)

        try:
            # Get probability of maker class (assuming class 1 is maker)
            proba = self.model.predict_proba(features)[0]
            maker_probability = proba[1] if len(proba) > 1 else proba[0]

            threshold = threshold or self.config.prediction_threshold
            is_maker = maker_probability >= threshold

            return is_maker, float(maker_probability)
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return False, 0.0

    def predict_batch(
        self,
        features: np.ndarray,
        threshold: Optional[float] = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Predict for multiple samples.

        Args:
            features: Feature matrix (2D array)
            threshold: Prediction threshold

        Returns:
            Tuple of (is_maker_array, probabilities_array)
        """
        if self.model is None:
            logger.warning("Model not loaded, defaulting to taker")
            return (
                np.zeros(len(features), dtype=bool),
                np.zeros(len(features), dtype=float),
            )

        try:
            proba = self.model.predict_proba(features)
            maker_probabilities = proba[:, 1] if proba.shape[1] > 1 else proba[:, 0]

            threshold = threshold or self.config.prediction_threshold
            is_maker = maker_probabilities >= threshold

            return is_maker, maker_probabilities
        except Exception as e:
            logger.error(f"Error making batch prediction: {e}")
            return (
                np.zeros(len(features), dtype=bool),
                np.zeros(len(features), dtype=float),
            )

    def is_loaded(self) -> bool:
        """
        Check if model is loaded.

        Returns:
            True if model is loaded
        """
        return self.model is not None

    def set_model(self, model: xgb.XGBClassifier, feature_names: list[str]) -> None:
        """
        Set model and feature names (used after training).

        Args:
            model: Trained XGBoost model
            feature_names: List of feature names
        """
        self.model = model
        self.feature_names = feature_names

