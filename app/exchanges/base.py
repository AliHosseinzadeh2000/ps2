"""Abstract base class for exchange interfaces."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel


class OrderBookEntry(BaseModel):
    """Single order book entry."""

    price: float
    quantity: float


class OrderBook(BaseModel):
    """Order book data structure."""

    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]
    timestamp: float
    symbol: str


class Balance(BaseModel):
    """Account balance for a currency."""

    currency: str
    available: float
    locked: float

    @property
    def total(self) -> float:
        """Total balance (available + locked)."""
        return self.available + self.locked


class Order(BaseModel):
    """Order information."""

    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market', 'limit', etc.
    quantity: float
    price: Optional[float] = None
    status: str  # 'pending', 'filled', 'cancelled', etc.
    filled_quantity: float = 0.0
    timestamp: float


class OHLCData(BaseModel):
    """OHLC (Open, High, Low, Close) candlestick data."""

    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: float
    symbol: str


class ExchangeInterface(ABC):
    """Abstract interface for cryptocurrency exchanges."""

    def __init__(self, config) -> None:
        """
        Initialize exchange interface.

        Args:
            config: Exchange configuration object
        """
        self.config = config
        self.name = self.__class__.__name__

    @abstractmethod
    async def fetch_orderbook(
        self, symbol: str, depth: int = 20
    ) -> OrderBook:
        """
        Fetch order book for a trading pair.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            depth: Number of price levels to fetch

        Returns:
            OrderBook object with bids and asks

        Raises:
            Exception: If orderbook fetch fails
        """
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        is_maker: bool = False,
    ) -> Order:
        """
        Place an order on the exchange.

        Args:
            symbol: Trading pair symbol
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            quantity: Order quantity
            price: Limit price (required for limit orders)
            is_maker: Whether to attempt maker order (post-only)

        Returns:
            Order object with order details

        Raises:
            Exception: If order placement fails
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an existing order.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            True if cancellation successful, False otherwise

        Raises:
            Exception: If cancellation fails
        """
        pass

    @abstractmethod
    async def get_balance(self, currency: Optional[str] = None) -> Dict[str, Balance]:
        """
        Get account balance.

        Args:
            currency: Specific currency to fetch (None for all)

        Returns:
            Dictionary mapping currency to Balance object

        Raises:
            Exception: If balance fetch fails
        """
        pass

    async def fetch_ohlc(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
    ) -> List[OHLCData]:
        """
        Fetch OHLC (candlestick) data for a trading pair.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Time interval (e.g., '1m', '5m', '1h', '1d')
            limit: Number of candles to fetch

        Returns:
            List of OHLCData objects, sorted by timestamp (oldest first)

        Raises:
            Exception: If OHLC fetch fails
        """
        # Default implementation - exchanges should override
        raise NotImplementedError(
            f"fetch_ohlc not implemented for {self.__class__.__name__}"
        )

    async def get_open_orders(
        self, symbol: Optional[str] = None
    ) -> List[Order]:
        """
        Get open orders for the account.

        Args:
            symbol: Optional trading pair symbol to filter by (None for all)

        Returns:
            List of open Order objects

        Raises:
            Exception: If fetching open orders fails
        """
        # Default implementation - exchanges should override
        raise NotImplementedError(
            f"get_open_orders not implemented for {self.__class__.__name__}"
        )

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Order:
        """
        Get order details by order ID.

        Args:
            order_id: Order ID to fetch
            symbol: Trading pair symbol

        Returns:
            Order object with current status and fill information

        Raises:
            Exception: If order fetch fails or order not found
        """
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        Check if exchange has valid authentication credentials configured.

        Returns:
            True if authentication is configured, False otherwise
        """
        pass

    def get_maker_fee(self) -> float:
        """Get maker fee rate."""
        return self.config.maker_fee

    def get_taker_fee(self) -> float:
        """Get taker fee rate."""
        return self.config.taker_fee

