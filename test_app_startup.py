"""Test if the app can start without errors."""

import asyncio
import sys

async def test_startup():
    """Test that all services can be initialized."""
    print("Testing app startup...")
    
    try:
        # Test imports
        print("1. Testing imports...")
        from app.api.services import (
            get_exchanges,
            get_arbitrage_engine,
            get_order_executor,
            get_price_stream,
        )
        print("   ✓ All imports successful")
        
        # Test service initialization
        print("\n2. Testing service initialization...")
        exchanges = get_exchanges()
        print(f"   ✓ Exchanges initialized: {list(exchanges.keys())}")
        
        engine = get_arbitrage_engine()
        print("   ✓ Arbitrage engine initialized")
        
        executor = get_order_executor()
        print("   ✓ Order executor initialized")
        
        price_stream = get_price_stream()
        print("   ✓ Price stream initialized")
        
        # Test Wallex orderbook (should work without API keys)
        print("\n3. Testing Wallex orderbook (public endpoint)...")
        wallex = exchanges.get("wallex")
        if wallex:
            try:
                orderbook = await wallex.fetch_orderbook("BTCUSDT", depth=5)
                print(f"   ✓ Wallex orderbook fetched successfully")
                print(f"   Best bid: {orderbook.bids[0].price if orderbook.bids else 'N/A'}")
                print(f"   Best ask: {orderbook.asks[0].price if orderbook.asks else 'N/A'}")
            except Exception as e:
                print(f"   ⚠️ Wallex orderbook error: {e}")
                print("   (This might be a network issue or API change)")
        
        print("\n" + "="*50)
        print("✓ App startup test completed!")
        print("\nNote: Exchange implementations need to be updated")
        print("based on actual API documentation.")
        print("See FIX_EXCHANGES.md for details.")
        
    except Exception as e:
        print(f"\n❌ Error during startup test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_startup())




