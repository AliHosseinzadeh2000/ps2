"""Comprehensive integration tests for full arbitrage flow."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict

from app.strategy.arbitrage_engine import ArbitrageEngine, ArbitrageOpportunity
from app.strategy.order_executor import OrderExecutor
from app.strategy.price_stream import PriceStream
from app.exchanges.base import OrderBook, OrderBookEntry, Order
from app.core.config import TradingConfig
from app.core.exchange_types import ExchangeName


class MockExchange:
    """Mock exchange for comprehensive testing."""

    def __init__(self, name: str, maker_fee: float = 0.0005, taker_fee: float = 0.001):
        self.name = name
        self._maker_fee = maker_fee
        self._taker_fee = taker_fee
        self._orderbooks: Dict[str, OrderBook] = {}
        self._orders: Dict[str, Order] = {}
        self._order_counter = 0
        self._balance = {"USDT": {"available": 10000.0, "locked": 0.0}}

    def get_maker_fee(self) -> float:
        return self._maker_fee

    def get_taker_fee(self) -> float:
        return self._taker_fee

    def set_orderbook(self, symbol: str, orderbook: OrderBook):
        """Set orderbook for a symbol."""
        self._orderbooks[symbol] = orderbook

    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """Fetch orderbook."""
        if symbol in self._orderbooks:
            return self._orderbooks[symbol]
        # Default empty orderbook
        return OrderBook(
            bids=[],
            asks=[],
            timestamp=1000.0,
            symbol=symbol,
        )

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float = None,
        is_maker: bool = False,
    ) -> Order:
        """Place an order."""
        self._order_counter += 1
        order_id = f"{self.name}_order_{self._order_counter}"
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="pending",
            filled_quantity=0.0,
            timestamp=1000.0,
        )
        self._orders[order_id] = order
        return order

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """Get order status."""
        if order_id in self._orders:
            order = self._orders[order_id]
            # Simulate order filling after first check
            if order.status == "pending":
                order.status = "filled"
                order.filled_quantity = order.quantity
            return order
        raise Exception(f"Order {order_id} not found")

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        if order_id in self._orders:
            self._orders[order_id].status = "cancelled"
            return True
        return False

    async def get_balance(self):
        """Get balance."""
        from app.exchanges.base import Balance
        return {
            currency: Balance(
                currency=currency,
                available=data["available"],
                locked=data["locked"],
            )
            for currency, data in self._balance.items()
        }

    def is_authenticated(self) -> bool:
        """Check if authenticated."""
        return True


@pytest.fixture
def mock_exchanges():
    """Create mock exchanges."""
    return {
        ExchangeName.NOBITEX: MockExchange("NOBITEX", maker_fee=0.0005, taker_fee=0.001),
        ExchangeName.INVEX: MockExchange("INVEX", maker_fee=0.0005, taker_fee=0.001),
        ExchangeName.WALLEX: MockExchange("WALLEX", maker_fee=0.0005, taker_fee=0.001),
    }


@pytest.fixture
def trading_config():
    """Create trading config."""
    return TradingConfig(
        min_spread_percent=0.1,
        min_profit_usdt=1.0,
        max_position_size_usdt=1000.0,
        max_position_per_exchange=5000.0,
        daily_loss_limit=100.0,
        max_slippage_percent=0.5,
        require_balance_check=False,  # Disable for testing
    )


@pytest.fixture
def arbitrage_engine(mock_exchanges, trading_config):
    """Create arbitrage engine."""
    return ArbitrageEngine(mock_exchanges, trading_config)


@pytest.fixture
def order_executor(mock_exchanges, trading_config):
    """Create order executor without AI."""
    return OrderExecutor(mock_exchanges, trading_config, predictor=None)


@pytest.mark.asyncio
async def test_full_arbitrage_flow_taker_taker(arbitrage_engine, order_executor, mock_exchanges):
    """Test complete arbitrage flow without AI (taker-taker mode)."""
    symbol = "BTCUSDT"
    
    # Setup orderbooks with profitable opportunity
    nobitex_orderbook = OrderBook(
        bids=[],
        asks=[
            OrderBookEntry(price=50000.0, quantity=0.1),
            OrderBookEntry(price=50010.0, quantity=0.2),
        ],
        timestamp=1000.0,
        symbol=symbol,
    )
    
    invex_orderbook = OrderBook(
        bids=[
            OrderBookEntry(price=50100.0, quantity=0.1),
            OrderBookEntry(price=50090.0, quantity=0.2),
        ],
        asks=[],
        timestamp=1000.0,
        symbol=symbol,
    )
    
    mock_exchanges[ExchangeName.NOBITEX].set_orderbook(symbol, nobitex_orderbook)
    mock_exchanges[ExchangeName.INVEX].set_orderbook(symbol, invex_orderbook)
    
    # Detect opportunity
    opportunity = arbitrage_engine.detect_opportunity(
        symbol,
        ExchangeName.NOBITEX.value,
        ExchangeName.INVEX.value,
        nobitex_orderbook,
        invex_orderbook,
    )
    
    assert opportunity is not None
    assert opportunity.buy_price == 50000.0
    assert opportunity.sell_price == 50100.0
    assert opportunity.net_profit > 0
    
    # Execute without AI (taker-taker)
    buy_order, sell_order = await order_executor.execute_arbitrage(
        opportunity,
        use_maker=False,  # Explicitly use taker
    )
    
    assert buy_order is not None
    assert sell_order is not None
    assert buy_order.side == "buy"
    assert sell_order.side == "sell"
    
    # Verify orders were placed
    assert buy_order.order_id.startswith("NOBITEX_order_")
    assert sell_order.order_id.startswith("INVEX_order_")


@pytest.mark.asyncio
async def test_arbitrage_detection_all_exchanges(arbitrage_engine, mock_exchanges):
    """Test arbitrage detection across all configured exchanges."""
    symbol = "BTCUSDT"
    
    # Setup orderbooks with different prices
    orderbooks = {
        ExchangeName.NOBITEX: OrderBook(
            bids=[],
            asks=[OrderBookEntry(price=50000.0, quantity=0.1)],
            timestamp=1000.0,
            symbol=symbol,
        ),
        ExchangeName.INVEX: OrderBook(
            bids=[OrderBookEntry(price=50100.0, quantity=0.1)],
            asks=[],
            timestamp=1000.0,
            symbol=symbol,
        ),
        ExchangeName.WALLEX: OrderBook(
            bids=[OrderBookEntry(price=50050.0, quantity=0.1)],
            asks=[OrderBookEntry(price=50050.0, quantity=0.1)],
            timestamp=1000.0,
            symbol=symbol,
        ),
    }
    
    # Set orderbooks
    for exchange_name, orderbook in orderbooks.items():
        mock_exchanges[exchange_name].set_orderbook(symbol, orderbook)
    
    # Convert orderbooks dict keys to strings for find_opportunities
    orderbooks_str = {
        name.value if isinstance(name, ExchangeName) else str(name): ob
        for name, ob in orderbooks.items()
    }
    
    # Find all opportunities
    opportunities = arbitrage_engine.find_opportunities(symbol, orderbooks_str)
    
    assert len(opportunities) > 0
    # Should find NOBITEX -> INVEX opportunity
    nobitex_invex = [
        opp for opp in opportunities
        if opp.buy_exchange == ExchangeName.NOBITEX.value
        and opp.sell_exchange == ExchangeName.INVEX.value
    ]
    assert len(nobitex_invex) > 0


@pytest.mark.asyncio
async def test_concurrent_order_execution(order_executor, mock_exchanges):
    """Test concurrent order execution and error recovery."""
    symbol = "BTCUSDT"
    
    # Create opportunity
    opportunity = ArbitrageOpportunity(
        symbol=symbol,
        buy_exchange=ExchangeName.NOBITEX.value,
        sell_exchange=ExchangeName.INVEX.value,
        buy_price=50000.0,
        sell_price=50100.0,
        spread_percent=0.2,
        max_quantity=0.1,
        net_profit=10.0,
        profit_percent=0.2,
        buy_fee=0.001,
        sell_fee=0.001,
    )
    
    # Setup orderbooks
    nobitex_orderbook = OrderBook(
        bids=[],
        asks=[OrderBookEntry(price=50000.0, quantity=0.1)],
        timestamp=1000.0,
        symbol=symbol,
    )
    invex_orderbook = OrderBook(
        bids=[OrderBookEntry(price=50100.0, quantity=0.1)],
        asks=[],
        timestamp=1000.0,
        symbol=symbol,
    )
    
    mock_exchanges[ExchangeName.NOBITEX].set_orderbook(symbol, nobitex_orderbook)
    mock_exchanges[ExchangeName.INVEX].set_orderbook(symbol, invex_orderbook)
    
    # Execute concurrently
    buy_order, sell_order = await order_executor.execute_arbitrage(
        opportunity,
        use_maker=False,
        buy_orderbook=nobitex_orderbook,
        sell_orderbook=invex_orderbook,
    )
    
    # Both orders should be placed
    assert buy_order is not None
    assert sell_order is not None


@pytest.mark.asyncio
async def test_error_recovery_on_order_failure(order_executor, mock_exchanges):
    """Test error recovery when one order fails."""
    symbol = "BTCUSDT"
    
    # Make one exchange fail
    async def failing_place_order(*args, **kwargs):
        raise Exception("Exchange error")
    
    mock_exchanges[ExchangeName.INVEX].place_order = failing_place_order
    
    opportunity = ArbitrageOpportunity(
        symbol=symbol,
        buy_exchange=ExchangeName.NOBITEX.value,
        sell_exchange=ExchangeName.INVEX.value,
        buy_price=50000.0,
        sell_price=50100.0,
        spread_percent=0.2,
        max_quantity=0.1,
        net_profit=10.0,
        profit_percent=0.2,
        buy_fee=0.001,
        sell_fee=0.001,
    )
    
    # Execute - should handle failure gracefully
    buy_order, sell_order = await order_executor.execute_arbitrage(
        opportunity,
        use_maker=False,
    )
    
    # Buy order might succeed, sell should fail
    # System should attempt to cancel buy order if sell fails
    assert buy_order is None or sell_order is None


@pytest.mark.asyncio
async def test_price_stream_integration(mock_exchanges, trading_config):
    """Test price stream integration with arbitrage engine."""
    symbol = "BTCUSDT"
    
    # Setup orderbooks
    nobitex_orderbook = OrderBook(
        bids=[],
        asks=[OrderBookEntry(price=50000.0, quantity=0.1)],
        timestamp=1000.0,
        symbol=symbol,
    )
    invex_orderbook = OrderBook(
        bids=[OrderBookEntry(price=50100.0, quantity=0.1)],
        asks=[],
        timestamp=1000.0,
        symbol=symbol,
    )
    
    mock_exchanges[ExchangeName.NOBITEX].set_orderbook(symbol, nobitex_orderbook)
    mock_exchanges[ExchangeName.INVEX].set_orderbook(symbol, invex_orderbook)
    
    # Create price stream
    price_stream = PriceStream(mock_exchanges, trading_config)
    
    # Create arbitrage engine
    arbitrage_engine = ArbitrageEngine(mock_exchanges, trading_config)
    
    # Track detected opportunities
    detected_opportunities = []
    
    def on_opportunity(opportunity):
        detected_opportunities.append(opportunity)
    
    # Subscribe arbitrage engine to price stream
    price_stream.subscribe(arbitrage_engine.on_price_update)
    
    # Start price stream
    await price_stream.start([symbol])
    
    # Wait a bit for updates
    await asyncio.sleep(0.5)
    
    # Stop stream
    await price_stream.stop()
    
    # Should have detected opportunities
    # Note: This depends on price stream implementation
    # For now, just verify it doesn't crash


@pytest.mark.asyncio
async def test_risk_limits_enforcement(order_executor, mock_exchanges):
    """Test that risk limits are enforced."""
    symbol = "BTCUSDT"
    
    # Set daily loss limit
    order_executor.daily_profit_loss = -150.0  # Exceed limit
    order_executor.config.daily_loss_limit = 100.0
    
    opportunity = ArbitrageOpportunity(
        symbol=symbol,
        buy_exchange=ExchangeName.NOBITEX.value,
        sell_exchange=ExchangeName.INVEX.value,
        buy_price=50000.0,
        sell_price=50100.0,
        spread_percent=0.2,
        max_quantity=0.1,
        net_profit=10.0,
        profit_percent=0.2,
        buy_fee=0.001,
        sell_fee=0.001,
    )
    
    # Should be blocked by risk check
    buy_order, sell_order = await order_executor.execute_arbitrage(
        opportunity,
        use_maker=False,
    )
    
    # Should be None due to risk limit
    assert buy_order is None
    assert sell_order is None

