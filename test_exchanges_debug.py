#!/usr/bin/env python3
"""Quick test script to debug exchange issues."""

import asyncio
import sys
from app.exchanges.nobitex import NobitexExchange
from app.exchanges.invex import InvexExchange
from app.exchanges.wallex import WallexExchange
from app.core.config import NobitexConfig, InvexConfig, WallexConfig
from app.core.logging import setup_logging

setup_logging()

async def test_nobitex():
    print("\n" + "="*60)
    print("TESTING NOBITEX")
    print("="*60)
    try:
        ex = NobitexExchange(NobitexConfig())
        
        print("\n1. Testing orderbook...")
        ob = await ex.fetch_orderbook('BTCIRT', depth=5)
        print(f"   ✅ Orderbook OK: {len(ob.bids)} bids, {len(ob.asks)} asks")
        if ob.bids and ob.asks:
            print(f"   Best bid: {ob.bids[0].price}, Best ask: {ob.asks[0].price}")
        
        print("\n2. Testing OHLC...")
        ohlc = await ex.fetch_ohlc('BTCIRT', interval='1h', limit=5)
        print(f"   ✅ OHLC OK: {len(ohlc)} candles")
        if ohlc:
            print(f"   First candle: O={ohlc[0].open}, H={ohlc[0].high}, L={ohlc[0].low}, C={ohlc[0].close}")
        
        await ex.close()
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

async def test_invex():
    print("\n" + "="*60)
    print("TESTING INVEX")
    print("="*60)
    try:
        ex = InvexExchange(InvexConfig())
        
        print("\n1. Testing symbol conversion...")
        from app.utils.symbol_converter import ExchangeSymbolMapper
        from app.core.exchange_types import ExchangeName
        
        test_symbols = ['BTCUSDT', 'BTCIRT', 'BTCIRR', 'USDTIRR']
        for sym in test_symbols:
            converted = ExchangeSymbolMapper.get_symbol_for_exchange(sym, ExchangeName.INVEX)
            print(f"   {sym} -> {converted}")
        
        print("\n2. Testing orderbook...")
        ob = await ex.fetch_orderbook('BTCUSDT', depth=5)
        print(f"   ✅ Orderbook OK: {len(ob.bids)} bids, {len(ob.asks)} asks")
        if ob.bids and ob.asks:
            print(f"   Best bid: {ob.bids[0].price}, Best ask: {ob.asks[0].price}")
        
        await ex.close()
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

async def test_wallex():
    print("\n" + "="*60)
    print("TESTING WALLEX")
    print("="*60)
    try:
        ex = WallexExchange(WallexConfig())
        
        print("\n1. Testing orderbook...")
        ob = await ex.fetch_orderbook('BTCUSDT', depth=5)
        print(f"   ✅ Orderbook OK: {len(ob.bids)} bids, {len(ob.asks)} asks")
        if ob.bids and ob.asks:
            print(f"   Best bid: {ob.bids[0].price}, Best ask: {ob.asks[0].price}")
        
        await ex.close()
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await test_nobitex()
    await test_invex()
    await test_wallex()

if __name__ == "__main__":
    asyncio.run(main())





