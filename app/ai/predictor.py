"""Unified AI predictor for maker/taker decisions and price forecasting."""

from typing import Optional, Tuple

import numpy as np

from app.ai.features import combine_features, extract_orderbook_features
from app.ai.model import TradingModel
from app.core.logging import get_logger
from app.exchanges.base import OrderBook

logger = get_logger(__name__)


class TradingPredictor:
    """Unified predictor that combines classification and regression predictions."""

    def __init__(self, model: TradingModel) -> None:
        """
        Initialize trading predictor.

        Args:
            model: TradingModel instance with loaded classifier and/or regressor
        """
        self.model = model

    def predict_from_orderbook(
        self,
        orderbook: OrderBook,
        ohlc_features: Optional[dict] = None,
        threshold: Optional[float] = None,
    ) -> Tuple[bool, float, float]:
        """
        Predict maker/taker decision and price from orderbook.

        Args:
            orderbook: OrderBook object
            ohlc_features: Optional OHLC features dictionary
            threshold: Prediction threshold for classification

        Returns:
            Tuple of (is_maker: bool, probability: float, predicted_price: float)
        """
        try:
            # Extract features
            orderbook_features = extract_orderbook_features(orderbook)
            feature_vector = combine_features(orderbook_features, ohlc_features)

            # Get predictions
            is_maker, probability, predicted_price = self.model.predict_combined(
                feature_vector, threshold
            )

            return is_maker, probability, predicted_price
        except Exception as e:
            logger.error(f"Error in prediction from orderbook: {e}")
            # Fallback to taker
            return False, 0.0, 0.0

    def predict_from_features(
        self,
        features: np.ndarray,
        threshold: Optional[float] = None,
    ) -> Tuple[bool, float, float]:
        """
        Predict maker/taker decision and price from feature vector.

        Args:
            features: Feature vector (1D or 2D array)
            threshold: Prediction threshold for classification

        Returns:
            Tuple of (is_maker: bool, probability: float, predicted_price: float)
        """
        try:
            return self.model.predict_combined(features, threshold)
        except Exception as e:
            logger.error(f"Error in prediction from features: {e}")
            return False, 0.0, 0.0

    def should_use_maker(
        self,
        orderbook: OrderBook,
        ohlc_features: Optional[dict] = None,
        threshold: Optional[float] = None,
    ) -> bool:
        """
        Quick check if maker order should be used.

        Args:
            orderbook: OrderBook object
            ohlc_features: Optional OHLC features dictionary
            threshold: Prediction threshold

        Returns:
            True if maker order should be used
        """
        is_maker, _, _ = self.predict_from_orderbook(orderbook, ohlc_features, threshold)
        return is_maker

    def predict_optimal_price(
        self,
        orderbook: OrderBook,
        ohlc_features: Optional[dict] = None,
        base_price: Optional[float] = None,
    ) -> float:
        """
        Predict optimal limit order price.

        Args:
            orderbook: OrderBook object
            ohlc_features: Optional OHLC features dictionary
            base_price: Base price to adjust (uses mid_price if None)

        Returns:
            Predicted optimal price
        """
        try:
            # Extract features
            orderbook_features = extract_orderbook_features(orderbook)
            feature_vector = combine_features(orderbook_features, ohlc_features)

            # Get price prediction
            predicted_price = self.model.predict_price(feature_vector)

            # If regressor not loaded, use base price or mid price
            if predicted_price == 0.0 and not self.model.is_regressor_loaded():
                if base_price:
                    return base_price
                return orderbook_features.get("mid_price", 0.0)

            return predicted_price
        except Exception as e:
            logger.error(f"Error predicting optimal price: {e}")
            # Fallback to base price or mid price
            if base_price:
                return base_price
            try:
                orderbook_features = extract_orderbook_features(orderbook)
                return orderbook_features.get("mid_price", 0.0)
            except Exception:
                return 0.0

    def is_ready(self) -> bool:
        """
        Check if predictor is ready (has at least classifier loaded).

        Returns:
            True if ready
        """
        return self.model.is_classifier_loaded()

    def has_price_prediction(self) -> bool:
        """
        Check if price prediction is available.

        Returns:
            True if regressor is loaded
        """
        return self.model.is_regressor_loaded()




