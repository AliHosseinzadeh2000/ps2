"""Automated model retraining from collected data."""

import asyncio
from pathlib import Path
from typing import Optional

import pandas as pd

from app.ai.trainer import ModelTrainer
from app.core.config import AIConfig
from app.core.logging import get_logger
from app.data.storage import combine_ohlc_data, load_trade_data

logger = get_logger(__name__)


class ModelRetrainer:
    """Automated model retraining from collected trade and OHLC data."""

    def __init__(self, config: Optional[AIConfig] = None) -> None:
        """
        Initialize model retrainer.

        Args:
            config: AI configuration
        """
        self.config = config or AIConfig()
        self.trainer = ModelTrainer(self.config)
        self._retraining_task: Optional[asyncio.Task] = None

    async def retrain_from_collected_data(
        self,
        data_dir: str = "data",
        symbols: Optional[list[str]] = None,
        exchanges: Optional[list[str]] = None,
    ) -> bool:
        """
        Retrain models from collected trade and OHLC data.

        Args:
            data_dir: Data directory path
            symbols: List of symbols to use (None for all)
            exchanges: List of exchanges to use (None for all)

        Returns:
            True if retraining successful
        """
        try:
            # Load trade data
            trade_data = self._load_trade_data_for_training(data_dir, exchanges)
            if trade_data is None or len(trade_data) < self.config.min_training_samples:
                logger.warning(
                    f"Insufficient training data: {len(trade_data) if trade_data is not None else 0} samples "
                    f"(minimum: {self.config.min_training_samples})"
                )
                return False

            # Prepare training data
            # For classification: use 'used_maker' as label
            # For regression: use 'price' or calculate next_price from OHLC

            # Train classifier if we have maker/taker labels
            if "used_maker" in trade_data.columns:
                # Prepare DataFrame: features + label
                # Extract feature columns (all except metadata columns)
                metadata_cols = [
                    "timestamp",
                    "order_id",
                    "symbol",
                    "side",
                    "quantity",
                    "price",
                    "fees",
                    "profit_loss",
                    "execution_time",
                    "used_maker",
                    "success",
                    "exchange",
                ]
                feature_cols = [col for col in trade_data.columns if col not in metadata_cols]

                # Create training DataFrame with features and label
                training_df = trade_data[feature_cols + ["used_maker"]].copy()
                # Convert used_maker to binary (1 for maker, 0 for taker)
                training_df["used_maker"] = training_df["used_maker"].astype(int)

                classifier_model, classifier_metrics, feature_names = (
                    self.trainer.train_classifier_from_dataframe(
                        training_df,
                        label_column="used_maker",
                    )
                )
                # Save classifier
                from app.ai.model import TradingModel

                trading_model = TradingModel(self.config)
                trading_model.set_classifier(classifier_model, feature_names)
                trading_model.save()
                logger.info(
                    f"Retrained classifier: accuracy={classifier_metrics.get('accuracy', 0):.4f}"
                )

            # Train regressor if we have price data
            # This would require OHLC data to predict next price
            # For now, we'll skip regression retraining as it requires more complex data preparation

            return True
        except Exception as e:
            logger.error(f"Error in automated retraining: {e}", exc_info=True)
            return False

    def _load_trade_data_for_training(
        self, data_dir: str, exchanges: Optional[list[str]]
    ) -> Optional[pd.DataFrame]:
        """
        Load and combine trade data for training.

        Args:
            data_dir: Data directory path
            exchanges: List of exchanges to load (None for all)

        Returns:
            Combined DataFrame or None if no data
        """
        all_data = []

        data_path = Path(data_dir) / "trades"
        exchange_dirs = [data_path / e for e in exchanges] if exchanges else data_path.iterdir()

        for exchange_dir in exchange_dirs:
            if not exchange_dir.is_dir():
                continue

            try:
                # Load most recent trade file
                files = sorted(exchange_dir.glob("trades_*.csv"), reverse=True)
                if files:
                    df = pd.read_csv(files[0])
                    df["exchange"] = exchange_dir.name
                    all_data.append(df)
            except Exception as e:
                logger.warning(f"Error loading trade data from {exchange_dir}: {e}")

        if not all_data:
            return None

        combined = pd.concat(all_data, ignore_index=True)
        logger.info(f"Loaded {len(combined)} trade records for retraining")
        return combined

    async def start_auto_retraining(self) -> None:
        """Start automated retraining task."""
        if not self.config.auto_retrain_enabled:
            logger.info("Auto-retraining is disabled")
            return

        if self._retraining_task and not self._retraining_task.done():
            logger.warning("Auto-retraining already running")
            return

        self._retraining_task = asyncio.create_task(self._retraining_loop())
        logger.info(
            f"Started auto-retraining (interval: {self.config.auto_retrain_interval_hours} hours)"
        )

    async def stop_auto_retraining(self) -> None:
        """Stop automated retraining task."""
        if self._retraining_task:
            self._retraining_task.cancel()
            try:
                await self._retraining_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped auto-retraining")

    async def _retraining_loop(self) -> None:
        """Internal retraining loop."""
        interval_seconds = self.config.auto_retrain_interval_hours * 3600

        while True:
            try:
                await asyncio.sleep(interval_seconds)
                logger.info("Starting scheduled model retraining...")
                success = await self.retrain_from_collected_data()
                if success:
                    logger.info("Model retraining completed successfully")
                else:
                    logger.warning("Model retraining failed or insufficient data")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in retraining loop: {e}", exc_info=True)

