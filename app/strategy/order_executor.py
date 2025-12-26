"""Order execution module with AI-powered maker/taker logic."""

import asyncio
import time
from typing import Optional, Union

from app.ai.features import extract_orderbook_features
from app.core.exchange_types import ExchangeName
from app.ai.predictor import TradingPredictor
from app.core.config import TradingConfig
from app.core.logging import get_logger
from app.data.collector import DataCollector
from app.db.db import get_session_factory
from app.db.repository import add_trade, upsert_order
from app.exchanges.base import Balance, ExchangeInterface, Order, OrderBook
from app.monitoring.metrics import PerformanceMonitor
from app.strategy.arbitrage_engine import ArbitrageOpportunity
from app.strategy.circuit_breakers import (
    MarketVolatilityCircuitBreaker,
    ExchangeConnectivityCircuitBreaker,
    ErrorRateCircuitBreaker,
)
from app.utils.math import adjust_price_for_arbitrage

logger = get_logger(__name__)


class OrderExecutor:
    """Handles order execution with AI-powered retry logic and maker/taker support."""

    def __init__(
        self,
        exchanges: dict[Union[ExchangeName, str], ExchangeInterface],
        config: Optional[TradingConfig] = None,
        predictor: Optional[TradingPredictor] = None,
        data_collector: Optional[DataCollector] = None,
    ) -> None:
        """
        Initialize order executor.

        Args:
            exchanges: Dictionary mapping exchange names to ExchangeInterface instances
            config: Trading configuration
            predictor: Optional AI predictor for automatic maker/taker decisions
            data_collector: Optional data collector for logging trades
        """
        self.exchanges = exchanges
        self.config = config or TradingConfig()
        self.predictor = predictor
        self.data_collector = data_collector
        self.active_orders: dict[str, Order] = {}
        # Risk management tracking
        self.daily_profit_loss: float = 0.0
        self.exchange_positions: dict[str, float] = {}  # Exchange -> total position size
        self._initial_balance: float = 0.0  # For drawdown calculation
        self._peak_balance: float = 0.0  # Track peak for drawdown
        self._slippage_history: list[float] = []  # Track slippage for monitoring
        # Circuit breakers
        self.volatility_breaker = MarketVolatilityCircuitBreaker(
            max_volatility_percent=5.0,
            window_seconds=60,
        )
        self.connectivity_breaker = ExchangeConnectivityCircuitBreaker(
            max_failures=5,
            window_seconds=60,
        )
        self.error_rate_breaker = ErrorRateCircuitBreaker(
            max_error_rate=0.5,
            window_seconds=60,
        )
        # Performance monitoring
        self.monitor = PerformanceMonitor()
        # Database session factory for persistence
        self._session_factory = get_session_factory()

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        use_maker: Optional[bool] = None,
        buy_orderbook: Optional[OrderBook] = None,
        sell_orderbook: Optional[OrderBook] = None,
    ) -> tuple[Optional[Order], Optional[Order]]:
        """
        Execute an arbitrage opportunity with AI-powered decision making.

        Args:
            opportunity: Arbitrage opportunity to execute
            use_maker: Whether to attempt maker orders (None = use AI, False = taker, True = maker)
            buy_orderbook: Optional orderbook for buy exchange (for AI prediction)
            sell_orderbook: Optional orderbook for sell exchange (for AI prediction)

        Returns:
            Tuple of (buy_order, sell_order) or (None, None) if failed
        """
        # Resolve exchanges for both enum and string keys (tests use plain strings)
        buy_exchange_key_raw = opportunity.buy_exchange
        sell_exchange_key_raw = opportunity.sell_exchange

        buy_exchange = self.exchanges.get(buy_exchange_key_raw)
        sell_exchange = self.exchanges.get(sell_exchange_key_raw)

        buy_exchange_enum = buy_exchange_key_raw if isinstance(buy_exchange_key_raw, ExchangeName) else None
        sell_exchange_enum = sell_exchange_key_raw if isinstance(sell_exchange_key_raw, ExchangeName) else None

        if not buy_exchange:
            try:
                buy_exchange_enum = ExchangeName.from_string(str(buy_exchange_key_raw))
                buy_exchange = self.exchanges.get(buy_exchange_enum)
            except ValueError:
                buy_exchange_enum = None

        if not sell_exchange:
            try:
                sell_exchange_enum = ExchangeName.from_string(str(sell_exchange_key_raw))
                sell_exchange = self.exchanges.get(sell_exchange_enum)
            except ValueError:
                sell_exchange_enum = None

        if not buy_exchange or not sell_exchange:
            logger.error(
                f"Exchanges not found: {opportunity.buy_exchange}, "
                f"{opportunity.sell_exchange}"
            )
            return None, None

        # Risk management checks
        if not await self._check_risk_limits(opportunity, buy_exchange, sell_exchange):
            logger.warning(
                f"Risk limits exceeded for opportunity {opportunity.symbol}, skipping execution"
            )
            return None, None

        # Determine maker/taker using AI if predictor available and use_maker not explicitly set
        buy_use_maker = use_maker if use_maker is not None else False
        sell_use_maker = use_maker if use_maker is not None else False
        buy_price = opportunity.buy_price
        sell_price = opportunity.sell_price

        if use_maker is None and self.predictor and self.predictor.is_ready():
            try:
                # Convert symbols to exchange-specific format for orderbook fetching
                buy_exchange_enum_temp = buy_exchange_key if isinstance(buy_exchange_key, ExchangeName) else ExchangeName.from_string(str(buy_exchange_key))
                sell_exchange_enum_temp = sell_exchange_key if isinstance(sell_exchange_key, ExchangeName) else ExchangeName.from_string(str(sell_exchange_key))
                
                from app.utils.symbol_converter import ExchangeSymbolMapper
                buy_symbol_for_orderbook = ExchangeSymbolMapper.get_symbol_for_exchange(opportunity.symbol, buy_exchange_enum_temp) or opportunity.symbol
                sell_symbol_for_orderbook = ExchangeSymbolMapper.get_symbol_for_exchange(opportunity.symbol, sell_exchange_enum_temp) or opportunity.symbol
                
                # Fetch orderbooks if not provided
                if buy_orderbook is None:
                    buy_orderbook = await buy_exchange.fetch_orderbook(buy_symbol_for_orderbook)
                if sell_orderbook is None:
                    sell_orderbook = await sell_exchange.fetch_orderbook(sell_symbol_for_orderbook)

                # Get AI predictions
                buy_is_maker, buy_prob, buy_pred_price = self.predictor.predict_from_orderbook(
                    buy_orderbook
                )
                sell_is_maker, sell_prob, sell_pred_price = self.predictor.predict_from_orderbook(
                    sell_orderbook
                )

                buy_use_maker = buy_is_maker
                sell_use_maker = sell_is_maker

                # Use predicted prices if regressor is available, adjusting to maintain profitability
                if self.predictor.has_price_prediction():
                    if buy_pred_price > 0:
                        buy_price = adjust_price_for_arbitrage(
                            buy_pred_price,
                            opportunity.buy_price,
                            opportunity.sell_price,
                            is_buy=True,
                        )
                    if sell_pred_price > 0:
                        sell_price = adjust_price_for_arbitrage(
                            sell_pred_price,
                            opportunity.buy_price,
                            opportunity.sell_price,
                            is_buy=False,
                        )

                logger.info(
                    f"AI prediction: buy_maker={buy_is_maker} (prob={buy_prob:.3f}), "
                    f"sell_maker={sell_is_maker} (prob={sell_prob:.3f})"
                )

                # Record predictions for monitoring
                self.monitor.record_prediction(buy_is_maker, buy_prob)
                self.monitor.record_prediction(sell_is_maker, sell_prob)
            except Exception as e:
                logger.warning(f"AI prediction failed, using taker: {e}")
                buy_use_maker = False
                sell_use_maker = False

        # Convert symbol to exchange-specific format
        from app.utils.symbol_converter import ExchangeSymbolMapper
        if buy_exchange_enum:
            buy_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(opportunity.symbol, buy_exchange_enum) or opportunity.symbol
        else:
            buy_symbol = opportunity.symbol

        if sell_exchange_enum:
            sell_symbol = ExchangeSymbolMapper.get_symbol_for_exchange(opportunity.symbol, sell_exchange_enum) or opportunity.symbol
        else:
            sell_symbol = opportunity.symbol
        
        if not buy_symbol:
            logger.error(f"Could not convert symbol {opportunity.symbol} for buy exchange {buy_exchange_enum.value}")
            return None, None
        if not sell_symbol:
            logger.error(f"Could not convert symbol {opportunity.symbol} for sell exchange {sell_exchange_enum.value}")
            return None, None
        
        logger.info(
            f"Executing arbitrage: {opportunity.symbol} "
            f"buy@{opportunity.buy_exchange} ({buy_symbol}) sell@{opportunity.sell_exchange} ({sell_symbol}) "
            f"qty={opportunity.max_quantity:.8f} profit={opportunity.net_profit:.2f} "
            f"buy_maker={buy_use_maker} sell_maker={sell_use_maker}"
        )

        # Execute buy and sell orders concurrently
        buy_task = self._place_order_with_retry(
            buy_exchange,
            buy_symbol,  # Use exchange-specific symbol
            "buy",
            opportunity.max_quantity,
            buy_price,
            buy_use_maker,
        )

        sell_task = self._place_order_with_retry(
            sell_exchange,
            sell_symbol,  # Use exchange-specific symbol
            "sell",
            opportunity.max_quantity,
            sell_price,
            sell_use_maker,
        )

        execution_start = time.time()
        buy_order, sell_order = await asyncio.gather(
            buy_task,
            sell_task,
            return_exceptions=True,
        )
        execution_time = time.time() - execution_start

        # Handle exceptions
        if isinstance(buy_order, Exception):
            logger.error(f"Buy order failed: {buy_order}")
            buy_order = None
        if isinstance(sell_order, Exception):
            logger.error(f"Sell order failed: {sell_order}")
            sell_order = None

        # If one order failed to place, cancel the other
        if buy_order and not sell_order:
            await self._cancel_order_safe(buy_exchange, buy_order.order_id, buy_symbol)
            logger.warning("Buy order placed but sell order failed - cancelled buy order")
        elif sell_order and not buy_order:
            await self._cancel_order_safe(sell_exchange, sell_order.order_id, sell_symbol)
            logger.warning("Sell order placed but buy order failed - cancelled sell order")

        # Verify order execution: poll status until filled or timeout
        # Only verify if exchange supports get_order
        if buy_order and hasattr(buy_exchange, 'get_order'):
            try:
                buy_order = await self._verify_order_execution(
                    buy_exchange, buy_order, buy_symbol, "buy"
                )
            except Exception as e:
                logger.warning(f"Failed to verify buy order: {e}")
        if sell_order and hasattr(sell_exchange, 'get_order'):
            try:
                sell_order = await self._verify_order_execution(
                    sell_exchange, sell_order, sell_symbol, "sell"
                )
            except Exception as e:
                logger.warning(f"Failed to verify sell order: {e}")

        # If one order didn't fill, cancel the other
        if buy_order and buy_order.status == "filled" and sell_order and sell_order.status != "filled":
            await self._cancel_order_safe(sell_exchange, sell_order.order_id, sell_symbol)
            logger.warning("Buy order filled but sell order didn't - cancelled sell order")
        elif sell_order and sell_order.status == "filled" and buy_order and buy_order.status != "filled":
            await self._cancel_order_safe(buy_exchange, buy_order.order_id, buy_symbol)
            logger.warning("Sell order filled but buy order didn't - cancelled buy order")

        # Log trade data for retraining
        if self.data_collector:
            try:
                # Extract features if orderbooks available
                buy_features = None
                sell_features = None
                if buy_orderbook:
                    buy_features = extract_orderbook_features(buy_orderbook)
                if sell_orderbook:
                    sell_features = extract_orderbook_features(sell_orderbook)

                # Calculate fee rates for profit calculation
                buy_fee_rate = buy_exchange.get_maker_fee() if buy_use_maker else buy_exchange.get_taker_fee()
                sell_fee_rate = sell_exchange.get_maker_fee() if sell_use_maker else sell_exchange.get_taker_fee()
                
                # Calculate actual profit (will be updated after verification)
                actual_profit = self._calculate_actual_profit(
                    buy_order, sell_order, buy_fee_rate, sell_fee_rate
                )

                # Log buy order
                if buy_order:
                    # Use actual filled quantity and appropriate fee
                    buy_filled_qty = buy_order.filled_quantity if buy_order.filled_quantity > 0 else opportunity.max_quantity
                    buy_fee_rate = buy_exchange.get_maker_fee() if buy_use_maker else buy_exchange.get_taker_fee()
                    buy_fees = buy_filled_qty * buy_price * buy_fee_rate
                    await self.data_collector.save_trade_data(
                        exchange_name=opportunity.buy_exchange,
                        symbol=opportunity.symbol,
                        order_id=buy_order.order_id,
                        side="buy",
                        quantity=buy_filled_qty,
                        price=buy_price,
                        fees=buy_fees,
                        profit_loss=actual_profit / 2 if buy_order.status == "filled" and sell_order and sell_order.status == "filled" else None,
                        execution_time=execution_time,
                        features=buy_features,
                        used_maker=buy_use_maker,
                        success=buy_order.status == "filled" and sell_order and sell_order.status == "filled",
                    )

                # Log sell order
                if sell_order:
                    # Use actual filled quantity and appropriate fee
                    sell_filled_qty = sell_order.filled_quantity if sell_order.filled_quantity > 0 else opportunity.max_quantity
                    sell_fee_rate = sell_exchange.get_maker_fee() if sell_use_maker else sell_exchange.get_taker_fee()
                    sell_fees = sell_filled_qty * sell_price * sell_fee_rate
                    await self.data_collector.save_trade_data(
                        exchange_name=opportunity.sell_exchange,
                        symbol=opportunity.symbol,
                        order_id=sell_order.order_id,
                        side="sell",
                        quantity=sell_filled_qty,
                        price=sell_price,
                        fees=sell_fees,
                        profit_loss=actual_profit / 2 if sell_order.status == "filled" and buy_order and buy_order.status == "filled" else None,
                        execution_time=execution_time,
                        features=sell_features,
                        used_maker=sell_use_maker,
                        success=sell_order.status == "filled" and buy_order and buy_order.status == "filled",
                    )
            except Exception as e:
                logger.warning(f"Failed to log trade data: {e}")

        # Calculate actual profit based on fill prices and quantities
        # Use appropriate fees based on maker/taker
        buy_fee_rate = buy_exchange.get_maker_fee() if buy_use_maker else buy_exchange.get_taker_fee()
        sell_fee_rate = sell_exchange.get_maker_fee() if sell_use_maker else sell_exchange.get_taker_fee()
        
        actual_profit = self._calculate_actual_profit(
            buy_order, sell_order, buy_fee_rate, sell_fee_rate
        )

        # Update risk tracking with actual profit
        self._update_risk_tracking(opportunity, buy_order, sell_order, actual_profit)

        # Record trade for monitoring
        both_filled = (
            buy_order is not None
            and sell_order is not None
            and buy_order.status == "filled"
            and sell_order.status == "filled"
        )
        profit = actual_profit if both_filled else (
            -opportunity.buy_price * opportunity.max_quantity * 0.01 if buy_order or sell_order else 0.0
        )
        used_maker = buy_use_maker or sell_use_maker
        self.monitor.record_trade(both_filled, profit, used_maker, execution_time)

        if buy_order:
            self.active_orders[buy_order.order_id] = buy_order
        if sell_order:
            self.active_orders[sell_order.order_id] = sell_order

        return buy_order, sell_order

    async def _place_order_with_retry(
        self,
        exchange: ExchangeInterface,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        is_maker: bool,
    ) -> Order:
        """
        Place order with retry logic.

        Args:
            exchange: Exchange interface
            symbol: Trading pair symbol
            side: 'buy' or 'sell'
            quantity: Order quantity
            price: Order price
            is_maker: Whether to attempt maker order

        Returns:
            Order object

        Raises:
            Exception: If all retries fail
        """
        order_type = "limit" if price else "market"
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                # Check slippage protection for limit orders
                if price and order_type == "limit":
                    try:
                        current_orderbook = await exchange.fetch_orderbook(symbol, depth=1)
                        if side == "buy" and current_orderbook.asks:
                            current_price = current_orderbook.asks[0].price
                            slippage = abs(current_price - price) / price * 100.0
                            if slippage > self.config.max_slippage_percent:
                                raise Exception(
                                    f"Slippage too high: {slippage:.2f}% > {self.config.max_slippage_percent:.2f}%"
                                )
                        elif side == "sell" and current_orderbook.bids:
                            current_price = current_orderbook.bids[0].price
                            slippage = abs(current_price - price) / price * 100.0
                            if slippage > self.config.max_slippage_percent:
                                raise Exception(
                                    f"Slippage too high: {slippage:.2f}% > {self.config.max_slippage_percent:.2f}%"
                                )
                    except Exception as e:
                        if "Slippage" in str(e):
                            raise
                        # If orderbook fetch fails, continue (don't block on slippage check)

                order = await exchange.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=price,
                    is_maker=is_maker,
                )
                logger.info(
                    f"Order placed: {order.order_id} on {exchange.name} "
                    f"{side} {quantity:.8f} @ {price if price else 'market'}"
                )

                # Persist order (best-effort)
                await self._persist_order(
                    order,
                    getattr(exchange, "name", str(exchange)),
                    status_override=order.status,
                )
                
                # Record success for circuit breakers
                exchange_name = getattr(exchange, 'name', str(exchange))
                self.connectivity_breaker.record_success(exchange_name)
                self.error_rate_breaker.record_request(exchange_name, True)
                
                return order
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Order placement attempt {attempt + 1} failed: {e}"
                )
                
                # Record failure for circuit breakers
                exchange_name = getattr(exchange, 'name', str(exchange))
                self.connectivity_breaker.record_failure(exchange_name)
                self.error_rate_breaker.record_request(exchange_name, False)
                
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay_seconds)

        raise Exception(
            f"Failed to place order after {self.config.max_retries + 1} attempts"
        ) from last_exception

    async def _cancel_order_safe(
        self,
        exchange: ExchangeInterface,
        order_id: str,
        symbol: str,
    ) -> bool:
        """
        Safely cancel an order, handling errors.

        Args:
            exchange: Exchange interface
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            True if cancellation successful or order not found
        """
        try:
            success = await exchange.cancel_order(order_id, symbol)
            if success:
                logger.info(f"Order cancelled: {order_id} on {exchange.name}")
                cached = self.active_orders.pop(order_id, None)
                order_for_persist = cached or Order(
                    order_id=order_id,
                    symbol=symbol,
                    side="cancel",
                    order_type="",
                    quantity=0.0,
                    price=None,
                    status="cancelled",
                    timestamp=time.time(),
                )
                # Persist cancellation
                await self._persist_order(
                    order_for_persist,
                    getattr(exchange, "name", str(exchange)),
                    status_override="cancelled",
                )
            return success
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    async def cancel_all_orders(self) -> None:
        """Cancel all active orders."""
        tasks = []
        for order_id, order in list(self.active_orders.items()):
            exchange = self.exchanges.get(order.symbol.split("_")[0])
            if exchange:
                tasks.append(
                    self._cancel_order_safe(exchange, order_id, order.symbol)
                )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_active_orders(self) -> dict[str, Order]:
        """
        Get all active orders.

        Returns:
            Dictionary of active orders
        """
        return self.active_orders.copy()

    async def _persist_order(
        self,
        order: Order,
        exchange_name: str,
        *,
        status_override: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Persist order state to database (best-effort)."""
        try:
            async with self._session_factory() as session:
                await upsert_order(
                    session,
                    order_id=order.order_id,
                    exchange=exchange_name,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    status=status_override or order.status,
                    quantity=order.quantity,
                    filled_quantity=order.filled_quantity,
                    price=order.price,
                    fee=getattr(order, "fee", None),
                    fee_currency=None,
                    average_price=getattr(order, "price", None),
                    cost=None,
                    exchange_order_id=order.order_id,
                    error=error,
                )
        except Exception:
            logger.exception("Failed to persist order %s on %s", order.order_id, exchange_name)

    async def _persist_trade(
        self,
        order: Order,
        exchange_name: str,
        *,
        realized_pnl: Optional[float] = None,
    ) -> None:
        """Persist trade/fill record when an order is filled."""
        try:
            if order.filled_quantity and order.filled_quantity > 0:
                async with self._session_factory() as session:
                    await add_trade(
                        session,
                        order_id=order.order_id,
                        exchange=exchange_name,
                        symbol=order.symbol,
                        side=order.side,
                        price=order.price,
                        quantity=order.filled_quantity,
                        fee=getattr(order, "fee", None),
                        fee_currency=None,
                        realized_pnl=realized_pnl,
                        trade_id=getattr(order, "order_id", None),
                    )
        except Exception:
            logger.exception("Failed to persist trade for order %s on %s", order.order_id, exchange_name)

    async def _verify_order_execution(
        self,
        exchange: ExchangeInterface,
        order: Order,
        symbol: str,
        side: str,
        max_wait_seconds: Optional[float] = None,
        poll_interval: float = 1.0,
    ) -> Order:
        """
        Verify order execution by polling status until filled or timeout.

        Args:
            exchange: Exchange interface
            order: Order object to verify
            symbol: Trading pair symbol
            side: 'buy' or 'sell' (for logging)
            max_wait_seconds: Maximum time to wait (None = use config timeout)
            poll_interval: Time between status checks

        Returns:
            Updated Order object with current status
        """
        if max_wait_seconds is None:
            max_wait_seconds = self.config.order_timeout_seconds

        start_time = time.time()
        last_status = order.status

        logger.info(f"Verifying {side} order {order.order_id} on {exchange.name}")

        while time.time() - start_time < max_wait_seconds:
            try:
                # Fetch current order status
                updated_order = await exchange.get_order(order.order_id, symbol)

                # Update active orders
                self.active_orders[order.order_id] = updated_order

                # Persist status change
                await self._persist_order(
                    updated_order,
                    getattr(exchange, "name", str(exchange)),
                    status_override=updated_order.status,
                )

                # Check if order is filled or cancelled
                if updated_order.status == "filled":
                    await self._persist_trade(
                        updated_order,
                        getattr(exchange, "name", str(exchange)),
                    )
                    logger.info(
                        f"{side.capitalize()} order {order.order_id} filled: "
                        f"{updated_order.filled_quantity:.8f}/{updated_order.quantity:.8f} "
                        f"at avg price {updated_order.price or 'market'}"
                    )
                    return updated_order
                elif updated_order.status == "cancelled":
                    logger.warning(f"{side.capitalize()} order {order.order_id} was cancelled")
                    return updated_order
                elif updated_order.status != last_status:
                    logger.info(
                        f"{side.capitalize()} order {order.order_id} status: {last_status} -> {updated_order.status}"
                    )
                    last_status = updated_order.status

                # Check for partial fills
                if updated_order.filled_quantity > 0 and updated_order.filled_quantity < updated_order.quantity:
                    logger.info(
                        f"{side.capitalize()} order {order.order_id} partially filled: "
                        f"{updated_order.filled_quantity:.8f}/{updated_order.quantity:.8f}"
                    )

                # Wait before next poll
                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.warning(f"Error checking order status: {e}, retrying...")
                await asyncio.sleep(poll_interval)

        # Timeout reached
        logger.warning(
            f"{side.capitalize()} order {order.order_id} verification timeout after {max_wait_seconds}s. "
            f"Current status: {last_status}"
        )
        return order  # Return order with last known status

    def _calculate_actual_profit(
        self,
        buy_order: Optional[Order],
        sell_order: Optional[Order],
        buy_fee_rate: float,
        sell_fee_rate: float,
    ) -> float:
        """
        Calculate actual profit based on order fill prices and quantities.

        Args:
            buy_order: Buy order (may be None or not filled)
            sell_order: Sell order (may be None or not filled)
            buy_fee_rate: Buy exchange fee rate (maker or taker)
            sell_fee_rate: Sell exchange fee rate (maker or taker)

        Returns:
            Actual profit in base currency (negative if loss)
        """
        if not buy_order or not sell_order:
            return 0.0

        if buy_order.status != "filled" or sell_order.status != "filled":
            return 0.0

        # Use filled quantities (handle partial fills)
        buy_filled_qty = buy_order.filled_quantity
        sell_filled_qty = sell_order.filled_quantity
        filled_qty = min(buy_filled_qty, sell_filled_qty)

        if filled_qty <= 0:
            return 0.0

        # Get actual fill prices (use order price for limit orders, or estimate from orderbook)
        # Note: Some exchanges provide average fill price, but we use order price as approximation
        buy_price = buy_order.price or 0.0
        sell_price = sell_order.price or 0.0

        if buy_price <= 0 or sell_price <= 0:
            logger.warning("Cannot calculate profit: missing fill prices")
            return 0.0

        # Calculate costs and revenue with appropriate fees
        buy_cost = buy_price * filled_qty * (1 + buy_fee_rate)
        sell_revenue = sell_price * filled_qty * (1 - sell_fee_rate)

        actual_profit = sell_revenue - buy_cost

        logger.info(
            f"Actual profit calculation: "
            f"buy={buy_price:.2f}*{filled_qty:.8f} (fee={buy_fee_rate:.4f}), "
            f"sell={sell_price:.2f}*{filled_qty:.8f} (fee={sell_fee_rate:.4f}), "
            f"profit={actual_profit:.2f}"
        )

        return actual_profit

    async def _check_risk_limits(
        self,
        opportunity: ArbitrageOpportunity,
        buy_exchange: ExchangeInterface,
        sell_exchange: ExchangeInterface,
    ) -> bool:
        """
        Check if opportunity passes risk management limits.

        Args:
            opportunity: Arbitrage opportunity
            buy_exchange: Buy exchange interface
            sell_exchange: Sell exchange interface

        Returns:
            True if risk checks pass
        """
        # Check if trading is manually halted
        if self.config.trading_halted:
            logger.warning("Trading is manually halted")
            return False

        # Check exchange connectivity circuit breakers
        buy_exchange_name = opportunity.buy_exchange
        sell_exchange_name = opportunity.sell_exchange
        
        if self.connectivity_breaker.is_halted(buy_exchange_name):
            logger.warning(f"Buy exchange {buy_exchange_name} is halted due to connectivity issues")
            return False
        
        if self.connectivity_breaker.is_halted(sell_exchange_name):
            logger.warning(f"Sell exchange {sell_exchange_name} is halted due to connectivity issues")
            return False

        # Check error rate circuit breakers
        if self.error_rate_breaker.is_halted(buy_exchange_name):
            logger.warning(f"Buy exchange {buy_exchange_name} is halted due to high error rate")
            return False
        
        if self.error_rate_breaker.is_halted(sell_exchange_name):
            logger.warning(f"Sell exchange {sell_exchange_name} is halted due to high error rate")
            return False

        # Check market volatility circuit breaker
        if not self.volatility_breaker.check_volatility(opportunity.symbol, opportunity.buy_price):
            logger.warning(f"Trading halted for {opportunity.symbol} due to high volatility")
            return False

        # Check daily loss limit
        if self.daily_profit_loss < -self.config.daily_loss_limit:
            logger.warning(
                f"Daily loss limit exceeded: {self.daily_profit_loss:.2f} < "
                f"-{self.config.daily_loss_limit:.2f}"
            )
            return False

        # Check per-trade loss limit (estimate worst case)
        estimated_max_loss = opportunity.buy_price * opportunity.max_quantity * 0.01  # 1% worst case
        if estimated_max_loss > self.config.per_trade_loss_limit:
            logger.warning(
                f"Per-trade loss limit exceeded: {estimated_max_loss:.2f} > "
                f"{self.config.per_trade_loss_limit:.2f}"
            )
            return False

        # Check position size per exchange
        buy_position = self.exchange_positions.get(opportunity.buy_exchange, 0.0)
        sell_position = self.exchange_positions.get(opportunity.sell_exchange, 0.0)
        position_value = opportunity.buy_price * opportunity.max_quantity

        if buy_position + position_value > self.config.max_position_per_exchange:
            logger.warning(
                f"Max position limit exceeded on {opportunity.buy_exchange}: "
                f"{buy_position + position_value:.2f} > {self.config.max_position_per_exchange:.2f}"
            )
            return False

        if sell_position + position_value > self.config.max_position_per_exchange:
            logger.warning(
                f"Max position limit exceeded on {opportunity.sell_exchange}: "
                f"{sell_position + position_value:.2f} > {self.config.max_position_per_exchange:.2f}"
            )
            return False

        # Check total portfolio position limit
        total_position = sum(self.exchange_positions.values()) + position_value
        if total_position > self.config.max_total_position:
            logger.warning(
                f"Total portfolio position limit exceeded: {total_position:.2f} > "
                f"{self.config.max_total_position:.2f}"
            )
            return False

        # Check drawdown protection
        if hasattr(self, '_initial_balance') and self._initial_balance > 0:
            current_balance = self._initial_balance + self.daily_profit_loss
            drawdown_percent = ((self._initial_balance - current_balance) / self._initial_balance) * 100
            if drawdown_percent > self.config.max_drawdown_percent:
                logger.warning(
                    f"Max drawdown exceeded: {drawdown_percent:.2f}% > "
                    f"{self.config.max_drawdown_percent:.2f}%"
                )
                return False

        # Pre-trade balance verification
        if self.config.require_balance_check:
            try:
                buy_balance = await buy_exchange.get_balance()
                sell_balance = await sell_exchange.get_balance()
                
                # Ensure we got dictionaries, not strings or other types
                if not isinstance(buy_balance, dict):
                    logger.warning(f"Balance check: buy_balance is not a dict (type: {type(buy_balance)}), skipping balance check")
                    return True
                if not isinstance(sell_balance, dict):
                    logger.warning(f"Balance check: sell_balance is not a dict (type: {type(sell_balance)}), skipping balance check")
                    return True
                
                # Extract quote currency from symbol (e.g., BTCUSDT -> USDT for buy)
                from app.utils.symbol_converter import SymbolConverter
                quote_currency = SymbolConverter.get_quote_currency(opportunity.symbol)
                if not quote_currency:
                    quote_currency = "USDT"  # Default assumption
                
                quote_needed = position_value

                # Check if we have enough balance
                buy_available = buy_balance.get(quote_currency, None)
                if buy_available and isinstance(buy_available, Balance) and buy_available.available < quote_needed:
                    logger.warning(
                        f"Insufficient balance on {opportunity.buy_exchange}: "
                        f"{buy_available.available:.2f} < {quote_needed:.2f}"
                    )
                    return False
            except Exception as e:
                logger.warning(f"Balance check failed: {e}, allowing trade")
                # Don't block trade if balance check fails

        return True

    def _update_risk_tracking(
        self,
        opportunity: ArbitrageOpportunity,
        buy_order: Optional[Order],
        sell_order: Optional[Order],
        actual_profit: float = 0.0,
    ) -> None:
        """
        Update risk tracking after order execution.

        Args:
            opportunity: Arbitrage opportunity
            buy_order: Buy order result
            sell_order: Sell order result
            actual_profit: Actual profit/loss from the trade (based on fill prices)
        """
        # Calculate position value based on actual filled quantities
        if buy_order and buy_order.status == "filled":
            buy_filled_qty = buy_order.filled_quantity
            buy_price = buy_order.price or opportunity.buy_price
            position_value = buy_price * buy_filled_qty
        elif sell_order and sell_order.status == "filled":
            sell_filled_qty = sell_order.filled_quantity
            sell_price = sell_order.price or opportunity.sell_price
            position_value = sell_price * sell_filled_qty
        else:
            position_value = opportunity.buy_price * opportunity.max_quantity

        # Update positions (only for filled orders)
        if buy_order and buy_order.status == "filled":
            self.exchange_positions[opportunity.buy_exchange] = (
                self.exchange_positions.get(opportunity.buy_exchange, 0.0) + position_value
            )
        if sell_order and sell_order.status == "filled":
            self.exchange_positions[opportunity.sell_exchange] = (
                self.exchange_positions.get(opportunity.sell_exchange, 0.0) + position_value
            )

        # Update daily P&L with actual profit
        self.daily_profit_loss += actual_profit
        
        # Update peak balance for drawdown calculation
        current_balance = self._initial_balance + self.daily_profit_loss
        if current_balance > self._peak_balance:
            self._peak_balance = current_balance

        # If only one order filled, estimate loss
        if (buy_order and buy_order.status == "filled" and 
            (not sell_order or sell_order.status != "filled")):
            self.daily_profit_loss -= position_value * 0.01  # Assume 1% loss
        elif (sell_order and sell_order.status == "filled" and 
              (not buy_order or buy_order.status != "filled")):
            self.daily_profit_loss -= position_value * 0.01  # Assume 1% loss

    def initialize_balance_tracking(self, initial_balance: float) -> None:
        """
        Initialize balance tracking for drawdown calculation.
        
        Args:
            initial_balance: Initial balance in USDT
        """
        self._initial_balance = initial_balance
        self._peak_balance = initial_balance
        logger.info(f"Initialized balance tracking: {initial_balance:.2f} USDT")

    def reset_daily_tracking(self) -> None:
        """Reset daily profit/loss and position tracking."""
        self.daily_profit_loss = 0.0
        self.exchange_positions.clear()
        self._slippage_history.clear()
        if hasattr(self, '_initial_balance'):
            self._peak_balance = self._initial_balance + self.daily_profit_loss
        logger.info("Reset daily risk tracking")

    def get_risk_metrics(self) -> dict:
        """
        Get current risk management metrics.
        
        Returns:
            Dictionary with risk metrics
        """
        total_position = sum(self.exchange_positions.values())
        drawdown_percent = 0.0
        if hasattr(self, '_initial_balance') and self._initial_balance > 0:
            current_balance = self._initial_balance + self.daily_profit_loss
            drawdown_percent = ((self._peak_balance - current_balance) / self._peak_balance) * 100 if self._peak_balance > 0 else 0.0
        
        avg_slippage = 0.0
        max_slippage = 0.0
        if self._slippage_history:
            avg_slippage = sum(self._slippage_history) / len(self._slippage_history)
            max_slippage = max(self._slippage_history)
        
        # Get circuit breaker states
        halted_exchanges = []
        for exchange_name in self.exchanges.keys():
            exchange_str = exchange_name.value if isinstance(exchange_name, ExchangeName) else str(exchange_name)
            if self.connectivity_breaker.is_halted(exchange_str):
                halted_exchanges.append(f"{exchange_str}(connectivity)")
            if self.error_rate_breaker.is_halted(exchange_str):
                halted_exchanges.append(f"{exchange_str}(error_rate)")
        
        return {
            "daily_profit_loss": self.daily_profit_loss,
            "total_position": total_position,
            "exchange_positions": dict(self.exchange_positions),
            "drawdown_percent": drawdown_percent,
            "avg_slippage_percent": avg_slippage,
            "max_slippage_percent": max_slippage,
            "trading_halted": self.config.trading_halted,
            "volatility_halted": self.volatility_breaker.is_halted(),
            "halted_exchanges": halted_exchanges,
        }

