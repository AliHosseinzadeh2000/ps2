"""Error recovery utilities for exchange operations."""

from typing import Callable, TypeVar, Optional, List
import asyncio
import time

from app.core.logging import get_logger
from app.exchanges.exceptions import (
    ExchangeError,
    ExchangeNetworkError,
    ExchangeAPIError,
    ExchangeAuthenticationError,
)

logger = get_logger(__name__)

T = TypeVar("T")


class ErrorRecoveryStrategy:
    """Strategy for recovering from exchange errors."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        exponential_backoff: bool = True,
        retryable_errors: Optional[List[type]] = None,
    ):
        """
        Initialize error recovery strategy.

        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (seconds)
            exponential_backoff: Whether to use exponential backoff
            retryable_errors: List of error types that should be retried
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.exponential_backoff = exponential_backoff
        self.retryable_errors = retryable_errors or [
            ExchangeNetworkError,
            ExchangeAPIError,  # Some API errors are transient
        ]

    async def execute_with_recovery(
        self,
        func: Callable,
        *args,
        on_retry: Optional[Callable[[Exception, int], None]] = None,
        **kwargs,
    ) -> T:
        """
        Execute a function with error recovery.

        Args:
            func: Async function to execute
            *args: Positional arguments
            on_retry: Optional callback called on each retry
            **kwargs: Keyword arguments

        Returns:
            Result of func

        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        delay = self.retry_delay

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except tuple(self.retryable_errors) as e:
                last_exception = e

                if attempt < self.max_retries:
                    logger.warning(
                        f"Error recovery attempt {attempt + 1}/{self.max_retries + 1} "
                        f"for {func.__name__}: {e}"
                    )

                    if on_retry:
                        on_retry(e, attempt + 1)

                    await asyncio.sleep(delay)

                    if self.exponential_backoff:
                        delay *= 2
                else:
                    logger.error(
                        f"Error recovery exhausted for {func.__name__} after "
                        f"{self.max_retries + 1} attempts: {e}"
                    )
            except ExchangeAuthenticationError:
                # Don't retry authentication errors
                raise
            except Exception as e:
                # Unexpected errors - don't retry
                logger.error(f"Unexpected error in {func.__name__}: {e}")
                raise

        if last_exception:
            raise last_exception


def recover_from_network_error(
    func: Callable,
    *args,
    max_retries: int = 3,
    **kwargs,
) -> T:
    """
    Recover from network errors with retries.

    Args:
        func: Async function to execute
        *args: Positional arguments
        max_retries: Maximum retry attempts
        **kwargs: Keyword arguments

    Returns:
        Result of func
    """
    strategy = ErrorRecoveryStrategy(
        max_retries=max_retries,
        retryable_errors=[ExchangeNetworkError],
    )
    return strategy.execute_with_recovery(func, *args, **kwargs)


async def recover_from_api_error(
    func: Callable,
    *args,
    max_retries: int = 2,
    retry_delay: float = 2.0,
    **kwargs,
) -> T:
    """
    Recover from API errors with retries.

    Args:
        func: Async function to execute
        *args: Positional arguments
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries
        **kwargs: Keyword arguments

    Returns:
        Result of func
    """
    strategy = ErrorRecoveryStrategy(
        max_retries=max_retries,
        retry_delay=retry_delay,
        retryable_errors=[ExchangeAPIError],
    )
    return await strategy.execute_with_recovery(func, *args, **kwargs)


class OrderExecutionRecovery:
    """Recovery strategies for order execution failures."""

    @staticmethod
    async def recover_partial_fill(
        buy_order_id: Optional[str],
        sell_order_id: Optional[str],
        buy_exchange,
        sell_exchange,
        symbol: str,
    ) -> tuple[bool, bool]:
        """
        Recover from partial fill scenario.

        Args:
            buy_order_id: Buy order ID (if placed)
            sell_order_id: Sell order ID (if placed)
            buy_exchange: Buy exchange interface
            sell_exchange: Sell exchange interface
            symbol: Trading symbol

        Returns:
            Tuple of (buy_cancelled, sell_cancelled)
        """
        buy_cancelled = False
        sell_cancelled = False

        # Cancel buy order if it exists
        if buy_order_id:
            try:
                await buy_exchange.cancel_order(buy_order_id, symbol)
                buy_cancelled = True
                logger.info(f"Recovered: Cancelled buy order {buy_order_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel buy order {buy_order_id}: {e}")

        # Cancel sell order if it exists
        if sell_order_id:
            try:
                await sell_exchange.cancel_order(sell_order_id, symbol)
                sell_cancelled = True
                logger.info(f"Recovered: Cancelled sell order {sell_order_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel sell order {sell_order_id}: {e}")

        return buy_cancelled, sell_cancelled

    @staticmethod
    async def recover_from_timeout(
        order_id: str,
        exchange,
        symbol: str,
        timeout_seconds: int = 30,
    ) -> bool:
        """
        Recover from order timeout by checking status and cancelling if needed.

        Args:
            order_id: Order ID to check
            exchange: Exchange interface
            symbol: Trading symbol
            timeout_seconds: Timeout in seconds

        Returns:
            True if order was cancelled, False otherwise
        """
        try:
            # Check order status
            order = await exchange.get_order(order_id, symbol)
            if order.status in ["pending", "open"]:
                # Order still pending, cancel it
                await exchange.cancel_order(order_id, symbol)
                logger.info(f"Recovered: Cancelled timed-out order {order_id}")
                return True
            elif order.status == "filled":
                logger.info(f"Order {order_id} was filled before timeout recovery")
                return False
        except Exception as e:
            logger.warning(f"Failed to recover from timeout for order {order_id}: {e}")
            return False

        return False


