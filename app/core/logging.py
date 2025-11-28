"""Structured logging setup with async-safe handlers."""

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record

        Returns:
            JSON string
        """
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, default=str)


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    use_json: bool = False,
) -> None:
    """
    Configure application logging with structured output.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        use_json: Whether to use JSON formatting (default: False, uses human-readable)
    """
    level = getattr(logging, (log_level or settings.log_level).upper(), logging.INFO)

    # Choose formatter
    if use_json:
        formatter = StructuredFormatter()
        console_formatter = StructuredFormatter()
    else:
        # Human-readable formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_formatter = formatter

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Set levels for third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    return logger


def log_exchange_error(
    logger: logging.Logger,
    exchange_name: str,
    operation: str,
    error: Exception,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log exchange error with structured information.

    Args:
        logger: Logger instance
        exchange_name: Name of the exchange
        operation: Operation that failed
        error: Exception that occurred
        details: Additional error details
    """
    extra = {
        "exchange": exchange_name,
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    if details:
        extra.update(details)

    logger.error(
        f"Exchange error: {exchange_name} - {operation} failed: {error}",
        extra={"extra_fields": extra},
    )

