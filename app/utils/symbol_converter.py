"""Symbol conversion utilities for handling different exchange formats and quote currencies."""

from typing import Dict, Optional, Tuple, List
from app.core.exchange_types import ExchangeName
from app.core.logging import get_logger

logger = get_logger(__name__)


class SymbolConverter:
    """Handles symbol conversion between exchanges and formats."""

    # Exchange quote currency mapping
    # Maps exchange to their default quote currencies
    # Note: IRT, IRR, and TMN are the same currency (Iranian Toman/Rial)
    # Different exchanges use different names for the same currency
    EXCHANGE_QUOTE_CURRENCIES: Dict[ExchangeName, List[str]] = {
        ExchangeName.NOBITEX: ["IRT"],  # Nobitex uses IRT
        ExchangeName.INVEX: ["USDT", "IRR"],  # Invex supports USDT and IRR
        ExchangeName.WALLEX: ["USDT", "TMN"],  # Wallex uses USDT and TMN (Toman)
        ExchangeName.KUCOIN: ["USDT"],  # KuCoin uses USDT
        ExchangeName.TABDEAL: ["IRT"],  # Tabdeal uses IRT
    }
    
    # Iranian currency aliases (all refer to the same currency)
    IRANIAN_CURRENCY_ALIASES = ["IRT", "IRR", "TMN"]

    # Symbol format converters per exchange
    @staticmethod
    def convert_to_exchange_format(symbol: str, exchange: ExchangeName) -> str:
        """
        Convert standard symbol format to exchange-specific format.

        Args:
            symbol: Standard symbol (e.g., "BTCUSDT", "BTCIRT")
            exchange: Target exchange

        Returns:
            Exchange-specific symbol format
        """
        if not symbol:
            return symbol

        # Extract base and quote currency
        base, quote = SymbolConverter._parse_symbol(symbol)
        if not base or not quote:
            return symbol  # Return as-is if can't parse

        # Exchange-specific format conversion
        if exchange == ExchangeName.KUCOIN:
            # KuCoin uses hyphen: BTC-USDT
            return f"{base}-{quote}"
        elif exchange == ExchangeName.INVEX:
            # Invex uses underscore: BTC_USDT, BTC_IRR
            return f"{base}_{quote}"
        else:
            # Nobitex, Wallex, Tabdeal use no separator: BTCUSDT, BTCIRT
            return f"{base}{quote}"

    @staticmethod
    def _parse_symbol(symbol: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse symbol into base and quote currency.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "BTC-USDT", "BTC_USDT")

        Returns:
            Tuple of (base_currency, quote_currency) or (None, None) if can't parse
        """
        if not symbol:
            return None, None

        # Remove separators
        clean_symbol = symbol.replace("-", "").replace("_", "").upper()

        # Common base currencies (order matters - longer symbols first to avoid partial matches)
        # USDT must come before USDC to avoid matching USDC as USD+C
        base_currencies = ["BTC", "ETH", "LTC", "USDT", "USDC", "BNB", "ADA", "DOT", "LINK", "XRP", "BCH", "EOS", "XLM", "ETC", "TRX", "DOGE", "UNI", "DAI", "AAVE", "SHIB", "FTM", "MATIC", "AXS", "MANA", "SAND", "AVAX", "MKR", "GMT", "ATOM", "SOL", "NEAR", "TON", "FIL", "APT", "ARB"]
        quote_currencies = ["USDT", "USDC", "IRT", "IRR", "TMN", "BTC", "ETH"]

        # Try to find base currency first (prioritize longer matches)
        # Sort by length descending to match longer symbols first
        sorted_bases = sorted(base_currencies, key=len, reverse=True)
        for base in sorted_bases:
            if clean_symbol.startswith(base):
                quote = clean_symbol[len(base):]
                if quote in quote_currencies:
                    return base, quote

        # Fallback: try to split at quote currency (prioritize longer quotes)
        sorted_quotes = sorted(quote_currencies, key=len, reverse=True)
        for quote in sorted_quotes:
            if clean_symbol.endswith(quote):
                base = clean_symbol[:-len(quote)]
                if base and base in base_currencies:
                    return base, quote

        logger.warning(f"Could not parse symbol: {symbol}")
        return None, None

    @staticmethod
    def get_exchange_symbols_for_base(
        base_currency: str, exchange: ExchangeName
    ) -> List[str]:
        """
        Get all possible symbols for a base currency on an exchange.

        Args:
            base_currency: Base currency (e.g., "BTC", "ETH")
            exchange: Target exchange

        Returns:
            List of possible symbols (e.g., ["BTCUSDT", "BTCIRT"] for base="BTC")
        """
        quotes = SymbolConverter.EXCHANGE_QUOTE_CURRENCIES.get(exchange, ["USDT"])
        symbols = []
        for quote in quotes:
            symbol = f"{base_currency}{quote}"
            converted = SymbolConverter.convert_to_exchange_format(symbol, exchange)
            symbols.append(converted)
        return symbols

    @staticmethod
    def find_compatible_symbols(
        symbol: str, exchanges: List[ExchangeName]
    ) -> Dict[ExchangeName, Optional[str]]:
        """
        Find compatible symbols across exchanges for arbitrage.

        Args:
            symbol: Input symbol (e.g., "BTCUSDT", "BTCIRT")
            exchanges: List of exchanges to check

        Returns:
            Dictionary mapping exchange to compatible symbol (or None if not available)
            
        Note:
            Only IRT/IRR are considered compatible (same currency).
            IRT/USDT are NOT compatible (different markets).
        """
        base, quote = SymbolConverter._parse_symbol(symbol)
        if not base or not quote:
            return {ex: None for ex in exchanges}

        result = {}
        for exchange in exchanges:
            # Check if exchange supports this quote currency OR compatible one (IRT/IRR)
            supported_quotes = SymbolConverter.EXCHANGE_QUOTE_CURRENCIES.get(exchange, [])
            
            # Check exact match first
            if quote in supported_quotes:
                converted = SymbolConverter.convert_to_exchange_format(f"{base}{quote}", exchange)
                result[exchange] = converted
            else:
                # Check for compatible quote currency (IRT/IRR/TMN are all the same)
                iranian_currencies = SymbolConverter.IRANIAN_CURRENCY_ALIASES
                compatible_quote = None
                
                if quote.upper() in iranian_currencies:
                    # Find which Iranian currency the exchange supports
                    for iranian_quote in iranian_currencies:
                        if iranian_quote in supported_quotes:
                            compatible_quote = iranian_quote
                            break
                
                if compatible_quote:
                    converted = SymbolConverter.convert_to_exchange_format(f"{base}{compatible_quote}", exchange)
                    result[exchange] = converted
                else:
                    # No compatible quote currency found
                    result[exchange] = None

        return result

    @staticmethod
    def get_base_currency(symbol: str) -> Optional[str]:
        """Extract base currency from symbol."""
        base, _ = SymbolConverter._parse_symbol(symbol)
        return base

    @staticmethod
    def get_quote_currency(symbol: str) -> Optional[str]:
        """Extract quote currency from symbol."""
        _, quote = SymbolConverter._parse_symbol(symbol)
        return quote

    @staticmethod
    def are_quote_currencies_compatible(quote1: str, quote2: str) -> bool:
        """
        Check if two quote currencies are compatible for arbitrage.
        
        IRT, IRR, and TMN are all the same currency (Iranian Toman/Rial).
        All other currencies are NOT compatible (e.g., IRT != USDT).

        Args:
            quote1: First quote currency
            quote2: Second quote currency

        Returns:
            True if quote currencies are compatible
        """
        if quote1 == quote2:
            return True
        
        # IRT, IRR, and TMN are all the same currency (Iranian Toman/Rial)
        # Different exchanges use different names for the same currency
        iranian_currencies = SymbolConverter.IRANIAN_CURRENCY_ALIASES
        if quote1.upper() in iranian_currencies and quote2.upper() in iranian_currencies:
            return True
        
        return False

    @staticmethod
    def are_compatible_for_arbitrage(symbol1: str, symbol2: str) -> bool:
        """
        Check if two symbols are compatible for arbitrage.

        For arbitrage, we need:
        - Same base currency (e.g., BTC)
        - Same quote currency (e.g., USDT) OR compatible quote currencies (IRT/IRR only)

        Args:
            symbol1: First symbol
            symbol2: Second symbol

        Returns:
            True if symbols are compatible for arbitrage
        """
        base1, quote1 = SymbolConverter._parse_symbol(symbol1)
        base2, quote2 = SymbolConverter._parse_symbol(symbol2)

        if not base1 or not base2 or not quote1 or not quote2:
            return False

        # Base currencies must match
        if base1 != base2:
            return False

        # Quote currencies must match OR be IRT/IRR (same currency)
        return SymbolConverter.are_quote_currencies_compatible(quote1, quote2)

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        Normalize symbol to standard format (no separators, uppercase, canonical quote currency).

        Normalizes Iranian currencies to IRT (the canonical form):
        - IRR -> IRT
        - TMN -> IRT

        Args:
            symbol: Any symbol format (e.g., "BTC-USDT", "BTCIRR", "BTC_TMN")

        Returns:
            Normalized symbol (e.g., "BTCUSDT", "BTCIRT")
        """
        if not symbol:
            return symbol

        # Remove separators and convert to uppercase
        clean_symbol = symbol.replace("-", "").replace("_", "").upper()

        # Parse to get base and quote currencies
        base, quote = SymbolConverter._parse_symbol(clean_symbol)
        if not base or not quote:
            return clean_symbol  # Return as-is if can't parse

        # Normalize Iranian currencies to IRT (canonical form)
        if quote in ["IRR", "TMN"]:
            quote = "IRT"

        return f"{base}{quote}"


class ExchangeSymbolMapper:
    """Maps symbols between exchanges for arbitrage opportunities."""

    @staticmethod
    def get_symbol_for_exchange(
        base_symbol: str, exchange: ExchangeName
    ) -> Optional[str]:
        """
        Get the correct symbol format for an exchange given a base symbol.

        Args:
            base_symbol: Base symbol in standard format (e.g., "BTCUSDT", "BTCIRT")
            exchange: Target exchange

        Returns:
            Exchange-specific symbol or None if not supported
            
        Note:
            Only allows IRT/IRR conversion (same currency).
            Does NOT convert IRT to USDT (different markets).
        """
        base, quote = SymbolConverter._parse_symbol(base_symbol)
        if not base or not quote:
            return None

        # Check if exchange supports this quote currency
        supported_quotes = SymbolConverter.EXCHANGE_QUOTE_CURRENCIES.get(exchange, [])
        
        # Check exact match first
        if quote in supported_quotes:
            return SymbolConverter.convert_to_exchange_format(f"{base}{quote}", exchange)
        
        # Check for compatible quote currency (IRT/IRR/TMN are all the same currency)
        iranian_currencies = SymbolConverter.IRANIAN_CURRENCY_ALIASES
        compatible_quote = None
        
        if quote.upper() in iranian_currencies:
            # We have an Iranian currency, find which one the exchange supports
            for iranian_quote in iranian_currencies:
                if iranian_quote in supported_quotes:
                    compatible_quote = iranian_quote
                    break
        
        # Also handle case where exchange doesn't explicitly list all Iranian currency aliases
        if not compatible_quote and quote.upper() in iranian_currencies:
            if exchange in [ExchangeName.NOBITEX, ExchangeName.TABDEAL]:
                compatible_quote = "IRT"
            elif exchange == ExchangeName.INVEX:
                compatible_quote = "IRR"
            elif exchange == ExchangeName.WALLEX:
                compatible_quote = "TMN"
        
        if compatible_quote:
            return SymbolConverter.convert_to_exchange_format(f"{base}{compatible_quote}", exchange)
        
        # No compatible quote currency found
        return None

    @staticmethod
    def get_common_symbols(
        exchanges: List[ExchangeName], base_currency: str, quote_currency: str
    ) -> Dict[ExchangeName, str]:
        """
        Get symbols for a base/quote pair across multiple exchanges.

        Args:
            exchanges: List of exchanges
            base_currency: Base currency (e.g., "BTC")
            quote_currency: Quote currency (e.g., "USDT")
            exchanges: List of exchanges

        Returns:
            Dictionary mapping exchange to symbol (only includes exchanges that support the pair)
        """
        result = {}
        standard_symbol = f"{base_currency}{quote_currency}"

        for exchange in exchanges:
            supported_quotes = SymbolConverter.EXCHANGE_QUOTE_CURRENCIES.get(exchange, [])
            if quote_currency in supported_quotes:
                symbol = SymbolConverter.convert_to_exchange_format(standard_symbol, exchange)
                result[exchange] = symbol

        return result


