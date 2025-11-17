"""Model training pipeline for XGBoost."""

import pickle
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

from app.ai.features import get_feature_names
from app.core.config import AIConfig
from app.core.logging import get_logger

logger = get_logger(__name__)


class ModelTrainer:
    """Trainer for XGBoost trading model."""

    def __init__(self, config: Optional[AIConfig] = None) -> None:
        """
        Initialize model trainer.

        Args:
            config: AI configuration
        """
        self.config = config or AIConfig()

    def load_data(self, data_path: Optional[str] = None) -> pd.DataFrame:
        """
        Load training data from CSV file.

        Args:
            data_path: Path to CSV file (uses config default if not provided)

        Returns:
            DataFrame with training data

        Raises:
            FileNotFoundError: If data file doesn't exist
        """
        path = Path(data_path or self.config.training_data_path)

        if not path.exists():
            raise FileNotFoundError(f"Training data file not found: {path}")

        try:
            df = pd.read_csv(path)
            logger.info(f"Loaded {len(df)} samples from {path}")
            return df
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            raise

    def prepare_features_and_labels(
        self, df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, list[str]]:
        """
        Prepare features and labels from training DataFrame.

        Expected columns:
        - Feature columns (orderbook and OHLC features)
        - 'label' or 'is_maker' column (0 for taker, 1 for maker)

        Args:
            df: Training DataFrame

        Returns:
            Tuple of (features, labels, feature_names)
        """
        # Identify label column
        label_col = None
        for col in ["label", "is_maker", "target"]:
            if col in df.columns:
                label_col = col
                break

        if label_col is None:
            raise ValueError(
                "No label column found. Expected 'label', 'is_maker', or 'target'"
            )

        # Get feature columns (all except label)
        feature_cols = [col for col in df.columns if col != label_col]
        feature_names = sorted(feature_cols)

        # Extract features and labels
        X = df[feature_names].values.astype(np.float32)
        y = df[label_col].values.astype(np.int32)

        # Handle NaN values
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        logger.info(
            f"Prepared {len(X)} samples with {len(feature_names)} features. "
            f"Label distribution: {np.bincount(y)}"
        )

        return X, y, feature_names

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        test_size: float = 0.2,
        random_state: int = 42,
        xgb_params: Optional[dict] = None,
    ) -> Tuple[xgb.XGBClassifier, dict]:
        """
        Train XGBoost model.

        Args:
            X: Feature matrix
            y: Labels (0=taker, 1=maker)
            feature_names: List of feature names
            test_size: Proportion of data for testing
            random_state: Random seed
            xgb_params: XGBoost parameters (uses defaults if not provided)

        Returns:
            Tuple of (trained_model, metrics_dict)
        """
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        logger.info(
            f"Training set: {len(X_train)} samples, "
            f"Test set: {len(X_test)} samples"
        )

        # Default XGBoost parameters
        default_params = {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "max_depth": 6,
            "learning_rate": 0.1,
            "n_estimators": 100,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": random_state,
            "verbosity": 0,
        }

        if xgb_params:
            default_params.update(xgb_params)

        # Train model
        model = xgb.XGBClassifier(**default_params)

        logger.info("Training XGBoost model...")
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_test, y_test)],
            early_stopping_rounds=10,
            verbose=False,
        )

        # Evaluate
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        logger.info(f"Test accuracy: {accuracy:.4f}")

        # Classification report
        report = classification_report(y_test, y_pred, output_dict=True)
        logger.info(f"Classification report:\n{classification_report(y_test, y_pred)}")

        metrics = {
            "accuracy": float(accuracy),
            "classification_report": report,
            "n_train": len(X_train),
            "n_test": len(X_test),
        }

        return model, metrics

    def train_from_csv(
        self,
        data_path: Optional[str] = None,
        test_size: float = 0.2,
        random_state: int = 42,
        xgb_params: Optional[dict] = None,
    ) -> Tuple[xgb.XGBClassifier, dict, list[str]]:
        """
        Complete training pipeline from CSV file.

        Args:
            data_path: Path to CSV file
            test_size: Proportion of data for testing
            random_state: Random seed
            xgb_params: XGBoost parameters

        Returns:
            Tuple of (trained_model, metrics_dict, feature_names)
        """
        # Load data
        df = self.load_data(data_path)

        # Prepare features and labels
        X, y, feature_names = self.prepare_features_and_labels(df)

        # Train model
        model, metrics = self.train(
            X, y, feature_names, test_size, random_state, xgb_params
        )

        return model, metrics, feature_names

    def save_model(
        self,
        model: xgb.XGBClassifier,
        feature_names: list[str],
        model_path: Optional[str] = None,
    ) -> bool:
        """
        Save trained model to file.

        Args:
            model: Trained XGBoost model
            feature_names: List of feature names
            model_path: Path to save model

        Returns:
            True if saved successfully
        """
        path = Path(model_path or self.config.model_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                "model": model,
                "feature_names": feature_names,
            }
            with open(path, "wb") as f:
                pickle.dump(data, f)

            logger.info(f"Model saved to {path}")
            return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

