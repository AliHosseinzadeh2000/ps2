"""Helper utilities for exchange implementations."""

from typing import Callable, TypeVar, Optional
import httpx

from app.exchanges.exceptions import (
    ExchangeAPIError,
    ExchangeAuthenticationError,
    ExchangeNetworkError,
    ExchangeOrderError,
)
from app.utils.retry import retry_with_backoff, RetryConfig
from app.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Default retry configuration for exchanges
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    retryable_exceptions=(httpx.HTTPError, httpx.RequestError, httpx.TimeoutException),
)

# Default circuit breaker configuration
DEFAULT_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    expected_exception=Exception,
)


def create_exchange_circuit_breaker(name: str) -> CircuitBreaker:
    """
    Create a circuit breaker for an exchange.
    
    Args:
        name: Exchange name
        
    Returns:
        CircuitBreaker instance
    """
    return CircuitBreaker(name, DEFAULT_CIRCUIT_BREAKER_CONFIG)


def handle_exchange_error(
    error: Exception,
    exchange_name: str,
    operation: str,
    status_code: Optional[int] = None,
    response_data: Optional[dict] = None,
) -> Exception:
    """
    Convert generic exceptions to appropriate ExchangeError types.
    
    Args:
        error: Original exception
        exchange_name: Name of the exchange
        operation: Operation that failed (e.g., "fetch_orderbook")
        status_code: HTTP status code if available
        response_data: Response data if available
        
    Returns:
        Appropriate ExchangeError instance
    """
    error_msg = f"{exchange_name}: {operation} failed"
    
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 401 or status == 403:
            return ExchangeAuthenticationError(
                f"{error_msg}: Authentication failed",
                exchange_name=exchange_name,
                status_code=status,
                response_data=response_data,
            )
        elif status == 429:
            return ExchangeAPIError(
                f"{error_msg}: Rate limit exceeded",
                exchange_name=exchange_name,
                status_code=status,
                response_data=response_data,
            )
        else:
            return ExchangeAPIError(
                f"{error_msg}: HTTP {status}",
                exchange_name=exchange_name,
                status_code=status,
                response_data=response_data,
            )
    elif isinstance(error, (httpx.RequestError, httpx.TimeoutException, httpx.ConnectError)):
        return ExchangeNetworkError(
            f"{error_msg}: Network error - {str(error)}",
            exchange_name=exchange_name,
            status_code=status_code,
            response_data=response_data,
        )
    elif isinstance(error, (ExchangeAPIError, ExchangeAuthenticationError, ExchangeNetworkError, ExchangeOrderError)):
        # Already an ExchangeError, return as-is
        return error
    else:
        # Generic error, wrap as API error
        return ExchangeAPIError(
            f"{error_msg}: {str(error)}",
            exchange_name=exchange_name,
            status_code=status_code,
            response_data=response_data,
        )


