"""Wallex exchange implementation."""

import hashlib
import hmac
import time
from typing import Dict, List, Optional

import httpx

from app.core.config import WallexConfig
from app.exchanges.base import (
    Balance,
    ExchangeInterface,
    OHLCData,
    Order,
    OrderBook,
    OrderBookEntry,
)


class WallexExchange(ExchangeInterface):
    """Wallex exchange client implementation."""

    def __init__(self, config: Optional[WallexConfig] = None) -> None:
        """
        Initialize Wallex exchange client.

        Args:
            config: Wallex configuration (uses default if not provided)
        """
        if config is None:
            config = WallexConfig()
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

    def is_authenticated(self) -> bool:
        """
        Check if Wallex has valid authentication credentials.

        Returns:
            True if api_key AND api_secret are configured
        """
        return bool(self.api_key) and bool(self.api_secret)

    def _generate_signature(self, query_string: str) -> str:
        """
        Generate HMAC-SHA256 signature for authenticated requests.
        
        Wallex uses HMAC-SHA256 signature similar to Binance-style APIs.
        The signature is generated from the query string.

        Args:
            query_string: Query string to sign (e.g., "symbol=BTCUSDT&side=BUY")

        Returns:
            HMAC-SHA256 signature as hex string
        """
        return hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _get_headers(self, signed: bool = False, query_string: str = "") -> Dict[str, str]:
        """
        Get request headers.

        Args:
            signed: Whether to include authentication headers
            query_string: Query string for signature generation (if signed)

        Returns:
            Headers dictionary
        """
        headers = {"Content-Type": "application/json"}
        if signed and self.api_key:
            headers["X-API-Key"] = self.api_key
            if query_string:
                signature = self._generate_signature(query_string)
                headers["X-API-Sign"] = signature
        return headers

    async def fetch_orderbook(
        self, symbol: str, depth: int = 20
    ) -> OrderBook:
        """
        Fetch order book from Wallex.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            depth: Number of price levels

        Returns:
            OrderBook object
        """
        client = await self._get_client()
        endpoint = "/v1/depth"
        params = {"symbol": symbol}

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            # Wallex API response structure: {"result": {"bid": [...], "ask": [...]}, "success": true}
            if not data.get("success") or "result" not in data:
                raise Exception(f"Invalid Wallex response: {data}")

            result = data["result"]
            
            # Wallex format: bids/asks are objects with 'price', 'quantity', 'sum' keys
            bids = [
                OrderBookEntry(price=float(entry["price"]), quantity=float(entry["quantity"]))
                for entry in result.get("bid", [])[:depth]
            ]
            asks = [
                OrderBookEntry(price=float(entry["price"]), quantity=float(entry["quantity"]))
                for entry in result.get("ask", [])[:depth]
            ]

            return OrderBook(
                bids=bids,
                asks=asks,
                timestamp=time.time(),
                symbol=symbol,
            )
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch orderbook from Wallex: {e}") from e

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
        Place an order on Wallex.

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
        endpoint = "/v1/orders"

        # Build query string for signature
        query_params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": str(quantity),
        }

        if order_type == "limit":
            query_params["price"] = str(price)

        if is_maker:
            query_params["timeInForce"] = "GTD"  # Good Till Date / Post-Only
            query_params["postOnly"] = "true"

        # Create query string for signature
        query_string = "&".join([f"{k}={v}" for k, v in sorted(query_params.items())])

        try:
            response = await client.post(
                endpoint,
                json=query_params,
                headers=self._get_headers(signed=True, query_string=query_string),
            )
            response.raise_for_status()
            data = response.json()

            # Wallex response format: {"result": {...}, "success": true}
            if not data.get("success"):
                raise Exception(f"Wallex API error: {data}")

            order_data = data.get("result", data)
            
            # Map Wallex status to our format
            status_map = {
                "NEW": "pending",
                "PARTIALLY_FILLED": "pending",
                "FILLED": "filled",
                "CANCELED": "cancelled",
                "REJECTED": "cancelled",
            }
            wallex_status = order_data.get("status", "NEW")
            status = status_map.get(wallex_status, "pending")

            return Order(
                order_id=str(order_data.get("orderId", order_data.get("id", ""))),
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status=status,
                filled_quantity=float(order_data.get("executedQty", order_data.get("executedQuantity", 0))),
                timestamp=float(order_data.get("time", time.time())),
            )
        except httpx.HTTPError as e:
            raise Exception(f"Failed to place order on Wallex: {e}") from e

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order on Wallex.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            True if successful
        """
        client = await self._get_client()
        endpoint = f"/v1/orders/{order_id}"

        # Build query string for signature
        query_params = {"symbol": symbol}
        query_string = "&".join([f"{k}={v}" for k, v in sorted(query_params.items())])

        try:
            response = await client.delete(
                endpoint,
                params=query_params,
                headers=self._get_headers(signed=True, query_string=query_string),
            )
            response.raise_for_status()
            data = response.json()
            return data.get("success", False)
        except httpx.HTTPError:
            return False

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """
        Get order details by order ID from Wallex.

        Args:
            order_id: Order ID to fetch
            symbol: Trading pair symbol

        Returns:
            Order object with current status and fill information
        """
        client = await self._get_client()
        endpoint = f"/v1/orders/{order_id}"

        # Build query string for signature
        query_params = {"symbol": symbol}
        query_string = "&".join([f"{k}={v}" for k, v in sorted(query_params.items())])

        try:
            response = await client.get(
                endpoint,
                params=query_params,
                headers=self._get_headers(signed=True, query_string=query_string),
            )
            response.raise_for_status()
            data = response.json()

            # Wallex response format: {"result": {...}, "success": true}
            if not data.get("success"):
                raise Exception(f"Order {order_id} not found or error: {data}")

            order_data = data.get("result", data)
            if not order_data:
                raise Exception(f"Order {order_id} not found")

            # Map Wallex status to our format
            status_map = {
                "NEW": "pending",
                "PARTIALLY_FILLED": "pending",
                "FILLED": "filled",
                "CANCELED": "cancelled",
                "REJECTED": "cancelled",
            }
            wallex_status = order_data.get("status", "NEW")
            status = status_map.get(wallex_status, "pending")

            return Order(
                order_id=str(order_data.get("orderId", order_data.get("id", order_id))),
                symbol=order_data.get("symbol", symbol),
                side=order_data.get("side", "").lower(),
                order_type=order_data.get("type", "limit").lower(),
                quantity=float(order_data.get("quantity", 0)),
                price=float(order_data.get("price", 0)) if order_data.get("price") else None,
                status=status,
                filled_quantity=float(order_data.get("executedQty", order_data.get("executedQuantity", 0))),
                timestamp=float(order_data.get("time", time.time())),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception(f"Order {order_id} not found on Wallex")
            raise Exception(f"Failed to fetch order from Wallex: {e}") from e
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch order from Wallex: {e}") from e

    async def get_balance(
        self, currency: Optional[str] = None
    ) -> Dict[str, Balance]:
        """
        Get account balance from Wallex.

        Args:
            currency: Specific currency (None for all)

        Returns:
            Dictionary of balances
        """
        client = await self._get_client()
        endpoint = "/v1/account/balances"

        # Build query string for signature (empty for balance endpoint)
        query_string = ""

        try:
            response = await client.get(
                endpoint,
                headers=self._get_headers(signed=True, query_string=query_string),
            )
            response.raise_for_status()
            data = response.json()

            # Wallex response format: {"result": {"balances": [...]}, "success": true}
            if not data.get("success"):
                raise Exception(f"Wallex API error: {data}")

            result = data.get("result", {})
            account_balances = result.get("balances", [])

            balances = {}
            for balance_data in account_balances:
                curr = balance_data.get("asset", balance_data.get("currency", "")).upper()
                if currency and curr != currency.upper():
                    continue

                balances[curr] = Balance(
                    currency=curr,
                    available=float(balance_data.get("free", balance_data.get("available", 0))),
                    locked=float(balance_data.get("locked", balance_data.get("inOrder", 0))),
                )

            return balances
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch balance from Wallex: {e}") from e

    async def fetch_ohlc(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
    ) -> list[OHLCData]:
        """
        Fetch OHLC data from Wallex.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Time interval (e.g., '1m', '5m', '1h', '1d')
            limit: Number of candles to fetch

        Returns:
            List of OHLCData objects
        """
        client = await self._get_client()
        endpoint = "/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            # Wallex response format: {"result": [[timestamp, open, high, low, close, volume], ...], "success": true}
            if isinstance(data, dict):
                if not data.get("success"):
                    raise Exception(f"Wallex API error: {data}")
                candles = data.get("result", [])
            else:
                # Direct array format
                candles = data

            # Normalize response to OHLCData format
            # Expected format: [[timestamp, open, high, low, close, volume], ...]
            ohlc_list = []
            for candle in candles:
                if isinstance(candle, list) and len(candle) >= 6:
                    ohlc_list.append(
                        OHLCData(
                            open=float(candle[1]),
                            high=float(candle[2]),
                            low=float(candle[3]),
                            close=float(candle[4]),
                            volume=float(candle[5]),
                            timestamp=float(candle[0]) / 1000.0,  # Convert ms to seconds
                            symbol=symbol,
                        )
                    )
            return ohlc_list
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch OHLC from Wallex: {e}") from e

    async def get_open_orders(
        self, symbol: Optional[str] = None
    ) -> List[Order]:
        """
        Get open orders from Wallex.

        Args:
            symbol: Optional trading pair symbol to filter by

        Returns:
            List of open Order objects
        """
        if not self.api_key or not self.api_secret:
            raise Exception("Wallex: API key and secret required for open orders")

        client = await self._get_client()
        endpoint = "/v1/orders"

        # Build query string for signature
        query_params = {"status": "NEW"}  # Open orders
        if symbol:
            query_params["symbol"] = symbol
        query_string = "&".join([f"{k}={v}" for k, v in sorted(query_params.items())])

        try:
            response = await client.get(
                endpoint,
                params=query_params,
                headers=self._get_headers(signed=True, query_string=query_string),
            )
            response.raise_for_status()
            data = response.json()

            # Wallex response format: {"result": [...], "success": true}
            if not data.get("success"):
                raise Exception(f"Wallex API error: {data}")

            orders_data = data.get("result", [])
            orders = []

            # Map Wallex status to our format
            status_map = {
                "NEW": "pending",
                "PARTIALLY_FILLED": "pending",
                "FILLED": "filled",
                "CANCELED": "cancelled",
                "REJECTED": "cancelled",
            }

            for order_data in orders_data:
                wallex_status = order_data.get("status", "NEW")
                status = status_map.get(wallex_status, "pending")

                orders.append(
                    Order(
                        order_id=str(order_data.get("orderId", order_data.get("id", ""))),
                        symbol=order_data.get("symbol", symbol or ""),
                        side=order_data.get("side", "").lower(),
                        order_type=order_data.get("type", "limit").lower(),
                        quantity=float(order_data.get("quantity", 0)),
                        price=float(order_data.get("price", 0)) if order_data.get("price") else None,
                        status=status,
                        filled_quantity=float(order_data.get("executedQty", order_data.get("executedQuantity", 0))),
                        timestamp=float(order_data.get("time", time.time())),
                    )
                )

            return orders
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch open orders from Wallex: {e}") from e

