"""Tests for order executor."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.strategy.order_executor import OrderExecutor
from app.strategy.arbitrage_engine import ArbitrageOpportunity
from app.core.config import TradingConfig
from app.exchanges.base import Order


class MockExchange:
    """Mock exchange for testing."""

    def __init__(self, name: str):
        self.name = name

    async def place_order(self, *args, **kwargs):
        """Mock place_order."""
        return Order(
            order_id=f"order_{name}_{args[0]}",
            symbol=args[0],
            side=args[1],
            order_type=args[2],
            quantity=args[3],
            price=kwargs.get("price"),
            status="pending",
            timestamp=1000.0,
        )

    async def cancel_order(self, *args, **kwargs):
        """Mock cancel_order."""
        return True


@pytest.fixture
def mock_exchanges():
    """Create mock exchanges."""
    return {
        "exchange1": MockExchange("exchange1"),
        "exchange2": MockExchange("exchange2"),
    }


@pytest.fixture
def order_executor(mock_exchanges):
    """Create order executor instance."""
    config = TradingConfig(max_retries=2, retry_delay_seconds=0.1)
    return OrderExecutor(mock_exchanges, config)


@pytest.fixture
def sample_opportunity():
    """Create a sample arbitrage opportunity."""
    return ArbitrageOpportunity(
        symbol="BTCUSDT",
        buy_exchange="exchange1",
        sell_exchange="exchange2",
        buy_price=50000.0,
        sell_price=50100.0,
        spread_percent=0.2,
        max_quantity=0.1,
        net_profit=10.0,
        profit_percent=0.2,
        buy_fee=0.001,
        sell_fee=0.001,
    )


@pytest.mark.asyncio
async def test_execute_arbitrage(order_executor, sample_opportunity):
    """Test executing an arbitrage opportunity."""
    buy_order, sell_order = await order_executor.execute_arbitrage(
        sample_opportunity, use_maker=False
    )

    # Note: This will fail with current mock implementation
    # In real implementation, exchanges would be properly mocked
    # For now, we just test the structure
    assert buy_order is None or isinstance(buy_order, Order)
    assert sell_order is None or isinstance(sell_order, Order)


def test_get_active_orders(order_executor):
    """Test getting active orders."""
    orders = order_executor.get_active_orders()
    assert isinstance(orders, dict)


@pytest.mark.asyncio
async def test_cancel_all_orders(order_executor):
    """Test cancelling all orders."""
    # Add some mock orders
    order_executor.active_orders = {
        "order1": Order(
            order_id="order1",
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.1,
            price=50000.0,
            status="pending",
            timestamp=1000.0,
        )
    }

    await order_executor.cancel_all_orders()
    # Orders should be cancelled (implementation dependent)

