"""Tests for arbitrage engine."""

import pytest
from app.exchanges.base import OrderBook, OrderBookEntry
from app.strategy.arbitrage_engine import ArbitrageEngine, ArbitrageOpportunity
from app.core.config import TradingConfig


class MockExchange:
    """Mock exchange for testing."""

    def __init__(self, name: str, maker_fee: float = 0.0005, taker_fee: float = 0.001):
        self.name = name
        self._maker_fee = maker_fee
        self._taker_fee = taker_fee

    def get_maker_fee(self) -> float:
        return self._maker_fee

    def get_taker_fee(self) -> float:
        return self._taker_fee


@pytest.fixture
def mock_exchanges():
    """Create mock exchanges."""
    return {
        "exchange1": MockExchange("exchange1", maker_fee=0.0005, taker_fee=0.001),
        "exchange2": MockExchange("exchange2", maker_fee=0.0005, taker_fee=0.001),
    }


@pytest.fixture
def arbitrage_engine(mock_exchanges):
    """Create arbitrage engine instance."""
    config = TradingConfig(min_spread_percent=0.1, min_profit_usdt=0.1)
    return ArbitrageEngine(mock_exchanges, config)


def test_detect_opportunity_profitable(arbitrage_engine):
    """Test detecting a profitable arbitrage opportunity."""
    symbol = "BTCUSDT"

    # Create orderbooks with price difference
    buy_orderbook = OrderBook(
        bids=[],
        asks=[
            OrderBookEntry(price=50000.0, quantity=1.0),
            OrderBookEntry(price=50010.0, quantity=2.0),
        ],
        timestamp=1000.0,
        symbol=symbol,
    )

    sell_orderbook = OrderBook(
        bids=[
            OrderBookEntry(price=50100.0, quantity=1.0),
            OrderBookEntry(price=50090.0, quantity=2.0),
        ],
        asks=[],
        timestamp=1000.0,
        symbol=symbol,
    )

    opportunity = arbitrage_engine.detect_opportunity(
        symbol,
        "exchange1",
        "exchange2",
        buy_orderbook,
        sell_orderbook,
    )

    assert opportunity is not None
    assert opportunity.buy_price == 50000.0
    assert opportunity.sell_price == 50100.0
    assert opportunity.spread_percent > 0
    assert opportunity.net_profit > 0


def test_detect_opportunity_not_profitable(arbitrage_engine):
    """Test that unprofitable opportunities are not detected."""
    symbol = "BTCUSDT"

    # Create orderbooks with no profitable spread
    buy_orderbook = OrderBook(
        bids=[],
        asks=[OrderBookEntry(price=50000.0, quantity=1.0)],
        timestamp=1000.0,
        symbol=symbol,
    )

    sell_orderbook = OrderBook(
        bids=[OrderBookEntry(price=49900.0, quantity=1.0)],
        asks=[],
        timestamp=1000.0,
        symbol=symbol,
    )

    opportunity = arbitrage_engine.detect_opportunity(
        symbol,
        "exchange1",
        "exchange2",
        buy_orderbook,
        sell_orderbook,
    )

    assert opportunity is None


def test_find_opportunities(arbitrage_engine):
    """Test finding opportunities across exchanges."""
    symbol = "BTCUSDT"

    orderbooks = {
        "exchange1": OrderBook(
            bids=[],
            asks=[OrderBookEntry(price=50000.0, quantity=1.0)],
            timestamp=1000.0,
            symbol=symbol,
        ),
        "exchange2": OrderBook(
            bids=[OrderBookEntry(price=50100.0, quantity=1.0)],
            asks=[],
            timestamp=1000.0,
            symbol=symbol,
        ),
    }

    opportunities = arbitrage_engine.find_opportunities(symbol, orderbooks)

    assert len(opportunities) > 0
    assert all(isinstance(opp, ArbitrageOpportunity) for opp in opportunities)

