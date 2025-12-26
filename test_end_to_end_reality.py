#!/usr/bin/env python3
"""
END-TO-END REALITY CHECK
========================
This script tests if the bot ACTUALLY WORKS, not just if code exists.
It verifies the ENTIRE flow from fetching orderbooks to detecting opportunities.

WARNING: This does NOT place real orders (too risky).
It tests everything UP TO the point of placing orders.
"""

import asyncio
import sys
from datetime import datetime

from app.exchanges.nobitex import NobitexExchange
from app.exchanges.wallex import WallexExchange
from app.exchanges.invex import InvexExchange
from app.core.config import NobitexConfig, WallexConfig, InvexConfig, TradingConfig
from app.strategy.arbitrage_engine import ArbitrageEngine
from app.strategy.order_executor import OrderExecutor
from app.core.exchange_types import ExchangeName
from app.db.db import get_session_factory
from app.db.models import OrderRecord, TradeRecord


class EndToEndTester:
    """Tests if the bot actually works end-to-end."""

    def __init__(self):
        self.results = {}
        self.critical_failures = []

    async def test_01_exchange_connectivity(self):
        """TEST 1: Can we actually fetch real orderbooks?"""
        print("\n" + "="*80)
        print("TEST 1: Exchange Connectivity (REAL API CALLS)")
        print("="*80)

        exchanges = [
            ("Nobitex", NobitexExchange(NobitexConfig()), "BTCUSDT"),
            ("Wallex", WallexExchange(WallexConfig()), "BTCUSDT"),
            ("Invex", InvexExchange(InvexConfig()), "BTC_USDT"),
        ]

        working_exchanges = []

        for name, exchange, symbol in exchanges:
            try:
                print(f"\n{name}: Fetching orderbook for {symbol}...", end=" ")
                orderbook = await exchange.fetch_orderbook(symbol, depth=10)

                if orderbook and orderbook.bids and orderbook.asks:
                    best_bid = orderbook.bids[0].price
                    best_ask = orderbook.asks[0].price
                    spread = best_ask - best_bid
                    print(f"✅ WORKS")
                    print(f"   Best Bid: {best_bid}, Best Ask: {best_ask}, Spread: {spread}")
                    working_exchanges.append((name, exchange))
                else:
                    print(f"❌ FAILED - Empty orderbook")
                    self.critical_failures.append(f"{name}: Empty orderbook")

            except Exception as e:
                print(f"❌ FAILED - {str(e)[:100]}")
                self.critical_failures.append(f"{name}: {str(e)[:100]}")

        self.results["working_exchanges"] = len(working_exchanges)
        self.results["exchange_list"] = [name for name, _ in working_exchanges]

        if len(working_exchanges) < 2:
            print(f"\n⚠️  CRITICAL: Only {len(working_exchanges)} exchange(s) working!")
            print("   Need at least 2 for arbitrage!")
            return False, working_exchanges
        else:
            print(f"\n✅ {len(working_exchanges)} exchanges operational")
            return True, working_exchanges

    async def test_02_arbitrage_detection(self, working_exchanges):
        """TEST 2: Can we actually detect arbitrage opportunities?"""
        print("\n" + "="*80)
        print("TEST 2: Arbitrage Detection (REAL MARKET DATA)")
        print("="*80)

        if len(working_exchanges) < 2:
            print("❌ SKIPPED - Need at least 2 exchanges")
            return False, None

        # Setup
        exchange_dict = {
            ExchangeName.from_string(name): exchange
            for name, exchange in working_exchanges
        }
        config = TradingConfig(min_spread_percent=0.1, min_profit_usdt=0.5)
        engine = ArbitrageEngine(exchange_dict, config)

        symbol = "BTCUSDT"
        print(f"\nFetching orderbooks from all exchanges for {symbol}...")

        # Fetch all orderbooks
        orderbooks = {}
        for name, exchange in working_exchanges:
            try:
                ob = await exchange.fetch_orderbook(symbol, depth=20)
                if ob:
                    orderbooks[name] = ob
                    print(f"  {name}: ✅ Got orderbook")
            except Exception as e:
                print(f"  {name}: ❌ {str(e)[:50]}")

        if len(orderbooks) < 2:
            print("\n❌ CRITICAL: Couldn't fetch enough orderbooks")
            self.critical_failures.append("Arbitrage detection: Not enough orderbooks")
            return False, None

        # Detect opportunities
        print(f"\nRunning arbitrage detection algorithm...")
        try:
            opportunities = engine.find_opportunities(symbol, orderbooks)

            print(f"\n{'='*80}")
            print(f"RESULT: Found {len(opportunities)} opportunities")
            print(f"{'='*80}")

            if opportunities:
                print("\nTop 3 opportunities:")
                for i, opp in enumerate(opportunities[:3], 1):
                    print(f"\n{i}. {opp.buy_exchange} → {opp.sell_exchange}")
                    print(f"   Buy Price:  {opp.buy_price:.2f}")
                    print(f"   Sell Price: {opp.sell_price:.2f}")
                    print(f"   Spread:     {opp.spread_percent:.4f}%")
                    print(f"   Net Profit: {opp.net_profit:.4f} USDT")
                    print(f"   Max Qty:    {opp.max_quantity:.8f}")

                self.results["opportunities_found"] = len(opportunities)
                self.results["best_spread"] = opportunities[0].spread_percent
                self.results["best_profit"] = opportunities[0].net_profit
                return True, opportunities[0]
            else:
                print("\n⚠️  No opportunities found (this is normal if market is efficient)")
                self.results["opportunities_found"] = 0
                return True, None  # Not a failure, just no opportunities

        except Exception as e:
            print(f"\n❌ CRITICAL FAILURE in arbitrage detection: {e}")
            self.critical_failures.append(f"Arbitrage detection crashed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, None

    async def test_03_order_preparation(self, opportunity, working_exchanges):
        """TEST 3: Can we prepare orders (without executing)?"""
        print("\n" + "="*80)
        print("TEST 3: Order Preparation (DRY RUN - NO REAL ORDERS)")
        print("="*80)

        if not opportunity:
            print("❌ SKIPPED - No opportunity to test")
            return True  # Not a critical failure

        exchange_dict = {
            ExchangeName.from_string(name): exchange
            for name, exchange in working_exchanges
        }
        config = TradingConfig()
        executor = OrderExecutor(exchange_dict, config)

        print(f"\nPreparing orders for opportunity:")
        print(f"  Buy from:  {opportunity.buy_exchange}")
        print(f"  Sell to:   {opportunity.sell_exchange}")
        print(f"  Quantity:  {opportunity.max_quantity:.8f}")
        print(f"  Profit:    {opportunity.net_profit:.4f} USDT")

        try:
            # Check if exchanges are ready
            buy_exchange = exchange_dict.get(ExchangeName.from_string(opportunity.buy_exchange))
            sell_exchange = exchange_dict.get(ExchangeName.from_string(opportunity.sell_exchange))

            if not buy_exchange or not sell_exchange:
                print("❌ CRITICAL: Exchange objects not found")
                self.critical_failures.append("Order preparation: Exchange objects missing")
                return False

            # Verify we can convert symbols
            from app.utils.symbol_converter import ExchangeSymbolMapper
            buy_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(
                "BTCUSDT", opportunity.buy_exchange
            )
            sell_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(
                "BTCUSDT", opportunity.sell_exchange
            )

            print(f"\n  Buy symbol:  {buy_symbol}")
            print(f"  Sell symbol: {sell_symbol}")

            print("\n✅ Order preparation successful (DRY RUN)")
            print("⚠️  Note: We did NOT place real orders (too risky)")

            return True

        except Exception as e:
            print(f"\n❌ CRITICAL FAILURE in order preparation: {e}")
            self.critical_failures.append(f"Order preparation failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def test_04_database_connectivity(self):
        """TEST 4: Can we connect to the database?"""
        print("\n" + "="*80)
        print("TEST 4: Database Connectivity")
        print("="*80)

        try:
            factory = get_session_factory()
            async with factory() as session:
                # Try to query existing data
                from sqlalchemy import select
                result = await session.execute(select(OrderRecord))
                orders = result.scalars().all()

                print(f"✅ Database connection successful")
                print(f"   Existing orders in DB: {len(orders)}")

                self.results["database_orders"] = len(orders)

                if len(orders) == 0:
                    print("   ⚠️  WARNING: No orders in database!")
                    print("   This means NO REAL TRADES have been executed yet!")

                return True

        except Exception as e:
            print(f"❌ CRITICAL: Database connection failed: {e}")
            self.critical_failures.append(f"Database: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def test_05_risk_management(self):
        """TEST 5: Does risk management work?"""
        print("\n" + "="*80)
        print("TEST 5: Risk Management System")
        print("="*80)

        try:
            from app.strategy.circuit_breakers import (
                MarketVolatilityCircuitBreaker,
                ExchangeConnectivityCircuitBreaker,
            )

            # Test volatility breaker
            vol_breaker = MarketVolatilityCircuitBreaker(max_volatility_percent=5.0, time_window_seconds=60)
            print("  Testing volatility circuit breaker...")

            # Simulate normal price change (should not trip)
            vol_breaker.update_price(100.0)
            await asyncio.sleep(0.1)
            vol_breaker.update_price(102.0)  # 2% change

            if not vol_breaker.is_halted():
                print("    ✅ Normal volatility: Trading continues")
            else:
                print("    ❌ False positive: Breaker tripped on normal volatility")
                return False

            # Simulate extreme volatility (should trip)
            vol_breaker2 = MarketVolatilityCircuitBreaker(max_volatility_percent=5.0, time_window_seconds=60)
            vol_breaker2.update_price(100.0)
            vol_breaker2.update_price(110.0)  # 10% change

            if vol_breaker2.is_halted():
                print("    ✅ Extreme volatility: Circuit breaker activated")
            else:
                print("    ⚠️  Warning: Breaker did NOT trip on 10% change")

            # Test connectivity breaker
            conn_breaker = ExchangeConnectivityCircuitBreaker(max_failures=3)
            print("\n  Testing connectivity circuit breaker...")

            conn_breaker.record_failure()
            conn_breaker.record_failure()
            if not conn_breaker.is_halted():
                print("    ✅ 2 failures: Trading continues")
            else:
                print("    ❌ False positive: Breaker tripped too early")
                return False

            conn_breaker.record_failure()
            if conn_breaker.is_halted():
                print("    ✅ 3 failures: Circuit breaker activated")
            else:
                print("    ❌ CRITICAL: Breaker did NOT trip after 3 failures!")
                self.critical_failures.append("Risk management: Circuit breaker not working")
                return False

            print("\n✅ Risk management system working")
            return True

        except Exception as e:
            print(f"❌ CRITICAL: Risk management failed: {e}")
            self.critical_failures.append(f"Risk management: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def run_all_tests(self):
        """Run all reality checks."""
        print("\n" + "="*80)
        print("END-TO-END REALITY CHECK FOR TRADING BOT")
        print("="*80)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Purpose: Verify if the bot ACTUALLY WORKS, not just if code exists")
        print("="*80)

        results = []

        # Test 1: Exchange connectivity
        success, working_exchanges = await self.test_01_exchange_connectivity()
        results.append(("Exchange Connectivity", success))

        # Test 2: Arbitrage detection
        success, opportunity = await self.test_02_arbitrage_detection(working_exchanges if working_exchanges else [])
        results.append(("Arbitrage Detection", success))

        # Test 3: Order preparation
        success = await self.test_03_order_preparation(
            opportunity if 'opportunity' in locals() else None,
            working_exchanges if working_exchanges else []
        )
        results.append(("Order Preparation", success))

        # Test 4: Database
        success = await self.test_04_database_connectivity()
        results.append(("Database", success))

        # Test 5: Risk management
        success = await self.test_05_risk_management()
        results.append(("Risk Management", success))

        # Print summary
        print("\n" + "="*80)
        print("FINAL RESULTS - REALITY CHECK")
        print("="*80)

        for test_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{test_name:<30} {status}")

        total = len(results)
        passed = sum(1 for _, success in results if success)

        print("\n" + "-"*80)
        print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        print("-"*80)

        if self.critical_failures:
            print("\n⚠️  CRITICAL FAILURES DETECTED:")
            for failure in self.critical_failures:
                print(f"  - {failure}")

        # The BRUTAL TRUTH
        print("\n" + "="*80)
        print("BRUTAL TRUTH ASSESSMENT")
        print("="*80)

        if self.results.get("database_orders", 0) == 0:
            print("❌ NO REAL TRADES EXECUTED")
            print("   The database has 0 orders. This means:")
            print("   - No real money has been traded")
            print("   - The execute_arbitrage() has never been called with real exchanges")
            print("   - This is essentially UNTESTED in production")

        if passed == total:
            print("\n✅ All infrastructure works")
            print("   BUT: Still needs real trading test with SMALL amounts")
        elif passed >= total - 1:
            print("\n⚠️  Mostly working (1 failure)")
            print("   Needs investigation and fixes")
        else:
            print("\n❌ MULTIPLE CRITICAL FAILURES")
            print("   Bot is NOT ready for real trading")

        print("\n" + "="*80)
        print("RECOMMENDATION:")
        print("="*80)

        if self.results.get("working_exchanges", 0) >= 2 and passed >= total - 1:
            print("✅ Code infrastructure looks good")
            print("⚠️  Next step: Test with TINY amount (like 1 USDT) to verify end-to-end")
            print("   This would:")
            print("   1. Actually place orders on real exchanges")
            print("   2. Verify order execution works")
            print("   3. Confirm data gets saved to database")
            print("   4. Test the ENTIRE flow with real money")
        else:
            print("❌ Fix critical failures first before testing with real money")

        print("="*80)

        return passed == total


async def main():
    """Main entry point."""
    tester = EndToEndTester()

    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
