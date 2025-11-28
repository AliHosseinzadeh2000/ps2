"""Integration tests for exchange implementations.

These tests verify that exchange implementations work correctly with real API endpoints
(where possible) or with mocked responses that match real API formats.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Optional

from app.exchanges.nobitex import NobitexExchange
from app.exchanges.invex import InvexExchange
from app.exchanges.wallex import WallexExchange
from app.exchanges.kucoin import KucoinExchange
from app.exchanges.tabdeal import TabdealExchange
from app.core.config import (
    NobitexConfig,
    InvexConfig,
    WallexConfig,
    KucoinConfig,
    TabdealConfig,
)
from app.core.exchange_types import ExchangeName


@pytest.fixture
def nobitex_config():
    """Create Nobitex config for testing."""
    return NobitexConfig(
        base_url="https://apiv2.nobitex.ir",
        token="test_token",
    )


@pytest.fixture
def invex_config():
    """Create Invex config for testing."""
    return InvexConfig(
        base_url="https://api.invex.ir/trading/v1",
        api_key="test_key",
        api_secret="308204bd020100300d06092a864886f70d0101010500048204a7308204a30201000282010100",
    )


@pytest.fixture
def wallex_config():
    """Create Wallex config for testing."""
    return WallexConfig(
        base_url="https://api.wallex.ir",
        api_key="test_key",
        api_secret="test_secret",
    )


@pytest.fixture
def kucoin_config():
    """Create KuCoin config for testing."""
    return KucoinConfig(
        base_url="https://api.kucoin.com",
        api_key="test_key",
        api_secret="test_secret",
        api_passphrase="test_passphrase",
    )


@pytest.fixture
def tabdeal_config():
    """Create Tabdeal config for testing."""
    return TabdealConfig(
        base_url="https://api.tabdeal.org",
        api_key="test_key",
        api_secret="test_secret",
    )


class TestExchangeAuthentication:
    """Test authentication methods for all exchanges."""

    def test_nobitex_authentication_with_token(self, nobitex_config):
        """Test Nobitex authentication with token."""
        exchange = NobitexExchange(nobitex_config)
        assert exchange.is_authenticated() is True

    def test_nobitex_authentication_with_username_password(self):
        """Test Nobitex authentication with username/password."""
        config = NobitexConfig(
            username="test_user",
            password="test_pass",
        )
        exchange = NobitexExchange(config)
        assert exchange.is_authenticated() is True

    def test_nobitex_authentication_no_credentials(self):
        """Test Nobitex authentication without credentials."""
        config = NobitexConfig()
        exchange = NobitexExchange(config)
        assert exchange.is_authenticated() is False

    def test_invex_authentication(self, invex_config):
        """Test Invex authentication."""
        exchange = InvexExchange(invex_config)
        assert exchange.is_authenticated() is True

    def test_invex_authentication_no_credentials(self):
        """Test Invex authentication without credentials."""
        config = InvexConfig()
        exchange = InvexExchange(config)
        assert exchange.is_authenticated() is False

    def test_wallex_authentication(self, wallex_config):
        """Test Wallex authentication."""
        exchange = WallexExchange(wallex_config)
        assert exchange.is_authenticated() is True

    def test_wallex_authentication_no_credentials(self):
        """Test Wallex authentication without credentials."""
        config = WallexConfig()
        exchange = WallexExchange(config)
        assert exchange.is_authenticated() is False

    def test_kucoin_authentication(self, kucoin_config):
        """Test KuCoin authentication."""
        exchange = KucoinExchange(kucoin_config)
        assert exchange.is_authenticated() is True

    def test_kucoin_authentication_no_credentials(self):
        """Test KuCoin authentication without credentials."""
        config = KucoinConfig()
        exchange = KucoinExchange(config)
        assert exchange.is_authenticated() is False

    def test_tabdeal_authentication(self, tabdeal_config):
        """Test Tabdeal authentication."""
        exchange = TabdealExchange(tabdeal_config)
        assert exchange.is_authenticated() is True

    def test_tabdeal_authentication_no_credentials(self):
        """Test Tabdeal authentication without credentials."""
        config = TabdealConfig()
        exchange = TabdealExchange(config)
        assert exchange.is_authenticated() is False


class TestExchangeOrderbook:
    """Test orderbook fetching for all exchanges."""

    @pytest.mark.asyncio
    async def test_nobitex_fetch_orderbook(self, nobitex_config):
        """Test Nobitex orderbook fetching."""
        exchange = NobitexExchange(nobitex_config)
        
        # Mock response
        mock_response = {
            "status": "ok",
            "bids": [["106191000010", "0.004338"], ["106190000000", "0.5"]],
            "asks": [["106192000000", "0.010925"], ["106193000000", "0.5"]],
        }
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=MagicMock(),
            )
            
            orderbook = await exchange.fetch_orderbook("BTCIRT")
            assert orderbook is not None
            assert len(orderbook.bids) == 2
            assert len(orderbook.asks) == 2
            assert orderbook.symbol == "BTCIRT"

    @pytest.mark.asyncio
    async def test_invex_fetch_orderbook(self, invex_config):
        """Test Invex orderbook fetching."""
        exchange = InvexExchange(invex_config)
        
        # Mock response
        mock_response = {
            "bid_orders": [
                {"price": "92231.37", "quantity": "0.012851"},
                {"price": "92230.00", "quantity": "0.5"},
            ],
            "ask_orders": [
                {"price": "92414.78", "quantity": "0.012851"},
                {"price": "92415.00", "quantity": "0.5"},
            ],
        }
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=MagicMock(),
            )
            
            orderbook = await exchange.fetch_orderbook("BTCUSDT")
            assert orderbook is not None
            assert len(orderbook.bids) == 2
            assert len(orderbook.asks) == 2

    @pytest.mark.asyncio
    async def test_wallex_fetch_orderbook(self, wallex_config):
        """Test Wallex orderbook fetching."""
        exchange = WallexExchange(wallex_config)
        
        # Mock response
        mock_response = {
            "success": True,
            "result": {
                "bid": [
                    {"price": "50000.0", "quantity": "1.0"},
                    {"price": "49999.0", "quantity": "2.0"},
                ],
                "ask": [
                    {"price": "50100.0", "quantity": "1.0"},
                    {"price": "50101.0", "quantity": "2.0"},
                ],
            },
        }
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=MagicMock(),
            )
            
            orderbook = await exchange.fetch_orderbook("BTCUSDT")
            assert orderbook is not None
            assert len(orderbook.bids) == 2
            assert len(orderbook.asks) == 2
            assert orderbook.symbol == "BTCUSDT"


class TestExchangeErrorHandling:
    """Test error handling for all exchanges."""

    @pytest.mark.asyncio
    async def test_orderbook_http_error(self, nobitex_config):
        """Test handling of HTTP errors in orderbook fetching."""
        import httpx
        
        exchange = NobitexExchange(nobitex_config)
        
        # Mock httpx.HTTPError (which is what httpx actually raises)
        with patch("httpx.AsyncClient.get") as mock_get:
            # Create a proper httpx.HTTPError
            mock_error = httpx.HTTPError("Connection error")
            mock_get.side_effect = mock_error
            
            # After retries, should raise ExchangeNetworkError
            from app.exchanges.exceptions import ExchangeNetworkError
            with pytest.raises((ExchangeNetworkError, Exception)) as exc_info:
                await exchange.fetch_orderbook("BTCIRT")
            # The error should mention network or connection
            assert "Network error" in str(exc_info.value) or "Connection error" in str(exc_info.value) or "Connection error" == str(exc_info.value)

    @pytest.mark.asyncio
    async def test_orderbook_invalid_response(self, wallex_config):
        """Test handling of invalid API responses."""
        exchange = WallexExchange(wallex_config)
        
        mock_response = {"success": False, "error": "Invalid symbol"}
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = AsyncMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=MagicMock(),
            )
            
            with pytest.raises(Exception) as exc_info:
                await exchange.fetch_orderbook("INVALID")
            assert "Invalid Wallex response" in str(exc_info.value)


class TestExchangeSymbolConversion:
    """Test symbol format conversion for exchanges that need it."""

    def test_invex_symbol_conversion(self, invex_config):
        """Test Invex symbol format conversion."""
        exchange = InvexExchange(invex_config)
        
        assert exchange._convert_symbol_format("BTCUSDT") == "BTC_USDT"
        assert exchange._convert_symbol_format("BTCIRT") == "BTC_IRR"
        assert exchange._convert_symbol_format("BTC_USDT") == "BTC_USDT"  # Already correct

    def test_kucoin_symbol_conversion(self, kucoin_config):
        """Test KuCoin symbol format conversion."""
        exchange = KucoinExchange(kucoin_config)
        
        # Test conversion
        assert exchange._convert_symbol_format("BTCUSDT") == "BTC-USDT"
        assert exchange._convert_symbol_format("ETHUSDT") == "ETH-USDT"
        assert exchange._convert_symbol_format("BTC-USDT") == "BTC-USDT"  # Already correct
        
        # Test edge cases
        assert exchange._convert_symbol_format("BTCBTC") == "BTC-BTC"  # Generic conversion


class TestExchangeMethods:
    """Test that all required methods are implemented."""

    def test_all_exchanges_have_required_methods(self):
        """Verify all exchanges implement required methods."""
        required_methods = [
            "fetch_orderbook",
            "place_order",
            "cancel_order",
            "get_order",
            "get_balance",
            "fetch_ohlc",
            "get_open_orders",
            "is_authenticated",
        ]
        
        exchanges = [
            NobitexExchange(NobitexConfig()),
            InvexExchange(InvexConfig()),
            WallexExchange(WallexConfig()),
            KucoinExchange(KucoinConfig()),
            TabdealExchange(TabdealConfig()),
        ]
        
        for exchange in exchanges:
            for method in required_methods:
                assert hasattr(exchange, method), f"{exchange.__class__.__name__} missing {method}"
                assert callable(getattr(exchange, method)), f"{exchange.__class__.__name__}.{method} is not callable"

