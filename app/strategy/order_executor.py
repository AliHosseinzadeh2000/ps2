"""Order execution module with maker/taker logic."""

import asyncio
from typing import Optional

from app.core.config import TradingConfig
from app.core.logging import get_logger
from app.exchanges.base import ExchangeInterface, Order
from app.strategy.arbitrage_engine import ArbitrageOpportunity

logger = get_logger(__name__)


class OrderExecutor:
    """Handles order execution with retry logic and maker/taker support."""

    def __init__(
        self,
        exchanges: dict[str, ExchangeInterface],
        config: Optional[TradingConfig] = None,
    ) -> None:
        """
        Initialize order executor.

        Args:
            exchanges: Dictionary mapping exchange names to ExchangeInterface instances
            config: Trading configuration
        """
        self.exchanges = exchanges
        self.config = config or TradingConfig()
        self.active_orders: dict[str, Order] = {}

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        use_maker: bool = False,
    ) -> tuple[Optional[Order], Optional[Order]]:
        """
        Execute an arbitrage opportunity.

        Args:
            opportunity: Arbitrage opportunity to execute
            use_maker: Whether to attempt maker orders (post-only)

        Returns:
            Tuple of (buy_order, sell_order) or (None, None) if failed
        """
        buy_exchange = self.exchanges.get(opportunity.buy_exchange)
        sell_exchange = self.exchanges.get(opportunity.sell_exchange)

        if not buy_exchange or not sell_exchange:
            logger.error(
                f"Exchanges not found: {opportunity.buy_exchange}, "
                f"{opportunity.sell_exchange}"
            )
            return None, None

        logger.info(
            f"Executing arbitrage: {opportunity.symbol} "
            f"buy@{opportunity.buy_exchange} sell@{opportunity.sell_exchange} "
            f"qty={opportunity.max_quantity:.8f} profit={opportunity.net_profit:.2f}"
        )

        # Execute buy and sell orders concurrently
        buy_task = self._place_order_with_retry(
            buy_exchange,
            opportunity.symbol,
            "buy",
            opportunity.max_quantity,
            opportunity.buy_price,
            use_maker,
        )

        sell_task = self._place_order_with_retry(
            sell_exchange,
            opportunity.symbol,
            "sell",
            opportunity.max_quantity,
            opportunity.sell_price,
            use_maker,
        )

        buy_order, sell_order = await asyncio.gather(
            buy_task,
            sell_task,
            return_exceptions=True,
        )

        # Handle exceptions
        if isinstance(buy_order, Exception):
            logger.error(f"Buy order failed: {buy_order}")
            buy_order = None
        if isinstance(sell_order, Exception):
            logger.error(f"Sell order failed: {sell_order}")
            sell_order = None

        # If one order failed, cancel the other
        if buy_order and not sell_order:
            await self._cancel_order_safe(buy_exchange, buy_order.order_id, opportunity.symbol)
        elif sell_order and not buy_order:
            await self._cancel_order_safe(sell_exchange, sell_order.order_id, opportunity.symbol)

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
                return order
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Order placement attempt {attempt + 1} failed: {e}"
                )
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
                self.active_orders.pop(order_id, None)
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

