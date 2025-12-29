# Project Context Summary

## Project Overview

This is a **Cryptocurrency Arbitrage Trading Bot** built for detecting and executing arbitrage opportunities between multiple Iranian and international cryptocurrency exchanges. The bot is designed for an important resaerch organization project presentation and operates in multiple modes: realistic trading, paper trading, and dry-run testing.

**Key Characteristics:**
- Fully asynchronous Python implementation using `asyncio` and `httpx`
- Modular architecture with clear separation of concerns
- Supports 5 exchanges: Nobitex, Wallex, KuCoin, Invex, Tabdeal
- Optional AI/ML component (XGBoost) for maker/taker optimization (infrastructure ready, model not trained)
- REST API using FastAPI for monitoring and control
- SQLite database for order and trade persistence
- Comprehensive risk management and circuit breakers

## Architecture

### Core Components

1. **Exchange Layer** (`app/exchanges/`)
   - `ExchangeInterface` abstract base class defining the contract
   - Individual exchange implementations: `NobitexExchange`, `WallexExchange`, `InvexExchange`, `KucoinExchange`, `TabdealExchange`
   - Each exchange handles authentication, API calls, and data transformation
   - Symbol conversion handled by `SymbolConverter` and `ExchangeSymbolMapper`

2. **Strategy Layer** (`app/strategy/`)
   - `ArbitrageEngine`: Detects arbitrage opportunities by comparing orderbooks
   - `OrderExecutor`: Executes trades with retry logic, risk checks, and AI integration
   - `PriceStream`: Continuously fetches and updates orderbooks from exchanges

3. **AI/ML Layer** (`app/ai/`) - **Infrastructure Ready, Model Not Trained**
   - `TradingModel`: XGBoost classifier/regressor wrapper
   - `TradingPredictor`: Makes maker/taker decisions and price predictions
   - `Feature Engineering`: Extracts orderbook and OHLC features
   - **Status**: Code is complete, but model training requires labeled historical data

4. **API Layer** (`app/api/`)
   - FastAPI application with multiple routers:
     - `/health` - Health checks
     - `/metrics` - Trading metrics and opportunities
     - `/orders` - Order preview and execution
     - `/ai` - AI model status and training
     - `/risk` - Risk management status
     - `/history` - Historical orders and trades

5. **Database Layer** (`app/db/`)
   - SQLite with async SQLAlchemy
   - `OrderRecord`: Stores all order attempts and statuses
   - `TradeRecord`: Stores completed trades with P&L
   - Database path supports `{mode}` templating for mode separation

6. **Risk Management** (`app/strategy/order_executor.py`, `app/monitoring/`)
   - Position limits (per-exchange and total)
   - Daily loss limits and drawdown protection
   - Slippage protection
   - Circuit breakers: MarketVolatilityCircuitBreaker, ExchangeConnectivityCircuitBreaker, ErrorRateCircuitBreaker

## Key Technical Details

### Symbol Conversion System

The bot handles multiple symbol formats across exchanges:
- **Formats**: `BTCUSDT`, `BTC-USDT`, `BTC_USDT`, `BTCIRT`, `BTCTMN`, `BTCIRR`
- **Compatibility**: IRT/IRR/TMN are interchangeable (Iranian Rial variants), but not with USDT
- **Implementation**: `SymbolConverter` and `ExchangeSymbolMapper` in `app/utils/symbol_converter.py`
- **Critical**: All order placement and opportunity detection must use exchange-specific symbols

### Exchange-Specific Implementation Details

**Nobitex:**
- Token-based authentication (username/password or direct token)
- Fees: maker=0.002, taker=0.0025
- Symbols: `BTCIRT`, `ETHIRT`, etc.

**Wallex:**
- API key/secret authentication
- Fees: maker=0.0025, taker=0.003
- Symbols: `BTCUSDT`, `ETHUSDT`, etc.
- **Critical**: Requires decimal strings (not scientific notation) for quantities

**Invex:**
- RSA signature authentication with hex-encoded private key
- Fees: maker=0.0025, taker=0.0025
- Symbols: `BTC_USDT`, `ETH_USDT`, etc.
- **Critical**: Requires signature in request body, not just headers
- **Critical**: `expire_at` must be timezone-naive ISO datetime string

**KuCoin & Tabdeal:**
- Standard API key/secret authentication
- Implemented but less tested

### Fee Configuration

Fees are configured in `app/core/config.py`:
- Nobitex: maker=0.002, taker=0.0025
- Wallex: maker=0.0025, taker=0.003
- Invex: maker=0.0025, taker=0.0025
- KuCoin/Tabdeal: Default values (check config)

**Important**: Arbitrage detection uses the **lower of maker/taker fees** to avoid over-filtering profitable opportunities. Actual fees applied during execution depend on order type.

## Major Fixes and Changes Made

### 1. Exchange API Compatibility Fixes

**Invex:**
- Tried to Fixed `expire_at` format: Changed from Unix timestamp to timezone-naive ISO datetime string.
- Fixed signature: Now includes signature in request body JSON payload (not just headers)
- Fixed timezone comparison errors
- But the problem still exists; Maybe my solutions did not fit or I have not understood the issue yet.

**Wallex:**
- Fixed quantity formatting: Implemented `format_decimal()` to avoid scientific notation
- Enhanced error logging for better debugging

### 2. Database Integration

- Added SQLite database with async SQLAlchemy
- `OrderRecord` model for order persistence
- `TradeRecord` model for trade history
- Database path supports `{mode}` templating: `data/bot_{mode}.db`
- Separate databases for realistic/paper/dry-run modes
- Read-only API endpoints (`/history`) for querying historical data

### 3. API Robustness

- Fixed `NameError: name 'SymbolConverter' is not defined` in `/metrics/opportunities`
- Replaced deprecated `@root_validator` with `@model_validator(mode="after")` in Pydantic models
- Added input validation: `quantity > 0`, `buy_exchange != sell_exchange`
- Proper error handling and validation throughout

### 4. Test Suite Fixes

- Fixed mock exchange initialization to use `ExchangeName` enums
- Fixed `ArbitrageEngine` to handle both enum and string exchange keys
- Fixed `OrderExecutor` to handle arbitrary string exchanges in tests
- Real API tests skip by default (`SKIP_REAL_API_TESTS=1`)
- All unit tests now pass (12/12)

### 5. Balance Check Fixes

- Fixed `'str' object has no attribute 'get'` error
- Improved quote currency extraction using `SymbolConverter.get_quote_currency()`
- Proper type checking for balance objects

## Current State

### Working Features

✅ **Arbitrage Detection**: Fully functional, detects opportunities across exchanges
✅ **Order Execution**: Concurrent order placement with retry logic
✅ **Risk Management**: Position limits, loss limits, slippage protection, circuit breakers
✅ **Database Persistence**: Orders and trades are saved to SQLite
✅ **REST API**: All endpoints functional
✅ **Symbol Conversion**: Handles all exchange-specific formats
✅ **Exchange Integration**: Nobitex, Wallex, Invex fully integrated
✅ **Testing**: Unit tests passing, integration tests available

But overally, they need to be tested to make sure if they properly work together.

### Partially Working / Infrastructure Ready

⚠️ **AI/ML Component**: 
- Code seems to be complete but not tested
- Model training infrastructure ready
- **Model not trained** - requires labeled historical data
- Bot works without AI (defaults to taker orders)

### Testing Modes

The bot supports multiple testing modes via `test_bot.py`:

1. **Realistic Mode** (`--mode realistic`): Uses real exchanges, requires `--execute` flag to actually place orders
2. **Paper Mode** (`--mode paper`): Simulated trading with real market data
3. **Dry-Run Mode** (`--mode dry-run`): Preview only, no orders placed
4. **Integration Mode** (`--mode integration`): Full integration tests

### Main Bot Execution

The main bot runs via `./run.sh` which:
1. Starts FastAPI server on port 8000
2. Initializes exchanges, arbitrage engine, order executor
3. Starts price stream for continuous orderbook updates
4. Subscribes arbitrage engine to price updates
5. Automatically detects and can execute opportunities

**Note**: The main bot (`./run.sh`) continuously monitors markets and can execute trades automatically. The `test_bot.py` script is for manual testing and presentation purposes.

## Important Files

### Configuration
- `app/core/config.py`: Centralized configuration using Pydantic `BaseSettings`
- `.env`: Environment variables for API keys and settings (not in git)

### Core Logic
- `app/strategy/arbitrage_engine.py`: Opportunity detection logic
- `app/strategy/order_executor.py`: Order execution with risk management
- `app/strategy/price_stream.py`: Continuous orderbook updates
- `app/utils/symbol_converter.py`: Symbol format conversion

### Exchange Implementations
- `app/exchanges/base.py`: Abstract `ExchangeInterface`
- `app/exchanges/nobitex.py`: Nobitex implementation
- `app/exchanges/wallex.py`: Wallex implementation
- `app/exchanges/invex.py`: Invex implementation

### API
- `app/api/main.py`: FastAPI application entry point
- `app/api/routes/`: Individual route modules
- `app/api/services.py`: Singleton services (exchanges, engine, executor)

### Database
- `app/db/db.py`: Database connection and session factory
- `app/db/models.py`: SQLAlchemy ORM models
- `app/db/repository.py`: CRUD operations

### Testing
- `test_bot.py`: Unified test script for all modes
- `tests/`: Pytest test suite
  - `test_arbitrage.py`: Arbitrage detection tests
  - `test_arbitrage_integration.py`: Full flow integration tests
  - `test_executor.py`: Order executor tests
  - `test_real_api_integration.py`: Real API tests (skip by default)
  - `test_db.py`: Database persistence tests

### Documentation
- `README.md`: Main project documentation
- `USAGE_GUIDE.md`: How to use the API
- `EXCHANGES.md`: Exchange-specific documentation
- `ROADMAP.md`: Project roadmap and phases
- `DOCUMENTATION_INDEX.md`: Index of all documentation files
- `CURL_EXAMPLES.md`: curl examples for API requests

## Testing Approach

### Running Tests

```bash
# Unit tests (skip real API calls)
SKIP_REAL_API_TESTS=1 ./venv/bin/pytest tests/test_arbitrage.py tests/test_arbitrage_integration.py tests/test_executor.py -q

# All tests
./venv/bin/pytest tests/ -v

# Specific test file
./venv/bin/pytest tests/test_db.py -q
```

### Test Results

**Current Status**: 12/12 unit tests passing
- `test_arbitrage.py`: 3/3 passing
- `test_arbitrage_integration.py`: 6/6 passing  
- `test_executor.py`: 3/3 passing

**Warnings**: Pydantic v2 deprecation warnings (non-functional, can be ignored)

### Real API Tests

Real API tests are skipped by default to avoid:
- External API failures (404s, rate limits)
- Network dependencies
- Credential requirements

To enable: `SKIP_REAL_API_TESTS=0 ./venv/bin/pytest tests/test_real_api_integration.py`

## Known Issues and Limitations

### Current Limitations

1. **AI Model Not Trained**: Infrastructure is ready, but model requires labeled historical data
2. **Pydantic Deprecation Warnings**: Using deprecated `Field(env=...)` syntax (non-functional)
3. **Real API Tests**: Skip by default due to external dependencies
4. **OHLC Data**: Some exchanges may return 404 for OHLC endpoints (external API issue)

### Exchange-Specific Notes

- **Nobitex**: OHLC endpoint may return 404 (external API issue, not bot bug)
- **Invex**: Requires careful signature generation and timezone handling
- **Wallex**: Requires decimal string formatting (no scientific notation)

## Environment Variables

Key environment variables (set in `.env` file):

```bash
# Exchange Credentials
NOBITEX_TOKEN=...
NOBITEX_USERNAME=...
NOBITEX_PASSWORD=...
WALLEX_API_KEY=...
WALLEX_API_SECRET=...
INVEX_API_KEY=...
INVEX_API_SECRET=...  # Hex-encoded private key
KUCOIN_API_KEY=...
KUCOIN_API_SECRET=...
KUCOIN_API_PASSPHRASE=...
TABDEAL_API_KEY=...
TABDEAL_API_SECRET=...

# Trading Configuration
TRADING_MIN_SPREAD_PERCENT=0.5
TRADING_MIN_PROFIT_USDT=1.0
TRADING_MAX_POSITION_SIZE_USDT=1000.0
TRADING_DAILY_LOSS_LIMIT=100.0

# Database
DB_MODE=realistic  # or "paper", "dry-run"
DB_PATH=data/bot_{mode}.db

# API
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=DEBUG  # or INFO, WARNING, ERROR
```

## Quick Start Commands

```bash
# Setup (first time)
./setup.sh

# Run main bot
./run.sh

# Test bot (realistic mode with execution)
python3 test_bot.py --mode realistic --symbol BTCUSDT --execute

# Run tests
SKIP_REAL_API_TESTS=1 ./venv/bin/pytest tests/ -q

# API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/metrics/opportunities?symbol=BTCUSDT
```

## Project Status for Presentation

### Completed ✅
- Multi-exchange arbitrage detection
- Order execution with risk management
- Database persistence
- REST API with comprehensive endpoints
- Symbol conversion system
- Exchange integrations (Nobitex, Wallex, Invex)
- Testing infrastructure
- Documentation

### Infrastructure Ready ⚠️
- AI/ML component (code complete, model not trained)
- Model training pipeline
- Feature engineering

### Future Enhancements 🔮
- WebSocket support for real-time updates
- Advanced risk management features
- Multi-asset arbitrage
- Portfolio optimization
- Real-time monitoring dashboard

## Important Notes for New Conversations

1. **AI Status**: The AI component is almost infrastructure-ready but not trained. The bot works fully without AI.

2. **Database Separation**: Each mode (realistic/paper/dry-run) uses a separate database file via `DB_MODE` environment variable.

3. **Exchange Switching**: The main bot (`./run.sh`) automatically handles exchange switching and order tracking. All orders are persisted to the database.

4. **Test Bot vs Main Bot**: 
   - `test_bot.py`: For manual testing and presentation
   - `./run.sh`: Main production bot that runs continuously

5. **Symbol Formats**: Always use `ExchangeSymbolMapper` to convert symbols for exchange-specific APIs.

6. **Fee Calculation**: Detection uses lower fees, execution uses actual fees based on order type.

7. **Error Handling**: Most exchange-specific errors have been fixed. If new errors appear, check:
   - Symbol format conversion
   - Authentication/signature generation
   - Data type formatting (decimals, dates, timezones)

## Code Quality

- Type hints throughout
- Google-style docstrings
- Async/await for I/O operations
- Pydantic models for validation
- Comprehensive error handling
- Structured logging
- Modular, extensible architecture

---

**Last Updated**: Based on conversation history up to pytest fixes and appendix preparation
**Project Path**: `/home/ali/Desktop/sarbazi/code/ps2`
**Python Version**: 3.12 (recommended) or 3.11+







