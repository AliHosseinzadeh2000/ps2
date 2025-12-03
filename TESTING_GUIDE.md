# Testing Guide

This guide explains how to test the trading bot with both mock and real API data.

## Quick Start

### 1. Test with Mock Data (No API credentials needed)

```bash
# Run integration tests with mocks
pytest tests/test_arbitrage_integration.py -v

# Run performance benchmarks
pytest tests/test_performance.py -v -s
```

### 2. Test with Real API Data (Public endpoints only)

```bash
# Run the demonstration script (no authentication needed)
python test_bot_demo.py --skip-auth

# Or test specific functionality
python test_bot_demo.py --skip-auth --symbol BTCUSDT --stream-duration 10
```

### 3. Test with Real API Data (Full functionality - requires credentials)

First, set up your `.env` file with exchange credentials:

```bash
# Nobitex (choose one method)
NOBITEX_TOKEN=your_token_here
# OR
NOBITEX_USERNAME=your_username
NOBITEX_PASSWORD=your_password

# Invex
INVEX_API_KEY=your_api_key
INVEX_API_SECRET=your_api_secret

# Wallex
WALLEX_API_KEY=your_api_key
WALLEX_API_SECRET=your_api_secret
```

Then run:

```bash
# Full demonstration (includes order placement, cancellation, etc.)
python test_bot_demo.py

# Run real API integration tests
pytest tests/test_real_api_integration.py -v -s

# Skip real API tests if needed
SKIP_REAL_API_TESTS=1 pytest tests/test_real_api_integration.py
```

## Test Categories

### 1. Unit Tests
- **Location**: `tests/test_exchanges_integration.py`
- **Purpose**: Test exchange interfaces, authentication, error handling
- **Requirements**: No API credentials needed (uses mocks)

### 2. Integration Tests
- **Location**: `tests/test_arbitrage_integration.py`
- **Purpose**: Test full arbitrage flow with mocks
- **Requirements**: No API credentials needed

### 3. Performance Tests
- **Location**: `tests/test_performance.py`
- **Purpose**: Benchmark performance of key operations
- **Requirements**: No API credentials needed

### 4. Real API Tests
- **Location**: `tests/test_real_api_integration.py`
- **Purpose**: Test with real exchange APIs
- **Requirements**: 
  - Public endpoints: No credentials needed
  - Authenticated endpoints: Valid credentials in `.env`

### 5. Demonstration Script
- **Location**: `test_bot_demo.py`
- **Purpose**: Comprehensive demonstration of bot functionality
- **Requirements**: 
  - Public endpoints: No credentials needed
  - Full functionality: Valid credentials in `.env`

## What Gets Tested

### Without Authentication (Public APIs)

1. **Orderbook Fetching**
   - ✅ Fetch orderbooks from Nobitex, Invex, Wallex
   - ✅ Verify bid/ask data structure
   - ✅ Calculate spreads

2. **Opportunity Detection**
   - ✅ Scan multiple exchanges for arbitrage opportunities
   - ✅ Calculate profit potential
   - ✅ Filter by minimum spread/profit thresholds

3. **Price Stream**
   - ✅ Real-time orderbook updates
   - ✅ Multi-exchange monitoring
   - ✅ Event-driven opportunity detection

### With Authentication (Full Functionality)

4. **Order Lifecycle**
   - ✅ Place limit orders
   - ✅ Check order status
   - ✅ Cancel orders
   - ✅ Verify order state changes

5. **Order Management**
   - ✅ Fetch open orders
   - ✅ Monitor order status
   - ✅ Handle partial fills

6. **Account Management**
   - ✅ Fetch account balance
   - ✅ Check available funds
   - ✅ Monitor locked funds

## Running Tests for Presentation

For your jury presentation, we recommend:

### Step 1: Verify Core Functionality (No credentials needed)

```bash
# This demonstrates the bot works with real market data
python test_bot_demo.py --skip-auth --symbol BTCUSDT
```

This will show:
- ✅ Real-time orderbook data from exchanges
- ✅ Opportunity detection working
- ✅ Price stream integration
- ✅ All core functionality without needing to place real orders

### Step 2: Full Demonstration (With credentials)

```bash
# This shows complete functionality including order management
python test_bot_demo.py --symbol BTCUSDT
```

This will additionally show:
- ✅ Order placement (with test orders)
- ✅ Order status monitoring
- ✅ Order cancellation
- ✅ Balance checking

### Step 3: Run Test Suite

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_real_api_integration.py -v -s
pytest tests/test_arbitrage_integration.py -v
pytest tests/test_performance.py -v -s
```

## Expected Results

### Orderbook Fetching
- Should successfully fetch from at least 2 exchanges
- Should show valid bid/ask prices
- Should calculate spreads correctly

### Opportunity Detection
- May or may not find opportunities (depends on market conditions)
- If opportunities exist, should show:
  - Buy/sell exchanges
  - Prices and spreads
  - Profit calculations
- If no opportunities, this is **normal** - the bot only trades when profitable!

### Price Stream
- Should receive updates every 2-5 seconds
- Should show price changes in real-time
- Should work across multiple exchanges simultaneously

### Order Lifecycle (if authenticated)
- Should place test order successfully
- Should retrieve order status
- Should cancel order successfully
- Should verify cancellation

## Troubleshooting

### "No orderbooks fetched"
- Check internet connection
- Verify exchange APIs are accessible
- Some exchanges may have rate limits

### "No opportunities found"
- This is **normal** - arbitrage opportunities are rare
- The bot is working correctly if it doesn't find unprofitable trades
- Try different symbols or wait for market conditions to change

### "Authentication failed"
- Check `.env` file has correct credentials
- Verify credentials are valid on exchange
- Some exchanges require IP whitelisting

### "Rate limit exceeded"
- Wait a few minutes and try again
- Reduce test frequency
- Some exchanges have strict rate limits

## Safety Features Demonstrated

The bot includes multiple safety features:

1. **Risk Management**
   - Position limits
   - Loss limits
   - Drawdown protection
   - Slippage protection

2. **Circuit Breakers**
   - Market volatility protection
   - Exchange connectivity monitoring
   - Error rate limiting

3. **Error Recovery**
   - Automatic retry with exponential backoff
   - Partial fill recovery
   - Timeout handling

4. **Order Verification**
   - Pre-trade balance checks
   - Order status polling
   - Automatic cleanup on failures

## Presentation Tips

1. **Start with public API tests** - Shows the bot works without needing credentials
2. **Explain that "no opportunities" is good** - Shows the bot won't take unprofitable trades
3. **Demonstrate price stream** - Shows real-time monitoring capability
4. **Show order lifecycle** - Demonstrates complete order management
5. **Highlight safety features** - Risk management, circuit breakers, error recovery

## Next Steps

After testing:
1. Review test results
2. Check logs for any warnings
3. Verify all features work as expected
4. Prepare demonstration for jury

Good luck with your presentation! 🚀


