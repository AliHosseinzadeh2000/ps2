"""Custom exceptions for exchange operations."""


class ExchangeError(Exception):
    """Base exception for exchange-related errors."""

    def __init__(self, message: str, exchange_name: str = "", details: dict = None):
        """
        Initialize exchange error.

        Args:
            message: Error message
            exchange_name: Name of the exchange
            details: Additional error details
        """
        super().__init__(message)
        self.exchange_name = exchange_name
        self.details = details or {}


class ExchangeAuthenticationError(ExchangeError):
    """Raised when authentication fails."""

    pass


class ExchangeAPIError(ExchangeError):
    """Raised when API returns an error response."""

    def __init__(self, message: str, exchange_name: str = "", status_code: int = None, response_data: dict = None):
        """
        Initialize API error.

        Args:
            message: Error message
            exchange_name: Name of the exchange
            status_code: HTTP status code
            response_data: API response data
        """
        super().__init__(message, exchange_name, {"status_code": status_code, "response": response_data})
        self.status_code = status_code
        self.response_data = response_data


class ExchangeNetworkError(ExchangeError):
    """Raised when network/connection errors occur."""

    pass


class ExchangeOrderError(ExchangeError):
    """Raised when order operations fail."""

    def __init__(self, message: str, exchange_name: str = "", order_id: str = None, symbol: str = None):
        """
        Initialize order error.

        Args:
            message: Error message
            exchange_name: Name of the exchange
            order_id: Order ID if applicable
            symbol: Trading symbol if applicable
        """
        super().__init__(message, exchange_name, {"order_id": order_id, "symbol": symbol})
        self.order_id = order_id
        self.symbol = symbol


class ExchangeOrderNotFoundError(ExchangeOrderError):
    """Raised when an order is not found."""

    pass


class ExchangeInsufficientBalanceError(ExchangeError):
    """Raised when there's insufficient balance for an operation."""

    def __init__(self, message: str, exchange_name: str = "", currency: str = None, required: float = None, available: float = None):
        """
        Initialize insufficient balance error.

        Args:
            message: Error message
            exchange_name: Name of the exchange
            currency: Currency code
            required: Required amount
            available: Available amount
        """
        super().__init__(message, exchange_name, {"currency": currency, "required": required, "available": available})
        self.currency = currency
        self.required = required
        self.available = available


class ExchangeRateLimitError(ExchangeAPIError):
    """Raised when rate limit is exceeded."""

    pass


class ExchangeInvalidSymbolError(ExchangeError):
    """Raised when an invalid trading symbol is used."""

    def __init__(self, message: str, exchange_name: str = "", symbol: str = None):
        """
        Initialize invalid symbol error.

        Args:
            message: Error message
            exchange_name: Name of the exchange
            symbol: Invalid symbol
        """
        super().__init__(message, exchange_name, {"symbol": symbol})
        self.symbol = symbol

