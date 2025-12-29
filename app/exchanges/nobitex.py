"""Nobitex exchange implementation based on official API documentation.

API Documentation: https://apidocs.nobitex.ir/
"""

import time
from typing import Dict, List, Optional

import httpx

from app.core.config import NobitexConfig
from app.exchanges.base import (
    Balance,
    ExchangeInterface,
    OHLCData,
    Order,
    OrderBook,
    OrderBookEntry,
)
from app.exchanges.exceptions import (
    ExchangeAPIError,
    ExchangeAuthenticationError,
    ExchangeNetworkError,
    ExchangeOrderError,
    ExchangeOrderNotFoundError,
)
from app.core.logging import get_logger
from app.utils.retry import retry_with_backoff, RetryConfig
from app.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = get_logger(__name__)

# Circuit breaker for Nobitex API
_nobitex_circuit_breaker = CircuitBreaker(
    "nobitex",
    CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0,
    ),
)

# Retry configuration for Nobitex
_nobitex_retry_config = RetryConfig(
    max_retries=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
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
        self.username = config.username
        self.password = config.password
        self.token = config.token
        self.api_key = config.api_key  # For experimental API key support
        self.api_secret = config.api_secret
        self.timeout = config.timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._cached_token: Optional[str] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},  # Required by Nobitex
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_authenticated(self) -> bool:
        """
        Check if Nobitex has valid authentication credentials.

        Returns:
            True if token OR (username AND password) is configured
        """
        # Nobitex can authenticate with:
        # 1. Direct token
        # 2. Username and password (which will be used to get token)
        return bool(self.token) or (bool(self.username) and bool(self.password))

    async def _get_token(self) -> Optional[str]:
        """
        Get authentication token.
        
        Returns:
            Token string or None if authentication fails
        """
        # If token is directly provided, use it
        if self.token:
            return self.token
        
        # If we have cached token, use it
        if self._cached_token:
            return self._cached_token
        
        # Otherwise, try to login with username/password
        if not self.username or not self.password:
            logger.warning("Nobitex: No token, username, or password provided")
            return None
        
        client = await self._get_client()
        try:
            # Login endpoint: POST /auth/login
            response = await client.post(
                "/auth/login",
                json={
                    "username": self.username,
                    "password": self.password,
                    "captcha": "api",  # For API usage
                },
            )
            response.raise_for_status()
            data = response.json()
            
            # Response format: {"status": "ok", "token": "..."}
            if data.get("status") == "ok" and "token" in data:
                self._cached_token = data["token"]
                logger.info("Nobitex: Successfully authenticated")
                return self._cached_token
            else:
                logger.error(f"Nobitex: Login failed: {data}")
                return None
        except Exception as e:
            logger.error(f"Nobitex: Authentication error: {e}")
            return None

    def _get_headers(self, signed: bool = False) -> Dict[str, str]:
        """
        Get request headers.

        Args:
            signed: Whether to include authentication headers

        Returns:
            Headers dictionary
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",  # Required by Nobitex
        }
        if signed:
            # Token will be added in the request method
            pass
        return headers

    @retry_with_backoff(config=_nobitex_retry_config)
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

        Raises:
            ExchangeAPIError: If API returns an error
            ExchangeNetworkError: If network error occurs
        """
        async def _fetch():
            client = await self._get_client()
            # Use v3 endpoint only (v2 returns 503 Service Unavailable)
            endpoint = f"/v3/orderbook/{symbol}"

            try:
                response = await client.get(
                    endpoint,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()

                # Nobitex response format: {"status": "ok", "lastUpdate": ..., "bids": [[price, amount], ...], "asks": [[price, amount], ...]}
                if data.get("status") != "ok":
                    raise ExchangeAPIError(
                        f"Nobitex API returned error status: {data.get('message', 'Unknown error')}",
                        exchange_name="Nobitex",
                        status_code=response.status_code,
                        response_data=data,
                    )

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
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise ExchangeAuthenticationError(
                        "Nobitex authentication failed",
                        exchange_name="Nobitex",
                    ) from e
                elif e.response.status_code == 429:
                    raise ExchangeAPIError(
                        "Nobitex rate limit exceeded",
                        exchange_name="Nobitex",
                        status_code=429,
                    ) from e
                else:
                    raise ExchangeAPIError(
                        f"Nobitex API error: {e.response.text[:200]}",
                        exchange_name="Nobitex",
                        status_code=e.response.status_code,
                    ) from e
            except httpx.HTTPError as e:
                raise ExchangeNetworkError(
                    f"Network error while fetching Nobitex orderbook: {e}",
                    exchange_name="Nobitex",
                ) from e

        return await _nobitex_circuit_breaker.call_async(_fetch)

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

        token = await self._get_token()
        if not token:
            raise Exception("Nobitex: Authentication required for placing orders")

        client = await self._get_client()
        # Nobitex order endpoint: POST /v2/orders/add
        endpoint = "/v2/orders/add"

        # Nobitex order format
        payload = {
            "type": side.lower(),  # 'buy' or 'sell'
            "execution": "maker" if is_maker else "taker",
            "amount": str(quantity),
            "symbol": symbol,
        }

        if order_type == "limit":
            payload["price"] = str(price)
        else:
            payload["execution"] = "taker"  # Market orders are always taker

        if is_maker and order_type == "limit":
            payload["postOnly"] = True

        headers = self._get_headers(signed=True)
        headers["Authorization"] = f"Token {token}"

        try:
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            # Response format: {"status": "ok", "order": {"id": ..., ...}}
            if data.get("status") != "ok":
                raise Exception(f"Nobitex API error: {data}")

            order_data = data.get("order", {})
            return Order(
                order_id=str(order_data.get("id", "")),
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
        token = await self._get_token()
        if not token:
            logger.warning("Nobitex: Authentication required for canceling orders")
            return False

        client = await self._get_client()
        # Nobitex cancel endpoint: POST /v2/orders/{id}/cancel
        endpoint = f"/v2/orders/{order_id}/cancel"

        headers = self._get_headers(signed=True)
        headers["Authorization"] = f"Token {token}"

        try:
            response = await client.post(
                endpoint,
                json={"symbol": symbol},
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("status") == "ok"
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
        token = await self._get_token()
        if not token:
            raise Exception("Nobitex: Authentication required for balance")

        client = await self._get_client()
        # Nobitex wallets endpoint: GET /v2/wallets
        endpoint = "/v2/wallets"

        headers = self._get_headers(signed=True)
        headers["Authorization"] = f"Token {token}"

        try:
            response = await client.get(
                endpoint,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            # Response format: {"status": "ok", "wallets": {"RLS": {"id": ..., "balance": "...", "blocked": "..."}, ...}}
            if data.get("status") != "ok":
                raise Exception(f"Nobitex API error: {data}")

            balances = {}
            wallets = data.get("wallets", {})

            # Nobitex returns wallets as a dict with currency names as keys
            if isinstance(wallets, dict):
                for curr, wallet_data in wallets.items():
                    curr_upper = curr.upper()

                    # Filter by requested currency if specified
                    if currency and curr_upper != currency.upper():
                        continue

                    # wallet_data format: {"id": 123, "balance": "100.0", "blocked": "0"}
                    if isinstance(wallet_data, dict):
                        balances[curr_upper] = Balance(
                            currency=curr_upper,
                            available=float(wallet_data.get("balance", 0)),
                            locked=float(wallet_data.get("blocked", 0)),
                        )

            return balances
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch balance from Nobitex: {e}") from e

    async def get_open_orders(
        self, symbol: Optional[str] = None
    ) -> List[Order]:
        """
        Get open orders from Nobitex.

        Args:
            symbol: Optional trading pair symbol to filter by

        Returns:
            List of open Order objects
        """
        token = await self._get_token()
        if not token:
            raise Exception("Nobitex: Authentication required for open orders")

        client = await self._get_client()
        # Nobitex open orders endpoint: GET /v2/orders/open
        endpoint = "/v2/orders/open"
        params = {}
        if symbol:
            params["market"] = symbol

        headers = self._get_headers(signed=True)
        headers["Authorization"] = f"Token {token}"

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                raise Exception(f"Nobitex API error: {data}")

            orders = []
            orders_data = data.get("orders", [])
            
            for order_data in orders_data:
                orders.append(Order(
                    order_id=str(order_data.get("id", "")),
                    symbol=order_data.get("market", ""),
                    side=order_data.get("type", "").lower(),  # 'buy' or 'sell'
                    order_type=order_data.get("orderType", "limit").lower(),
                    quantity=float(order_data.get("amount", 0)),
                    price=float(order_data.get("price", 0)) if order_data.get("price") else None,
                    status=order_data.get("status", "pending").lower(),
                    filled_quantity=float(order_data.get("matchedAmount", 0)),
                    timestamp=float(order_data.get("createdAt", time.time())),
                ))

            return orders
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch open orders from Nobitex: {e}") from e

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """
        Get order details by order ID from Nobitex.

        Args:
            order_id: Order ID to fetch
            symbol: Trading pair symbol

        Returns:
            Order object with current status and fill information
        """
        token = await self._get_token()
        if not token:
            raise Exception("Nobitex: Authentication required for get order")

        client = await self._get_client()
        # Nobitex get order endpoint: GET /v2/orders/{order_id}
        endpoint = f"/v2/orders/{order_id}"

        headers = self._get_headers(signed=True)
        headers["Authorization"] = f"Token {token}"

        try:
            response = await client.get(
                endpoint,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                raise Exception(f"Nobitex API error: {data}")

            order_data = data.get("order", {})
            if not order_data:
                raise Exception(f"Order {order_id} not found")

            # Map Nobitex status to our format
            status_map = {
                "Active": "pending",
                "PartiallyMatched": "pending",
                "Matched": "filled",
                "Canceled": "cancelled",
                "Rejected": "cancelled",
            }
            nobitex_status = order_data.get("status", "Active")
            status = status_map.get(nobitex_status, "pending")

            return Order(
                order_id=str(order_data.get("id", order_id)),
                symbol=order_data.get("market", symbol),
                side=order_data.get("type", "").lower(),
                order_type=order_data.get("orderType", "limit").lower(),
                quantity=float(order_data.get("amount", 0)),
                price=float(order_data.get("price", 0)) if order_data.get("price") else None,
                status=status,
                filled_quantity=float(order_data.get("matchedAmount", 0)),
                timestamp=float(order_data.get("createdAt", time.time())),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception(f"Order {order_id} not found on Nobitex")
            raise Exception(f"Failed to fetch order from Nobitex: {e}") from e
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch order from Nobitex: {e}") from e

    async def fetch_ohlc(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
    ) -> list[OHLCData]:
        """
        Fetch OHLC data from Nobitex.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCIRT')
            interval: Time interval (e.g., '1m', '5m', '1h', '1d')
            limit: Number of candles to fetch

        Returns:
            List of OHLCData objects
        """
        client = await self._get_client()
        # Nobitex OHLC endpoint: GET /market/udf/history
        # Documentation: https://apidocs.nobitex.ir/
        endpoint = "/market/udf/history"
        
        # Map interval to Nobitex resolution format
        interval_map = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "2h": "120",
            "4h": "240",
            "6h": "360",
            "12h": "720",
            "1d": "D",
            "1w": "W",
        }
        resolution = interval_map.get(interval, "1")
        
        # Calculate time range
        current_time = int(time.time())
        # Approximate: each candle is resolution minutes (or days for D/W)
        if resolution in ["D", "W"]:
            time_range = limit * 86400  # days in seconds
        else:
            time_range = limit * int(resolution) * 60
        
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "from": current_time - time_range,
            "to": current_time,
        }

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            # Nobitex UDF format: {"s": "ok", "t": [timestamps], "o": [opens], "h": [highs], "l": [lows], "c": [closes], "v": [volumes]}
            # Check response status
            if data.get("s") != "ok":
                error_msg = data.get("errmsg", "Unknown error")
                raise ExchangeAPIError(
                    f"Nobitex OHLC API returned error: {error_msg}",
                    exchange_name="Nobitex",
                    response_data=data,
                )
            
            ohlc_list = []
            if "t" in data and "o" in data and len(data["t"]) > 0:
                for i in range(len(data["t"])):
                    ohlc_list.append(
                        OHLCData(
                            open=float(data["o"][i]),
                            high=float(data["h"][i]),
                            low=float(data["l"][i]),
                            close=float(data["c"][i]),
                            volume=float(data.get("v", [0])[i] if "v" in data and i < len(data["v"]) else 0),
                            timestamp=float(data["t"][i]),
                            symbol=symbol,
                        )
                    )
            return ohlc_list
        except httpx.HTTPStatusError as e:
            raise ExchangeAPIError(
                f"Failed to fetch OHLC from Nobitex: HTTP {e.response.status_code}",
                exchange_name="Nobitex",
                response_data=e.response.text[:500] if e.response.text else None,
            ) from e
        except httpx.HTTPError as e:
            raise ExchangeAPIError(
                f"Failed to fetch OHLC from Nobitex: {e}",
                exchange_name="Nobitex",
            ) from e
