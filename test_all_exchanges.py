#!/usr/bin/env python3
"""Comprehensive test for all exchange APIs - public and authenticated endpoints."""

import asyncio
import sys
from datetime import datetime

# Setup logging first
from app.core.logging import setup_logging
setup_logging()

from app.exchanges.nobitex import NobitexExchange
from app.exchanges.invex import InvexExchange
from app.exchanges.wallex import WallexExchange
from app.exchanges.kucoin import KucoinExchange
from app.exchanges.tabdeal import TabdealExchange
from app.core.config import settings  # Use global settings with credentials

# Test results storage
results = {}

async def test_exchange(name: str, exchange, test_symbol: str):
    """Test an exchange's public and authenticated endpoints."""
    results[name] = {
        "orderbook": {"status": "❌", "details": ""},
        "ohlc": {"status": "❌", "details": ""},
        "auth": {"status": "❌", "details": ""},
        "balance": {"status": "❌", "details": ""},
    }

    print(f"\n{'='*60}")
    print(f"TESTING {name}")
    print(f"{'='*60}")

    try:
        # Test 1: Orderbook (public)
        print(f"\n1. Orderbook ({test_symbol})...")
        try:
            ob = await exchange.fetch_orderbook(test_symbol, depth=5)
            if ob and ob.bids and ob.asks:
                best_bid = ob.bids[0].price
                best_ask = ob.asks[0].price
                spread = ((best_ask - best_bid) / best_bid) * 100
                results[name]["orderbook"] = {
                    "status": "✅",
                    "details": f"bid={best_bid:,.2f}, ask={best_ask:,.2f}, spread={spread:.3f}%"
                }
                print(f"   ✅ OK: {results[name]['orderbook']['details']}")
            else:
                results[name]["orderbook"]["details"] = "Empty orderbook"
                print(f"   ⚠️ Empty orderbook returned")
        except Exception as e:
            results[name]["orderbook"]["details"] = str(e)[:100]
            print(f"   ❌ ERROR: {e}")

        # Test 2: OHLC (public)
        print(f"\n2. OHLC data...")
        try:
            ohlc = await exchange.fetch_ohlc(test_symbol, interval='1h', limit=3)
            if ohlc and len(ohlc) > 0:
                results[name]["ohlc"] = {
                    "status": "✅",
                    "details": f"{len(ohlc)} candles, last close={ohlc[-1].close:,.2f}"
                }
                print(f"   ✅ OK: {results[name]['ohlc']['details']}")
            else:
                results[name]["ohlc"]["details"] = "No OHLC data"
                print(f"   ⚠️ No OHLC data returned")
        except Exception as e:
            results[name]["ohlc"]["details"] = str(e)[:100]
            print(f"   ❌ ERROR: {e}")

        # Test 3: Authentication check (not async)
        print(f"\n3. Authentication...")
        try:
            is_auth = exchange.is_authenticated()  # Not async
            if is_auth:
                results[name]["auth"] = {"status": "✅", "details": "Credentials configured"}
                print(f"   ✅ Credentials configured")
            else:
                results[name]["auth"]["details"] = "No credentials"
                print(f"   ⚠️ No credentials configured")
        except Exception as e:
            results[name]["auth"]["details"] = str(e)[:100]
            print(f"   ❌ ERROR: {e}")

        # Test 4: Balance (authenticated)
        print(f"\n4. Get balance...")
        try:
            # Invex requires a currency parameter
            if name == "INVEX":
                balance = await exchange.get_balance("USDT")
            else:
                balance = await exchange.get_balance()
            if balance:
                # Balance values are Balance objects with .available and .locked
                non_zero = {k: v for k, v in balance.items() if v.available > 0 or v.locked > 0}
                if non_zero:
                    sample = list(non_zero.items())[:3]
                    details = ", ".join([f"{k}={v.available:.4f}" for k, v in sample])
                    results[name]["balance"] = {"status": "✅", "details": details}
                    print(f"   ✅ OK: {details}")
                else:
                    results[name]["balance"] = {"status": "✅", "details": "All balances zero"}
                    print(f"   ✅ OK (all balances zero)")
            else:
                results[name]["balance"]["details"] = "Empty response"
                print(f"   ⚠️ Empty balance response")
        except Exception as e:
            results[name]["balance"]["details"] = str(e)[:100]
            print(f"   ❌ ERROR: {e}")

    except Exception as e:
        print(f"   ❌ FATAL ERROR: {e}")
    finally:
        try:
            await exchange.close()
        except:
            pass


async def main():
    print(f"\n{'#'*60}")
    print(f"# EXCHANGE API TEST - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # Define exchanges with their test symbols (using global settings with credentials)
    exchanges = [
        ("NOBITEX", NobitexExchange(settings.nobitex), "BTCIRT"),
        ("WALLEX", WallexExchange(settings.wallex), "USDTTMN"),
        ("INVEX", InvexExchange(settings.invex), "BTC_USDT"),
        ("KUCOIN", KucoinExchange(settings.kucoin), "BTC-USDT"),
        ("TABDEAL", TabdealExchange(settings.tabdeal), "BTCIRT"),
    ]

    for name, exchange, symbol in exchanges:
        await test_exchange(name, exchange, symbol)

    # Print summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"\n{'Exchange':<12} {'Orderbook':<12} {'OHLC':<12} {'Auth':<12} {'Balance':<12}")
    print("-" * 60)

    for name in ["NOBITEX", "WALLEX", "INVEX", "KUCOIN", "TABDEAL"]:
        if name in results:
            r = results[name]
            print(f"{name:<12} {r['orderbook']['status']:<12} {r['ohlc']['status']:<12} {r['auth']['status']:<12} {r['balance']['status']:<12}")

    print(f"\n{'='*60}")
    print("DETAILED RESULTS")
    print(f"{'='*60}")
    for name, r in results.items():
        print(f"\n{name}:")
        for test, data in r.items():
            print(f"  {test}: {data['status']} {data['details']}")


if __name__ == "__main__":
    asyncio.run(main())
