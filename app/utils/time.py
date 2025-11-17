"""Time and timestamp utilities."""

import time
from datetime import datetime, timezone
from typing import Optional


def get_current_timestamp() -> float:
    """
    Get current Unix timestamp.

    Returns:
        Current timestamp as float
    """
    return time.time()


def timestamp_to_datetime(timestamp: float, tz: Optional[timezone] = None) -> datetime:
    """
    Convert Unix timestamp to datetime object.

    Args:
        timestamp: Unix timestamp
        tz: Timezone (defaults to UTC)

    Returns:
        Datetime object
    """
    if tz is None:
        tz = timezone.utc
    return datetime.fromtimestamp(timestamp, tz=tz)


def datetime_to_timestamp(dt: datetime) -> float:
    """
    Convert datetime object to Unix timestamp.

    Args:
        dt: Datetime object

    Returns:
        Unix timestamp as float
    """
    return dt.timestamp()


def format_timestamp(timestamp: float, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format timestamp as string.

    Args:
        timestamp: Unix timestamp
        format_str: strftime format string

    Returns:
        Formatted timestamp string
    """
    dt = timestamp_to_datetime(timestamp)
    return dt.strftime(format_str)


def sleep_async(seconds: float) -> None:
    """
    Sleep for specified seconds (async-compatible).

    Note: This is a synchronous sleep. For async code, use asyncio.sleep().

    Args:
        seconds: Seconds to sleep
    """
    time.sleep(seconds)

