"""XGBoost model wrapper for maker/taker predictions and price forecasting."""

import pickle
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import xgboost as xgb

from app.core.config import AIConfig
from app.core.logging import get_logger

logger = get_logger(__name__)


class TradingModel:
    """XGBoost model for predicting maker vs taker order decisions and price forecasts."""

    def __init__(self, config: Optional[AIConfig] = None) -> None:
        """
        Initialize trading model.

        Args:
            config: AI configuration
        """
        self.config = config or AIConfig()
        # Classification model for maker/taker decision
        self.classifier: Optional[xgb.XGBClassifier] = None
        # Regression model for price prediction
        self.regressor: Optional[xgb.XGBRegressor] = None
        self.feature_names: list[str] = []

    def load(self, model_path: Optional[str] = None) -> bool:
        """
        Load trained model(s) from file.

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
                    # New format: supports both classifier and regressor
                    self.classifier = data.get("classifier")
                    self.regressor = data.get("regressor")
                    # Backward compatibility: check for old "model" key
                    if self.classifier is None and "model" in data:
                        self.classifier = data.get("model")
                    self.feature_names = data.get("feature_names", [])
                else:
                    # Old format: assume it's just the classifier
                    self.classifier = data
                    self.regressor = None
                    self.feature_names = []

            loaded_models = []
            if self.classifier:
                loaded_models.append("classifier")
            if self.regressor:
                loaded_models.append("regressor")
            logger.info(f"Model(s) loaded from {path}: {', '.join(loaded_models)}")
            return True
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def save(self, model_path: Optional[str] = None) -> bool:
        """
        Save trained model(s) to file.

        Args:
            model_path: Path to save model (uses config default if not provided)

        Returns:
            True if saved successfully
        """
        if self.classifier is None and self.regressor is None:
            logger.error("No model to save")
            return False

        path = Path(model_path or self.config.model_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                "classifier": self.classifier,
                "regressor": self.regressor,
                "feature_names": self.feature_names,
            }
            with open(path, "wb") as f:
                pickle.dump(data, f)

            saved_models = []
            if self.classifier:
                saved_models.append("classifier")
            if self.regressor:
                saved_models.append("regressor")
            logger.info(f"Model(s) saved to {path}: {', '.join(saved_models)}")
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
        Predict whether to use maker order (classification).

        Args:
            features: Feature vector (1D or 2D array)
            threshold: Prediction threshold (uses config default if not provided)

        Returns:
            Tuple of (is_maker: bool, probability: float)
        """
        if self.classifier is None:
            logger.warning("Classifier not loaded, defaulting to taker")
            return False, 0.0

        # Ensure features are 2D
        if features.ndim == 1:
            features = features.reshape(1, -1)

        try:
            # Get probability of maker class (assuming class 1 is maker)
            proba = self.classifier.predict_proba(features)[0]
            maker_probability = proba[1] if len(proba) > 1 else proba[0]

            threshold = threshold or self.config.prediction_threshold
            is_maker = maker_probability >= threshold

            return is_maker, float(maker_probability)
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return False, 0.0

    def predict_price(
        self,
        features: np.ndarray,
    ) -> float:
        """
        Predict future price (regression).

        Args:
            features: Feature vector (1D or 2D array)

        Returns:
            Predicted price value
        """
        if self.regressor is None:
            logger.warning("Regressor not loaded, returning 0.0")
            return 0.0

        # Ensure features are 2D
        if features.ndim == 1:
            features = features.reshape(1, -1)

        try:
            predicted_price = self.regressor.predict(features)[0]
            return float(predicted_price)
        except Exception as e:
            logger.error(f"Error making price prediction: {e}")
            return 0.0

    def predict_combined(
        self,
        features: np.ndarray,
        threshold: Optional[float] = None,
    ) -> Tuple[bool, float, float]:
        """
        Predict both maker/taker decision and price forecast.

        Args:
            features: Feature vector (1D or 2D array)
            threshold: Prediction threshold for classification

        Returns:
            Tuple of (is_maker: bool, probability: float, predicted_price: float)
        """
        is_maker, probability = self.predict(features, threshold)
        predicted_price = self.predict_price(features)
        return is_maker, probability, predicted_price

    def predict_batch(
        self,
        features: np.ndarray,
        threshold: Optional[float] = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Predict for multiple samples (classification).

        Args:
            features: Feature matrix (2D array)
            threshold: Prediction threshold

        Returns:
            Tuple of (is_maker_array, probabilities_array)
        """
        if self.classifier is None:
            logger.warning("Classifier not loaded, defaulting to taker")
            return (
                np.zeros(len(features), dtype=bool),
                np.zeros(len(features), dtype=float),
            )

        try:
            proba = self.classifier.predict_proba(features)
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

    def predict_price_batch(
        self,
        features: np.ndarray,
    ) -> np.ndarray:
        """
        Predict prices for multiple samples (regression).

        Args:
            features: Feature matrix (2D array)

        Returns:
            Array of predicted prices
        """
        if self.regressor is None:
            logger.warning("Regressor not loaded, returning zeros")
            return np.zeros(len(features), dtype=float)

        try:
            predicted_prices = self.regressor.predict(features)
            return predicted_prices.astype(float)
        except Exception as e:
            logger.error(f"Error making batch price prediction: {e}")
            return np.zeros(len(features), dtype=float)

    def is_loaded(self) -> bool:
        """
        Check if any model is loaded.

        Returns:
            True if at least one model is loaded
        """
        return self.classifier is not None or self.regressor is not None

    def is_classifier_loaded(self) -> bool:
        """
        Check if classifier is loaded.

        Returns:
            True if classifier is loaded
        """
        return self.classifier is not None

    def is_regressor_loaded(self) -> bool:
        """
        Check if regressor is loaded.

        Returns:
            True if regressor is loaded
        """
        return self.regressor is not None

    def set_classifier(
        self, model: xgb.XGBClassifier, feature_names: list[str]
    ) -> None:
        """
        Set classifier model and feature names (used after training).

        Args:
            model: Trained XGBoost classifier
            feature_names: List of feature names
        """
        self.classifier = model
        self.feature_names = feature_names

    def set_regressor(
        self, model: xgb.XGBRegressor, feature_names: list[str]
    ) -> None:
        """
        Set regressor model and feature names (used after training).

        Args:
            model: Trained XGBoost regressor
            feature_names: List of feature names
        """
        self.regressor = model
        if not self.feature_names:
            self.feature_names = feature_names

    def set_models(
        self,
        classifier: Optional[xgb.XGBClassifier],
        regressor: Optional[xgb.XGBRegressor],
        feature_names: list[str],
    ) -> None:
        """
        Set both models and feature names (used after training).

        Args:
            classifier: Trained XGBoost classifier (optional)
            regressor: Trained XGBoost regressor (optional)
            feature_names: List of feature names
        """
        if classifier:
            self.classifier = classifier
        if regressor:
            self.regressor = regressor
        self.feature_names = feature_names

    # Backward compatibility
    def set_model(self, model: xgb.XGBClassifier, feature_names: list[str]) -> None:
        """
        Set model and feature names (backward compatibility).

        Args:
            model: Trained XGBoost model
            feature_names: List of feature names
        """
        self.set_classifier(model, feature_names)

