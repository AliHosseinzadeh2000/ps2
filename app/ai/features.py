"""Feature engineering from OHLC and orderbook data."""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from app.exchanges.base import OrderBook


def extract_orderbook_features(orderbook: OrderBook) -> Dict[str, float]:
    """
    Extract features from orderbook data.

    Args:
        orderbook: OrderBook object

    Returns:
        Dictionary of feature names to values
    """
    if not orderbook.bids or not orderbook.asks:
        return {}

    bid_prices = [b.price for b in orderbook.bids]
    ask_prices = [a.price for a in orderbook.asks]
    bid_volumes = [b.quantity for b in orderbook.bids]
    ask_volumes = [a.quantity for a in orderbook.asks]

    best_bid = bid_prices[0] if bid_prices else 0.0
    best_ask = ask_prices[0] if ask_prices else 0.0
    mid_price = (best_bid + best_ask) / 2.0 if best_bid and best_ask else 0.0
    spread = best_ask - best_bid if best_bid and best_ask else 0.0
    spread_percent = (spread / mid_price * 100.0) if mid_price > 0 else 0.0

    # Order book depth features
    bid_depth = sum(bid_volumes[:5])  # Top 5 levels
    ask_depth = sum(ask_volumes[:5])
    depth_imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth) if (bid_depth + ask_depth) > 0 else 0.0

    # Price levels
    bid_price_levels = len(bid_prices)
    ask_price_levels = len(ask_prices)

    # Volume-weighted average prices
    bid_vwap = (
        sum(b.price * b.quantity for b in orderbook.bids[:5])
        / bid_depth
        if bid_depth > 0
        else 0.0
    )
    ask_vwap = (
        sum(a.price * a.quantity for a in orderbook.asks[:5])
        / ask_depth
        if ask_depth > 0
        else 0.0
    )

    # Price volatility (standard deviation of top levels)
    bid_price_std = np.std(bid_prices[:5]) if len(bid_prices) >= 5 else 0.0
    ask_price_std = np.std(ask_prices[:5]) if len(ask_prices) >= 5 else 0.0

    features = {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid_price,
        "spread": spread,
        "spread_percent": spread_percent,
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "depth_imbalance": depth_imbalance,
        "bid_price_levels": float(bid_price_levels),
        "ask_price_levels": float(ask_price_levels),
        "bid_vwap": bid_vwap,
        "ask_vwap": ask_vwap,
        "bid_price_std": bid_price_std,
        "ask_price_std": ask_price_std,
    }

    return features


def extract_ohlc_features(
    ohlc_data: pd.DataFrame,
    periods: List[int] = [5, 10, 20],
) -> Dict[str, float]:
    """
    Extract features from OHLC data.

    Args:
        ohlc_data: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        periods: List of periods for moving averages

    Returns:
        Dictionary of feature names to values
    """
    if ohlc_data.empty or len(ohlc_data) < max(periods):
        return {}

    features = {}

    # Basic price features
    close = ohlc_data["close"].iloc[-1]
    high = ohlc_data["high"].iloc[-1]
    low = ohlc_data["low"].iloc[-1]
    open_price = ohlc_data["open"].iloc[-1]
    volume = ohlc_data["volume"].iloc[-1]

    features["close"] = close
    features["high"] = high
    features["low"] = low
    features["open"] = open_price
    features["volume"] = volume

    # Price changes
    features["price_change"] = close - open_price
    features["price_change_percent"] = (
        (close - open_price) / open_price * 100.0 if open_price > 0 else 0.0
    )
    features["high_low_spread"] = high - low
    features["high_low_spread_percent"] = (
        (high - low) / low * 100.0 if low > 0 else 0.0
    )

    # Moving averages
    for period in periods:
        if len(ohlc_data) >= period:
            ma = ohlc_data["close"].rolling(period).mean().iloc[-1]
            features[f"ma_{period}"] = ma
            features[f"price_vs_ma_{period}"] = (
                (close - ma) / ma * 100.0 if ma > 0 else 0.0
            )

    # Volume features
    for period in periods:
        if len(ohlc_data) >= period:
            vol_ma = ohlc_data["volume"].rolling(period).mean().iloc[-1]
            features[f"volume_ma_{period}"] = vol_ma
            features[f"volume_ratio_{period}"] = (
                volume / vol_ma if vol_ma > 0 else 0.0
            )

    # Volatility (standard deviation of returns)
    returns = ohlc_data["close"].pct_change().dropna()
    if len(returns) >= 20:
        features["volatility_20"] = returns.tail(20).std() * 100.0
    if len(returns) >= 5:
        features["volatility_5"] = returns.tail(5).std() * 100.0

    # RSI-like momentum (simplified)
    if len(ohlc_data) >= 14:
        price_changes = ohlc_data["close"].diff()
        gains = price_changes.where(price_changes > 0, 0.0)
        losses = -price_changes.where(price_changes < 0, 0.0)
        avg_gain = gains.tail(14).mean()
        avg_loss = losses.tail(14).mean()
        rs = avg_gain / avg_loss if avg_loss > 0 else 0.0
        features["rsi"] = 100.0 - (100.0 / (1.0 + rs))

    return features


def combine_features(
    orderbook_features: Dict[str, float],
    ohlc_features: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """
    Combine orderbook and OHLC features into a feature vector.

    Args:
        orderbook_features: Features from orderbook
        ohlc_features: Optional features from OHLC data

    Returns:
        NumPy array of feature values
    """
    all_features = orderbook_features.copy()

    if ohlc_features:
        all_features.update(ohlc_features)

    # Sort features by name for consistency
    feature_names = sorted(all_features.keys())
    feature_vector = np.array([all_features[name] for name in feature_names])

    return feature_vector


def get_feature_names(
    include_ohlc: bool = True,
    ohlc_periods: List[int] = [5, 10, 20],
) -> List[str]:
    """
    Get list of feature names in the order they appear in feature vectors.

    Args:
        include_ohlc: Whether to include OHLC features
        ohlc_periods: Periods for moving averages

    Returns:
        List of feature names
    """
    orderbook_feature_names = [
        "best_bid",
        "best_ask",
        "mid_price",
        "spread",
        "spread_percent",
        "bid_depth",
        "ask_depth",
        "depth_imbalance",
        "bid_price_levels",
        "ask_price_levels",
        "bid_vwap",
        "ask_vwap",
        "bid_price_std",
        "ask_price_std",
    ]

    if not include_ohlc:
        return sorted(orderbook_feature_names)

    ohlc_feature_names = [
        "close",
        "high",
        "low",
        "open",
        "volume",
        "price_change",
        "price_change_percent",
        "high_low_spread",
        "high_low_spread_percent",
    ]

    for period in ohlc_periods:
        ohlc_feature_names.extend([f"ma_{period}", f"price_vs_ma_{period}"])
        ohlc_feature_names.extend([f"volume_ma_{period}", f"volume_ratio_{period}"])

    ohlc_feature_names.extend(["volatility_20", "volatility_5", "rsi"])

    all_names = orderbook_feature_names + ohlc_feature_names
    return sorted(all_names)

