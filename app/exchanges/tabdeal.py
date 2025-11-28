"""Tabdeal exchange implementation."""

import hashlib
import hmac
import time
from typing import Dict, Optional

import httpx

from app.core.config import TabdealConfig
from app.exchanges.base import (
    Balance,
    ExchangeInterface,
    OHLCData,
    Order,
    OrderBook,
    OrderBookEntry,
)


class TabdealExchange(ExchangeInterface):
    """Tabdeal exchange client implementation."""

    def __init__(self, config: Optional[TabdealConfig] = None) -> None:
        """
        Initialize Tabdeal exchange client.

        Args:
            config: Tabdeal configuration (uses default if not provided)
        """
        if config is None:
            config = TabdealConfig()
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
        Check if Tabdeal has valid authentication credentials.

        Returns:
            True if api_key AND api_secret are configured
        """
        return bool(self.api_key) and bool(self.api_secret)

    def _generate_signature(self, params: Dict[str, str]) -> str:
        """
        Generate HMAC signature for authenticated requests.
        
        According to Tabdeal docs: Create query string from params (sorted),
        then HMAC-SHA256 with api-secret.

        Args:
            params: Request parameters (including timestamp)

        Returns:
            HMAC signature string
        """
        # Create query string: param1=value1&param2=value2&...&timestamp=value
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
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
            headers["X-MBX-APIKEY"] = self.api_key  # Tabdeal uses X-MBX-APIKEY
        return headers
    
    def _prepare_signed_params(self, params: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Prepare parameters with timestamp and signature for authenticated requests.
        
        Args:
            params: Original parameters
            
        Returns:
            Parameters with timestamp and signature added
        """
        if params is None:
            params = {}
        
        # Add timestamp (milliseconds)
        timestamp = str(int(time.time() * 1000))
        params["timestamp"] = timestamp
        
        # Generate signature
        signature = self._generate_signature(params)
        params["signature"] = signature
        
        return params

    async def fetch_orderbook(
        self, symbol: str, depth: int = 20
    ) -> OrderBook:
        """
        Fetch order book from Tabdeal.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCIRT')
            depth: Number of price levels

        Returns:
            OrderBook object
        """
        client = await self._get_client()
        endpoint = "/api/v1/depth"  # Tabdeal uses /api/v1/depth with symbol as query param
        params = {
            "symbol": symbol,
            "limit": str(depth),
        }

        try:
            # Orderbook is public, no authentication needed
            response = await client.get(
                endpoint,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            # Normalize response to OrderBook format
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
            raise Exception(f"Failed to fetch orderbook from Tabdeal: {e}") from e

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
        Place an order on Tabdeal.

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
        endpoint = "/api/v1/orders"

        payload = {
            "symbol": symbol,
            "side": side.lower(),
            "type": order_type.lower(),
            "amount": str(quantity),
        }

        if order_type == "limit":
            payload["price"] = str(price)

        if is_maker:
            payload["postOnly"] = True

        # Tabdeal: Convert payload to query params for signature, then send as JSON body
        # But signature is calculated from query string format
        params = {k: str(v) for k, v in payload.items()}
        signed_params = self._prepare_signed_params(params)
        
        try:
            response = await client.post(
                endpoint,
                json=payload,  # Body is JSON
                params={"signature": signed_params["signature"], "timestamp": signed_params["timestamp"]},  # Signature in query
                headers=self._get_headers(signed=True),
            )
            response.raise_for_status()
            data = response.json()

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
            raise Exception(f"Failed to place order on Tabdeal: {e}") from e

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order on Tabdeal.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            True if successful
        """
        client = await self._get_client()
        endpoint = f"/api/v1/orders/{order_id}"

        # Tabdeal: Signature in query params
        params = {"symbol": symbol}
        signed_params = self._prepare_signed_params(params)
        
        try:
            response = await client.delete(
                endpoint,
                params=signed_params,
                headers=self._get_headers(signed=True),
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """
        Get order details by order ID from Tabdeal.

        Args:
            order_id: Order ID to fetch
            symbol: Trading pair symbol

        Returns:
            Order object with current status and fill information
        """
        client = await self._get_client()
        endpoint = f"/api/v1/orders/{order_id}"

        # Tabdeal: Signature in query params
        params = {"symbol": symbol}
        signed_params = self._prepare_signed_params(params)

        try:
            response = await client.get(
                endpoint,
                params=signed_params,
                headers=self._get_headers(signed=True),
            )
            response.raise_for_status()
            data = response.json()

            order_data = data.get("order", data)
            if not order_data:
                raise Exception(f"Order {order_id} not found")

            # Map Tabdeal status to our format
            status_map = {
                "NEW": "pending",
                "PARTIALLY_FILLED": "pending",
                "FILLED": "filled",
                "CANCELED": "cancelled",
                "REJECTED": "cancelled",
            }
            tabdeal_status = order_data.get("status", "NEW")
            status = status_map.get(tabdeal_status, "pending")

            return Order(
                order_id=str(order_data.get("orderId", order_id)),
                symbol=order_data.get("symbol", symbol),
                side=order_data.get("side", "").lower(),
                order_type=order_data.get("type", "limit").lower(),
                quantity=float(order_data.get("quantity", 0)),
                price=float(order_data.get("price", 0)) if order_data.get("price") else None,
                status=status,
                filled_quantity=float(order_data.get("executedQty", 0)),
                timestamp=float(order_data.get("time", time.time())),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception(f"Order {order_id} not found on Tabdeal")
            raise Exception(f"Failed to fetch order from Tabdeal: {e}") from e
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch order from Tabdeal: {e}") from e

    async def get_balance(
        self, currency: Optional[str] = None
    ) -> Dict[str, Balance]:
        """
        Get account balance from Tabdeal.

        Args:
            currency: Specific currency (None for all)

        Returns:
            Dictionary of balances
        """
        client = await self._get_client()
        endpoint = "/api/v1/account/balances"

        # Tabdeal: Signature in query params
        signed_params = self._prepare_signed_params()
        
        try:
            response = await client.get(
                endpoint,
                params=signed_params,
                headers=self._get_headers(signed=True),
            )
            response.raise_for_status()
            data = response.json()

            balances = {}
            account_balances = data.get("balances", [])

            for balance_data in account_balances:
                curr = balance_data.get("currency", "").upper()
                if currency and curr != currency.upper():
                    continue

                balances[curr] = Balance(
                    currency=curr,
                    available=float(balance_data.get("available", 0)),
                    locked=float(balance_data.get("locked", 0)),
                )

            return balances
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch balance from Tabdeal: {e}") from e

    async def fetch_ohlc(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
    ) -> list[OHLCData]:
        """
        Fetch OHLC data from Tabdeal.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCIRT')
            interval: Time interval (e.g., '1m', '5m', '1h', '1d')
            limit: Number of candles to fetch

        Returns:
            List of OHLCData objects
        """
        client = await self._get_client()
        # Tabdeal OHLC endpoint (public, no auth needed)
        endpoint = f"/api/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": str(limit),
        }

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            # Normalize response to OHLCData format
            ohlc_list = []
            candles = data.get("data", [])
            for candle in candles:
                if isinstance(candle, list) and len(candle) >= 6:
                    ohlc_list.append(
                        OHLCData(
                            open=float(candle[1]),
                            high=float(candle[2]),
                            low=float(candle[3]),
                            close=float(candle[4]),
                            volume=float(candle[5]),
                            timestamp=float(candle[0]) / 1000.0,
                            symbol=symbol,
                        )
                    )
            return ohlc_list
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch OHLC from Tabdeal: {e}") from e

