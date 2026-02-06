"""KuCoin exchange implementation."""

import base64
import hashlib
import hmac
import time
from typing import Dict, Optional

import httpx

from app.core.config import KucoinConfig
from app.exchanges.base import (
    Balance,
    ExchangeInterface,
    OHLCData,
    Order,
    OrderBook,
    OrderBookEntry,
)


class KucoinExchange(ExchangeInterface):
    """KuCoin exchange client implementation."""

    def __init__(self, config: Optional[KucoinConfig] = None) -> None:
        """
        Initialize KuCoin exchange client.

        Args:
            config: KuCoin configuration (uses default if not provided)
        """
        if config is None:
            config = KucoinConfig()
        super().__init__(config)
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        self.api_passphrase = config.api_passphrase if hasattr(config, "api_passphrase") else ""
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
        Check if KuCoin has valid authentication credentials.

        Returns:
            True if api_key AND api_secret AND api_passphrase are configured
        """
        return bool(self.api_key) and bool(self.api_secret) and bool(self.api_passphrase)

    def _convert_symbol_format(self, symbol: str) -> str:
        """
        Convert symbol format to KuCoin format (with hyphen).
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT', 'BTC-USDT')
            
        Returns:
            KuCoin format symbol (e.g., 'BTC-USDT')
        """
        if '-' in symbol:
            return symbol  # Already in correct format
        
        # Convert format like BTCUSDT to BTC-USDT
        # Try common patterns
        if symbol.endswith('USDT'):
            base = symbol[:-4]
            return f"{base}-USDT"
        elif symbol.endswith('BTC'):
            base = symbol[:-3]
            return f"{base}-BTC"
        elif symbol.endswith('ETH'):
            base = symbol[:-3]
            return f"{base}-ETH"
        else:
            # Generic: split at 3 or 4 character boundary
            # This is a heuristic and may not work for all symbols
            if len(symbol) >= 6:
                # Try splitting at common boundaries
                for split_pos in [3, 4]:
                    if split_pos < len(symbol):
                        return f"{symbol[:split_pos]}-{symbol[split_pos:]}"
            return symbol  # Return as-is if can't convert

    def _generate_signature(
        self, timestamp: str, method: str, endpoint: str, body: str = ""
    ) -> str:
        """
        Generate KuCoin signature.

        Args:
            timestamp: Request timestamp
            method: HTTP method
            endpoint: API endpoint
            body: Request body

        Returns:
            Signature string
        """
        message = timestamp + method + endpoint + body
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode(),
                message.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()
        return signature

    def _get_headers(
        self, method: str, endpoint: str, signed: bool = False, body: str = ""
    ) -> Dict[str, str]:
        """
        Get request headers.

        Args:
            method: HTTP method
            endpoint: API endpoint
            signed: Whether to include authentication headers
            body: Request body

        Returns:
            Headers dictionary
        """
        headers = {"Content-Type": "application/json"}
        if signed and self.api_key:
            timestamp = str(int(time.time() * 1000))
            signature = self._generate_signature(timestamp, method, endpoint, body)
            # KuCoin requires passphrase to be signed
            passphrase_signature = base64.b64encode(
                hmac.new(
                    self.api_secret.encode(),
                    self.api_passphrase.encode() if self.api_passphrase else b"",
                    hashlib.sha256,
                ).digest()
            ).decode()
            
            headers["KC-API-KEY"] = self.api_key
            headers["KC-API-SIGN"] = signature
            headers["KC-API-TIMESTAMP"] = timestamp
            headers["KC-API-PASSPHRASE"] = passphrase_signature
            headers["KC-API-KEY-VERSION"] = "2"
        return headers

    async def fetch_orderbook(
        self, symbol: str, depth: int = 20
    ) -> OrderBook:
        """
        Fetch order book from KuCoin.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC-USDT')
            depth: Number of price levels

        Returns:
            OrderBook object
        """
        client = await self._get_client()
        # KuCoin uses hyphenated symbols (BTC-USDT)
        # Convert symbol format: BTCUSDT -> BTC-USDT
        if "-" not in symbol:
            # Try to split common patterns
            if symbol.endswith("USDT"):
                base = symbol[:-4]
                kucoin_symbol = f"{base}-USDT"
            elif symbol.endswith("USD"):
                base = symbol[:-3]
                kucoin_symbol = f"{base}-USD"
            else:
                # Default: assume first 3 chars are base, rest is quote
                if len(symbol) >= 6:
                    kucoin_symbol = f"{symbol[:3]}-{symbol[3:]}"
                else:
                    kucoin_symbol = symbol
        else:
            kucoin_symbol = symbol
        
        endpoint = f"/api/v1/market/orderbook/level2_{depth}"
        params = {"symbol": kucoin_symbol}

        try:
            response = await client.get(
                endpoint,
                params=params,
                headers=self._get_headers("GET", endpoint),
            )
            response.raise_for_status()
            data = response.json()

            # Normalize response to OrderBook format
            # KuCoin returns: {"data": {"bids": [[price, size]], "asks": [[price, size]]}}
            orderbook_data = data.get("data", {})
            bids = [
                OrderBookEntry(price=float(bid[0]), quantity=float(bid[1]))
                for bid in orderbook_data.get("bids", [])[:depth]
            ]
            asks = [
                OrderBookEntry(price=float(ask[0]), quantity=float(ask[1]))
                for ask in orderbook_data.get("asks", [])[:depth]
            ]

            return OrderBook(
                bids=bids,
                asks=asks,
                timestamp=time.time(),
                symbol=symbol,
            )
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch orderbook from KuCoin: {e}") from e

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
        Place an order on KuCoin.

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

        # KuCoin uses hyphenated symbols (BTC-USDT)
        # Convert symbol format: BTCUSDT -> BTC-USDT
        if "-" not in symbol:
            if symbol.endswith("USDT"):
                base = symbol[:-4]
                kucoin_symbol = f"{base}-USDT"
            elif symbol.endswith("USD"):
                base = symbol[:-3]
                kucoin_symbol = f"{base}-USD"
            else:
                # Default: assume first 3 chars are base, rest is quote
                if len(symbol) >= 6:
                    kucoin_symbol = f"{symbol[:3]}-{symbol[3:]}"
                else:
                    kucoin_symbol = symbol
        else:
            kucoin_symbol = symbol

        # NOTE: is_maker parameter is currently ignored (Phase 2 limitation)
        # TODO PHASE 3: Implement proper maker/taker support with price buffering
        payload = {
            "clientOid": f"arbitrage_{int(time.time() * 1000)}",
            "side": side.lower(),
            "symbol": kucoin_symbol,
            "type": order_type.lower(),
            "size": str(quantity),
        }

        if order_type == "limit":
            payload["price"] = str(price)

        # postOnly removed - Phase 2 uses taker mode only

        body = str(payload)
        try:
            response = await client.post(
                endpoint,
                json=payload,
                headers=self._get_headers("POST", endpoint, signed=True, body=body),
            )
            response.raise_for_status()
            data = response.json()

            return Order(
                order_id=str(data.get("data", {}).get("orderId", "")),
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status="pending",
                timestamp=time.time(),
            )
        except httpx.HTTPError as e:
            raise Exception(f"Failed to place order on KuCoin: {e}") from e

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order on KuCoin.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            True if successful
        """
        client = await self._get_client()
        endpoint = f"/api/v1/orders/{order_id}"

        try:
            response = await client.delete(
                endpoint,
                headers=self._get_headers("DELETE", endpoint, signed=True),
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """
        Get order details by order ID from KuCoin.

        Args:
            order_id: Order ID to fetch
            symbol: Trading pair symbol

        Returns:
            Order object with current status and fill information
        """
        client = await self._get_client()
        endpoint = f"/api/v1/orders/{order_id}"

        # Convert symbol format
        if "-" not in symbol:
            if symbol.endswith("USDT"):
                base = symbol[:-4]
                kucoin_symbol = f"{base}-USDT"
            elif symbol.endswith("USD"):
                base = symbol[:-3]
                kucoin_symbol = f"{base}-USD"
            else:
                if len(symbol) >= 6:
                    kucoin_symbol = f"{symbol[:3]}-{symbol[3:]}"
                else:
                    kucoin_symbol = symbol
        else:
            kucoin_symbol = symbol

        try:
            response = await client.get(
                endpoint,
                params={"symbol": kucoin_symbol},
                headers=self._get_headers("GET", endpoint, signed=True),
            )
            response.raise_for_status()
            data = response.json()

            order_data = data.get("data", {})
            if not order_data:
                raise Exception(f"Order {order_id} not found")

            # Map KuCoin status to our format
            status_map = {
                "open": "pending",
                "done": "filled",
                "match": "pending",  # Partially filled
                "cancel": "cancelled",
            }
            kucoin_status = order_data.get("status", "open")
            status = status_map.get(kucoin_status, "pending")

            return Order(
                order_id=str(order_data.get("id", order_id)),
                symbol=symbol,
                side=order_data.get("side", "").lower(),
                order_type=order_data.get("type", "limit").lower(),
                quantity=float(order_data.get("size", 0)),
                price=float(order_data.get("price", 0)) if order_data.get("price") else None,
                status=status,
                filled_quantity=float(order_data.get("dealSize", 0)),
                timestamp=float(order_data.get("createdAt", time.time()) / 1000),  # KuCoin uses milliseconds
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception(f"Order {order_id} not found on KuCoin")
            raise Exception(f"Failed to fetch order from KuCoin: {e}") from e
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch order from KuCoin: {e}") from e

    async def get_balance(
        self, currency: Optional[str] = None
    ) -> Dict[str, Balance]:
        """
        Get account balance from KuCoin.

        Args:
            currency: Specific currency (None for all)

        Returns:
            Dictionary of balances
        """
        client = await self._get_client()
        endpoint = "/api/v1/accounts"

        try:
            response = await client.get(
                endpoint,
                headers=self._get_headers("GET", endpoint, signed=True),
            )
            response.raise_for_status()
            data = response.json()

            balances = {}
            accounts = data.get("data", [])

            for account in accounts:
                curr = account.get("currency", "").upper()
                if currency and curr != currency.upper():
                    continue

                balances[curr] = Balance(
                    currency=curr,
                    available=float(account.get("available", 0)),
                    locked=float(account.get("holds", 0)),
                )

            return balances
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch balance from KuCoin: {e}") from e

    async def fetch_ohlc(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
    ) -> list[OHLCData]:
        """
        Fetch OHLC data from KuCoin.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC-USDT')
            interval: Time interval (e.g., '1min', '5min', '1hour', '1day')
            limit: Number of candles to fetch

        Returns:
            List of OHLCData objects
        """
        client = await self._get_client()
        # KuCoin uses hyphenated symbols
        kucoin_symbol = symbol.replace("USDT", "-USDT").replace("BTC", "BTC-")
        # Map interval format
        interval_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "1h": "1hour",
            "4h": "4hour",
            "1d": "1day",
        }
        kucoin_interval = interval_map.get(interval, interval)

        endpoint = "/api/v1/market/candles"
        params = {
            "symbol": kucoin_symbol,
            "type": kucoin_interval,
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
            # KuCoin format: {"data": [[time, open, close, high, low, volume, amount], ...]}
            ohlc_list = []
            candles = data.get("data", [])
            for candle in candles[:limit]:
                if isinstance(candle, list) and len(candle) >= 6:
                    ohlc_list.append(
                        OHLCData(
                            open=float(candle[1]),
                            high=float(candle[3]),
                            low=float(candle[4]),
                            close=float(candle[2]),
                            volume=float(candle[5]),
                            timestamp=float(candle[0]),
                            symbol=symbol,
                        )
                    )
            return ohlc_list
        except httpx.HTTPError as e:
            raise Exception(f"Failed to fetch OHLC from KuCoin: {e}") from e

