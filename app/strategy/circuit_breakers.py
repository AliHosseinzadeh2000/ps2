"""Market and exchange circuit breakers for risk management."""

import time
from typing import Dict, Optional
from collections import deque

from app.core.logging import get_logger
from app.exchanges.base import OrderBook

logger = get_logger(__name__)


class MarketVolatilityCircuitBreaker:
    """Circuit breaker for market volatility."""

    def __init__(
        self,
        max_volatility_percent: float = 5.0,
        window_seconds: int = 60,
        min_samples: int = 10,
    ):
        """
        Initialize market volatility circuit breaker.

        Args:
            max_volatility_percent: Maximum allowed price change percentage
            window_seconds: Time window for volatility calculation
            min_samples: Minimum samples needed for calculation
        """
        self.max_volatility_percent = max_volatility_percent
        self.window_seconds = window_seconds
        self.min_samples = min_samples
        self._price_history: Dict[str, deque] = {}  # symbol -> deque of (timestamp, price)
        self._halted: bool = False

    def check_volatility(self, symbol: str, current_price: float) -> bool:
        """
        Check if market volatility is acceptable.

        Args:
            symbol: Trading pair symbol
            current_price: Current market price

        Returns:
            True if volatility is acceptable, False if circuit should break
        """
        now = time.time()
        
        # Initialize history for symbol if needed
        if symbol not in self._price_history:
            self._price_history[symbol] = deque()
        
        history = self._price_history[symbol]
        
        # Add current price
        history.append((now, current_price))
        
        # Remove old entries outside window
        while history and (now - history[0][0]) > self.window_seconds:
            history.popleft()
        
        # Need minimum samples
        if len(history) < self.min_samples:
            return True  # Not enough data, allow trading
        
        # Calculate volatility (price range in window)
        prices = [price for _, price in history]
        min_price = min(prices)
        max_price = max(prices)
        
        if min_price == 0:
            return True
        
        volatility = ((max_price - min_price) / min_price) * 100.0
        
        if volatility > self.max_volatility_percent:
            logger.warning(
                f"Market volatility circuit breaker triggered for {symbol}: "
                f"{volatility:.2f}% > {self.max_volatility_percent:.2f}%"
            )
            self._halted = True
            return False
        
        self._halted = False
        return True

    def is_halted(self) -> bool:
        """Check if trading is halted due to volatility."""
        return self._halted

    def reset(self):
        """Reset circuit breaker."""
        self._halted = False
        self._price_history.clear()


class ExchangeConnectivityCircuitBreaker:
    """Circuit breaker for exchange connectivity issues."""

    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: int = 60,
        recovery_timeout: int = 300,
    ):
        """
        Initialize exchange connectivity circuit breaker.

        Args:
            max_failures: Maximum failures before opening circuit
            window_seconds: Time window for counting failures
            recovery_timeout: Seconds to wait before attempting recovery
        """
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.recovery_timeout = recovery_timeout
        self._failures: Dict[str, deque] = {}  # exchange -> deque of failure timestamps
        self._open_time: Dict[str, float] = {}  # exchange -> when circuit opened
        self._state: Dict[str, str] = {}  # exchange -> 'closed', 'open', 'half_open'

    def record_failure(self, exchange_name: str):
        """
        Record a failure for an exchange.

        Args:
            exchange_name: Name of the exchange
        """
        now = time.time()
        
        if exchange_name not in self._failures:
            self._failures[exchange_name] = deque()
            self._state[exchange_name] = "closed"
        
        failures = self._failures[exchange_name]
        failures.append(now)
        
        # Remove old failures outside window
        while failures and (now - failures[0]) > self.window_seconds:
            failures.popleft()
        
        # Check if should open circuit
        if len(failures) >= self.max_failures:
            if self._state[exchange_name] != "open":
                logger.warning(
                    f"Exchange connectivity circuit breaker opened for {exchange_name}: "
                    f"{len(failures)} failures in {self.window_seconds}s"
                )
                self._state[exchange_name] = "open"
                self._open_time[exchange_name] = now

    def record_success(self, exchange_name: str):
        """
        Record a success for an exchange.

        Args:
            exchange_name: Name of the exchange
        """
        if exchange_name in self._state:
            if self._state[exchange_name] == "half_open":
                # Success in half-open, close circuit
                logger.info(f"Exchange connectivity circuit breaker closed for {exchange_name}")
                self._state[exchange_name] = "closed"
                self._failures[exchange_name].clear()
            elif self._state[exchange_name] == "open":
                # Try half-open
                self._state[exchange_name] = "half_open"

    def is_halted(self, exchange_name: str) -> bool:
        """
        Check if exchange is halted.

        Args:
            exchange_name: Name of the exchange

        Returns:
            True if halted
        """
        if exchange_name not in self._state:
            return False
        
        state = self._state[exchange_name]
        
        if state == "closed":
            return False
        
        if state == "open":
            # Check if recovery timeout has passed
            if exchange_name in self._open_time:
                if (time.time() - self._open_time[exchange_name]) >= self.recovery_timeout:
                    # Try half-open
                    self._state[exchange_name] = "half_open"
                    logger.info(f"Exchange connectivity circuit breaker half-open for {exchange_name}")
                    return False
            return True
        
        # half_open: allow one attempt
        return False

    def reset(self, exchange_name: Optional[str] = None):
        """
        Reset circuit breaker.

        Args:
            exchange_name: Specific exchange to reset, or None for all
        """
        if exchange_name:
            if exchange_name in self._failures:
                self._failures[exchange_name].clear()
            if exchange_name in self._state:
                self._state[exchange_name] = "closed"
            if exchange_name in self._open_time:
                del self._open_time[exchange_name]
        else:
            self._failures.clear()
            self._state.clear()
            self._open_time.clear()


class ErrorRateCircuitBreaker:
    """Circuit breaker for error rate."""

    def __init__(
        self,
        max_error_rate: float = 0.5,  # 50% error rate
        window_seconds: int = 60,
        min_requests: int = 10,
    ):
        """
        Initialize error rate circuit breaker.

        Args:
            max_error_rate: Maximum allowed error rate (0.0 to 1.0)
            window_seconds: Time window for error rate calculation
            min_requests: Minimum requests needed for calculation
        """
        self.max_error_rate = max_error_rate
        self.window_seconds = window_seconds
        self.min_requests = min_requests
        self._requests: Dict[str, deque] = {}  # exchange -> deque of (timestamp, success)
        self._halted: Dict[str, bool] = {}

    def record_request(self, exchange_name: str, success: bool):
        """
        Record a request result.

        Args:
            exchange_name: Name of the exchange
            success: Whether request was successful
        """
        now = time.time()
        
        if exchange_name not in self._requests:
            self._requests[exchange_name] = deque()
        
        requests = self._requests[exchange_name]
        requests.append((now, success))
        
        # Remove old requests outside window
        while requests and (now - requests[0][0]) > self.window_seconds:
            requests.popleft()
        
        # Calculate error rate
        if len(requests) >= self.min_requests:
            errors = sum(1 for _, success in requests if not success)
            error_rate = errors / len(requests)
            
            if error_rate > self.max_error_rate:
                logger.warning(
                    f"Error rate circuit breaker triggered for {exchange_name}: "
                    f"{error_rate:.2%} > {self.max_error_rate:.2%}"
                )
                self._halted[exchange_name] = True
            else:
                self._halted[exchange_name] = False

    def is_halted(self, exchange_name: str) -> bool:
        """
        Check if exchange is halted due to error rate.

        Args:
            exchange_name: Name of the exchange

        Returns:
            True if halted
        """
        return self._halted.get(exchange_name, False)

    def reset(self, exchange_name: Optional[str] = None):
        """
        Reset circuit breaker.

        Args:
            exchange_name: Specific exchange to reset, or None for all
        """
        if exchange_name:
            if exchange_name in self._requests:
                self._requests[exchange_name].clear()
            if exchange_name in self._halted:
                self._halted[exchange_name] = False
        else:
            self._requests.clear()
            self._halted.clear()

