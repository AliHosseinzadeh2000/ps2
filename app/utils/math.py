"""Financial and mathematical calculation utilities."""

from typing import Optional, Tuple


def calculate_spread_percent(buy_price: float, sell_price: float) -> float:
    """
    Calculate spread percentage between two prices.

    Args:
        buy_price: Buy price (lower price)
        sell_price: Sell price (higher price)

    Returns:
        Spread percentage
    """
    if buy_price <= 0:
        return 0.0
    return ((sell_price - buy_price) / buy_price) * 100.0


def calculate_net_profit(
    buy_price: float,
    sell_price: float,
    quantity: float,
    buy_fee: float,
    sell_fee: float,
) -> float:
    """
    Calculate net profit after fees.

    Args:
        buy_price: Price at which asset is bought
        sell_price: Price at which asset is sold
        quantity: Quantity of asset
        buy_fee: Fee rate for buy order (e.g., 0.001 for 0.1%)
        sell_fee: Fee rate for sell order (e.g., 0.001 for 0.1%)

    Returns:
        Net profit in quote currency
    """
    buy_cost = buy_price * quantity * (1 + buy_fee)
    sell_revenue = sell_price * quantity * (1 - sell_fee)
    return sell_revenue - buy_cost


def calculate_required_quantity(
    capital: float,
    price: float,
    fee: float = 0.0,
) -> float:
    """
    Calculate maximum quantity that can be bought with given capital.

    Args:
        capital: Available capital
        price: Asset price
        fee: Trading fee rate

    Returns:
        Maximum quantity
    """
    if price <= 0:
        return 0.0
    return capital / (price * (1 + fee))


def calculate_fee_amount(price: float, quantity: float, fee_rate: float) -> float:
    """
    Calculate trading fee amount.

    Args:
        price: Asset price
        quantity: Asset quantity
        fee_rate: Fee rate (e.g., 0.001 for 0.1%)

    Returns:
        Fee amount in quote currency
    """
    return price * quantity * fee_rate


def calculate_effective_price(
    price: float,
    quantity: float,
    fee_rate: float,
    is_buy: bool,
) -> float:
    """
    Calculate effective price including fees.

    Args:
        price: Base price
        quantity: Asset quantity
        fee_rate: Trading fee rate
        is_buy: True for buy orders, False for sell orders

    Returns:
        Effective price per unit
    """
    if is_buy:
        return price * (1 + fee_rate)
    else:
        return price * (1 - fee_rate)


def calculate_arbitrage_profit(
    buy_exchange_price: float,
    sell_exchange_price: float,
    quantity: float,
    buy_fee: float,
    sell_fee: float,
) -> Tuple[float, float]:
    """
    Calculate arbitrage profit and profit percentage.

    Args:
        buy_exchange_price: Price on exchange where we buy
        sell_exchange_price: Price on exchange where we sell
        quantity: Trading quantity
        buy_fee: Fee rate for buy order
        sell_fee: Fee rate for sell order

    Returns:
        Tuple of (net_profit, profit_percentage)
    """
    net_profit = calculate_net_profit(
        buy_exchange_price,
        sell_exchange_price,
        quantity,
        buy_fee,
        sell_fee,
    )

    total_cost = buy_exchange_price * quantity * (1 + buy_fee)
    profit_percentage = (net_profit / total_cost * 100.0) if total_cost > 0 else 0.0

    return net_profit, profit_percentage


def round_to_precision(value: float, precision: int = 8) -> float:
    """
    Round value to specified decimal precision.

    Args:
        value: Value to round
        precision: Number of decimal places

    Returns:
        Rounded value
    """
    return round(value, precision)


def calculate_optimal_limit_price(
    predicted_price: float,
    current_price: float,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    safety_margin_percent: float = 0.001,
    is_buy: bool = True,
) -> float:
    """
    Calculate optimal limit order price using AI prediction with safety margins.

    Args:
        predicted_price: AI-predicted future price
        current_price: Current market price
        min_price: Minimum allowed price (for buy orders)
        max_price: Maximum allowed price (for sell orders)
        safety_margin_percent: Safety margin percentage (default 0.1%)
        is_buy: True for buy orders, False for sell orders

    Returns:
        Optimal limit price
    """
    if predicted_price <= 0:
        return current_price

    # For buy orders: set price slightly below predicted to increase fill probability
    # For sell orders: set price slightly above predicted to increase fill probability
    if is_buy:
        optimal_price = predicted_price * (1 - safety_margin_percent)
        # Ensure we don't go below minimum profitable price
        if min_price:
            optimal_price = max(optimal_price, min_price)
        # Don't go above current ask (would be immediately filled as taker)
        optimal_price = min(optimal_price, current_price)
    else:
        optimal_price = predicted_price * (1 + safety_margin_percent)
        # Ensure we don't go above maximum profitable price
        if max_price:
            optimal_price = min(optimal_price, max_price)
        # Don't go below current bid (would be immediately filled as taker)
        optimal_price = max(optimal_price, current_price)

    return optimal_price


def adjust_price_for_arbitrage(
    predicted_price: float,
    opportunity_buy_price: float,
    opportunity_sell_price: float,
    is_buy: bool,
    safety_margin_percent: float = 0.001,
) -> float:
    """
    Adjust predicted price to stay within profitable arbitrage bounds.

    Args:
        predicted_price: AI-predicted price
        opportunity_buy_price: Buy price from arbitrage opportunity
        opportunity_sell_price: Sell price from arbitrage opportunity
        is_buy: True for buy orders, False for sell orders
        safety_margin_percent: Safety margin to maintain profitability

    Returns:
        Adjusted price that maintains arbitrage profitability
    """
    if is_buy:
        # For buy: price should be <= opportunity_buy_price to maintain profit
        max_allowed = opportunity_buy_price * (1 - safety_margin_percent)
        return min(predicted_price, max_allowed)
    else:
        # For sell: price should be >= opportunity_sell_price to maintain profit
        min_allowed = opportunity_sell_price * (1 + safety_margin_percent)
        return max(predicted_price, min_allowed)

