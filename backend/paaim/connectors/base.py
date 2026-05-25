"""Abstract base class for all manufacturing system connectors."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncGenerator
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class ConnectorStatus(str, Enum):
    """Health status of a connector."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ConnectorConfig:
    """Configuration for a connector."""
    name: str
    host: str
    port: int
    timeout_seconds: int = 30
    retry_max_attempts: int = 3
    retry_backoff_base: float = 2.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 60
    extra_config: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ConnectorHealth:
    """Health status of a connector."""
    status: ConnectorStatus
    last_check: datetime
    error_count: int
    last_error: Optional[str] = None
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "last_check": self.last_check.isoformat(),
            "error_count": self.error_count,
            "last_error": self.last_error,
            "latency_ms": self.latency_ms,
        }


class CircuitBreaker:
    """Simple circuit breaker pattern for fault tolerance."""

    def __init__(self, threshold: int = 5, timeout_seconds: int = 60):
        self.threshold = threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.is_open = False

    def record_success(self) -> None:
        """Record successful call."""
        self.failure_count = 0
        self.is_open = False

    def record_failure(self) -> None:
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        if self.failure_count >= self.threshold:
            self.is_open = True
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def can_execute(self) -> bool:
        """Check if circuit allows execution."""
        if not self.is_open:
            return True

        # Check if timeout expired
        if self.last_failure_time:
            elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if elapsed > self.timeout_seconds:
                logger.info("Circuit breaker attempting recovery")
                self.is_open = False
                self.failure_count = 0
                return True

        return False


class ConnectorException(Exception):
    """Base exception for connector errors."""
    pass


class ConnectorTimeoutException(ConnectorException):
    """Timeout connecting to external system."""
    pass


class ConnectorAuthException(ConnectorException):
    """Authentication error with external system."""
    pass


class ManufacturingConnector(ABC):
    """
    Abstract base class for all manufacturing system connectors.

    Provides:
    - Async connection management
    - Retry logic with exponential backoff
    - Circuit breaker for fault tolerance
    - Health monitoring
    - Structured error logging
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize connector."""
        self.config = config
        self.circuit_breaker = CircuitBreaker(
            threshold=config.circuit_breaker_threshold,
            timeout_seconds=config.circuit_breaker_timeout_seconds,
        )
        self.health = ConnectorHealth(
            status=ConnectorStatus.UNKNOWN,
            last_check=datetime.utcnow(),
            error_count=0,
        )
        self._logger = logging.getLogger(f"{__name__}.{config.name}")

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to external system.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to external system."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform health check on connection.

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    async def fetch_events(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch events from external system.

        Args:
            since: Fetch events since this timestamp (optional)

        Returns:
            List of events as dictionaries
        """
        pass

    async def execute_with_retry(
        self,
        coro,
        operation_name: str = "operation",
        max_attempts: Optional[int] = None,
    ):
        """
        Execute async operation with retry logic and circuit breaker.

        Args:
            coro: Coroutine to execute
            operation_name: Name for logging
            max_attempts: Max retry attempts (uses config default if None)

        Returns:
            Result of coroutine

        Raises:
            ConnectorException: If all retries fail
        """
        max_attempts = max_attempts or self.config.retry_max_attempts

        if not self.circuit_breaker.can_execute():
            raise ConnectorException(
                f"Circuit breaker open for {self.config.name}"
            )

        last_error = None
        for attempt in range(max_attempts):
            try:
                result = await asyncio.wait_for(
                    coro,
                    timeout=self.config.timeout_seconds,
                )
                self.circuit_breaker.record_success()
                self.health.error_count = 0
                self.health.status = ConnectorStatus.HEALTHY
                return result

            except asyncio.TimeoutError as e:
                last_error = e
                self._logger.warning(
                    f"{operation_name} timeout on attempt {attempt + 1}/{max_attempts}"
                )

            except ConnectorAuthException as e:
                # Don't retry auth errors
                self.circuit_breaker.record_failure()
                self.health.error_count += 1
                self.health.status = ConnectorStatus.UNHEALTHY
                self.health.last_error = str(e)
                self._logger.error(f"Authentication error: {e}")
                raise

            except Exception as e:
                last_error = e
                self._logger.warning(
                    f"{operation_name} error on attempt {attempt + 1}/{max_attempts}: {e}"
                )

            # Exponential backoff
            if attempt < max_attempts - 1:
                backoff_seconds = self.config.retry_backoff_base ** attempt
                await asyncio.sleep(backoff_seconds)

        # All retries exhausted
        self.circuit_breaker.record_failure()
        self.health.error_count += 1
        self.health.status = ConnectorStatus.UNHEALTHY
        self.health.last_error = str(last_error)
        self._logger.error(
            f"{operation_name} failed after {max_attempts} attempts: {last_error}"
        )
        raise ConnectorException(
            f"{self.config.name} {operation_name} failed: {last_error}"
        )

    async def stream_events(
        self,
        poll_interval_seconds: int = 10,
        since: Optional[datetime] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream events from external system via polling.

        Args:
            poll_interval_seconds: Seconds between polls
            since: Start fetching from this timestamp

        Yields:
            Events from external system
        """
        last_fetch = since or datetime.utcnow()

        while True:
            try:
                events = await self.execute_with_retry(
                    self.fetch_events(since=last_fetch),
                    operation_name="fetch_events",
                )

                for event in events:
                    last_fetch = datetime.utcnow()
                    yield event

                await asyncio.sleep(poll_interval_seconds)

            except ConnectorException as e:
                self._logger.error(f"Event streaming error: {e}")
                await asyncio.sleep(poll_interval_seconds)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
