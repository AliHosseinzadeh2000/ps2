"""Financial and mathematical calculation utilities."""

from typing import Tuple


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

