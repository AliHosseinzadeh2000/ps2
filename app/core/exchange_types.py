"""Exchange name and trading symbol types and utilities."""

from enum import Enum
from typing import Optional


class TradingSymbol(str, Enum):
    """Trading pair symbol enumeration.

    Uses standard format with canonical quote currencies:
    - IRT for Iranian markets (IRR and TMN are normalized to IRT)
    - USDT for international markets

    Exchanges will convert to their required format internally.
    Symbol converter normalizes IRR/TMN to IRT automatically.
    """

    # Bitcoin pairs
    BTCUSDT = "BTCUSDT"
    BTCIRT = "BTCIRT"  # Canonical form for Iranian markets (IRR/TMN are normalized to this)

    # Ethereum pairs
    ETHUSDT = "ETHUSDT"
    ETHIRT = "ETHIRT"  # Canonical form for Iranian markets (IRR/TMN are normalized to this)

    # Add more common pairs as needed
    # LTCUSDT = "LTCUSDT"
    # etc.

    @classmethod
    def from_string(cls, value: str) -> "TradingSymbol":
        """
        Convert string to TradingSymbol enum (case-insensitive, with normalization).

        Normalizes Iranian currencies (IRR, TMN) to IRT before matching.

        Args:
            value: String value (e.g., "btcusdt", "BTCIRR", "BTCTMN")

        Returns:
            TradingSymbol enum value

        Raises:
            ValueError: If symbol is not recognized
        """
        if not value:
            raise ValueError("Trading symbol cannot be empty")

        # Import here to avoid circular dependency
        from app.utils.symbol_converter import SymbolConverter

        # Normalize the symbol (handles IRR->IRT, TMN->IRT conversion)
        normalized_value = SymbolConverter.normalize_symbol(value)

        for symbol in cls:
            if symbol.value == normalized_value:
                return symbol

        raise ValueError(
            f"Unknown trading symbol: '{value}' (normalized to '{normalized_value}'). "
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
