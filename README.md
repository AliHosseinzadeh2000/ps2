# Cryptocurrency Arbitrage Trading Bot

A lightweight, production-oriented arbitrage trading bot that detects and executes arbitrage opportunities between cryptocurrency exchanges. **AI-powered maker/taker optimization is an optional enhancement** - the bot works fully without AI, using taker orders by default.

## Features

- **Arbitrage Detection**: Real-time detection of price differences between exchanges
- **AI-Enhanced Decisions** (Optional): XGBoost model for optimizing maker vs taker order selection when enabled
- **Works Without AI**: Fully functional arbitrage bot that operates without AI (uses taker orders by default)
- **Async Architecture**: Fully asynchronous Python implementation for high performance
- **Multiple Exchanges**: Support for Nobitex, Wallex, KuCoin, Invex, and Tabdeal exchanges (extensible)
- **Backtesting**: Historical data replay for strategy validation
- **REST API**: FastAPI-based monitoring and control interface
- **Fee Optimization**: AI can minimize trading fees through intelligent order type selection (optional)
- **Risk Management**: Built-in risk controls to prevent capital loss

## Project Structure

```
project/
├── app/
│   ├── core/              # Configuration and logging
│   │   ├── config.py
│   │   └── logging.py
│   ├── exchanges/        # Exchange interfaces
│   │   ├── base.py
│   │   ├── nobitex.py
│   │   ├── wallex.py
│   │   ├── kucoin.py
│   │   ├── invex.py
│   │   └── tabdeal.py
│   ├── strategy/         # Trading strategies
│   │   ├── arbitrage_engine.py
│   │   ├── order_executor.py
│   │   └── price_stream.py
│   ├── ai/               # AI/ML modules
│   │   ├── features.py
│   │   ├── model.py
│   │   └── trainer.py
│   ├── api/              # FastAPI application
│   │   ├── main.py
│   │   └── routes/
│   │       ├── health.py
│   │       ├── metrics.py
│   │       ├── orders.py
│   │       └── ai.py
│   ├── backtesting/      # Backtesting modules
│   │   ├── simulator.py
│   │   └── loader.py
│   └── utils/            # Utility modules
│       ├── time.py
│       └── math.py
├── tests/                # Test suite
│   ├── test_arbitrage.py
│   ├── test_ai.py
│   └── test_executor.py
├── requirements.txt
└── README.md
```

## Installation

### Prerequisites

- Python 3.12 (recommended) or Python 3.11+
- Internet connection for downloading packages

### Setup

**Quick Setup (Recommended):**

Use the provided setup script which handles the ensurepip issue:

```bash
cd /home/ali/Desktop/sarbazi/code/ps2
chmod +x setup.sh
./setup.sh
```

**Manual Setup:**

1. Navigate to the project directory:
```bash
cd /home/ali/Desktop/sarbazi/code/ps2
```

2. Create a virtual environment (if `ensurepip` is not available, use `--without-pip`):
```bash
python3.12 -m venv venv --without-pip
```

3. Install pip manually (if needed):
```bash
python3.12 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', 'get-pip.py')"
./venv/bin/python3.12 get-pip.py
rm get-pip.py
```

4. Install dependencies:
```bash
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt
```

**Note:** If your system Python 3.12 doesn't have `ensurepip` (common on some Linux distributions), the setup script automatically handles this by installing pip manually.

5. Create a `.env` file for configuration (optional):
```bash
# Exchange API credentials (configure only the exchanges you want to use)

# Nobitex - Token-based authentication (choose one method)
# Option 1: Direct token (if you have it from dashboard)
NOBITEX_TOKEN=your_token_here
# Option 2: Username/password (will auto-login and get token)
NOBITEX_USERNAME=your_username
NOBITEX_PASSWORD=your_password

# Wallex
WALLEX_API_KEY=your_wallex_api_key
WALLEX_API_SECRET=your_wallex_api_secret

# KuCoin
KUCOIN_API_KEY=your_kucoin_api_key
KUCOIN_API_SECRET=your_kucoin_api_secret
KUCOIN_API_PASSPHRASE=your_kucoin_passphrase

# Invex - RSA signature authentication
INVEX_API_KEY=your_invex_api_key
INVEX_API_SECRET=your_hex_encoded_private_key_here

# Tabdeal
TABDEAL_API_KEY=your_tabdeal_api_key
TABDEAL_API_SECRET=your_tabdeal_api_secret

# Trading configuration
TRADING_MIN_SPREAD_PERCENT=0.5
TRADING_MIN_PROFIT_USDT=1.0
TRADING_MAX_POSITION_SIZE_USDT=1000.0

# AI configuration
AI_MODEL_PATH=./models/xgboost_model.pkl
AI_TRAINING_DATA_PATH=./data/training_data.csv

# API configuration
API_HOST=0.0.0.0
API_PORT=8000
```

## Usage

### Running the API Server

**Quick Start (Recommended):**

Use the provided run script:

```bash
./run.sh
```

**Manual Start:**

Activate the virtual environment and run:

```bash
source venv/bin/activate
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the venv Python directly:

```bash
./venv/bin/python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`. Interactive API documentation is available at `http://localhost:8000/docs`.

### API Endpoints

#### Health Check
- `GET /health` - Health status
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness check

#### Metrics
- `GET /metrics` - Get trading metrics
- `GET /metrics/opportunities` - Get current arbitrage opportunities

#### Orders
- `POST /orders/preview` - Preview an order without executing
- `POST /orders/execute` - Execute an arbitrage order

#### AI/ML
- `POST /ai/predict` - Predict maker/taker decision
- `POST /ai/train` - Train the XGBoost model
- `GET /ai/status` - Get model status

### Training the AI Model

The AI model training follows an **iterative improvement methodology**: collect data, train, evaluate, collect more data, retrain, compare results. This demonstrates empirical machine learning best practices.

#### Step 1: Collect Training Data

Collect real orderbook snapshots from live exchanges:

```bash
# First collection (15-30 minutes recommended for baseline)
python scripts/collect_training_data.py --duration 1800 --output data/training_iter1.csv

# Second collection (1 hour for improved diversity)
python scripts/collect_training_data.py --duration 3600 --output data/training_iter2.csv

# Third collection if needed
python scripts/collect_training_data.py --duration 3600 --output data/training_iter3.csv
```

**What this does:**
- Fetches orderbook snapshots from Nobitex, Wallex, and Invex every 4-5 seconds
- Extracts 19 orderbook features (spread, depth, VWAP, pressure indicators)
- Generates labels using adaptive percentile-based strategy
- Saves to CSV with features + label column

#### Step 2: Combine Multiple Datasets (for iterative improvement)

Combine data from multiple collection sessions:

```bash
# Combine all iterations into one dataset
python scripts/combine_training_data.py data/training_iter*.csv --output data/training_combined.csv
```

**Why combine datasets?**
- More samples = better model generalization
- Different time periods capture diverse market conditions (calm + volatile)
- Typical improvement: 800 samples (63% accuracy) → 3,200 samples (68-72% accuracy)

**The script automatically:**
- Loads all specified CSV files
- Removes duplicate samples
- Shows label distribution for each dataset
- Reports combined statistics
- Saves merged dataset

#### Step 3: Train the Model

Train XGBoost classifier with full evaluation:

```bash
# Train on combined dataset
python scripts/train_model.py --data data/training_combined.csv

# Or train on single iteration
python scripts/train_model.py --data data/training_iter1.csv
```

**This generates:**
- `models/xgboost_model.pkl` - Trained model (auto-loaded by bot)
- `models/evaluation_report.json` - Metrics (accuracy, ROC-AUC, etc.)
- `models/plots/` - 3 visualizations (confusion matrix, feature importance, ROC curve)

**Evaluation metrics shown:**
- Accuracy, Precision, Recall, F1-Score
- ROC-AUC curve
- 5-fold cross-validation results
- Confusion matrix
- Feature importance rankings

#### Step 4: Track Improvements

Keep all iterations as records to show the improvement process:

```
data/
├── training_iter1.csv          # Baseline (e.g., 798 samples, 63% accuracy)
├── training_iter2.csv          # Second run (e.g., 2,400 samples)
├── training_combined.csv       # Combined dataset (e.g., 3,200 samples, 68% accuracy)

models/
├── iter1_baseline/             # First model results
│   ├── xgboost_model.pkl
│   ├── evaluation_report.json
│   └── plots/
├── iter2_improved/             # Second model results
│   ├── xgboost_model.pkl
│   ├── evaluation_report.json
│   └── plots/
└── xgboost_model.pkl          # Current production model (latest)
```

See `docs/model_training_log.md` for detailed iteration results and methodology.

#### Alternative: Train via API

You can also train via the REST API:

```bash
curl -X POST "http://localhost:8000/ai/train" \
  -H "Content-Type: application/json" \
  -d '{
    "data_path": "./data/training_combined.csv",
    "test_size": 0.2,
    "random_state": 42
  }'
```

Or use Python directly:
```python
from app.ai.trainer import ModelTrainer
from app.core.config import settings

trainer = ModelTrainer(settings.ai)
model, metrics, feature_names = trainer.train_from_csv("data/training_combined.csv")
trainer.save_model(model, feature_names)
```

### Backtesting

Run backtests on historical data:

```python
from app.backtesting.loader import DataLoader
from app.backtesting.simulator import BacktestSimulator
from app.strategy.arbitrage_engine import ArbitrageEngine

# Load historical orderbook data
loader = DataLoader("./data")
orderbooks = loader.load_multiple_orderbooks(
    file_paths={"nobitex": "./data/nobitex_orderbooks.csv", "wallex": "./data/wallex_orderbooks.csv"},
    symbols={"nobitex": "BTCUSDT", "wallex": "BTCUSDT"}
)

# Create engine and simulator
engine = ArbitrageEngine(exchanges, config)
simulator = BacktestSimulator(engine, initial_balance=10000.0)

# Run simulation
result = simulator.simulate(orderbooks, use_maker_orders=False)
print(simulator.get_summary())
```

## Configuration

### Logging Level

The default logging level is set to `DEBUG` for detailed development logs. You can change it by setting the `LOG_LEVEL` environment variable:

```bash
# In .env file or environment
LOG_LEVEL=INFO    # Less verbose (recommended for production)
LOG_LEVEL=DEBUG   # Detailed logs (default, recommended for development)
LOG_LEVEL=WARNING # Only warnings and errors
LOG_LEVEL=ERROR   # Only errors
```

Available levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Configuration

Configuration is managed through environment variables and Pydantic settings. Key settings include:

- **Exchange Configuration**: API keys, base URLs, maker/taker fees
- **Trading Parameters**: Minimum spread, profit thresholds, position limits
- **AI Settings**: Model path, training data path, prediction threshold
- **API Settings**: Host, port, CORS origins

See `app/core/config.py` for all available configuration options.

## Architecture

### Exchange Interface

All exchanges implement the `ExchangeInterface` abstract base class with methods:
- `fetch_orderbook()` - Get current order book
- `place_order()` - Place buy/sell orders
- `cancel_order()` - Cancel existing orders
- `get_balance()` - Get account balance

### Arbitrage Engine

The `ArbitrageEngine` detects opportunities by:
1. Comparing orderbooks across exchanges
2. Calculating spread and net profit after fees
3. Filtering by minimum thresholds
4. Ranking opportunities by profitability

### Order Executor

The `OrderExecutor` handles:
- Concurrent order placement
- Retry logic with exponential backoff
- Maker/taker order selection
- Error handling and order cancellation

### AI Model (Optional Enhancement)

When enabled, the XGBoost model predicts whether to use maker (post-only) or taker orders based on:
- Orderbook features (spread, depth, imbalance)
- OHLC features (price movements, volume, volatility)
- Historical patterns

**Note**: The bot works fully without AI. When AI is not available or not enabled, the bot defaults to taker orders, which still allows profitable arbitrage trading.

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Run specific test files:

```bash
pytest tests/test_arbitrage.py -v
pytest tests/test_ai.py -v
pytest tests/test_executor.py -v
pytest tests/test_exchanges_integration.py -v
pytest tests/test_api_enum_validation.py -v
```

### Test Coverage

- **Integration Tests**: Exchange API implementations (orderbook, orders, balance, OHLC)
- **Unit Tests**: Exchange interfaces, authentication, symbol conversion
- **API Tests**: Enum validation, error handling, endpoint functionality
- **Error Handling Tests**: Network errors, API errors, invalid responses

## Development

### Code Style

- Type hints throughout
- Google-style docstrings
- Async/await for I/O operations
- Pydantic models for data validation

### Adding New Exchanges

1. Create a new class inheriting from `ExchangeInterface`
2. Implement all abstract methods
3. Add configuration in `app/core/config.py`
4. Register in the exchanges dictionary

### Extending Features

- Add new features in `app/ai/features.py`
- Extend backtesting in `app/backtesting/simulator.py`
- Add API routes in `app/api/routes/`

## Security Notes

- **Never commit API keys** to version control
- Use environment variables for sensitive data
- Implement rate limiting for production
- Add authentication for API endpoints
- Validate all inputs and handle errors gracefully

## Limitations

- Initial implementation operates in taker-taker mode
- Exchange API endpoints need to be configured based on actual API documentation
- Model training requires labeled historical data
- Backtesting assumes perfect execution (no slippage)

## Future Enhancements

- WebSocket support for real-time orderbook updates
- Database integration for trade history
- Advanced risk management
- Multi-asset arbitrage
- Portfolio optimization
- Real-time monitoring dashboard

## License

This project is provided as-is for educational and development purposes.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions, please open an issue in the repository.

## Disclaimer

This software is for educational purposes only. Trading cryptocurrencies involves substantial risk. Use at your own risk. The authors are not responsible for any financial losses.

