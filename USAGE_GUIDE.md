# How to Use This Project

## Quick Start

1. **Start the API server:**
   ```bash
   ./run.sh
   # Or manually:
   ./venv/bin/python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Open Swagger UI:**
   - Navigate to: http://localhost:8000/docs
   - This provides an interactive interface to test all API endpoints

## API Endpoints Guide

### 1. Health Check (Works Immediately)
- **GET** `/health` - Check if API is running
- **GET** `/health/ready` - Readiness check
- **GET** `/health/live` - Liveness check

These work without any configuration.

### 2. Metrics Endpoints

#### Get Trading Metrics
- **GET** `/metrics` - Returns current trading statistics
  - Works immediately, returns default values (0 trades, etc.)

#### Get Arbitrage Opportunities
- **GET** `/metrics/opportunities?symbol=BTCUSDT` - Find arbitrage opportunities
  - **Without API keys:** Returns empty list (can't fetch real orderbooks)
  - **With API keys:** Fetches real orderbooks and finds actual opportunities
  - **Query parameter:** `symbol` (default: BTCUSDT)

**Example:**
```bash
curl http://localhost:8000/metrics/opportunities?symbol=BTCUSDT
```

### 3. Order Endpoints

#### Preview Order (Works in Demo Mode)
- **POST** `/orders/preview` - Preview an arbitrage order without executing
  - **Works without API keys:** Uses mock data for preview
  - **Works with API keys:** Uses real orderbook data

**Request Body:**
```json
{
  "symbol": "BTCUSDT",
  "buy_exchange": "nobitex",
  "sell_exchange": "wallex",
  "quantity": 0.01
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/orders/preview" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "buy_exchange": "nobitex",
    "sell_exchange": "wallex",
    "quantity": 0.01
  }'
```

#### Execute Order (Requires API Keys)
- **POST** `/orders/execute` - Execute an actual arbitrage order
  - **Without API keys:** Returns error message
  - **With API keys:** Executes real orders on exchanges

**Request Body:**
```json
{
  "symbol": "BTCUSDT",
  "buy_exchange": "nobitex",
  "sell_exchange": "wallex",
  "quantity": 0.01,
  "use_maker": false
}
```

### 4. AI/ML Endpoints

#### Get Model Status
- **GET** `/ai/status` - Check if AI model is loaded
  - Works immediately, shows model status

#### Predict (Requires Trained Model)
- **POST** `/ai/predict` - Predict maker/taker decision
  - **Without trained model:** Returns error (model not loaded)
  - **With trained model:** Returns prediction

**Request Body:**
```json
{
  "features": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0],
  "threshold": 0.5
}
```

#### Train Model (Requires Training Data)
- **POST** `/ai/train` - Train the XGBoost model
  - Requires CSV file with training data
  - See README for training data format

## Configuration Levels

### Level 1: No Configuration (Demo Mode)
- ✅ Health checks work
- ✅ Metrics endpoints work (with default/empty data)
- ✅ Order preview works (with mock data)
- ❌ Order execution doesn't work
- ❌ Real opportunities detection doesn't work

### Level 2: With API Keys (Real Data)
Create a `.env` file:
```bash
# Nobitex (choose one method)
# Option 1: Direct token
NOBITEX_TOKEN=your_token_here
# Option 2: Username/password
NOBITEX_USERNAME=your_username
NOBITEX_PASSWORD=your_password

# Wallex
WALLEX_API_KEY=your_key_here
WALLEX_API_SECRET=your_secret_here

# KuCoin (requires passphrase)
KUCOIN_API_KEY=your_key_here
KUCOIN_API_SECRET=your_secret_here
KUCOIN_API_PASSPHRASE=your_passphrase_here

# Invex (RSA signature authentication)
INVEX_API_KEY=your_api_key_here
INVEX_API_SECRET=your_hex_encoded_private_key_here

# Tabdeal
TABDEAL_API_KEY=your_key_here
TABDEAL_API_SECRET=your_secret_here
```

**Note:** You don't need to configure all exchanges. Only configure the ones you want to use. The system will work with any combination of configured exchanges.

Now:
- ✅ Real orderbook fetching works
- ✅ Real arbitrage opportunities detection works
- ✅ Order preview uses real data
- ⚠️ Order execution still requires valid API keys with trading permissions

### Level 3: Full Setup (With Trained Model)
- All of Level 2, plus:
- ✅ AI predictions work
- ✅ Maker/taker optimization works

## Testing in Swagger UI

1. **Start the server:** `./run.sh`
2. **Open:** http://localhost:8000/docs
3. **Try these endpoints in order:**

   a. **Health Check:**
      - Click on `GET /health`
      - Click "Try it out"
      - Click "Execute"
      - Should return: `{"status": "healthy", "timestamp": ...}`

   b. **Get Metrics:**
      - Click on `GET /metrics`
      - Click "Try it out" → "Execute"
      - Should return metrics with default values

   c. **Get Opportunities (Demo):**
      - Click on `GET /metrics/opportunities`
      - Click "Try it out"
      - Set `symbol` to `BTCUSDT` (or leave default)
      - Click "Execute"
      - Without API keys: Returns empty array `[]`
      - With API keys: Returns actual opportunities if found

   d. **Preview Order:**
      - Click on `POST /orders/preview`
      - Click "Try it out"
      - Use this request body:
        ```json
        {
          "symbol": "BTCUSDT",
          "buy_exchange": "nobitex",
          "sell_exchange": "wallex",
          "quantity": 0.01
        }
        ```
      - Click "Execute"
      - Should return preview with estimated profit (uses mock data if no API keys)

   e. **AI Status:**
      - Click on `GET /ai/status`
      - Click "Try it out" → "Execute"
      - Should return: `{"loaded": false, "model_path": "...", "feature_count": 0}`

## Common Issues

### "No arbitrage opportunity found"
- This is normal if:
  - No API keys configured (can't fetch real prices)
  - Current market prices don't have profitable spread
  - Spread is below minimum threshold (default: 0.5%)

### "API keys not configured"
- Create a `.env` file in the project root
- Add your exchange API keys
- Restart the server

### "Model not loaded"
- This is normal - the AI model needs to be trained first
- Use `/ai/train` endpoint with training data
- Or use the project without AI features

### "Failed to fetch orderbooks"
- Check your API keys are correct
- Check your internet connection
- Check if exchange APIs are accessible
- Some endpoints may require authentication even for public data

## Next Steps

1. **For Testing/Demo:**
   - Use the endpoints that work without API keys
   - Test `/orders/preview` with mock data
   - Check `/health` and `/metrics`

2. **For Real Trading:**
   - Get API keys from Nobitex and Wallex
   - Add them to `.env` file
   - Test with small amounts first
   - Monitor `/metrics/opportunities` for real opportunities

3. **For AI Features:**
   - Prepare training data (CSV format)
   - Train model using `/ai/train`
   - Use `/ai/predict` for maker/taker decisions

## Exchange Symbols

- **Nobitex:** Uses symbols like `BTCIRT`, `ETHIRT` (Iranian Toman)
- **Wallex:** Uses symbols like `BTCUSDT`, `ETHUSDT` (USDT pairs)
- **KuCoin:** Uses symbols like `BTC-USDT`, `ETH-USDT` (hyphenated format)
- **Invex:** Uses symbols like `BTCIRT`, `ETHIRT` (Iranian Toman)
- **Tabdeal:** Uses symbols like `BTCIRT`, `ETHIRT` (Iranian Toman)

Make sure to use the correct symbol format for each exchange!

## Available Exchanges

The following exchanges are supported:

1. **Nobitex** (`nobitex`) - Iranian exchange
2. **Wallex** (`wallex`) - Iranian exchange
3. **KuCoin** (`kucoin`) - International exchange
4. **Invex** (`invex`) - Iranian exchange
5. **Tabdeal** (`tabdeal`) - Iranian exchange

You can use any combination of these exchanges in your arbitrage requests. For example:
- `buy_exchange: "nobitex"` and `sell_exchange: "kucoin"`
- `buy_exchange: "invex"` and `sell_exchange: "tabdeal"`

