"""Basic performance benchmarks for trading operations."""

import pytest
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.strategy.arbitrage_engine import ArbitrageEngine
from app.strategy.order_executor import OrderExecutor
from app.exchanges.base import OrderBook, OrderBookEntry
from app.core.config import TradingConfig
from app.core.exchange_types import ExchangeName


class MockExchange:
    """Mock exchange for performance testing."""

    def __init__(self, name: str):
        self.name = name
        self._delay = 0.01  # 10ms delay

    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """Mock orderbook fetch with delay."""
        await asyncio.sleep(self._delay)
        return OrderBook(
            bids=[OrderBookEntry(price=50000.0, quantity=0.1)],
            asks=[OrderBookEntry(price=50010.0, quantity=0.1)],
            timestamp=time.time(),
            symbol=symbol,
        )

    def get_maker_fee(self) -> float:
        return 0.0005

    def get_taker_fee(self) -> float:
        return 0.001

    def is_authenticated(self) -> bool:
        return True


@pytest.fixture
def mock_exchanges():
    """Create mock exchanges for performance testing."""
    return {
        ExchangeName.NOBITEX: MockExchange("NOBITEX"),
        ExchangeName.INVEX: MockExchange("INVEX"),
    }


@pytest.fixture
def trading_config():
    """Create trading config."""
    return TradingConfig(
        min_spread_percent=0.1,
        min_profit_usdt=1.0,
        max_position_size_usdt=1000.0,
    )


@pytest.mark.asyncio
async def test_orderbook_fetch_performance(mock_exchanges):
    """Benchmark orderbook fetching performance."""
    symbol = "BTCUSDT"
    num_iterations = 10

    start_time = time.time()
    for _ in range(num_iterations):
        for exchange in mock_exchanges.values():
            await exchange.fetch_orderbook(symbol)
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / (num_iterations * len(mock_exchanges))

    print(f"\nOrderbook Fetch Performance:")
    print(f"  Total time: {total_time:.3f}s")
    print(f"  Average per fetch: {avg_time*1000:.2f}ms")
    print(f"  Throughput: {1/avg_time:.1f} fetches/second")

    # Assert reasonable performance (should be < 100ms per fetch with mocks)
    assert avg_time < 0.1, f"Orderbook fetch too slow: {avg_time*1000:.2f}ms"


@pytest.mark.asyncio
async def test_opportunity_detection_performance(mock_exchanges, trading_config):
    """Benchmark opportunity detection performance."""
    symbol = "BTCUSDT"
    engine = ArbitrageEngine(mock_exchanges, trading_config)

    # Setup orderbooks
    orderbooks = {}
    for name, exchange in mock_exchanges.items():
        orderbook = await exchange.fetch_orderbook(symbol)
        orderbooks[name.value] = orderbook

    num_iterations = 100
    start_time = time.time()
    for _ in range(num_iterations):
        opportunities = engine.find_opportunities(symbol, orderbooks)
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / num_iterations

    print(f"\nOpportunity Detection Performance:")
    print(f"  Total time: {total_time:.3f}s")
    print(f"  Average per detection: {avg_time*1000:.2f}ms")
    print(f"  Throughput: {1/avg_time:.1f} detections/second")

    # Assert reasonable performance (should be < 10ms per detection)
    assert avg_time < 0.01, f"Opportunity detection too slow: {avg_time*1000:.2f}ms"


@pytest.mark.asyncio
async def test_concurrent_orderbook_fetch(mock_exchanges):
    """Benchmark concurrent orderbook fetching."""
    symbol = "BTCUSDT"
    num_concurrent = 5

    start_time = time.time()
    tasks = [
        exchange.fetch_orderbook(symbol)
        for exchange in mock_exchanges.values()
        for _ in range(num_concurrent)
    ]
    await asyncio.gather(*tasks)
    end_time = time.time()

    total_time = end_time - start_time
    total_fetches = len(tasks)
    avg_time = total_time / total_fetches

    print(f"\nConcurrent Orderbook Fetch Performance:")
    print(f"  Concurrent fetches: {num_concurrent} per exchange")
    print(f"  Total fetches: {total_fetches}")
    print(f"  Total time: {total_time:.3f}s")
    print(f"  Average per fetch: {avg_time*1000:.2f}ms")
    print(f"  Throughput: {1/avg_time:.1f} fetches/second")

    # Concurrent should be faster than sequential
    assert total_time < 0.2, f"Concurrent fetch too slow: {total_time:.3f}s"


@pytest.mark.asyncio
async def test_risk_check_performance(trading_config):
    """Benchmark risk limit checking performance."""
    from app.strategy.arbitrage_engine import ArbitrageOpportunity
    from app.strategy.order_executor import OrderExecutor

    executor = OrderExecutor({}, trading_config)
    
    opportunity = ArbitrageOpportunity(
        symbol="BTCUSDT",
        buy_exchange="NOBITEX",
        sell_exchange="INVEX",
        buy_price=50000.0,
        sell_price=50100.0,
        spread_percent=0.2,
        max_quantity=0.1,
        net_profit=10.0,
        profit_percent=0.2,
        buy_fee=0.001,
        sell_fee=0.001,
    )

    buy_exchange = MagicMock()
    sell_exchange = MagicMock()
    buy_exchange.get_balance = AsyncMock(return_value={})
    sell_exchange.get_balance = AsyncMock(return_value={})

    num_iterations = 1000
    start_time = time.time()
    for _ in range(num_iterations):
        await executor._check_risk_limits(opportunity, buy_exchange, sell_exchange)
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / num_iterations

    print(f"\nRisk Check Performance:")
    print(f"  Total time: {total_time:.3f}s")
    print(f"  Average per check: {avg_time*1000000:.2f}μs")
    print(f"  Throughput: {1/avg_time:.0f} checks/second")

    # Risk checks should be very fast (< 1ms)
    assert avg_time < 0.001, f"Risk check too slow: {avg_time*1000:.2f}ms"


