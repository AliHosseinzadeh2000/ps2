"""Test script to verify Nobitex and Invex exchange API implementations."""

import asyncio
import os

import httpx

# Load environment variables
from dotenv import load_dotenv

load_dotenv()


async def test_nobitex_public():
    """Test Nobitex public endpoints (no auth required)."""
    print("\n=== Testing Nobitex Public Endpoints ===")
    
    base_url = "https://apiv2.nobitex.ir"
    
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
        # Test orderbook endpoint (v3 only - v2 is deprecated and returns 503)
        print("\n1. Testing /v3/orderbook endpoint...")
        try:
            response = await client.get("/v3/orderbook/BTCIRT")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✓ Orderbook endpoint works!")
                print(f"   Response keys: {list(data.keys()) if isinstance(data, dict) else 'List'}")
                if isinstance(data, dict):
                    if "bids" in data and "asks" in data:
                        print(f"   ✓ Found bids/asks structure")
                        print(f"   Bids count: {len(data.get('bids', []))}")
                        print(f"   Asks count: {len(data.get('asks', []))}")
                        if data.get('bids') and data.get('asks'):
                            print(f"   Best bid: {data['bids'][0]}")
                            print(f"   Best ask: {data['asks'][0]}")
            else:
                print(f"   Error: {response.text[:200]}")
        except Exception as e:
            print(f"   Error: {e}")


async def test_nobitex_auth():
    """Test Nobitex authentication methods."""
    print("\n=== Testing Nobitex Authentication ===")
    
    token = os.getenv("NOBITEX_TOKEN", "")
    username = os.getenv("NOBITEX_USERNAME", "")
    password = os.getenv("NOBITEX_PASSWORD", "")
    
    if not token and not (username and password):
        print("   No Nobitex credentials found in .env file")
        print("   Please add one of the following:")
        print("   - NOBITEX_TOKEN=your_token (direct token)")
        print("   - NOBITEX_USERNAME=your_username and NOBITEX_PASSWORD=your_password (auto-login)")
        return
    
    base_url = "https://apiv2.nobitex.ir"
    
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
        # Test token-based auth
        if token:
            print("\n1. Testing Token-based authentication...")
            headers = {"Authorization": f"Token {token}", "User-Agent": "Mozilla/5.0"}
            try:
                response = await client.get("/v2/wallets", headers=headers)
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✓ Token authentication successful")
                    if data.get("status") == "ok":
                        print(f"   Wallets found: {len(data.get('wallets', []))}")
                else:
                    print(f"   Response: {response.text[:200]}")
            except Exception as e:
                print(f"   Error: {e}")
        
        # Test username/password login
        if username and password:
            print("\n2. Testing Username/Password login...")
            try:
                response = await client.post(
                    "/auth/login",
                    json={
                        "username": username,
                        "password": password,
                        "captcha": "api",
                    },
                )
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok" and "token" in data:
                        print(f"   ✓ Login successful, token obtained")
                        print(f"   Token length: {len(data['token'])}")
                    else:
                        print(f"   Login failed: {data}")
                else:
                    print(f"   Response: {response.text[:200]}")
            except Exception as e:
                print(f"   Error: {e}")


async def test_invex_public():
    """Test Invex public endpoints."""
    print("\n=== Testing Invex Public Endpoints ===")
    
    # Based on Postman documentation, actual API is at: https://api.invex.ir/trading/v1
    base_url = "https://api.invex.ir/trading/v1"
    
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # Test orderbook endpoint - based on Postman documentation
        # Endpoint: GET /market-depth with symbol and depth parameters
        # Note: Symbols use underscore format (e.g., BTC_IRR, BTC_USDT)
        print("\n1. Testing /market-depth endpoint...")
        try:
            # Try with depth=20 (common value) and correct symbol format
            response = await client.get(
                "/market-depth",
                params={"symbol": "BTC_USDT", "depth": 20}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✓ Orderbook endpoint works!")
                print(f"   Response structure: {list(data.keys()) if isinstance(data, dict) else 'List'}")
                if isinstance(data, dict):
                    # Based on TradingAPIGetMarketDepthOutputDTOV1:
                    # {"ask_orders": [...], "bid_orders": [...]}
                    if "bid_orders" in data and "ask_orders" in data:
                        print(f"   ✓ Found bid_orders/ask_orders structure")
                        print(f"   Bid orders count: {len(data.get('bid_orders', []))}")
                        print(f"   Ask orders count: {len(data.get('ask_orders', []))}")
                        if data.get('bid_orders') and data.get('ask_orders'):
                            bid_sample = data['bid_orders'][0] if data['bid_orders'] else None
                            ask_sample = data['ask_orders'][0] if data['ask_orders'] else None
                            if bid_sample:
                                print(f"   Bid sample: {bid_sample}")
                            if ask_sample:
                                print(f"   Ask sample: {ask_sample}")
                    # Try alternative field names for backward compatibility
                    elif "bids" in data and "asks" in data:
                        print(f"   ✓ Found bids/asks at root level (alternative format)")
                        print(f"   Bids count: {len(data.get('bids', []))}")
                        print(f"   Asks count: {len(data.get('asks', []))}")
            else:
                print(f"   Error: {response.text[:200]}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test other public endpoints
        print("\n2. Testing other Invex endpoints...")
        endpoints = [
            ("/markets", {}),
            ("/market-price", {"market_type": "BTCIRT"}),
        ]
        for endpoint, params in endpoints:
            try:
                response = await client.get(endpoint, params=params)
                if response.status_code == 200:
                    data = response.json()
                    print(f"   {endpoint}: ✓ Works - {list(data.keys()) if isinstance(data, dict) else 'Success'}")
            except Exception as e:
                pass


async def test_invex_auth():
    """Test Invex authentication (requires API key and secret)."""
    print("\n=== Testing Invex Authentication ===")
    
    api_key = os.getenv("INVEX_API_KEY", "")
    api_secret = os.getenv("INVEX_API_SECRET", "")
    
    if not api_key or not api_secret:
        print("   No Invex credentials found in .env file")
        print("   Please add:")
        print("   - INVEX_API_KEY=your_api_key")
        print("   - INVEX_API_SECRET=your_hex_encoded_private_key")
        print("   Note: Invex uses RSA-PSS signature authentication")
        return
    
    print("   ✓ Credentials found in .env")
    print("   Note: Full authentication test requires RSA signature generation")
    print("   This will be tested when placing orders or checking balance")


async def main():
    """Run all tests."""
    print("Exchange API Testing Script - Nobitex & Invex")
    print("=" * 60)
    print("\nThis script tests Nobitex and Invex exchange API endpoints.")
    print("Note: DNS errors may indicate network/firewall issues.\n")
    
    await test_nobitex_public()
    await test_nobitex_auth()
    await test_invex_public()
    await test_invex_auth()
    
    print("\n" + "=" * 60)
    print("\nSummary:")
    print("- Nobitex: Base URL is https://apiv2.nobitex.ir")
    print("- Invex: Base URL is https://api.invex.ir")
    print("- Public endpoints: Test orderbook fetching")
    print("- Authentication: Test with credentials in .env file")
    print("\nFor more information, see README.md and EXCHANGES.md")


if __name__ == "__main__":
    asyncio.run(main())
