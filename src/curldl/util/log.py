"""Logging and tracing utilities"""
from __future__ import annotations

import logging
import traceback
import types
from typing import Type

log = logging.getLogger(__name__)


class Log:
    """Logging and tracing utilities"""

    @classmethod
    def trace_unhandled_exception(cls, exc_type: Type[BaseException], exc: BaseException,
                                  trace_back: types.TracebackType | None) -> None:
        """Top-level logger for unhandled exceptions, can be assigned to sys.excepthook"""
        log.critical('%s: %s', exc_type.__name__, exc)
        if log.isEnabledFor(logging.DEBUG):
            log.debug(''.join(traceback.format_exception(exc_type, value=exc, tb=trace_back)).rstrip('\n'))

    @classmethod
    def trace_exception(cls, exc: BaseException, msg: str) -> None:
        """Logging helper to trace an exception, including traceback at lower level"""
        log.error('%s: %s: %s', msg, exc.__class__.__name__, exc)
        if log.isEnabledFor(logging.DEBUG):
            log.debug(''.join(traceback.format_exception(exc.__class__, value=exc, tb=exc.__traceback__)).rstrip('\n'))
