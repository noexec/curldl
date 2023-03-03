"""Time and timestamp utilities"""
from __future__ import annotations

import datetime
import email.utils
import logging

log = logging.getLogger(__name__)


class Time:
    """Time and timestamp utilities"""

    @staticmethod
    def timestamp_to_dt(timestamp: int | float) -> datetime.datetime:
        """Convert POSIX timestamp to datetime in UTC timezone"""
        return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)

    @staticmethod
    def timestamp_to_http_date(timestamp: int | float) -> str:
        """Convert POSIX timestamp to HTTP date in GMT timezone"""
        return email.utils.formatdate(round(timestamp), usegmt=True)

    @staticmethod
    def timestamp_delta(timestamp_delta: int | float) -> datetime.timedelta:
        """Convert POSIX timestamp difference to a printable datetime duration"""
        return datetime.timedelta(seconds=round(timestamp_delta))
