"""Circuit breaker pattern for exchange API calls."""

import time
from enum import Enum
from typing import Callable, Optional, Dict
from dataclasses import dataclass, field
from app.core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Number of failures before opening
    success_threshold: int = 2  # Number of successes to close from half-open
    timeout: float = 60.0  # Time in seconds before attempting half-open
    expected_exception: type = Exception  # Exception type to count as failure


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""

    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[float] = None
    state: CircuitState = CircuitState.CLOSED
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Name identifier for this circuit breaker
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()

    def call(self, func: Callable, *args, **kwargs):
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of func

        Raises:
            Exception: If circuit is open or function fails
        """
        self.stats.total_requests += 1

        # Check if circuit should transition from open to half-open
        if self.stats.state == CircuitState.OPEN:
            if (
                self.stats.last_failure_time
                and time.time() - self.stats.last_failure_time >= self.config.timeout
            ):
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN")
                self.stats.state = CircuitState.HALF_OPEN
                self.stats.successes = 0
            else:
                raise Exception(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Too many failures. Retry after {self.config.timeout}s"
                )

        # Execute function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs):
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of func

        Raises:
            Exception: If circuit is open or function fails
        """
        self.stats.total_requests += 1

        # Check if circuit should transition from open to half-open
        if self.stats.state == CircuitState.OPEN:
            if (
                self.stats.last_failure_time
                and time.time() - self.stats.last_failure_time >= self.config.timeout
            ):
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN")
                self.stats.state = CircuitState.HALF_OPEN
                self.stats.successes = 0
            else:
                raise Exception(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Too many failures. Retry after {self.config.timeout}s"
                )

        # Execute function
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call."""
        self.stats.total_successes += 1
        self.stats.failures = 0

        if self.stats.state == CircuitState.HALF_OPEN:
            self.stats.successes += 1
            if self.stats.successes >= self.config.success_threshold:
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED")
                self.stats.state = CircuitState.CLOSED
                self.stats.successes = 0

    def _on_failure(self):
        """Handle failed call."""
        self.stats.total_failures += 1
        self.stats.failures += 1
        self.stats.last_failure_time = time.time()

        if self.stats.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (failure in test)")
            self.stats.state = CircuitState.OPEN
            self.stats.successes = 0
        elif (
            self.stats.state == CircuitState.CLOSED
            and self.stats.failures >= self.config.failure_threshold
        ):
            logger.warning(
                f"Circuit breaker {self.name}: CLOSED -> OPEN "
                f"({self.stats.failures} failures >= {self.config.failure_threshold})"
            )
            self.stats.state = CircuitState.OPEN

    def reset(self):
        """Reset circuit breaker to closed state."""
        logger.info(f"Circuit breaker {self.name}: Manual reset to CLOSED")
        self.stats.state = CircuitState.CLOSED
        self.stats.failures = 0
        self.stats.successes = 0
        self.stats.last_failure_time = None

    def get_stats(self) -> Dict:
        """Get current statistics."""
        return {
            "name": self.name,
            "state": self.stats.state.value,
            "failures": self.stats.failures,
            "successes": self.stats.successes,
            "total_requests": self.stats.total_requests,
            "total_failures": self.stats.total_failures,
            "total_successes": self.stats.total_successes,
            "last_failure_time": self.stats.last_failure_time,
        }


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""

    def __init__(self):
        """Initialize circuit breaker manager."""
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.

        Args:
            name: Breaker name
            config: Optional configuration

        Returns:
            CircuitBreaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all circuit breakers."""
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}

