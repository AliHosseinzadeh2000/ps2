"""Nobitex exchange implementation."""

import hashlib
import hmac
import time
from typing import Dict, List, Optional

import httpx

from app.core.config import NobitexConfig
from app.exchanges.base import (
    Balance,
    ExchangeInterface,
    Order,
    OrderBook,
    OrderBookEntry,
)


class NobitexExchange(ExchangeInterface):
    """Nobitex exchange client implementation."""

    def __init__(self, config: Optional[NobitexConfig] = None) -> None:
        """
        Initialize Nobitex exchange client.

        Args:
            config: Nobitex configuration (uses default if not provided)
        """
        if config is None:
            config = NobitexConfig()
        super().__init__(config)
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        self.timeout = config.timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _generate_signature(self, data: Dict) -> str:
        """
        Generate HMAC signature for authenticated requests.

        Args:
            data: Request data dictionary

        Returns:
            HMAC signature string
        """
        # TODO: Implement actual signature generation based on Nobitex API docs
        message = str(data)
        return hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _get_headers(self, signed: bool = False) -> Dict[str, str]:
        """
        Get request headers.

        Args:
            signed: Whether to include authentication headers

        Returns:
            Headers dictionary
        """
        headers = {"Content-Type": "application/json"}
        if signed and self.api_key:
            headers["Authorization"] = f"Token {self.api_key}"
            # TODO: Add signature to headers if required by Nobitex API
        return headers

    async def fetch_orderbook(
        self, symbol: str, depth: int = 20
    ) -> OrderBook:
        """
        Fetch order book from Nobitex.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCIRT')
            depth: Number of price levels

        Returns:
            OrderBook object
        """
        client = await self._get_client()
        # TODO: Replace with actual Nobitex orderbook endpoint
        endpoint = f"/v2/orderbook/{symbol}"
        params = {"depth": depth}

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            # Normalize response to OrderBook format
            # TODO: Adjust parsing based on actual Nobitex API response format
            bids = [
                OrderBookEntry(price=float(bid[0]), quantity=float(bid[1]))
                for bid in data.get("bids", [])[:depth]
            ]
            asks = [
                OrderBookEntry(price=float(ask[0]), quantity=float(ask[1]))
                for ask in data.get("asks", [])[:depth]
            ]

            return OrderBook(
                bids=bids,
                asks=asks,
                timestamp=time.time(),
                symbol=symbol,
            )
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch orderbook from Nobitex: {e}") from e

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
        Place an order on Nobitex.

        Args:
            symbol: Trading pair symbol
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            quantity: Order quantity
            price: Limit price (required for limit orders)
            is_maker: Whether to attempt maker order (post-only)

        Returns:
            Order object
        """
        if order_type == "limit" and price is None:
            raise ValueError("Price is required for limit orders")

        client = await self._get_client()
        # TODO: Replace with actual Nobitex order placement endpoint
        endpoint = "/v2/orders/add"

        payload = {
            "symbol": symbol,
            "type": side,
            "execution": "maker" if is_maker else "taker",
            "amount": str(quantity),
        }

        if order_type == "limit":
            payload["price"] = str(price)

        if is_maker:
            payload["postOnly"] = True

        try:
            response = await client.post(
                endpoint,
                json=payload,
                headers=self._get_headers(signed=True),
            )
            response.raise_for_status()
            data = response.json()

            # TODO: Adjust parsing based on actual Nobitex API response format
            return Order(
                order_id=str(data.get("id", "")),
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status="pending",
                timestamp=time.time(),
            )
        except httpx.HTTPError as e:
            raise Exception(f"Failed to place order on Nobitex: {e}") from e

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order on Nobitex.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            True if successful
        """
        client = await self._get_client()
        # TODO: Replace with actual Nobitex cancel endpoint
        endpoint = f"/v2/orders/{order_id}/cancel"

        try:
            response = await client.post(
                endpoint,
                json={"symbol": symbol},
                headers=self._get_headers(signed=True),
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def get_balance(
        self, currency: Optional[str] = None
    ) -> Dict[str, Balance]:
        """
        Get account balance from Nobitex.

        Args:
            currency: Specific currency (None for all)

        Returns:
            Dictionary of balances
        """
        client = await self._get_client()
        # TODO: Replace with actual Nobitex balance endpoint
        endpoint = "/v2/wallets"

        try:
            response = await client.get(
                endpoint,
                headers=self._get_headers(signed=True),
            )
            response.raise_for_status()
            data = response.json()

            # TODO: Adjust parsing based on actual Nobitex API response format
            balances = {}
            wallets = data.get("wallets", [])

            for wallet in wallets:
                curr = wallet.get("currency", "").upper()
                if currency and curr != currency.upper():
                    continue

                balances[curr] = Balance(
                    currency=curr,
                    available=float(wallet.get("available", 0)),
                    locked=float(wallet.get("blocked", 0)),
                )

            return balances
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch balance from Nobitex: {e}") from e

