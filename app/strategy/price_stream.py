"""Async orderbook polling and price streaming."""

import asyncio
from collections import defaultdict
from typing import Callable, Optional

from app.core.config import TradingConfig
from app.core.logging import get_logger
from app.exchanges.base import ExchangeInterface, OrderBook

logger = get_logger(__name__)


class PriceStream:
    """Async orderbook polling and event-driven price updates."""

    def __init__(
        self,
        exchanges: dict[str, ExchangeInterface],
        config: Optional[TradingConfig] = None,
    ) -> None:
        """
        Initialize price stream.

        Args:
            exchanges: Dictionary mapping exchange names to ExchangeInterface instances
            config: Trading configuration
        """
        self.exchanges = exchanges
        self.config = config or TradingConfig()
        self.orderbooks: dict[str, dict[str, OrderBook]] = defaultdict(dict)
        self.subscribers: list[Callable[[str, dict[str, OrderBook]], None]] = []
        self._running = False
        self._tasks: list[asyncio.Task] = []

    def subscribe(
        self,
        callback: Callable[[str, dict[str, OrderBook]], None],
    ) -> None:
        """
        Subscribe to orderbook updates.

        Args:
            callback: Function called with (symbol, orderbooks_dict) on updates
        """
        self.subscribers.append(callback)

    async def start(self, symbols: list[str]) -> None:
        """
        Start polling orderbooks for given symbols.

        Args:
            symbols: List of trading pair symbols to monitor
        """
        if self._running:
            logger.warning("Price stream already running")
            return

        self._running = True
        logger.info(f"Starting price stream for symbols: {symbols}")

        # Create polling tasks for each exchange-symbol pair
        for exchange_name, exchange in self.exchanges.items():
            for symbol in symbols:
                task = asyncio.create_task(
                    self._poll_orderbook(exchange_name, exchange, symbol)
                )
                self._tasks.append(task)

    async def stop(self) -> None:
        """Stop all polling tasks."""
        if not self._running:
            return

        logger.info("Stopping price stream")
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete cancellation
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _poll_orderbook(
        self,
        exchange_name: str,
        exchange: ExchangeInterface,
        symbol: str,
    ) -> None:
        """
        Continuously poll orderbook for an exchange-symbol pair.

        Args:
            exchange_name: Name of the exchange
            exchange: Exchange interface instance
            symbol: Trading pair symbol
        """
        while self._running:
            try:
                orderbook = await exchange.fetch_orderbook(symbol, depth=20)
                self.orderbooks[symbol][exchange_name] = orderbook

                # Notify subscribers
                for callback in self.subscribers:
                    try:
                        callback(symbol, self.orderbooks[symbol])
                    except Exception as e:
                        logger.error(f"Error in subscriber callback: {e}")

            except Exception as e:
                logger.error(
                    f"Error fetching orderbook from {exchange_name} "
                    f"for {symbol}: {str(e)}",
                    exc_info=True
                )

            # Wait before next poll
            await asyncio.sleep(self.config.polling_interval_seconds)

    def get_orderbooks(
        self, symbol: str
    ) -> Optional[dict[str, OrderBook]]:
        """
        Get current orderbooks for a symbol across all exchanges.

        Args:
            symbol: Trading pair symbol

        Returns:
            Dictionary mapping exchange names to OrderBook, or None if not available
        """
        return self.orderbooks.get(symbol)

    def get_latest_orderbook(
        self, exchange_name: str, symbol: str
    ) -> Optional[OrderBook]:
        """
        Get latest orderbook for a specific exchange and symbol.

        Args:
            exchange_name: Name of the exchange
            symbol: Trading pair symbol

        Returns:
            OrderBook or None if not available
        """
        symbol_orderbooks = self.orderbooks.get(symbol)
        if symbol_orderbooks:
            return symbol_orderbooks.get(exchange_name)
        return None

    def is_running(self) -> bool:
        """
        Check if price stream is running.

        Returns:
            True if running
        """
        return self._running

