"""API services for managing exchanges and arbitrage engine."""

from typing import Dict, Optional

from app.ai.model import TradingModel
from app.ai.predictor import TradingPredictor
from app.core.config import settings
from app.core.exchange_types import ExchangeName
from app.data.collector import DataCollector
from app.exchanges.nobitex import NobitexExchange
from app.exchanges.wallex import WallexExchange
from app.exchanges.kucoin import KucoinExchange
from app.exchanges.invex import InvexExchange
from app.exchanges.tabdeal import TabdealExchange
from app.exchanges.base import ExchangeInterface
from app.strategy.arbitrage_engine import ArbitrageEngine
from app.strategy.order_executor import OrderExecutor
from app.strategy.price_stream import PriceStream
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global instances
_exchanges: Optional[Dict[ExchangeName, ExchangeInterface]] = None
_arbitrage_engine: Optional[ArbitrageEngine] = None
_order_executor: Optional[OrderExecutor] = None
_trading_model: Optional[TradingModel] = None
_predictor: Optional[TradingPredictor] = None
_data_collector: Optional[DataCollector] = None
_price_stream: Optional[PriceStream] = None


def get_exchanges() -> Dict[ExchangeName, ExchangeInterface]:
    """Get or initialize exchanges."""
    global _exchanges
    if _exchanges is None:
        _exchanges = {
            ExchangeName.NOBITEX: NobitexExchange(settings.nobitex),
            ExchangeName.WALLEX: WallexExchange(settings.wallex),
            ExchangeName.KUCOIN: KucoinExchange(settings.kucoin),
            ExchangeName.INVEX: InvexExchange(settings.invex),
            ExchangeName.TABDEAL: TabdealExchange(settings.tabdeal),
        }
        logger.info("Initialized exchanges: %s", [e.value for e in _exchanges.keys()])
    return _exchanges


def get_data_collector() -> DataCollector:
    """Get or initialize data collector."""
    global _data_collector
    if _data_collector is None:
        exchanges = get_exchanges()
        _data_collector = DataCollector(exchanges)
        logger.info("Initialized data collector")
    return _data_collector


def get_arbitrage_engine() -> ArbitrageEngine:
    """Get or initialize arbitrage engine."""
    global _arbitrage_engine
    if _arbitrage_engine is None:
        exchanges = get_exchanges()
        data_collector = get_data_collector()
        _arbitrage_engine = ArbitrageEngine(exchanges, settings.trading, data_collector)
        logger.info("Initialized arbitrage engine")
    return _arbitrage_engine


def get_trading_model() -> TradingModel:
    """Get or initialize trading model."""
    global _trading_model
    if _trading_model is None:
        _trading_model = TradingModel(settings.ai)
        _trading_model.load()
        logger.info("Initialized trading model")
    return _trading_model


def get_predictor() -> TradingPredictor:
    """Get or initialize AI predictor."""
    global _predictor
    if _predictor is None:
        model = get_trading_model()
        _predictor = TradingPredictor(model)
        logger.info("Initialized AI predictor")
    return _predictor


def get_order_executor() -> OrderExecutor:
    """Get or initialize order executor."""
    global _order_executor
    if _order_executor is None:
        exchanges = get_exchanges()
        predictor = get_predictor()
        data_collector = get_data_collector()
        _order_executor = OrderExecutor(exchanges, settings.trading, predictor, data_collector)
        logger.info("Initialized order executor with AI predictor and data collector")
    return _order_executor


def get_price_stream() -> PriceStream:
    """Get or initialize price stream."""
    global _price_stream
    if _price_stream is None:
        exchanges = get_exchanges()
        _price_stream = PriceStream(exchanges, settings.trading)
        logger.info("Initialized price stream")
    return _price_stream


async def close_exchanges() -> None:
    """Close all exchange connections."""
    global _exchanges
    if _exchanges:
        for exchange in _exchanges.values():
            if hasattr(exchange, "close"):
                await exchange.close()
        logger.info("Closed all exchange connections")

