"""Order management endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, model_validator, validator
from typing import Optional, List

from app.api.services import get_arbitrage_engine, get_order_executor, get_exchanges
from app.core.exchange_types import ExchangeName, TradingSymbol
from app.core.logging import get_logger
from app.exchanges.base import Order

router = APIRouter(prefix="/orders", tags=["orders"])
logger = get_logger(__name__)


class OrderPreviewRequest(BaseModel):
    """Order preview request model."""

    symbol: TradingSymbol
    buy_exchange: ExchangeName
    sell_exchange: ExchangeName
    quantity: float

    @validator("quantity")
    def quantity_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity must be greater than zero")
        return v

    @model_validator(mode="after")
    def exchanges_must_differ(self):
        if self.buy_exchange and self.sell_exchange and self.buy_exchange == self.sell_exchange:
            raise ValueError("buy_exchange and sell_exchange must be different")
        return self


class OrderPreviewResponse(BaseModel):
    """Order preview response model."""

    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    quantity: float
    estimated_profit: float
    buy_fee: float
    sell_fee: float
    total_cost: float
    total_revenue: float


class OrderExecuteRequest(BaseModel):
    """Order execution request model."""

    symbol: TradingSymbol
    buy_exchange: ExchangeName
    sell_exchange: ExchangeName
    quantity: float
    use_maker: bool = False

    @validator("quantity")
    def quantity_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity must be greater than zero")
        return v

    @model_validator(mode="after")
    def exchanges_must_differ(self):
        if self.buy_exchange and self.sell_exchange and self.buy_exchange == self.sell_exchange:
            raise ValueError("buy_exchange and sell_exchange must be different")
        return self


class OrderExecuteResponse(BaseModel):
    """Order execution response model."""

    success: bool
    buy_order_id: Optional[str] = None
    sell_order_id: Optional[str] = None
    message: str


# TODO: Integrate with actual order executor
# This is a placeholder implementation


@router.post("/preview", response_model=OrderPreviewResponse)
async def preview_order(request: OrderPreviewRequest) -> OrderPreviewResponse:
    """
    Preview an arbitrage order without executing.

    Args:
        request: Order preview request

    Returns:
        Order preview with estimated costs and profits
    """
    try:
        exchanges = get_exchanges()
        engine = get_arbitrage_engine()
        
        # Exchange names are already enums from request
        buy_exchange_name = request.buy_exchange
        sell_exchange_name = request.sell_exchange
        
        # Validate exchanges exist
        if buy_exchange_name not in exchanges:
            raise HTTPException(
                status_code=400,
                detail=f"Buy exchange '{buy_exchange_name.value}' not found. Available: {[e.value for e in exchanges.keys()]}"
            )
        if sell_exchange_name not in exchanges:
            raise HTTPException(
                status_code=400,
                detail=f"Sell exchange '{sell_exchange_name.value}' not found. Available: {[e.value for e in exchanges.keys()]}"
            )
        
        # Fetch orderbooks
        buy_exchange = exchanges[buy_exchange_name]
        sell_exchange = exchanges[sell_exchange_name]
        
        try:
            buy_orderbook = await buy_exchange.fetch_orderbook(request.symbol.value)
            sell_orderbook = await sell_exchange.fetch_orderbook(request.symbol.value)
        except Exception as e:
            logger.warning(f"Failed to fetch orderbooks: {e}. Using mock data for preview.")
            # Fallback to mock data if API keys are not configured
            from app.utils.math import calculate_arbitrage_profit
            buy_price = 50000.0
            sell_price = 50100.0
            buy_fee = buy_exchange.config.taker_fee
            sell_fee = sell_exchange.config.taker_fee
            
            net_profit, _ = calculate_arbitrage_profit(
                buy_price, sell_price, request.quantity, buy_fee, sell_fee
            )
            
            return OrderPreviewResponse(
                symbol=request.symbol.value,
                buy_exchange=buy_exchange_name.value,
                sell_exchange=sell_exchange_name.value,
                buy_price=buy_price,
                sell_price=sell_price,
                quantity=request.quantity,
                estimated_profit=net_profit,
                buy_fee=buy_fee,
                sell_fee=sell_fee,
                total_cost=buy_price * request.quantity * (1 + buy_fee),
                total_revenue=sell_price * request.quantity * (1 - sell_fee),
            )
        
        # Detect opportunity
        opportunity = engine.detect_opportunity(
            request.symbol.value,
            buy_exchange_name.value,
            sell_exchange_name.value,
            buy_orderbook,
            sell_orderbook,
        )
        
        if not opportunity:
            # If no opportunity found, still return preview with current prices
            # This allows users to see what the trade would look like even without profit
            from app.utils.math import calculate_arbitrage_profit
            
            # Use best bid/ask prices
            buy_price = buy_orderbook.asks[0].price if buy_orderbook.asks else 0.0
            sell_price = sell_orderbook.bids[0].price if sell_orderbook.bids else 0.0
            
            if buy_price == 0.0 or sell_price == 0.0:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid orderbook data: missing bid/ask prices"
                )
            
            buy_fee = buy_exchange.config.taker_fee
            sell_fee = sell_exchange.config.taker_fee
            
            net_profit, _ = calculate_arbitrage_profit(
                buy_price, sell_price, request.quantity, buy_fee, sell_fee
            )
            
            return OrderPreviewResponse(
                symbol=request.symbol.value,
                buy_exchange=buy_exchange_name.value,
                sell_exchange=sell_exchange_name.value,
                buy_price=buy_price,
                sell_price=sell_price,
                quantity=request.quantity,
                estimated_profit=net_profit,
                buy_fee=buy_fee,
                sell_fee=sell_fee,
                total_cost=buy_price * request.quantity * (1 + buy_fee),
                total_revenue=sell_price * request.quantity * (1 - sell_fee),
            )
        
        # Use actual opportunity data, but with requested quantity
        from app.utils.math import calculate_arbitrage_profit
        quantity = min(request.quantity, opportunity.max_quantity)
        
        net_profit, _ = calculate_arbitrage_profit(
            opportunity.buy_price,
            opportunity.sell_price,
            quantity,
            opportunity.buy_fee,
            opportunity.sell_fee,
        )
        
        return OrderPreviewResponse(
            symbol=request.symbol.value,
                buy_exchange=buy_exchange_name.value,
                sell_exchange=sell_exchange_name.value,
                buy_price=opportunity.buy_price,
                sell_price=opportunity.sell_price,
                quantity=quantity,
                estimated_profit=net_profit,
                buy_fee=opportunity.buy_fee,
                sell_fee=opportunity.sell_fee,
                total_cost=opportunity.buy_price * quantity * (1 + opportunity.buy_fee),
                total_revenue=opportunity.sell_price * quantity * (1 - opportunity.sell_fee),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in preview_order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to preview order: {str(e)}")


@router.post("/execute", response_model=OrderExecuteResponse)
async def execute_order(request: OrderExecuteRequest) -> OrderExecuteResponse:
    """
    Execute an arbitrage order.

    Args:
        request: Order execution request

    Returns:
        Order execution result
    """
    try:
        exchanges = get_exchanges()
        engine = get_arbitrage_engine()
        executor = get_order_executor()
        
        # Exchange names are already enums from request
        buy_exchange_name = request.buy_exchange
        sell_exchange_name = request.sell_exchange
        
        # Validate exchanges exist
        if buy_exchange_name not in exchanges:
            raise HTTPException(
                status_code=400,
                detail=f"Buy exchange '{buy_exchange_name.value}' not found. Available: {[e.value for e in exchanges.keys()]}"
            )
        if sell_exchange_name not in exchanges:
            raise HTTPException(
                status_code=400,
                detail=f"Sell exchange '{sell_exchange_name.value}' not found. Available: {[e.value for e in exchanges.keys()]}"
            )
        
        # Check if authenticated
        buy_exchange = exchanges[buy_exchange_name]
        sell_exchange = exchanges[sell_exchange_name]
        
        if not buy_exchange.is_authenticated() or not sell_exchange.is_authenticated():
            return OrderExecuteResponse(
                success=False,
                message="Authentication not configured. Please set exchange credentials in .env file to execute real orders.",
            )
        
        # Fetch orderbooks and find opportunity
        try:
            buy_orderbook = await buy_exchange.fetch_orderbook(request.symbol.value)
            sell_orderbook = await sell_exchange.fetch_orderbook(request.symbol.value)
        except Exception as e:
            logger.error(f"Failed to fetch orderbooks: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Failed to fetch orderbooks from exchanges: {str(e)}"
            )
        
        opportunity = engine.detect_opportunity(
            request.symbol,
            buy_exchange_name.value,
            sell_exchange_name.value,
            buy_orderbook,
            sell_orderbook,
        )
        
        if not opportunity:
            raise HTTPException(
                status_code=400,
                detail="No profitable arbitrage opportunity found"
            )
        
        # Adjust quantity if needed
        quantity = min(request.quantity, opportunity.max_quantity)
        
        # Execute orders with AI (pass None to use AI, or explicit value to override)
        use_maker_override = request.use_maker if request.use_maker is not None else None
        buy_order, sell_order = await executor.execute_arbitrage(
            opportunity,
            use_maker=use_maker_override,
            buy_orderbook=buy_orderbook,
            sell_orderbook=sell_orderbook,
        )
        
        # Check if both orders were successfully filled
        both_filled = (
            buy_order is not None
            and sell_order is not None
            and buy_order.status == "filled"
            and sell_order.status == "filled"
        )

        if both_filled:
            return OrderExecuteResponse(
                success=True,
                buy_order_id=buy_order.order_id,
                sell_order_id=sell_order.order_id,
                message=f"Arbitrage executed successfully. Buy: {buy_order.order_id} (filled {buy_order.filled_quantity:.8f}), Sell: {sell_order.order_id} (filled {sell_order.filled_quantity:.8f})",
            )
        elif buy_order or sell_order:
            # At least one order was placed
            status_msg = []
            if buy_order:
                status_msg.append(f"Buy: {buy_order.order_id} ({buy_order.status})")
            if sell_order:
                status_msg.append(f"Sell: {sell_order.order_id} ({sell_order.status})")
            
            return OrderExecuteResponse(
                success=False,
                buy_order_id=buy_order.order_id if buy_order else None,
                sell_order_id=sell_order.order_id if sell_order else None,
                message=f"Orders placed but not both filled. {', '.join(status_msg)}. Check order status.",
            )
        else:
            return OrderExecuteResponse(
                success=False,
                message="Failed to place orders. Check logs for details.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in execute_order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute order: {str(e)}")


class OpenOrderResponse(BaseModel):
    """Open order response model."""
    
    exchange: str
    orders: List[dict]


@router.get("/open", response_model=List[OpenOrderResponse])
async def get_open_orders(
    exchange: Optional[ExchangeName] = Query(None, description="Exchange name. If not provided, returns orders from all exchanges."),
    symbol: Optional[TradingSymbol] = Query(None, description="Trading pair symbol to filter by"),
) -> List[OpenOrderResponse]:
    """
    Get open orders from exchange(s).

    Args:
        exchange: Optional exchange name to filter by (case-insensitive)
        symbol: Optional trading pair symbol to filter by

    Returns:
        List of open orders grouped by exchange
    """
    try:
        exchanges = get_exchanges()
        results = []
        
        # Filter exchanges if specified
        if exchange:
            if exchange not in exchanges:
                raise HTTPException(
                    status_code=400,
                    detail=f"Exchange '{exchange.value}' not found. Available: {[e.value for e in exchanges.keys()]}"
                )
            exchanges_to_check = {exchange: exchanges[exchange]}
        else:
            exchanges_to_check = exchanges
        
        for exchange_name, exchange_obj in exchanges_to_check.items():
            # Check if authenticated
            if not exchange_obj.is_authenticated():
                # If specific exchange was requested, raise error immediately
                if exchange:
                    raise HTTPException(
                        status_code=401,
                        detail=f"Exchange '{exchange.value}' is not authenticated. Please configure credentials in .env file."
                    )
                # Otherwise, skip when fetching from all exchanges
                logger.debug(f"Skipping unauthenticated exchange: {exchange_name.value if isinstance(exchange_name, ExchangeName) else exchange_name}")
                continue
            
            try:
                # Check if exchange implements get_open_orders
                if hasattr(exchange_obj, 'get_open_orders'):
                    symbol_str = symbol.value if symbol else None
                    orders = await exchange_obj.get_open_orders(symbol=symbol_str)
                    orders_data = [
                        {
                            "order_id": order.order_id,
                            "symbol": order.symbol,
                            "side": order.side,
                            "order_type": order.order_type,
                            "quantity": order.quantity,
                            "price": order.price,
                            "status": order.status,
                            "filled_quantity": order.filled_quantity,
                            "timestamp": order.timestamp,
                        }
                        for order in orders
                    ]
                    results.append(OpenOrderResponse(
                        exchange=exchange_name.value if isinstance(exchange_name, ExchangeName) else exchange_name,
                        orders=orders_data,
                    ))
                else:
                    # Exchange doesn't support get_open_orders yet
                    logger.warning(f"Exchange {exchange_name.value if isinstance(exchange_name, ExchangeName) else exchange_name} does not support get_open_orders")
                    results.append(OpenOrderResponse(
                        exchange=exchange_name.value if isinstance(exchange_name, ExchangeName) else exchange_name,
                        orders=[],
                    ))
            except Exception as e:
                logger.error(f"Error fetching open orders from {exchange_name.value if isinstance(exchange_name, ExchangeName) else exchange_name}: {e}")
                results.append(OpenOrderResponse(
                    exchange=exchange_name.value if isinstance(exchange_name, ExchangeName) else exchange_name,
                    orders=[],
                ))
        
        return results
    except HTTPException:
        # Re-raise HTTPExceptions (like 401 for unauthenticated)
        raise
    except Exception as e:
        logger.error(f"Error in get_open_orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get open orders: {str(e)}")


class OrderStatusResponse(BaseModel):
    """Order status response model."""
    
    exchange: str
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    status: str
    filled_quantity: float
    timestamp: float


@router.get("/{order_id}", response_model=OrderStatusResponse)
async def get_order_status(
    order_id: str,
    exchange: ExchangeName = Query(..., description="Exchange name"),
    symbol: TradingSymbol = Query(..., description="Trading pair symbol"),
) -> OrderStatusResponse:
    """
    Get order status by order ID.

    Args:
        order_id: Order ID to check
        exchange: Exchange name where the order was placed
        symbol: Trading pair symbol

    Returns:
        Order status information
    """
    try:
        exchanges = get_exchanges()
        
        # Exchange is already an enum from query parameter
        if exchange not in exchanges:
            raise HTTPException(
                status_code=400,
                detail=f"Exchange '{exchange.value}' not found. Available: {[e.value for e in exchanges.keys()]}"
            )
        
        exchange_obj = exchanges[exchange]
        
        # Check if authenticated
        if not exchange_obj.is_authenticated():
            raise HTTPException(
                status_code=401,
                detail=f"Authentication not configured for {exchange.value}"
            )
        
        # Fetch order status
        order = await exchange_obj.get_order(order_id, symbol.value)
        
        return OrderStatusResponse(
            exchange=exchange.value,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            status=order.status,
            filled_quantity=order.filled_quantity,
            timestamp=order.timestamp,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_order_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get order status: {str(e)}")

