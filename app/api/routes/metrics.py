"""Trading metrics endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, List, Optional

from app.api.services import get_arbitrage_engine, get_exchanges, get_order_executor
from app.core.exchange_types import ExchangeName, TradingSymbol
from app.core.logging import get_logger

router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = get_logger(__name__)


class TradingMetrics(BaseModel):
    """Trading metrics response model."""

    total_trades: int = 0
    profitable_trades: int = 0
    successful_trades: int = 0
    total_profit: float = 0.0
    total_volume: float = 0.0
    win_rate: float = 0.0
    active_opportunities: int = 0
    # AI performance metrics
    ai_accuracy: float = 0.0
    ai_confidence: float = 0.0
    maker_profit: float = 0.0
    taker_profit: float = 0.0
    confidence_stats: Optional[Dict[str, float]] = None


class OpportunityMetrics(BaseModel):
    """Opportunity metrics."""

    symbol: str  # Keep as string in response for flexibility
    buy_exchange: str  # Keep as string in response for flexibility
    sell_exchange: str  # Keep as string in response for flexibility
    spread_percent: float
    net_profit: float
    max_quantity: float


# In-memory metrics storage (replace with database in production)
_metrics_store: Dict = {
    "total_trades": 0,
    "profitable_trades": 0,
    "total_profit": 0.0,
    "total_volume": 0.0,
    "opportunities": [],
}


@router.get("", response_model=TradingMetrics)
async def get_metrics() -> TradingMetrics:
    """
    Get trading metrics including AI performance.

    Returns:
        Current trading metrics with AI performance data
    """
    executor = get_order_executor()
    monitor = executor.monitor

    # Get prediction and trade metrics
    pred_metrics = monitor.get_prediction_metrics(hours=24)
    trade_metrics = monitor.get_trade_metrics(hours=24)
    confidence_stats = monitor.get_model_confidence_stats()

    return TradingMetrics(
        total_trades=trade_metrics.total_trades,
        profitable_trades=trade_metrics.successful_trades,
        successful_trades=trade_metrics.successful_trades,
        total_profit=trade_metrics.total_profit,
        total_volume=0.0,  # Can be calculated from trade history if needed
        win_rate=trade_metrics.win_rate * 100.0,
        active_opportunities=len(_metrics_store["opportunities"]),
        ai_accuracy=(
            pred_metrics.correct_predictions / pred_metrics.total_predictions
            if pred_metrics.total_predictions > 0
            else 0.0
        ),
        ai_confidence=pred_metrics.avg_confidence,
        maker_profit=pred_metrics.maker_profit,
        taker_profit=pred_metrics.taker_profit,
        confidence_stats=confidence_stats if confidence_stats else None,
    )


@router.get("/opportunities", response_model=List[OpportunityMetrics])
async def get_opportunities(
    symbol: TradingSymbol = Query(TradingSymbol.BTCUSDT, description="Trading pair symbol to check")
) -> List[OpportunityMetrics]:
    """
    Get current arbitrage opportunities.

    Args:
        symbol: Trading pair symbol to check (default: BTCUSDT)

    Returns:
        List of current opportunities
    """
    try:
        exchanges = get_exchanges()
        engine = get_arbitrage_engine()
        
        symbol_str = symbol.value
        
        # Try to fetch real orderbooks with proper symbol conversion
        orderbooks = {}
        failed_exchanges = []
        base_currency = SymbolConverter.get_base_currency(symbol_str)
        quote_currency = SymbolConverter.get_quote_currency(symbol_str)
        
        for name, exchange in exchanges.items():
            try:
                # Get compatible symbol for this exchange
                exchange_enum = name if isinstance(name, ExchangeName) else ExchangeName.from_string(str(name))
                supported_quotes = SymbolConverter.EXCHANGE_QUOTE_CURRENCIES.get(exchange_enum, [])
                
                # Only use exact quote currency match OR IRT/IRR conversion
                # Do NOT convert IRT to USDT (different markets!)
                exchange_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(symbol_str, exchange_enum)
                
                if not exchange_symbol and base_currency and quote_currency:
                    # Only allow IRT/IRR conversion (same currency)
                    if quote_currency == "IRT" and "IRR" in supported_quotes:
                        alt_symbol = f"{base_currency}IRR"
                        exchange_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(alt_symbol, exchange_enum)
                    elif quote_currency == "IRR" and "IRT" in supported_quotes:
                        alt_symbol = f"{base_currency}IRT"
                        exchange_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(alt_symbol, exchange_enum)
                
                if not exchange_symbol:
                    logger.warning(
                        f"No compatible symbol for {exchange_enum.value} with {symbol_str}. "
                        f"Exchange supports: {supported_quotes}"
                    )
                    failed_exchanges.append(exchange_enum.value)
                    continue
                
                if not exchange_symbol:
                    logger.warning(f"Could not determine symbol for {exchange_enum.value}")
                    failed_exchanges.append(exchange_enum.value)
                    continue
                
                orderbook = await exchange.fetch_orderbook(exchange_symbol)
                # Store with enum value as key for consistency
                orderbooks[exchange_enum.value] = orderbook
                logger.debug(f"Successfully fetched orderbook from {exchange_enum.value} for {exchange_symbol} (requested: {symbol_str})")
            except Exception as e:
                exchange_name_str = exchange_enum.value if 'exchange_enum' in locals() else (name.value if hasattr(name, 'value') else str(name))
                error_msg = str(e)
                if len(error_msg) > 150:
                    error_msg = error_msg[:150] + "..."
                logger.error(f"Failed to fetch orderbook from {exchange_name_str} for {symbol_str}: {error_msg}", exc_info=True)
                failed_exchanges.append(exchange_name_str)
        
        if len(orderbooks) < 2:
            error_msg = (
                f"Not enough orderbooks fetched for {symbol_str}. "
                f"Got {len(orderbooks)} orderbook(s), need at least 2. "
                f"Failed exchanges: {failed_exchanges if failed_exchanges else 'None'}"
            )
            logger.error(error_msg)
            raise HTTPException(
                status_code=503,
                detail=error_msg
            )
        
        # Find opportunities
        opportunities = engine.find_opportunities(symbol_str, orderbooks)
        
        # Update store
        _metrics_store["opportunities"] = [
            {
                "symbol": opp.symbol,
                "buy_exchange": opp.buy_exchange,
                "sell_exchange": opp.sell_exchange,
                "spread_percent": opp.spread_percent,
                "net_profit": opp.net_profit,
                "max_quantity": opp.max_quantity,
            }
            for opp in opportunities
        ]
        
        return [
            OpportunityMetrics(
                symbol=opp.symbol,
                buy_exchange=opp.buy_exchange,
                sell_exchange=opp.sell_exchange,
                spread_percent=opp.spread_percent,
                net_profit=opp.net_profit,
                max_quantity=opp.max_quantity,
            )
            for opp in opportunities
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching opportunities: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch opportunities: {str(e)}"
        )


@router.post("/update")
async def update_metrics(metrics: TradingMetrics) -> dict:
    """
    Update metrics (internal use).

    Args:
        metrics: Updated metrics

    Returns:
        Success status
    """
    _metrics_store["total_trades"] = metrics.total_trades
    _metrics_store["profitable_trades"] = metrics.profitable_trades
    _metrics_store["total_profit"] = metrics.total_profit
    _metrics_store["total_volume"] = metrics.total_volume
    return {"status": "updated"}


@router.post("/opportunities/update")
async def update_opportunities(
    opportunities: List[OpportunityMetrics],
) -> dict:
    """
    Update opportunities list (internal use).

    Args:
        opportunities: List of opportunities

    Returns:
        Success status
    """
    _metrics_store["opportunities"] = [opp.dict() for opp in opportunities]
    return {"status": "updated"}

