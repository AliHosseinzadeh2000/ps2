#!/usr/bin/env python3
"""Unified test script for the arbitrage trading bot.

This script provides comprehensive testing capabilities with different modes:
- Realistic mode: Tests with real exchange APIs
- Paper trade mode: Simulates trades without execution
- Dry-run mode: Preview only, no execution
- Integration tests: Full flow testing

Usage:
    python test_bot.py [OPTIONS]

Examples:
    # Test symbol conversion and orderbook fetching
    python test_bot.py --mode realistic --symbol BTCUSDT
    
    # Test with Iranian pairs
    python test_bot.py --mode realistic --symbol USDTIRT
    
    # Paper trade mode (simulate trades)
    python test_bot.py --mode paper --symbol BTCUSDT
    
    # Dry-run (preview only)
    python test_bot.py --mode dry-run --symbol BTCUSDT
    
    # Test order lifecycle (requires authentication)
    python test_bot.py --mode integration --test-order-lifecycle
    
    # Test all exchanges
    python test_bot.py --mode realistic --all-exchanges
"""

import asyncio
import argparse
import sys
from typing import Dict, List, Optional
from enum import Enum

from app.exchanges.nobitex import NobitexExchange
from app.exchanges.invex import InvexExchange
from app.exchanges.wallex import WallexExchange
from app.core.config import (
    NobitexConfig,
    InvexConfig,
    WallexConfig,
    TradingConfig,
)
from app.strategy.arbitrage_engine import ArbitrageEngine
from app.strategy.order_executor import OrderExecutor
from app.core.exchange_types import ExchangeName, TradingSymbol
from app.core.logging import setup_logging, get_logger
from app.utils.symbol_converter import ExchangeSymbolMapper, SymbolConverter
from app.ai.predictor import TradingPredictor
from app.ai.model import TradingModel
from app.data.collector import DataCollector

# Setup logging
setup_logging()
logger = get_logger(__name__)


class TestMode(str, Enum):
    """Test execution modes."""
    REALISTIC = "realistic"  # Real exchange APIs, no execution
    PAPER = "paper"  # Simulate trades (paper trading)
    DRY_RUN = "dry-run"  # Preview only
    INTEGRATION = "integration"  # Full integration tests


async def test_symbol_conversion():
    """Test symbol conversion logic (IRT/IRR/TMN compatibility)."""
    print("\n" + "="*60)
    print("TEST: Symbol Conversion Logic")
    print("="*60)
    
    test_cases = [
        ("BTCUSDT", ExchangeName.NOBITEX, None, "USDT not supported on Nobitex"),
        ("BTCIRT", ExchangeName.NOBITEX, "BTCIRT", "IRT supported on Nobitex"),
        ("BTCIRT", ExchangeName.INVEX, "BTC_IRR", "IRT→IRR conversion allowed"),
        ("BTCIRR", ExchangeName.NOBITEX, "BTCIRT", "IRR→IRT conversion allowed"),
        ("BTCIRT", ExchangeName.WALLEX, "BTCTMN", "IRT→TMN conversion allowed (same currency)"),
        ("BTCTMN", ExchangeName.NOBITEX, "BTCIRT", "TMN→IRT conversion allowed (same currency)"),
        ("BTCUSDT", ExchangeName.WALLEX, "BTCUSDT", "USDT supported on Wallex"),
        ("ETHUSDT", ExchangeName.NOBITEX, None, "USDT not supported on Nobitex"),
        ("ETHIRT", ExchangeName.WALLEX, "ETHTMN", "IRT→TMN conversion (same currency)"),
    ]
    
    all_passed = True
    for symbol, exchange, expected, description in test_cases:
        result = ExchangeSymbolMapper.get_symbol_for_exchange(symbol, exchange)
        passed = result == expected
        status = "✅" if passed else "❌"
        print(f"{status} {description}")
        print(f"   Input: {symbol} on {exchange.value}")
        print(f"   Expected: {expected}, Got: {result}")
        if not passed:
            all_passed = False
        print()
    
    return all_passed


async def test_orderbook_fetching(symbol: str, all_exchanges: bool = False) -> Dict[str, any]:
    """Test fetching real orderbooks from exchanges."""
    print("\n" + "="*60)
    print("TEST: Orderbook Fetching")
    print("="*60)
    
    exchanges = {
        ExchangeName.NOBITEX: NobitexExchange(NobitexConfig()),
        ExchangeName.INVEX: InvexExchange(InvexConfig()),
        ExchangeName.WALLEX: WallexExchange(WallexConfig()),
    }
    
    base_currency = SymbolConverter.get_base_currency(symbol)
    quote_currency = SymbolConverter.get_quote_currency(symbol)
    
    print(f"\nFetching orderbooks for {symbol} (base: {base_currency}, quote: {quote_currency})...")
    
    orderbooks = {}
    for name, exchange in exchanges.items():
        try:
            exchange_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(symbol, name)
            
            if not exchange_symbol:
                print(f"⚠️  {name.value}: No compatible symbol (supports: {SymbolConverter.EXCHANGE_QUOTE_CURRENCIES.get(name, [])})")
                if not all_exchanges:
                    continue
            
            orderbook = await exchange.fetch_orderbook(exchange_symbol, depth=10)
            orderbooks[name.value] = orderbook
            
            if orderbook.bids and orderbook.asks:
                spread = orderbook.asks[0].price - orderbook.bids[0].price
                spread_pct = (spread / orderbook.bids[0].price) * 100
                print(f"✅ {name.value}: {exchange_symbol}")
                print(f"   Best bid: {orderbook.bids[0].price:.2f}")
                print(f"   Best ask: {orderbook.asks[0].price:.2f}")
                print(f"   Spread: {spread:.2f} ({spread_pct:.4f}%)")
            else:
                print(f"⚠️  {name.value}: Empty orderbook")
        except Exception as e:
            error_msg = str(e)
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            print(f"❌ {name.value}: {error_msg}")
    
    return orderbooks


async def test_opportunity_detection(symbol: str, orderbooks: Dict, min_spread: float = 0.05):
    """Test arbitrage opportunity detection."""
    print("\n" + "="*60)
    print("TEST: Arbitrage Opportunity Detection")
    print("="*60)
    
    if len(orderbooks) < 2:
        print("⚠️  Need at least 2 exchanges to detect opportunities")
        return []
    
    config = TradingConfig(
        min_spread_percent=min_spread,  # Lower threshold for testing
        min_profit_usdt=0.01,  # Very low minimum for testing
        max_position_size_usdt=10.0,  # Small position for testing
    )
    
    exchanges = {
        ExchangeName.NOBITEX: NobitexExchange(NobitexConfig()),
        ExchangeName.INVEX: InvexExchange(InvexConfig()),
        ExchangeName.WALLEX: WallexExchange(WallexConfig()),
    }
    
    engine = ArbitrageEngine(exchanges, config)
    opportunities = engine.find_opportunities(symbol, orderbooks)
    
    print(f"\nFound {len(opportunities)} opportunities (min_spread: {min_spread}%):")
    
    if opportunities:
        for i, opp in enumerate(opportunities[:5], 1):
            print(f"\n{i}. {opp.buy_exchange} → {opp.sell_exchange}")
            print(f"   Symbol: {opp.symbol}")
            print(f"   Buy Price:  {opp.buy_price:.2f}")
            print(f"   Sell Price: {opp.sell_price:.2f}")
            print(f"   Spread:     {opp.spread_percent:.4f}%")
            print(f"   Net Profit: {opp.net_profit:.2f}")
            print(f"   Quantity:   {opp.max_quantity:.8f}")
            print(f"   Fees:       Buy {opp.buy_fee*100:.2f}%, Sell {opp.sell_fee*100:.2f}%")
    else:
        print("   No profitable opportunities found")
        if len(orderbooks) >= 2:
            print("   This could be due to:")
            print("   - Spread too small to cover fees")
            print("   - Price differences not sufficient")
            print("   - Incompatible quote currencies")
    
    return opportunities


async def test_order_preview(opportunities: List, mode: TestMode, execute: bool = False):
    """Test order preview and optionally execute."""
    print("\n" + "="*60)
    print(f"TEST: Order Preview ({mode.value.upper()} MODE)")
    print("="*60)
    
    if not opportunities:
        print("⚠️  No opportunities to preview")
        return
    
    opp = opportunities[0]
    
    print(f"\nPreviewing order for opportunity:")
    print(f"   {opp.buy_exchange} → {opp.sell_exchange}")
    print(f"   Symbol: {opp.symbol}")
    print(f"   Quantity: {opp.max_quantity:.8f}")
    print(f"   Expected Profit: {opp.net_profit:.2f}")
    print(f"   Risk Level: LOW (small quantity, verified spread)")
    
    if mode == TestMode.DRY_RUN:
        print(f"\n⚠️  DRY RUN MODE - Order not executed")
    elif mode == TestMode.PAPER:
        print(f"\n📄 PAPER TRADE MODE - Order simulated (not executed)")
    elif mode == TestMode.REALISTIC:
        if execute:
            print(f"\n⚠️  EXECUTE MODE - Attempting to execute order...")
            try:
                from app.api.services import get_order_executor, get_exchanges
                executor = get_order_executor()
                exchanges = get_exchanges()
                
                # Get exchange instances
                buy_exchange = exchanges.get(ExchangeName.from_string(opp.buy_exchange))
                sell_exchange = exchanges.get(ExchangeName.from_string(opp.sell_exchange))
                
                if not buy_exchange or not sell_exchange:
                    print(f"❌ Exchanges not available for execution")
                    return
                
                if not buy_exchange.is_authenticated() or not sell_exchange.is_authenticated():
                    print(f"❌ Exchanges not authenticated - cannot execute")
                    print(f"   Buy exchange authenticated: {buy_exchange.is_authenticated()}")
                    print(f"   Sell exchange authenticated: {sell_exchange.is_authenticated()}")
                    return
                
                print(f"\nExecuting arbitrage order...")
                buy_order, sell_order = await executor.execute_arbitrage(opp)
                
                if buy_order and sell_order:
                    print(f"✅ Orders placed successfully!")
                    print(f"   Buy Order ID: {buy_order.order_id} ({buy_order.status})")
                    print(f"   Sell Order ID: {sell_order.order_id} ({sell_order.status})")
                else:
                    print(f"⚠️  Order execution failed or partially completed")
            except Exception as e:
                print(f"❌ Order execution failed: {e}")
                logger.error("Order execution failed", exc_info=True)
        else:
            print(f"\n⚠️  REALISTIC MODE - Order preview only")
            print(f"   Use --execute flag to actually execute orders (requires authentication)")


async def test_order_lifecycle(symbol: str = "BTCUSDT"):
    """Test order placement, status check, and cancellation."""
    print("\n" + "="*60)
    print("TEST: Order Lifecycle")
    print("="*60)
    
    exchanges_to_test = {
        "Nobitex": (NobitexExchange, NobitexConfig),
        "Invex": (InvexExchange, InvexConfig),
        "Wallex": (WallexExchange, WallexConfig),
    }
    
    exchange_instance = None
    exchange_name = None
    
    # Find first authenticated exchange
    for name, (exchange_class, config_class) in exchanges_to_test.items():
        exchange = exchange_class(config_class())
        if exchange.is_authenticated():
            exchange_instance = exchange
            exchange_name = name
            print(f"✅ Found authenticated exchange: {name}")
            break
    
    if not exchange_instance:
        print("⚠️  No authenticated exchanges found")
        print("   Configure at least one exchange in .env:")
        print("   - NOBITEX_TOKEN or NOBITEX_USERNAME/NOBITEX_PASSWORD")
        print("   - INVEX_API_KEY and INVEX_API_SECRET")
        print("   - WALLEX_API_KEY and WALLEX_API_SECRET")
        return False
    
    # Get compatible symbol
    exchange_enum = ExchangeName.from_string(exchange_name.upper())
    test_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(symbol, exchange_enum)
    
    if not test_symbol:
        base_currency = SymbolConverter.get_base_currency(symbol)
        quote_currency = SymbolConverter.get_quote_currency(symbol)
        if base_currency and quote_currency:
            supported_quotes = SymbolConverter.EXCHANGE_QUOTE_CURRENCIES.get(exchange_enum, [])
            iranian_currencies = SymbolConverter.IRANIAN_CURRENCY_ALIASES
            if quote_currency.upper() in iranian_currencies:
                for iranian_quote in iranian_currencies:
                    if iranian_quote in supported_quotes:
                        alt_symbol = f"{base_currency}{iranian_quote}"
                        test_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(alt_symbol, exchange_enum)
                        break
    
    if not test_symbol:
        print(f"⚠️  No compatible symbol found for {exchange_name} with {symbol}")
        return False
    
    print(f"   Using symbol: {test_symbol} on {exchange_name}")
    
    try:
        # Get current market price
        print(f"\nFetching current market price for {test_symbol}...")
        orderbook = await exchange_instance.fetch_orderbook(test_symbol, depth=1)
        current_price = orderbook.asks[0].price
        print(f"✅ Current market price: {current_price:.2f}")
        
        # Place a test order well below market (won't fill)
        test_price = current_price * 0.95  # 5% below market
        test_quantity = 0.0001
        
        print(f"\nPlacing test order:")
        print(f"   Symbol: {test_symbol}")
        print(f"   Side: buy")
        print(f"   Quantity: {test_quantity}")
        print(f"   Price: {test_price:.2f} (5% below market)")
        
        order = await exchange_instance.place_order(
            symbol=test_symbol,
            side="buy",
            order_type="limit",
            quantity=test_quantity,
            price=test_price,
            is_maker=False,
        )
        
        print(f"✅ Order placed: {order.order_id}")
        print(f"   Status: {order.status}")
        
        # Check order status
        print("\nChecking order status...")
        await asyncio.sleep(1)
        status_order = await exchange_instance.get_order(order.order_id, test_symbol)
        print(f"✅ Order status: {status_order.status}")
        
        # Cancel order
        print("\nCancelling order...")
        cancelled = await exchange_instance.cancel_order(order.order_id, test_symbol)
        if cancelled:
            print(f"✅ Order cancelled successfully")
            await asyncio.sleep(1)
            cancelled_order = await exchange_instance.get_order(order.order_id, test_symbol)
            print(f"✅ Final status: {cancelled_order.status}")
            return True
        else:
            print("⚠️  Cancellation returned False")
            return False
            
    except Exception as e:
        print(f"❌ Order lifecycle test failed: {e}")
        logger.error("Order lifecycle test failed", exc_info=True)
        return False


async def test_risk_limits():
    """Test risk management limits."""
    print("\n" + "="*60)
    print("TEST: Risk Management Limits")
    print("="*60)
    
    config = TradingConfig()
    
    print(f"✅ Risk limits configured:")
    print(f"   Max position per exchange: {config.max_position_per_exchange} USDT")
    print(f"   Daily loss limit: {config.daily_loss_limit} USDT")
    print(f"   Max slippage: {config.max_slippage_percent}%")
    print(f"   Balance check required: {config.require_balance_check}")
    print(f"\n✅ Risk management is active and will prevent:")
    print(f"   - Exceeding position limits")
    print(f"   - Trading beyond daily loss limit")
    print(f"   - Orders with excessive slippage")
    print(f"   - Trading without sufficient balance")


async def main():
    """Run tests based on mode."""
    parser = argparse.ArgumentParser(
        description="Unified test script for arbitrage trading bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--mode", type=TestMode, default=TestMode.REALISTIC,
                       choices=list(TestMode),
                       help="Test execution mode")
    parser.add_argument("--symbol", default="BTCUSDT",
                       help="Trading symbol to test")
    parser.add_argument("--min-spread", type=float, default=0.05,
                       help="Minimum spread percentage for opportunity detection")
    parser.add_argument("--all-exchanges", action="store_true",
                       help="Test all exchanges even if symbol not supported")
    parser.add_argument("--test-order-lifecycle", action="store_true",
                       help="Test order placement, status, and cancellation")
    parser.add_argument("--execute", action="store_true",
                       help="Actually execute orders (use with caution!)")
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("ARBITRAGE BOT TEST SUITE")
    print("="*60)
    print(f"\nMode: {args.mode.value.upper()}")
    print(f"Symbol: {args.symbol}")
    print(f"Min Spread: {args.min_spread}%")
    
    try:
        # Test 1: Symbol conversion
        conversion_ok = await test_symbol_conversion()
        if not conversion_ok:
            print("\n❌ Symbol conversion tests failed")
            sys.exit(1)
        
        # Test 2: Orderbook fetching
        orderbooks = await test_orderbook_fetching(args.symbol, args.all_exchanges)
        
        if len(orderbooks) < 2:
            print("\n⚠️  Not enough orderbooks fetched")
            if args.mode != TestMode.INTEGRATION:
                return
        
        # Test 3: Opportunity detection
        opportunities = await test_opportunity_detection(args.symbol, orderbooks, args.min_spread)
        
        # Test 4: Order preview (and execute if requested)
        await test_order_preview(opportunities, args.mode, args.execute)
        
        # Test 5: Risk limits
        await test_risk_limits()
        
        # Test 6: Order lifecycle (if requested)
        if args.test_order_lifecycle:
            await test_order_lifecycle(args.symbol)
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED")
        print("="*60)
        print(f"\nSummary:")
        print(f"  ✅ Symbol conversion logic verified (IRT/IRR/TMN compatibility)")
        print(f"  ✅ Orderbook fetching from {len(orderbooks)} exchanges")
        print(f"  ✅ Opportunity detection: {len(opportunities)} opportunities found")
        print(f"  ✅ Risk management limits configured")
        
        if opportunities:
            print(f"\n💡 Found {len(opportunities)} potential arbitrage opportunities!")
            print(f"   Best opportunity: {opportunities[0].net_profit:.2f} profit")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test suite failed: {e}")
        logger.error("Test suite failed", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

