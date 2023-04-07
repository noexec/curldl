"""Time and timestamp utilities for internal use"""
from __future__ import annotations

import datetime
import email.utils


class Time:
    """Time and timestamp utilities"""

    @staticmethod
    def timestamp_to_dt(timestamp: int | float) -> datetime.datetime:
        """Convert POSIX timestamp to datetime in UTC timezone
        :param timestamp: UTC-based POSIX timestamp
        :return: :class:`datetime.datetime` in UTC timezone
        """
        return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)

    @staticmethod
    def timestamp_to_http_date(timestamp: int | float) -> str:
        """Convert POSIX timestamp to HTTP date in GMT timezone
        :param timestamp: POSIX timestamp
        :return: RFC-822 date suitable for HTTP headers
        """
        return email.utils.formatdate(round(timestamp), usegmt=True)

    @staticmethod
    def timestamp_delta(timestamp_delta: int | float) -> datetime.timedelta:
        """Convert POSIX timestamp difference to a printable datetime duration
        :param timestamp_delta: time period in seconds
        :return: :class:`datetime.datetime` duration, rounded to non-fractional seconds
        """
        return datetime.timedelta(seconds=round(timestamp_delta))
