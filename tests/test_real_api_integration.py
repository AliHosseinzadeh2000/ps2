"""Real API integration tests for exchanges.

WARNING: These tests make actual API calls to real exchanges.
Requires valid credentials in .env file.
Set SKIP_REAL_API_TESTS=1 to skip these tests.
"""

import pytest
import os
import asyncio
from typing import Dict

from app.exchanges.nobitex import NobitexExchange
from app.exchanges.invex import InvexExchange
from app.exchanges.wallex import WallexExchange
from app.exchanges.kucoin import KucoinExchange
from app.exchanges.tabdeal import TabdealExchange
from app.core.config import (
    NobitexConfig,
    InvexConfig,
    WallexConfig,
    KucoinConfig,
    TabdealConfig,
)
from app.strategy.arbitrage_engine import ArbitrageEngine
from app.core.config import TradingConfig
from app.core.exchange_types import ExchangeName, TradingSymbol
from app.core.logging import get_logger

logger = get_logger(__name__)

# Skip real API tests if flag is set
SKIP_REAL_API = os.getenv("SKIP_REAL_API_TESTS", "0") == "1"


@pytest.fixture
def nobitex_exchange():
    """Create Nobitex exchange instance."""
    config = NobitexConfig()
    return NobitexExchange(config)


@pytest.fixture
def invex_exchange():
    """Create Invex exchange instance."""
    config = InvexConfig()
    return InvexExchange(config)


@pytest.fixture
def wallex_exchange():
    """Create Wallex exchange instance."""
    config = WallexConfig()
    return WallexExchange(config)


@pytest.fixture
def trading_config():
    """Create trading config."""
    return TradingConfig(
        min_spread_percent=0.1,
        min_profit_usdt=1.0,
        max_position_size_usdt=100.0,  # Small for testing
    )


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_nobitex_orderbook_real(nobitex_exchange):
    """Test fetching real orderbook from Nobitex."""
    symbol = "BTCIRT"
    
    logger.info(f"Testing Nobitex orderbook fetch for {symbol}")
    orderbook = await nobitex_exchange.fetch_orderbook(symbol, depth=10)
    
    assert orderbook is not None
    assert len(orderbook.bids) > 0, "No bids in orderbook"
    assert len(orderbook.asks) > 0, "No asks in orderbook"
    assert orderbook.symbol == symbol
    
    logger.info(f"✅ Nobitex orderbook: {len(orderbook.bids)} bids, {len(orderbook.asks)} asks")
    logger.info(f"   Best bid: {orderbook.bids[0].price}, Best ask: {orderbook.asks[0].price}")
    logger.info(f"   Spread: {orderbook.asks[0].price - orderbook.bids[0].price:.2f}")


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_invex_orderbook_real(invex_exchange):
    """Test fetching real orderbook from Invex."""
    symbol = "BTCUSDT"
    
    logger.info(f"Testing Invex orderbook fetch for {symbol}")
    orderbook = await invex_exchange.fetch_orderbook(symbol, depth=10)
    
    assert orderbook is not None
    assert len(orderbook.bids) > 0, "No bids in orderbook"
    assert len(orderbook.asks) > 0, "No asks in orderbook"
    assert orderbook.symbol == symbol
    
    logger.info(f"✅ Invex orderbook: {len(orderbook.bids)} bids, {len(orderbook.asks)} asks")
    logger.info(f"   Best bid: {orderbook.bids[0].price}, Best ask: {orderbook.asks[0].price}")
    logger.info(f"   Spread: {orderbook.asks[0].price - orderbook.bids[0].price:.2f}")


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_wallex_orderbook_real(wallex_exchange):
    """Test fetching real orderbook from Wallex."""
    symbol = "BTCUSDT"
    
    logger.info(f"Testing Wallex orderbook fetch for {symbol}")
    orderbook = await wallex_exchange.fetch_orderbook(symbol, depth=10)
    
    assert orderbook is not None
    assert len(orderbook.bids) > 0, "No bids in orderbook"
    assert len(orderbook.asks) > 0, "No asks in orderbook"
    assert orderbook.symbol == symbol
    
    logger.info(f"✅ Wallex orderbook: {len(orderbook.bids)} bids, {len(orderbook.asks)} asks")
    logger.info(f"   Best bid: {orderbook.bids[0].price}, Best ask: {orderbook.asks[0].price}")
    logger.info(f"   Spread: {orderbook.asks[0].price - orderbook.bids[0].price:.2f}")


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_real_opportunity_detection(nobitex_exchange, invex_exchange, trading_config):
    """Test detecting real arbitrage opportunities."""
    symbol = "BTCUSDT"
    
    logger.info(f"Testing real opportunity detection for {symbol}")
    
    # Fetch real orderbooks
    nobitex_orderbook = await nobitex_exchange.fetch_orderbook(symbol, depth=20)
    invex_orderbook = await invex_exchange.fetch_orderbook(symbol, depth=20)
    
    # Create arbitrage engine
    exchanges = {
        ExchangeName.NOBITEX: nobitex_exchange,
        ExchangeName.INVEX: invex_exchange,
    }
    engine = ArbitrageEngine(exchanges, trading_config)
    
    # Find opportunities
    orderbooks = {
        ExchangeName.NOBITEX.value: nobitex_orderbook,
        ExchangeName.INVEX.value: invex_orderbook,
    }
    opportunities = engine.find_opportunities(symbol, orderbooks)
    
    logger.info(f"✅ Found {len(opportunities)} opportunities")
    
    if opportunities:
        best = opportunities[0]
        logger.info(f"   Best opportunity:")
        logger.info(f"   Buy: {best.buy_exchange} @ {best.buy_price:.2f}")
        logger.info(f"   Sell: {best.sell_exchange} @ {best.sell_price:.2f}")
        logger.info(f"   Spread: {best.spread_percent:.4f}%")
        logger.info(f"   Net Profit: {best.net_profit:.2f} USDT")
        logger.info(f"   Max Quantity: {best.max_quantity:.8f}")
    else:
        logger.info("   No profitable opportunities found (this is normal)")
    
    # Test should pass regardless of whether opportunities exist
    assert isinstance(opportunities, list)


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_real_order_lifecycle_authenticated(nobitex_exchange):
    """Test order placement, status check, and cancellation (requires authentication)."""
    if not nobitex_exchange.is_authenticated():
        pytest.skip("Nobitex not authenticated - skipping order lifecycle test")
    
    symbol = "BTCIRT"
    
    logger.info(f"Testing order lifecycle for {symbol} on Nobitex")
    
    # Get current market price
    orderbook = await nobitex_exchange.fetch_orderbook(symbol, depth=1)
    current_price = orderbook.asks[0].price
    
    # Place a limit order well below market (should not fill immediately)
    test_price = current_price * 0.9  # 10% below market
    
    logger.info(f"Placing test order at {test_price:.2f} (market: {current_price:.2f})")
    
    try:
        # Place order
        order = await nobitex_exchange.place_order(
            symbol=symbol,
            side="buy",
            order_type="limit",
            quantity=0.0001,  # Very small quantity
            price=test_price,
            is_maker=False,
        )
        
        assert order is not None
        assert order.order_id is not None
        logger.info(f"✅ Order placed: {order.order_id}")
        
        # Check order status
        await asyncio.sleep(1)  # Wait a bit
        status_order = await nobitex_exchange.get_order(order.order_id, symbol)
        
        assert status_order is not None
        assert status_order.order_id == order.order_id
        logger.info(f"✅ Order status retrieved: {status_order.status}")
        
        # Cancel order
        cancelled = await nobitex_exchange.cancel_order(order.order_id, symbol)
        assert cancelled is True
        logger.info(f"✅ Order cancelled successfully")
        
        # Verify cancellation
        await asyncio.sleep(1)
        cancelled_order = await nobitex_exchange.get_order(order.order_id, symbol)
        assert cancelled_order.status in ["cancelled", "canceled"]
        logger.info(f"✅ Order cancellation verified: {cancelled_order.status}")
        
    except Exception as e:
        logger.error(f"Order lifecycle test failed: {e}", exc_info=True)
        # Try to clean up if order was placed
        if 'order' in locals() and order.order_id:
            try:
                await nobitex_exchange.cancel_order(order.order_id, symbol)
            except:
                pass
        raise


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_real_open_orders_authenticated(nobitex_exchange):
    """Test fetching open orders (requires authentication)."""
    if not nobitex_exchange.is_authenticated():
        pytest.skip("Nobitex not authenticated - skipping open orders test")
    
    logger.info("Testing open orders retrieval")
    
    open_orders = await nobitex_exchange.get_open_orders()
    
    assert isinstance(open_orders, list)
    logger.info(f"✅ Retrieved {len(open_orders)} open orders")
    
    for order in open_orders[:5]:  # Log first 5
        logger.info(f"   Order: {order.order_id} - {order.symbol} - {order.side} - {order.status}")


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_real_balance_authenticated(nobitex_exchange):
    """Test fetching balance (requires authentication)."""
    if not nobitex_exchange.is_authenticated():
        pytest.skip("Nobitex not authenticated - skipping balance test")
    
    logger.info("Testing balance retrieval")
    
    balance = await nobitex_exchange.get_balance()
    
    assert isinstance(balance, dict)
    logger.info(f"✅ Retrieved balance for {len(balance)} currencies")
    
    for currency, bal in list(balance.items())[:5]:  # Log first 5
        logger.info(f"   {currency}: Available={bal.available:.2f}, Locked={bal.locked:.2f}")


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_real_price_stream_integration(nobitex_exchange, invex_exchange, trading_config):
    """Test price stream with real exchanges."""
    from app.strategy.price_stream import PriceStream
    
    symbol = "BTCUSDT"
    
    logger.info(f"Testing price stream integration for {symbol}")
    
    exchanges = {
        ExchangeName.NOBITEX.value: nobitex_exchange,
        ExchangeName.INVEX.value: invex_exchange,
    }
    
    price_stream = PriceStream(exchanges, trading_config)
    
    # Track updates
    updates_received = []
    
    def on_update(sym: str, orderbooks: Dict):
        updates_received.append((sym, len(orderbooks)))
        logger.info(f"Price update: {sym} - {len(orderbooks)} orderbooks")
    
    price_stream.subscribe(on_update)
    
    # Start stream
    await price_stream.start([symbol])
    
    # Wait for a few updates
    await asyncio.sleep(5)
    
    # Stop stream
    await price_stream.stop()
    
    assert len(updates_received) > 0, "No price updates received"
    logger.info(f"✅ Received {len(updates_received)} price updates")
    
    # Verify orderbooks are available
    orderbooks = price_stream.get_orderbooks(symbol)
    assert orderbooks is not None
    assert len(orderbooks) > 0
    logger.info(f"✅ Orderbooks available for {len(orderbooks)} exchanges")


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_real_ohlc_data(nobitex_exchange):
    """Test fetching OHLC data from real exchange."""
    symbol = "BTCIRT"
    
    logger.info(f"Testing OHLC data fetch for {symbol}")
    
    ohlc = await nobitex_exchange.fetch_ohlc(
        symbol=symbol,
        interval="1h",
        limit=10,
    )
    
    assert ohlc is not None
    assert isinstance(ohlc, list), "OHLC should be a list of OHLCData objects"
    assert len(ohlc) > 0, f"No OHLC data returned for {symbol} - endpoint may be incorrect or symbol not supported"
    
    logger.info(f"✅ Retrieved {len(ohlc)} OHLC candles")
    
    # Log first candle
    if ohlc:
        candle = ohlc[0]
        logger.info(f"   First candle: O={candle.open:.2f}, H={candle.high:.2f}, "
                   f"L={candle.low:.2f}, C={candle.close:.2f}, V={candle.volume:.2f}")


@pytest.mark.asyncio
@pytest.mark.skipif(SKIP_REAL_API, reason="Real API tests skipped")
async def test_real_multi_exchange_opportunity_scan(nobitex_exchange, invex_exchange, wallex_exchange, trading_config):
    """Test scanning for opportunities across multiple real exchanges."""
    symbol = "BTCUSDT"
    
    logger.info(f"Testing multi-exchange opportunity scan for {symbol}")
    
    exchanges = {
        ExchangeName.NOBITEX: nobitex_exchange,
        ExchangeName.INVEX: invex_exchange,
        ExchangeName.WALLEX: wallex_exchange,
    }
    
    engine = ArbitrageEngine(exchanges, trading_config)
    
    # Fetch orderbooks from all exchanges
    orderbooks = {}
    for name, exchange in exchanges.items():
        try:
            orderbook = await exchange.fetch_orderbook(symbol, depth=20)
            orderbooks[name.value] = orderbook
            logger.info(f"✅ Fetched orderbook from {name.value}")
        except Exception as e:
            logger.warning(f"Failed to fetch from {name.value}: {e}")
    
    if len(orderbooks) < 2:
        pytest.skip("Need at least 2 exchanges with valid orderbooks")
    
    # Find opportunities
    opportunities = engine.find_opportunities(symbol, orderbooks)
    
    logger.info(f"✅ Scanned {len(orderbooks)} exchanges, found {len(opportunities)} opportunities")
    
    # Log all opportunities
    for i, opp in enumerate(opportunities[:5], 1):  # Log first 5
        logger.info(f"   {i}. {opp.buy_exchange} -> {opp.sell_exchange}: "
                   f"Spread={opp.spread_percent:.4f}%, Profit={opp.net_profit:.2f} USDT")
    
    assert isinstance(opportunities, list)


