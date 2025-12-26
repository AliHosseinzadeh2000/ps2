# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a cryptocurrency arbitrage trading bot that detects and executes price differences between Iranian and international crypto exchanges. The bot features optional AI-powered maker/taker order optimization using XGBoost, but works fully without AI by defaulting to taker orders.

## Development Commands

### Environment Setup
```bash
# Create virtual environment (handles missing ensurepip)
./setup.sh

# Manual setup if needed
python3.12 -m venv venv --without-pip
./venv/bin/python3.12 get-pip.py
./venv/bin/pip install -r requirements.txt
```

### Running the Application
```bash
# Quick start
./run.sh

# Manual start
source venv/bin/activate
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

# Or with venv Python directly
./venv/bin/python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_arbitrage.py -v
pytest tests/test_exchanges_integration.py -v
pytest tests/test_api_enum_validation.py -v

# Run with async support
pytest tests/ -v --asyncio-mode=auto
```

### API Documentation
- Interactive docs: http://localhost:8000/docs
- API info: http://localhost:8000/

## Architecture Overview

### Exchange System
All exchanges implement `ExchangeInterface` (app/exchanges/base.py) with core methods:
- `fetch_orderbook()` - Get current orderbook
- `place_order()` - Place buy/sell orders (supports maker/taker)
- `cancel_order()` - Cancel orders
- `get_balance()` - Get account balances
- `fetch_ohlc()` - Get OHLC candlestick data
- `get_order()` - Get order status
- `is_authenticated()` - Check credentials

**Exchange-specific implementations** (app/exchanges/):
- **Nobitex**: Token-based auth (username/password login OR direct token)
- **Wallex**: API key/secret
- **KuCoin**: API key/secret/passphrase
- **Invex**: RSA signature authentication (api_key + hex-encoded private key)
- **Tabdeal**: API key/secret

### Symbol Conversion System
**Critical**: Different exchanges use different symbol formats and quote currencies:
- **KuCoin**: Hyphen separator (e.g., "BTC-USDT")
- **Invex**: Underscore separator (e.g., "BTC_USDT", "BTC_IRR")
- **Nobitex/Wallex/Tabdeal**: No separator (e.g., "BTCUSDT", "BTCIRT")

**Quote currency compatibility** (app/utils/symbol_converter.py):
- IRT, IRR, and TMN are the SAME currency (Iranian Toman/Rial) - arbitrage is valid
- IRT and USDT are DIFFERENT markets - NO arbitrage between them
- `SymbolConverter.are_quote_currencies_compatible()` enforces this
- `ExchangeSymbolMapper.get_symbol_for_exchange()` converts between formats

The arbitrage engine uses this system to ensure opportunities are only detected between compatible markets.

### Arbitrage Flow
1. **Price Stream** (app/strategy/price_stream.py): Polls orderbooks from all exchanges at configured interval
2. **Arbitrage Engine** (app/strategy/arbitrage_engine.py):
   - Receives orderbook updates via `on_price_update()` callback
   - Validates symbol compatibility using `SymbolConverter`
   - Detects opportunities using `detect_opportunity()`
   - Filters by min spread/profit thresholds
   - Returns ranked opportunities
3. **Order Executor** (app/strategy/order_executor.py):
   - Executes buy/sell orders concurrently using `asyncio.gather()`
   - Optional AI prediction for maker/taker selection
   - Converts symbols to exchange-specific format before placing orders
   - Retries with exponential backoff (configurable max_retries)
   - Verifies order execution by polling status
   - Cancels orphaned orders if counterpart fails
   - Risk management checks (position limits, drawdown, slippage)
   - Circuit breakers for connectivity, error rate, and volatility

### Database Architecture
SQLite database (SQLAlchemy async) stores:
- **Orders**: All order state transitions (placed, filled, cancelled)
- **Trades**: Executed fills with P&L
- **Features**: Historical orderbook features for AI retraining

Database path: `data/bot_{mode}.db` (configurable via DB_MODE env var)

Session factory: `app.db.db.get_session_factory()` (async context manager)

### Risk Management System
**Circuit Breakers** (app/strategy/circuit_breakers.py):
- `MarketVolatilityCircuitBreaker`: Halts trading on excessive price swings
- `ExchangeConnectivityCircuitBreaker`: Halts exchange after connection failures
- `ErrorRateCircuitBreaker`: Halts exchange with high error rate

**Risk Limits** (checked before each trade in `_check_risk_limits()`):
- Daily loss limit
- Per-trade loss limit
- Max position per exchange
- Max total portfolio position
- Max drawdown percentage
- Slippage protection
- Pre-trade balance verification

### AI System (Optional)
**Components**:
- **Features** (app/ai/features.py): Extracts orderbook depth, spread, imbalance, volatility
- **Model** (app/ai/model.py): XGBoost binary classifier (maker vs taker)
- **Trainer** (app/ai/trainer.py): Trains from CSV historical data
- **Predictor** (app/ai/predictor.py): Real-time predictions from orderbooks

**Behavior**:
- If predictor available and ready: AI decides maker/taker per order
- If not available or fails: Defaults to taker orders (bot still works)
- Predictions include probability and optional price prediction

### Configuration System
Pydantic settings with .env file support (app/core/config.py):
- Nested config classes per exchange
- Trading parameters (min_spread, profit thresholds, timeouts)
- AI settings (model paths)
- Database settings
- API settings (host, port, CORS)

**Important**: `.env` file is loaded at module level, then manually passed to nested configs to avoid Pydantic BaseSettings issues.

## Key Implementation Details

### Async Architecture
- All I/O operations use `async/await`
- Exchange API calls are fully asynchronous
- Concurrent order placement with `asyncio.gather(return_exceptions=True)`
- Price stream runs in background with configurable polling interval

### Enum Handling
`ExchangeName` enum (app/core/exchange_types.py) is used throughout but code also supports plain strings for backward compatibility (tests use plain strings). Exchange lookups handle both:
```python
buy_exchange = self.exchanges.get(buy_exchange_name)  # Try direct lookup
if not buy_exchange:
    buy_exchange_enum = ExchangeName.from_string(str(buy_exchange_name))
    buy_exchange = self.exchanges.get(buy_exchange_enum)
```

### Data Collector Pattern
`DataCollector` (app/data/collector.py) logs all trades with features for continuous learning:
- Called after each trade execution
- Stores orderbook features, prices, quantities, fees
- Used for AI model retraining
- Best-effort (doesn't fail trade if logging fails)

### Exchange-Specific Notes

**Invex Authentication**:
- Uses RSA signatures (cryptography library)
- `INVEX_API_SECRET` must be hex-encoded private key
- See `app/exchanges/invex.py` for signature generation

**Nobitex Authentication**:
- Supports two methods: username/password (auto-login) OR direct token
- Token is obtained via login and cached
- See `app/exchanges/nobitex.py`

**Symbol Mapping**:
Always use `ExchangeSymbolMapper.get_symbol_for_exchange()` before API calls to convert standard symbols to exchange format.

## Common Patterns

### Adding a New Exchange
1. Create class in `app/exchanges/` inheriting from `ExchangeInterface`
2. Implement all abstract methods
3. Add config class in `app/core/config.py`
4. Add to `EXCHANGE_QUOTE_CURRENCIES` in `symbol_converter.py`
5. Register in exchange dictionary (app/api/services.py)
6. Add symbol format conversion if needed in `SymbolConverter.convert_to_exchange_format()`

### Testing Exchange Integrations
Integration tests check: orderbook fetching, order placement/cancellation, balance retrieval, OHLC data, symbol conversion, and error handling. See `tests/test_exchanges_integration.py` for patterns.

### Error Handling
- All exchange methods should handle network errors, API errors, rate limits
- Use retry logic with exponential backoff
- Log errors with context (exchange name, symbol, params)
- Circuit breakers automatically disable failing exchanges

## API Endpoints Structure

Routes are organized by domain:
- `/health/*` - Health checks (app/api/routes/health.py)
- `/metrics/*` - Trading metrics and opportunities (app/api/routes/metrics.py)
- `/orders/*` - Order preview/execution (app/api/routes/orders.py)
- `/ai/*` - AI predictions and training (app/api/routes/ai.py)
- `/risk/*` - Risk management status (app/api/routes/risk.py)
- `/history/*` - Trade history (app/api/routes/history.py)

Services singleton pattern (app/api/services.py) ensures shared instances of exchanges, arbitrage engine, and executor.

## Environment Variables

Key variables (see README for complete list):
- `NOBITEX_USERNAME`, `NOBITEX_PASSWORD` or `NOBITEX_TOKEN`
- `WALLEX_API_KEY`, `WALLEX_API_SECRET`
- `INVEX_API_KEY`, `INVEX_API_SECRET` (hex-encoded RSA private key)
- `KUCOIN_API_KEY`, `KUCOIN_API_SECRET`, `KUCOIN_API_PASSPHRASE`
- `TRADING_MIN_SPREAD_PERCENT`, `TRADING_MIN_PROFIT_USDT`
- `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR)
- `DB_MODE` (affects database filename)

## Logging

Structured logging setup in `app/core/logging.py`:
- Default level: DEBUG (development)
- Set `LOG_LEVEL` env var to change
- All modules use `get_logger(__name__)` for consistent naming
- Logs include exchange names, symbols, prices, and error details

## Important Constraints

1. **No IRT/USDT arbitrage**: These are different markets, not compatible for arbitrage
2. **Symbol conversion required**: Always convert symbols before exchange API calls
3. **Risk limits enforced**: Trading halts when limits exceeded
4. **Async everywhere**: Use async/await for all I/O operations
5. **Both order must fill**: If one order fills and other doesn't, cancel the filled one
6. **Database persistence**: All orders/trades persisted for audit trail
