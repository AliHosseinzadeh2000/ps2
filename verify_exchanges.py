#!/usr/bin/env python3
"""
Exchange Connectivity Verification Script
==========================================
Tests connection to all 5 exchanges and generates a report.
"""

import asyncio
import sys
from datetime import datetime
from typing import Dict, List

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
from app.core.exchange_types import ExchangeName


class ExchangeVerifier:
    """Verifies connectivity to all exchanges."""

    def __init__(self):
        self.results: List[Dict] = []

    async def verify_exchange(self, name: str, exchange, symbol: str) -> Dict:
        """Verify a single exchange."""
        result = {
            "exchange": name,
            "symbol": symbol,
            "authenticated": False,
            "orderbook_fetch": False,
            "orderbook_depth": 0,
            "spread": None,
            "best_bid": None,
            "best_ask": None,
            "error": None,
            "response_time_ms": None,
        }

        try:
            # Check authentication
            result["authenticated"] = exchange.is_authenticated()

            # Try to fetch orderbook
            start_time = datetime.now()
            orderbook = await exchange.fetch_orderbook(symbol, depth=10)
            end_time = datetime.now()

            if orderbook and orderbook.bids and orderbook.asks:
                result["orderbook_fetch"] = True
                result["orderbook_depth"] = len(orderbook.bids) + len(orderbook.asks)
                result["best_bid"] = orderbook.bids[0].price
                result["best_ask"] = orderbook.asks[0].price
                result["spread"] = orderbook.asks[0].price - orderbook.bids[0].price
                result["response_time_ms"] = (end_time - start_time).total_seconds() * 1000

        except Exception as e:
            result["error"] = str(e)

        return result

    async def verify_all(self) -> List[Dict]:
        """Verify all exchanges."""
        exchanges = [
            ("Nobitex", NobitexExchange(NobitexConfig()), "BTCUSDT"),
            ("Wallex", WallexExchange(WallexConfig()), "BTCUSDT"),
            ("Invex", InvexExchange(InvexConfig()), "BTC_USDT"),
            ("KuCoin", KucoinExchange(KucoinConfig()), "BTC-USDT"),
            ("Tabdeal", TabdealExchange(TabdealConfig()), "BTCUSDT"),
        ]

        print("=" * 80)
        print("EXCHANGE CONNECTIVITY VERIFICATION")
        print("=" * 80)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        for name, exchange, symbol in exchanges:
            print(f"Testing {name}... ", end="", flush=True)
            result = await self.verify_exchange(name, exchange, symbol)
            self.results.append(result)

            if result["orderbook_fetch"]:
                print(f"✅ OK ({result['response_time_ms']:.0f}ms)")
            else:
                print(f"❌ FAILED")
                if result["error"]:
                    print(f"   Error: {result['error'][:100]}")

        return self.results

    def print_summary(self):
        """Print summary table."""
        print()
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print()

        # Table header
        print(f"{'Exchange':<12} {'Auth':<6} {'Orderbook':<10} {'Depth':<7} {'Best Bid':<12} {'Best Ask':<12} {'Spread':<10} {'Time(ms)':<10}")
        print("-" * 120)

        for result in self.results:
            auth = "✅" if result["authenticated"] else "❌"
            orderbook = "✅" if result["orderbook_fetch"] else "❌"
            depth = str(result["orderbook_depth"]) if result["orderbook_fetch"] else "-"
            bid = f"{result['best_bid']:.2f}" if result["best_bid"] else "-"
            ask = f"{result['best_ask']:.2f}" if result["best_ask"] else "-"
            spread = f"{result['spread']:.2f}" if result["spread"] else "-"
            time_ms = f"{result['response_time_ms']:.0f}" if result["response_time_ms"] else "-"

            print(f"{result['exchange']:<12} {auth:<6} {orderbook:<10} {depth:<7} {bid:<12} {ask:<12} {spread:<10} {time_ms:<10}")

        print()

        # Statistics
        total = len(self.results)
        authenticated = sum(1 for r in self.results if r["authenticated"])
        operational = sum(1 for r in self.results if r["orderbook_fetch"])

        print(f"Total Exchanges: {total}")
        print(f"Authenticated: {authenticated}/{total}")
        print(f"Operational: {operational}/{total}")
        print()

        if operational == total:
            print("✅ ALL EXCHANGES OPERATIONAL")
        elif operational >= total - 1:
            print("⚠️  MOSTLY OPERATIONAL (1 exchange down)")
        else:
            print("❌ MULTIPLE EXCHANGES HAVE ISSUES")

        print("=" * 80)

        return operational == total


async def main():
    """Main function."""
    verifier = ExchangeVerifier()

    try:
        await verifier.verify_all()
        all_ok = verifier.print_summary()

        # Exit code
        sys.exit(0 if all_ok else 1)

    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
