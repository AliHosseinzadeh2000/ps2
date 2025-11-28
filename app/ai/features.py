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

    # Buy/sell pressure indicators (as specified in proposal)
    # Buy pressure: ratio of bid volume to total volume
    total_volume = bid_depth + ask_depth
    buy_pressure = bid_depth / total_volume if total_volume > 0 else 0.0
    sell_pressure = ask_depth / total_volume if total_volume > 0 else 0.0
    pressure_ratio = buy_pressure / sell_pressure if sell_pressure > 0 else 0.0

    # Extended depth analysis (top 10 levels for better pressure measurement)
    bid_depth_10 = sum(bid_volumes[:10])
    ask_depth_10 = sum(ask_volumes[:10])
    buy_pressure_10 = bid_depth_10 / (bid_depth_10 + ask_depth_10) if (bid_depth_10 + ask_depth_10) > 0 else 0.0
    sell_pressure_10 = ask_depth_10 / (bid_depth_10 + ask_depth_10) if (bid_depth_10 + ask_depth_10) > 0 else 0.0

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
        # Buy/sell pressure indicators
        "buy_pressure": buy_pressure,
        "sell_pressure": sell_pressure,
        "pressure_ratio": pressure_ratio,
        "buy_pressure_10": buy_pressure_10,
        "sell_pressure_10": sell_pressure_10,
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

    # Simple Moving Averages (SMA)
    for period in periods:
        if len(ohlc_data) >= period:
            ma = ohlc_data["close"].rolling(period).mean().iloc[-1]
            features[f"sma_{period}"] = ma
            features[f"price_vs_sma_{period}"] = (
                (close - ma) / ma * 100.0 if ma > 0 else 0.0
            )

    # Exponential Moving Averages (EMA) - as specified in proposal
    for period in periods:
        if len(ohlc_data) >= period:
            ema = ohlc_data["close"].ewm(span=period, adjust=False).mean().iloc[-1]
            features[f"ema_{period}"] = ema
            features[f"price_vs_ema_{period}"] = (
                (close - ema) / ema * 100.0 if ema > 0 else 0.0
            )
            # EMA vs SMA divergence
            if f"sma_{period}" in features:
                features[f"ema_sma_divergence_{period}"] = (
                    (ema - features[f"sma_{period}"]) / features[f"sma_{period}"] * 100.0
                    if features[f"sma_{period}"] > 0
                    else 0.0
                )

    # Volume features - average trading volume in consecutive periods
    for period in periods:
        if len(ohlc_data) >= period:
            vol_ma = ohlc_data["volume"].rolling(period).mean().iloc[-1]
            features[f"volume_ma_{period}"] = vol_ma
            features[f"volume_ratio_{period}"] = (
                volume / vol_ma if vol_ma > 0 else 0.0
            )

    # Volume momentum indicators (as specified in proposal)
    if len(ohlc_data) >= 10:
        # Volume momentum: rate of change in volume
        vol_momentum_5 = (
            (ohlc_data["volume"].iloc[-1] - ohlc_data["volume"].iloc[-6])
            / ohlc_data["volume"].iloc[-6]
            * 100.0
            if ohlc_data["volume"].iloc[-6] > 0
            else 0.0
        )
        features["volume_momentum_5"] = vol_momentum_5

        if len(ohlc_data) >= 20:
            vol_momentum_10 = (
                (ohlc_data["volume"].iloc[-1] - ohlc_data["volume"].iloc[-11])
                / ohlc_data["volume"].iloc[-11]
                * 100.0
                if ohlc_data["volume"].iloc[-11] > 0
                else 0.0
            )
            features["volume_momentum_10"] = vol_momentum_10

    # Volatility features - standard deviation of closing prices (as specified in proposal)
    if len(ohlc_data) >= 20:
        close_std = ohlc_data["close"].tail(20).std()
        features["volatility_close_std_20"] = close_std
        features["volatility_close_std_percent_20"] = (
            close_std / close * 100.0 if close > 0 else 0.0
        )
    if len(ohlc_data) >= 5:
        close_std_5 = ohlc_data["close"].tail(5).std()
        features["volatility_close_std_5"] = close_std_5
        features["volatility_close_std_percent_5"] = (
            close_std_5 / close * 100.0 if close > 0 else 0.0
        )

    # Volatility (standard deviation of returns) - additional measure
    returns = ohlc_data["close"].pct_change().dropna()
    if len(returns) >= 20:
        features["volatility_returns_20"] = returns.tail(20).std() * 100.0
    if len(returns) >= 5:
        features["volatility_returns_5"] = returns.tail(5).std() * 100.0

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
        "buy_pressure",
        "sell_pressure",
        "pressure_ratio",
        "buy_pressure_10",
        "sell_pressure_10",
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
        ohlc_feature_names.extend([f"sma_{period}", f"price_vs_sma_{period}"])
        ohlc_feature_names.extend([f"ema_{period}", f"price_vs_ema_{period}"])
        ohlc_feature_names.extend([f"ema_sma_divergence_{period}"])
        ohlc_feature_names.extend([f"volume_ma_{period}", f"volume_ratio_{period}"])

    ohlc_feature_names.extend([
        "volume_momentum_5",
        "volume_momentum_10",
        "volatility_close_std_20",
        "volatility_close_std_percent_20",
        "volatility_close_std_5",
        "volatility_close_std_percent_5",
        "volatility_returns_20",
        "volatility_returns_5",
        "rsi",
    ])

    all_names = orderbook_feature_names + ohlc_feature_names
    return sorted(all_names)

