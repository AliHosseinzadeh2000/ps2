# Supported Exchanges

This project now supports **5 cryptocurrency exchanges** for arbitrage trading:

## Available Exchanges

### 1. Nobitex (`nobitex`)
- **Type:** Iranian Exchange
- **Base URL:** `https://apiv2.nobitex.ir`
- **Symbol Format:** `BTCIRT`, `ETHIRT` (Iranian Toman pairs)
- **Fees:** Maker 0.2% (0.002), Taker 0.25% (0.0025)
- **Authentication:** Token-based (obtained via login or provided directly)
- **API Documentation:** https://apidocs.nobitex.ir/
- **Configuration:**
  ```bash
  # Option 1: Direct token (if you have it from dashboard)
  NOBITEX_TOKEN=your_token
  
  # Option 2: Username/password (will auto-login and cache token)
  NOBITEX_USERNAME=your_username
  NOBITEX_PASSWORD=your_password
  ```
  **Note:** Nobitex uses token-based authentication, not API key/secret. The token is obtained via the `/auth/login` endpoint or can be provided directly if you have it from the dashboard.

### 2. Wallex (`wallex`)
- **Type:** Iranian Exchange
- **Base URL:** `https://api.wallex.ir`
- **Symbol Format:** `BTCUSDT`, `ETHUSDT`, `USDTTMN` (USDT pairs, TMN for Toman market)
- **Fees:** Maker 0.25% (0.0025), Taker 0.3% (0.003)
- **Authentication:** HMAC-SHA256 signature with API key
- **API Documentation:** https://developers.wallex.ir/intro
- **Configuration:**
  ```bash
  WALLEX_API_KEY=your_key
  WALLEX_API_SECRET=your_secret
  ```
  **Note:** Wallex uses HMAC-SHA256 signature authentication. The API key is sent in the `x-api-key` header (lowercase). Order placement endpoint is `/v1/account/orders` (POST).

### 3. KuCoin (`kucoin`)
- **Type:** International Exchange
- **Base URL:** `https://api.kucoin.com`
- **Symbol Format:** `BTC-USDT`, `ETH-USDT` (hyphenated format)
- **Fees:** Maker 0.1%, Taker 0.1%
- **Special:** Requires API passphrase
- **Configuration:**
  ```bash
  KUCOIN_API_KEY=your_key
  KUCOIN_API_SECRET=your_secret
  KUCOIN_API_PASSPHRASE=your_passphrase
  ```

### 4. Invex (`invex`)
- **Type:** Iranian Exchange
- **Base URL:** `https://api.invex.ir/trading/v1`
- **Symbol Format:** `BTC_USDT`, `BTC_IRR`, `ETH_USDT`, `ETH_IRR` (uses underscore separator)
  - **Note:** The system automatically converts formats like `BTCUSDT` → `BTC_USDT` and `BTCIRT` → `BTC_IRR`
- **Fees:** Maker 0.25% (0.0025), Taker 0.25% (0.0025)
- **Authentication:** RSA-PSS signature with SHA256
- **API Documentation:** https://documenter.getpostman.com/view/29635700/2sA2r813me
- **Configuration:**
  ```bash
  INVEX_API_KEY=your_api_key
  INVEX_API_SECRET=your_hex_encoded_private_key
  ```
  **Note:** Invex uses RSA-PSS signature authentication. The `INVEX_API_SECRET` should be your DER-encoded private key in hex format. Each signed request includes an `expire_at` timestamp to prevent replay attacks. Order sides use `BUYER`/`SELLER` format (automatically converted from `buy`/`sell`).

### 5. Tabdeal (`tabdeal`)
- **Type:** Iranian Exchange
- **Base URL:** `https://api.tabdeal.org`
- **Symbol Format:** `BTCIRT`, `ETHIRT` (Iranian Toman pairs, no separator)
- **Fees:** Maker 0.05%, Taker 0.1% (default, may vary by tier)
- **Authentication:** HMAC-SHA256 signature
- **API Documentation:** https://docs.tabdeal.org/
- **Configuration:**
  ```bash
  TABDEAL_API_KEY=your_key
  TABDEAL_API_SECRET=your_secret
  ```
  **Note:** Tabdeal uses HMAC-SHA256 signature authentication. The `X-MBX-APIKEY` header is required for authenticated requests. Order sides use `BUY`/`SELL` format.

## Usage Examples

### Finding Opportunities Across All Exchanges

```bash
# Get opportunities for BTCUSDT across all configured exchanges
curl "http://localhost:8000/metrics/opportunities?symbol=BTCUSDT"
```

### Preview Order Between Any Two Exchanges

```json
{
  "symbol": "BTCUSDT",
  "buy_exchange": "nobitex",
  "sell_exchange": "kucoin",
  "quantity": 0.01
}
```

### Execute Arbitrage Between Exchanges

```json
{
  "symbol": "BTCUSDT",
  "buy_exchange": "invex",
  "sell_exchange": "tabdeal",
  "quantity": 0.01,
  "use_maker": false
}
```

## Symbol Format Notes

⚠️ **Important:** Each exchange uses different symbol formats:

- **Nobitex, Tabdeal:** `BTCIRT`, `ETHIRT` (no separator, Iranian Toman pairs)
- **Wallex:** `BTCUSDT`, `ETHUSDT`, `USDTTMN` (no separator, USDT pairs or TMN for Toman market)
- **KuCoin:** `BTC-USDT`, `ETH-USDT` (hyphenated format)
- **Invex:** `BTC_USDT`, `BTC_IRR`, `ETH_USDT`, `ETH_IRR` (underscore separator)

**Symbol Conversion:** The system automatically handles symbol conversion:
- **KuCoin:** Converts `BTCUSDT` → `BTC-USDT`
- **Invex:** Converts `BTCUSDT` → `BTC_USDT` and `BTCIRT` → `BTC_IRR`
- **Wallex:** Converts `BTCIRT` → `BTCTMN` (IRT/IRR/TMN are interchangeable)
- **Nobitex:** Converts `BTCIRR` → `BTCIRT` (IRT/IRR/TMN are interchangeable)

**Currency Compatibility:** IRT, IRR, and TMN represent the same Iranian currency and are automatically converted between exchanges. USDT is a different market and cannot be arbitraged with Iranian currencies.

When making API calls, you can use any format - the system will convert automatically.

## Configuration

You don't need to configure all exchanges. Only configure the ones you want to use:

1. Add API keys to `.env` file
2. Restart the server
3. The system will automatically initialize configured exchanges
4. You can use any combination of configured exchanges for arbitrage

## Exchange Features

All exchanges support:
- ✅ Orderbook fetching (public endpoint, may work without API keys)
- ✅ Order placement (requires API keys)
- ✅ Order cancellation (requires API keys)
- ✅ Balance checking (requires API keys)
- ✅ OHLC data fetching (candlestick data)
- ✅ Open orders retrieval
- ✅ Order status checking
- ✅ Maker/Taker order types
- ✅ Post-only (maker) orders
- ✅ Retry logic with exponential backoff
- ✅ Circuit breaker protection
- ✅ Standardized error handling

## Error Handling

All exchanges use standardized error classes:
- `ExchangeError`: Base exception for all exchange errors
- `ExchangeAuthenticationError`: Authentication failures
- `ExchangeAPIError`: API response errors (with status codes)
- `ExchangeNetworkError`: Network/connection errors
- `ExchangeOrderError`: Order-related errors
- `ExchangeOrderNotFoundError`: Order not found
- `ExchangeInsufficientBalanceError`: Insufficient balance
- `ExchangeRateLimitError`: Rate limit exceeded
- `ExchangeInvalidSymbolError`: Invalid trading symbol

All exchanges implement:
- **Retry Logic**: Automatic retry with exponential backoff (3 attempts by default)
- **Circuit Breakers**: Protection against cascading failures
- **Structured Logging**: Detailed logging with exchange context

## API Endpoint Compatibility

The arbitrage engine will automatically:
- Find opportunities between any configured exchanges
- Handle different symbol formats
- Calculate fees correctly for each exchange
- Execute orders concurrently when possible

## Testing

To test with a specific exchange:

1. Configure only that exchange's API keys in `.env`
2. Use the exchange name in API requests
3. Check `/metrics/opportunities` to see if it can fetch orderbooks
4. Use `/orders/preview` to test without executing

## Notes

- **KuCoin** requires a passphrase in addition to API key/secret
- All exchanges use HMAC-SHA256 for authentication
- Public orderbook endpoints may work without API keys (depends on exchange)
- Trading endpoints always require valid API keys with trading permissions




