"""Invex exchange implementation based on official API documentation.

API Documentation: https://documenter.getpostman.com/view/29635700/2sA2r813me
"""

import binascii
import json
import time
from typing import Dict, List, Optional

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_private_key

from app.core.config import InvexConfig
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
from typing import List
from app.core.logging import get_logger
from app.utils.retry import retry_with_backoff, RetryConfig
from app.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = get_logger(__name__)

# Circuit breaker for Invex API
_invex_circuit_breaker = CircuitBreaker(
    "invex",
    CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0,
        expected_exception=Exception,
    ),
)

# Retry configuration for Invex
_invex_retry_config = RetryConfig(
    max_retries=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    retryable_exceptions=(httpx.HTTPError, httpx.RequestError, httpx.TimeoutException),
)


class InvexExchange(ExchangeInterface):
    """Invex exchange client implementation."""

    def __init__(self, config: Optional[InvexConfig] = None) -> None:
        """
        Initialize Invex exchange client.

        Args:
            config: Invex configuration (uses default if not provided)
        """
        if config is None:
            config = InvexConfig()
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
        Check if Invex has valid authentication credentials.

        Returns:
            True if api_key AND api_secret are configured
        """
        return bool(self.api_key) and bool(self.api_secret)

    def _convert_symbol_format(self, symbol: str) -> str:
        """
        Convert symbol format to Invex format (with underscore).
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCIRT', 'BTCUSDT')
            
        Returns:
            Invex format symbol (e.g., 'BTC_IRR', 'BTC_USDT')
        """
        if '_' in symbol:
            return symbol  # Already in correct format
        
        # Convert format like BTCIRT to BTC_IRR or BTCUSDT to BTC_USDT
        if symbol.endswith('IRT'):
            base = symbol[:-3]
            return f"{base}_IRR"
        elif symbol.endswith('USDT'):
            base = symbol[:-4]
            return f"{base}_USDT"
        elif symbol.endswith('USD'):
            base = symbol[:-3]
            return f"{base}_USD"
        else:
            # Return as-is, API will validate
            return symbol

    def _generate_signature(self, message: str) -> str:
        """
        Generate RSA-PSS signature for authenticated requests.

        Args:
            message: JSON string of request data (including expire_at)

        Returns:
            Hex-encoded signature string
        """
        try:
            # Convert hex secret key to bytes
            byte_private_key = binascii.unhexlify(self.api_secret)
            
            # Load RSA private key from DER format
            rsa_private_key = load_der_private_key(byte_private_key, password=None)
            
            # Sign using RSA-PSS with SHA256
            signature = rsa_private_key.sign(
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            
            return signature.hex()
        except Exception as e:
            logger.error(f"Invex: Signature generation error: {e}")
            raise ExchangeAuthenticationError(
                f"Failed to generate signature: {e}",
                exchange_name="Invex",
            ) from e

    def _get_headers(
        self, method: str, path: str, signed: bool = False, body_data: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Get request headers.

        Args:
            method: HTTP method
            path: API path
            signed: Whether to include authentication headers
            body_data: Request body data (for signing)

        Returns:
            Headers dictionary
        """
        headers = {"Content-Type": "application/json"}
        
        if signed and self.api_key and self.api_secret:
            # Add expire_at to body if not present
            if body_data is None:
                body_data = {}
            
            # expire_at should be Unix timestamp (seconds) + some buffer (e.g., 60 seconds)
            expire_at = int(time.time()) + 60
            body_data["expire_at"] = expire_at
            
            # Create message for signing (sorted JSON string)
            message = json.dumps(body_data, sort_keys=True, separators=(",", ":"))
            
            # Generate signature
            signature = self._generate_signature(message)
            
            headers["X-API-Key-Invex"] = self.api_key
            headers["X-API-Sign"] = signature
            headers["X-API-Expire-At"] = str(expire_at)
        
        return headers

    @retry_with_backoff(config=_invex_retry_config)
    async def fetch_orderbook(
        self, symbol: str, depth: int = 20
    ) -> OrderBook:
        """
        Fetch order book from Invex.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCIRT')
            depth: Number of price levels

        Returns:
            OrderBook object
        """
        client = await self._get_client()
        # Invex orderbook endpoint: GET /market-depth (public, no auth required)
        # Based on Postman documentation: https://api.invex.ir/trading/v1/market-depth
        endpoint = "/market-depth"
        
        # Convert symbol format
        invex_symbol = self._convert_symbol_format(symbol)
        
        # Invex only accepts specific depth values: 5, 20, or 50
        valid_depths = [5, 20, 50]
        # Find closest valid depth
        closest_depth = min(valid_depths, key=lambda x: abs(x - depth))
        # If requested depth is between values, use the next higher one
        if closest_depth < depth:
            idx = valid_depths.index(closest_depth)
            if idx < len(valid_depths) - 1:
                closest_depth = valid_depths[idx + 1]
            else:
                closest_depth = valid_depths[-1]  # Use max if depth is larger than all
        # Ensure we use a string for the API (Invex expects string values)
        closest_depth_str = str(closest_depth)
        
        params = {
            "symbol": invex_symbol,
            "depth": closest_depth_str,
        }
        
        try:
            # This is a public endpoint, no authentication required
            logger.debug(f"Invex: Fetching orderbook for symbol={symbol} (converted to {invex_symbol}), depth={closest_depth_str} (requested: {depth})")
            response = await client.get(
                endpoint,
                params=params,
                headers=self._get_headers("GET", endpoint),
            )
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Invex: Received orderbook response: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")

            # Invex response format (from actual API response):
            # {
            #   "bid_orders": [{"depth": 1, "price": "...", "quantity": "..."}, ...],
            #   "ask_orders": [{"depth": 1, "price": "...", "quantity": "..."}, ...]
            # }
            bids = []
            asks = []
            
            if isinstance(data, dict):
                # Parse bid_orders (primary format from API)
                bids_data = data.get("bid_orders", [])
                if not bids_data:
                    # Try alternative field names for backward compatibility
                    bids_data = data.get("bids", []) or data.get("bid", [])
                
                for bid in bids_data[:depth]:
                    if isinstance(bid, dict):
                        # Format: {"depth": 1, "price": "...", "quantity": "..."}
                        price = bid.get("price")
                        quantity = bid.get("quantity") or bid.get("amount")
                        if price and quantity:
                            bids.append(OrderBookEntry(price=float(price), quantity=float(quantity)))
                    elif isinstance(bid, list) and len(bid) >= 2:
                        # Fallback: [price, quantity] format
                        bids.append(OrderBookEntry(price=float(bid[0]), quantity=float(bid[1])))
                
                # Parse ask_orders (primary format from API)
                asks_data = data.get("ask_orders", [])
                if not asks_data:
                    # Try alternative field names for backward compatibility
                    asks_data = data.get("asks", []) or data.get("ask", [])
                
                for ask in asks_data[:depth]:
                    if isinstance(ask, dict):
                        # Format: {"depth": 1, "price": "...", "quantity": "..."}
                        price = ask.get("price")
                        quantity = ask.get("quantity") or ask.get("amount")
                        if price and quantity:
                            asks.append(OrderBookEntry(price=float(price), quantity=float(quantity)))
                    elif isinstance(ask, list) and len(ask) >= 2:
                        # Fallback: [price, quantity] format
                        asks.append(OrderBookEntry(price=float(ask[0]), quantity=float(ask[1])))

            if not bids or not asks:
                logger.warning(f"Invex: Empty orderbook for {symbol} (converted: {invex_symbol}). Response: {data}")
                raise ExchangeAPIError(
                    f"Invex returned empty orderbook for symbol {symbol} (converted: {invex_symbol}). This symbol may not be available on Invex.",
                    exchange_name="Invex",
                    response_data=data,
                )
            
            logger.debug(f"Invex: Parsed {len(bids)} bids and {len(asks)} asks for {symbol}")
            return OrderBook(
                bids=bids,
                asks=asks,
                timestamp=time.time(),
                symbol=symbol,
            )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = f"HTTP {status_code}"
            
            # Handle specific error codes
            if status_code == 504:
                error_detail = "Gateway Timeout - Exchange server is slow or unavailable"
                logger.warning(f"Invex: Gateway timeout for {symbol} (converted: {invex_symbol})")
            elif status_code == 503:
                error_detail = "Service Unavailable - Exchange is temporarily down"
                logger.warning(f"Invex: Service unavailable for {symbol} (converted: {invex_symbol})")
            else:
                try:
                    error_body = e.response.json()
                    error_detail += f": {error_body}"
                except:
                    error_detail += f": {e.response.text[:200]}"
            
            logger.error(f"Invex: Failed to fetch orderbook for {symbol} (converted: {invex_symbol}): {error_detail}")
            raise ExchangeAPIError(
                f"Failed to fetch orderbook from Invex for {symbol}: {error_detail}",
                exchange_name="Invex",
                status_code=status_code,
                response_data=error_detail,
            ) from e
        except httpx.HTTPError as e:
            logger.error(f"Invex: Network error fetching orderbook for {symbol} (converted: {invex_symbol}): {e}")
            raise ExchangeNetworkError(
                f"Failed to fetch orderbook from Invex for {symbol}: Network error - {e}",
                exchange_name="Invex",
            ) from e
        except Exception as e:
            logger.error(f"Invex: Unexpected error fetching orderbook for {symbol} (converted: {invex_symbol}): {e}", exc_info=True)
            raise ExchangeAPIError(
                f"Failed to fetch orderbook from Invex for {symbol}: {e}",
                exchange_name="Invex",
            ) from e

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
        Place an order on Invex.

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

        if not self.api_key or not self.api_secret:
            raise Exception("Invex: API key and secret required for placing orders")

        client = await self._get_client()
        endpoint = "/orders"
        
        # Convert symbol format
        invex_symbol = self._convert_symbol_format(symbol)

        # Convert side: 'buy' -> 'BUYER', 'sell' -> 'SELLER'
        side_mapping = {
            "buy": "BUYER",
            "sell": "SELLER",
        }
        invex_side = side_mapping.get(side.lower(), side.upper())
        
        # Convert order type: 'limit' -> 'LIMIT', 'market' -> 'MARKET_BY_AMOUNT'
        type_mapping = {
            "limit": "LIMIT",
            "market": "MARKET_BY_AMOUNT",
        }
        invex_type = type_mapping.get(order_type.lower(), order_type.upper())

        payload = {
            "symbol": invex_symbol,
            "side": invex_side,
            "type": invex_type,
            "quantity": str(quantity),
        }

        if order_type == "limit":
            payload["price"] = str(price)
        
        # Note: Invex doesn't have postOnly parameter in the interface
        # Maker orders are determined by order placement strategy

        headers = self._get_headers("POST", endpoint, signed=True, body_data=payload)

        try:
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            # Invex response format may vary
            order_id = None
            if isinstance(data, dict):
                order_id = data.get("orderId") or data.get("id") or data.get("order_id")
            
            if not order_id:
                raise ExchangeOrderError(
                    f"Invex: Invalid order response: {data}",
                    exchange_name="Invex",
                    response_data=data,
                )

            return Order(
                order_id=str(order_id),
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status="pending",
                timestamp=time.time(),
            )
        except httpx.HTTPError as e:
            raise ExchangeOrderError(
                f"Failed to place order on Invex: {e}",
                exchange_name="Invex",
            ) from e

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order on Invex.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            True if successful
        """
        if not self.api_key or not self.api_secret:
            logger.warning("Invex: API key and secret required for canceling orders")
            return False

        client = await self._get_client()
        endpoint = f"/orders/{order_id}"

        payload = {"symbol": symbol}
        headers = self._get_headers("DELETE", endpoint, signed=True, body_data=payload)

        try:
            response = await client.delete(
                endpoint,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def get_balance(
        self, currency: Optional[str] = None
    ) -> Dict[str, Balance]:
        """
        Get account balance from Invex.

        Args:
            currency: Specific currency (None for all)

        Returns:
            Dictionary of balances
        """
        if not self.api_key or not self.api_secret:
            raise Exception("Invex: API key and secret required for balance")

        client = await self._get_client()
        endpoint = "/account"

        headers = self._get_headers("GET", endpoint, signed=True)

        try:
            response = await client.get(
                endpoint,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            balances = {}
            
            # Invex response format may vary
            wallets = []
            if isinstance(data, dict):
                wallets = data.get("wallets", []) or data.get("balances", []) or []
            
            for wallet in wallets:
                if isinstance(wallet, dict):
                    curr = wallet.get("currency", "").upper()
                    if currency and curr != currency.upper():
                        continue

                    balances[curr] = Balance(
                        currency=curr,
                        available=float(wallet.get("available", wallet.get("free", 0))),
                        locked=float(wallet.get("locked", wallet.get("blocked", 0))),
                    )

            return balances
        except httpx.HTTPError as e:
            raise ExchangeAPIError(
                f"Failed to fetch balance from Invex: {e}",
                exchange_name="Invex",
            ) from e

    async def get_open_orders(
        self, symbol: Optional[str] = None
    ) -> List[Order]:
        """
        Get open orders from Invex.

        Args:
            symbol: Optional trading pair symbol to filter by

        Returns:
            List of open Order objects
        """
        if not self.api_key or not self.api_secret:
            raise Exception("Invex: API key and secret required for open orders")

        client = await self._get_client()
        endpoint = "/orders"
        
        # Invex search orders requires expire_at and signature
        expire_at = int(time.time()) + 60
        params = {
            "expire_at": expire_at,
            "status": "NOT_FILLED",  # Open orders
            "page": 1,
            "page_size": 100,
        }
        if symbol:
            # Convert symbol format
            invex_symbol = self._convert_symbol_format(symbol)
            params["symbol"] = invex_symbol

        # Create message for signing
        body_data = {k: str(v) for k, v in params.items()}
        message = json.dumps(body_data, sort_keys=True, separators=(",", ":"))
        signature = self._generate_signature(message)

        headers = self._get_headers("GET", endpoint)
        headers["X-API-Key-Invex"] = self.api_key
        headers["X-API-Sign"] = signature
        headers["X-API-Expire-At"] = str(expire_at)

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            orders = []
            orders_list = data.get("orders", [])
            
            for order_data in orders_list:
                # Map Invex order status to our format
                status_map = {
                    "NOT_FILLED": "pending",
                    "PARTIALLY_FILLED": "pending",
                    "FULL_FILLED": "filled",
                    "CANCELED_BY_USER": "cancelled",
                    "CANCELED_BY_MATCH_ENGINE": "cancelled",
                }
                status = status_map.get(order_data.get("status", ""), "pending")
                
                orders.append(Order(
                    order_id=str(order_data.get("order_id", "")),
                    symbol=order_data.get("symbol", ""),
                    side="buy" if order_data.get("side") == "BUYER" else "sell",
                    order_type=order_data.get("type", "LIMIT").lower(),
                    quantity=float(order_data.get("quantity", 0)),
                    price=float(order_data.get("price", 0)) if order_data.get("price") else None,
                    status=status,
                    filled_quantity=float(order_data.get("deal_quantity", 0)),
                    timestamp=float(order_data.get("created_at", time.time())),
                ))

            return orders
        except httpx.HTTPError as e:
            raise ExchangeAPIError(
                f"Failed to fetch open orders from Invex: {e}",
                exchange_name="Invex",
            ) from e

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """
        Get order details by order ID from Invex.

        Args:
            order_id: Order ID to fetch
            symbol: Trading pair symbol

        Returns:
            Order object with current status and fill information
        """
        if not self.api_key or not self.api_secret:
            raise Exception("Invex: API key and secret required for get order")

        client = await self._get_client()
        endpoint = "/order"
        
        # Invex get order requires expire_at and signature
        expire_at = int(time.time()) + 60
        params = {
            "order_id": order_id,
            "expire_at": expire_at,
        }

        # Create message for signing
        body_data = {k: str(v) for k, v in params.items()}
        message = json.dumps(body_data, sort_keys=True, separators=(",", ":"))
        signature = self._generate_signature(message)

        headers = self._get_headers("GET", endpoint)
        headers["X-API-Key-Invex"] = self.api_key
        headers["X-API-Sign"] = signature
        headers["X-API-Expire-At"] = str(expire_at)

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            order_data = data.get("order", {})
            if not order_data:
                raise Exception(f"Order {order_id} not found")

            # Map Invex order status to our format
            status_map = {
                "NOT_FILLED": "pending",
                "PARTIALLY_FILLED": "pending",
                "FULL_FILLED": "filled",
                "CANCELED_BY_USER": "cancelled",
                "CANCELED_BY_MATCH_ENGINE": "cancelled",
            }
            invex_status = order_data.get("status", "NOT_FILLED")
            status = status_map.get(invex_status, "pending")

            return Order(
                order_id=str(order_data.get("order_id", order_id)),
                symbol=order_data.get("symbol", symbol),
                side="buy" if order_data.get("side") == "BUYER" else "sell",
                order_type=order_data.get("type", "LIMIT").lower(),
                quantity=float(order_data.get("quantity", 0)),
                price=float(order_data.get("price", 0)) if order_data.get("price") else None,
                status=status,
                filled_quantity=float(order_data.get("deal_quantity", 0)),
                timestamp=float(order_data.get("created_at", time.time())),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception(f"Order {order_id} not found on Invex")
            raise Exception(f"Failed to fetch order from Invex: {e}") from e
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch order from Invex: {e}") from e

    async def fetch_ohlc(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
    ) -> list[OHLCData]:
        """
        Fetch OHLC data from Invex.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCIRT')
            interval: Time interval (e.g., '1m', '5m', '1h', '1d')
            limit: Number of candles to fetch

        Returns:
            List of OHLCData objects
        """
        client = await self._get_client()
        # Invex OHLC endpoint (may vary - adjust based on actual API)
        # Note: This endpoint may not be available in the public API
        endpoint = "/market/klines"
        
        # Convert symbol format
        invex_symbol = self._convert_symbol_format(symbol)
        
        params = {
            "symbol": invex_symbol,
            "interval": interval,
            "limit": limit,
        }

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=self._get_headers("GET", endpoint),
            )
            response.raise_for_status()
            data = response.json()

            # Normalize response to OHLCData format
            ohlc_list = []
            
            # Try different possible response structures
            candles = []
            if isinstance(data, list):
                candles = data
            elif isinstance(data, dict):
                candles = data.get("data", []) or data.get("klines", []) or []
            
            for candle in candles:
                if isinstance(candle, list) and len(candle) >= 6:
                    # Format: [timestamp, open, high, low, close, volume, ...]
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
                elif isinstance(candle, dict):
                    # Format: {"timestamp": ..., "open": ..., ...}
                    ohlc_list.append(
                        OHLCData(
                            open=float(candle.get("open", 0)),
                            high=float(candle.get("high", 0)),
                            low=float(candle.get("low", 0)),
                            close=float(candle.get("close", 0)),
                            volume=float(candle.get("volume", 0)),
                            timestamp=float(candle.get("timestamp", 0)) / 1000.0,
                            symbol=symbol,
                        )
                    )
            
            return ohlc_list
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch OHLC from Invex: {e}") from e
