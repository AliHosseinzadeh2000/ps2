"""Exchange name and trading symbol types and utilities."""

from enum import Enum
from typing import Optional


class TradingSymbol(str, Enum):
    """Trading pair symbol enumeration.
    
    Uses standard format (e.g., BTCUSDT, BTCIRT). Exchanges will convert
    to their required format internally.
    """

    # Bitcoin pairs
    BTCUSDT = "BTCUSDT"
    BTCIRT = "BTCIRT"
    BTCIRR = "BTCIRR"

    # Ethereum pairs
    ETHUSDT = "ETHUSDT"
    ETHIRT = "ETHIRT"
    ETHIRR = "ETHIRR"

    # Add more common pairs as needed
    # USDTUSDT = "USDTUSDT"  # If needed
    # LTCUSDT = "LTCUSDT"
    # etc.

    @classmethod
    def from_string(cls, value: str) -> "TradingSymbol":
        """
        Convert string to TradingSymbol enum (case-insensitive).

        Args:
            value: String value (e.g., "btcusdt", "BTCUSDT", "BtcUsdt")

        Returns:
            TradingSymbol enum value

        Raises:
            ValueError: If symbol is not recognized
        """
        if not value:
            raise ValueError("Trading symbol cannot be empty")

        value_upper = value.upper().strip()
        for symbol in cls:
            if symbol.value == value_upper:
                return symbol

        raise ValueError(
            f"Unknown trading symbol: '{value}'. "
            f"Available symbols: {[s.value for s in cls]}"
        )

    def __str__(self) -> str:
        """String representation returns the enum value."""
        return self.value

    @classmethod
    def all_symbols(cls) -> list[str]:
        """
        Get all trading symbols as strings.

        Returns:
            List of all trading symbols in uppercase
        """
        return [s.value for s in cls]


class ExchangeName(str, Enum):
    """Exchange name enumeration with case-insensitive support."""

    NOBITEX = "NOBITEX"
    INVEX = "INVEX"
    WALLEX = "WALLEX"
    KUCOIN = "KUCOIN"
    TABDEAL = "TABDEAL"

    @classmethod
    def from_string(cls, value: str) -> "ExchangeName":
        """
        Convert string to ExchangeName enum (case-insensitive).

        Args:
            value: String value (e.g., "nobitex", "NOBITEX", "Nobitex")

        Returns:
            ExchangeName enum value

        Raises:
            ValueError: If exchange name is not recognized
        """
        if not value:
            raise ValueError("Exchange name cannot be empty")

        value_upper = value.upper().strip()
        for exchange in cls:
            if exchange.value == value_upper:
                return exchange

        raise ValueError(
            f"Unknown exchange name: '{value}'. "
            f"Available exchanges: {[e.value for e in cls]}"
        )

    def to_string(self) -> str:
        """
        Convert enum to lowercase string for use in API keys.

        Returns:
            Lowercase string (e.g., "nobitex")
        """
        return self.value.lower()

    def __str__(self) -> str:
        """String representation returns the enum value."""
        return self.value

    @classmethod
    def all_names(cls) -> list[str]:
        """
        Get all exchange names as strings.

        Returns:
            List of all exchange names in uppercase
        """
        return [e.value for e in cls]

    @classmethod
    def all_names_lower(cls) -> list[str]:
        """
        Get all exchange names as lowercase strings.

        Returns:
            List of all exchange names in lowercase
        """
        return [e.to_string() for e in cls]
