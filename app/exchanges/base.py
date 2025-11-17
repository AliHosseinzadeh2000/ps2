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

    def get_maker_fee(self) -> float:
        """Get maker fee rate."""
        return self.config.maker_fee

    def get_taker_fee(self) -> float:
        """Get taker fee rate."""
        return self.config.taker_fee

