# AI-Assisted Cryptocurrency Arbitrage Trading Bot

A lightweight, production-oriented arbitrage trading bot that detects and executes arbitrage opportunities between cryptocurrency exchanges using AI-assisted maker/taker order decisions.

## Features

- **Arbitrage Detection**: Real-time detection of price differences between exchanges
- **AI-Powered Decisions**: XGBoost model for optimizing maker vs taker order selection
- **Async Architecture**: Fully asynchronous Python implementation for high performance
- **Multiple Exchanges**: Support for Nobitex and Wallex exchanges (extensible)
- **Backtesting**: Historical data replay for strategy validation
- **REST API**: FastAPI-based monitoring and control interface
- **Fee Optimization**: Minimizes trading fees through intelligent order type selection

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
│   │   └── wallex.py
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

- Python 3.11 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
cd /home/ali/Desktop/sarbazi/code/ps2
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file for configuration:
```bash
# Exchange API credentials
NOBITEX_API_KEY=your_nobitex_api_key
NOBITEX_API_SECRET=your_nobitex_api_secret
WALLEX_API_KEY=your_wallex_api_key
WALLEX_API_SECRET=your_wallex_api_secret

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

Start the FastAPI server:

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
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

1. Prepare training data in CSV format with features and labels:
   - Feature columns: orderbook and OHLC features
   - Label column: `label` or `is_maker` (0=taker, 1=maker)

2. Train the model via API:
```bash
curl -X POST "http://localhost:8000/ai/train" \
  -H "Content-Type: application/json" \
  -d '{
    "data_path": "./data/training_data.csv",
    "test_size": 0.2,
    "random_state": 42
  }'
```

Or use Python:
```python
from app.ai.trainer import ModelTrainer
from app.core.config import settings

trainer = ModelTrainer(settings.ai)
model, metrics, feature_names = trainer.train_from_csv()
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

### AI Model

The XGBoost model predicts whether to use maker (post-only) or taker orders based on:
- Orderbook features (spread, depth, imbalance)
- OHLC features (price movements, volume, volatility)
- Historical patterns

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
```

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

