"""Tests for AI/ML modules."""

import numpy as np
import pytest
from app.ai.features import extract_orderbook_features, get_feature_names
from app.ai.model import TradingModel
from app.exchanges.base import OrderBook, OrderBookEntry
from app.core.config import AIConfig


@pytest.fixture
def sample_orderbook():
    """Create a sample orderbook for testing."""
    return OrderBook(
        bids=[
            OrderBookEntry(price=49900.0, quantity=0.5),
            OrderBookEntry(price=49800.0, quantity=1.0),
            OrderBookEntry(price=49700.0, quantity=1.5),
        ],
        asks=[
            OrderBookEntry(price=50100.0, quantity=0.5),
            OrderBookEntry(price=50200.0, quantity=1.0),
            OrderBookEntry(price=50300.0, quantity=1.5),
        ],
        timestamp=1000.0,
        symbol="BTCUSDT",
    )


def test_extract_orderbook_features(sample_orderbook):
    """Test feature extraction from orderbook."""
    features = extract_orderbook_features(sample_orderbook)

    assert "best_bid" in features
    assert "best_ask" in features
    assert "mid_price" in features
    assert "spread" in features
    assert features["best_bid"] == 49900.0
    assert features["best_ask"] == 50100.0
    assert features["spread"] == 200.0


def test_get_feature_names():
    """Test getting feature names."""
    names = get_feature_names(include_ohlc=False)
    assert len(names) > 0
    assert "best_bid" in names
    assert "best_ask" in names

    names_with_ohlc = get_feature_names(include_ohlc=True)
    assert len(names_with_ohlc) > len(names)


def test_model_initialization():
    """Test model initialization."""
    model = TradingModel()
    assert not model.is_classifier_loaded()
    assert not model.is_regressor_loaded()
    assert model.classifier is None
    assert model.regressor is None


def test_model_predict_no_model():
    """Test prediction when model is not loaded."""
    model = TradingModel()
    features = np.array([1.0, 2.0, 3.0])

    is_maker, probability = model.predict(features)
    assert is_maker is False
    assert probability == 0.0


def test_model_save_load(tmp_path):
    """Test model save and load."""
    import xgboost as xgb

    # Create a simple model
    X = np.random.rand(100, 10)
    y = np.random.randint(0, 2, 100)

    xgb_model = xgb.XGBClassifier(n_estimators=10, random_state=42)
    xgb_model.fit(X, y)

    # Save and load
    model = TradingModel()
    model.set_model(xgb_model, ["feature_" + str(i) for i in range(10)])

    model_path = tmp_path / "test_model.pkl"
    assert model.save(str(model_path))

    # Load in new model instance
    new_model = TradingModel()
    assert new_model.load(str(model_path))
    assert new_model.is_loaded()

