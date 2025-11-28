"""Performance monitoring and metrics collection."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PredictionMetrics:
    """Metrics for AI predictions."""

    total_predictions: int = 0
    maker_predictions: int = 0
    taker_predictions: int = 0
    correct_predictions: int = 0
    total_profit: float = 0.0
    maker_profit: float = 0.0
    taker_profit: float = 0.0
    avg_confidence: float = 0.0


@dataclass
class TradeMetrics:
    """Metrics for executed trades."""

    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    avg_profit_per_trade: float = 0.0
    win_rate: float = 0.0


class PerformanceMonitor:
    """Monitor AI and trading performance."""

    def __init__(self) -> None:
        """Initialize performance monitor."""
        self.prediction_history: List[Dict] = []
        self.trade_history: List[Dict] = []
        self.start_time = datetime.now()

    def record_prediction(
        self,
        is_maker: bool,
        probability: float,
        actual_outcome: Optional[bool] = None,
        profit: Optional[float] = None,
    ) -> None:
        """
        Record an AI prediction.

        Args:
            is_maker: Whether maker was predicted
            probability: Prediction confidence
            actual_outcome: Actual outcome (True if maker was better, None if unknown)
            profit: Profit from the trade
        """
        record = {
            "timestamp": datetime.now(),
            "is_maker": is_maker,
            "probability": probability,
            "actual_outcome": actual_outcome,
            "profit": profit or 0.0,
        }
        self.prediction_history.append(record)

        # Keep only last 10000 records
        if len(self.prediction_history) > 10000:
            self.prediction_history = self.prediction_history[-10000:]

    def record_trade(
        self,
        success: bool,
        profit: float,
        used_maker: bool,
        execution_time: float,
    ) -> None:
        """
        Record a trade execution.

        Args:
            success: Whether trade was successful
            profit: Profit or loss from trade
            used_maker: Whether maker order was used
            execution_time: Time taken to execute
        """
        record = {
            "timestamp": datetime.now(),
            "success": success,
            "profit": profit,
            "used_maker": used_maker,
            "execution_time": execution_time,
        }
        self.trade_history.append(record)

        # Keep only last 10000 records
        if len(self.trade_history) > 10000:
            self.trade_history = self.trade_history[-10000:]

    def get_prediction_metrics(self, hours: int = 24) -> PredictionMetrics:
        """
        Get prediction metrics for the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            PredictionMetrics object
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [p for p in self.prediction_history if p["timestamp"] >= cutoff]

        if not recent:
            return PredictionMetrics()

        metrics = PredictionMetrics()
        metrics.total_predictions = len(recent)
        metrics.maker_predictions = sum(1 for p in recent if p["is_maker"])
        metrics.taker_predictions = metrics.total_predictions - metrics.maker_predictions

        # Calculate accuracy for predictions with known outcomes
        with_outcomes = [p for p in recent if p["actual_outcome"] is not None]
        if with_outcomes:
            metrics.correct_predictions = sum(
                1 for p in with_outcomes if p["is_maker"] == p["actual_outcome"]
            )

        # Calculate profits
        metrics.total_profit = sum(p["profit"] for p in recent)
        metrics.maker_profit = sum(p["profit"] for p in recent if p["is_maker"])
        metrics.taker_profit = metrics.total_profit - metrics.maker_profit

        # Average confidence
        if recent:
            metrics.avg_confidence = sum(p["probability"] for p in recent) / len(recent)

        return metrics

    def get_trade_metrics(self, hours: int = 24) -> TradeMetrics:
        """
        Get trade metrics for the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            TradeMetrics object
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [t for t in self.trade_history if t["timestamp"] >= cutoff]

        if not recent:
            return TradeMetrics()

        metrics = TradeMetrics()
        metrics.total_trades = len(recent)
        metrics.successful_trades = sum(1 for t in recent if t["success"])
        metrics.failed_trades = metrics.total_trades - metrics.successful_trades

        profits = [t["profit"] for t in recent]
        metrics.total_profit = sum(p for p in profits if p > 0)
        metrics.total_loss = abs(sum(p for p in profits if p < 0))

        if metrics.total_trades > 0:
            metrics.avg_profit_per_trade = sum(profits) / metrics.total_trades
            metrics.win_rate = metrics.successful_trades / metrics.total_trades

        return metrics

    def get_model_confidence_stats(self) -> Dict[str, float]:
        """
        Get statistics about model confidence.

        Returns:
            Dictionary with confidence statistics
        """
        if not self.prediction_history:
            return {}

        recent = self.prediction_history[-1000:]  # Last 1000 predictions
        confidences = [p["probability"] for p in recent]

        return {
            "mean": sum(confidences) / len(confidences) if confidences else 0.0,
            "min": min(confidences) if confidences else 0.0,
            "max": max(confidences) if confidences else 0.0,
            "std": (
                (sum((c - sum(confidences) / len(confidences)) ** 2 for c in confidences) / len(confidences)) ** 0.5
                if confidences
                else 0.0
            ),
        }




