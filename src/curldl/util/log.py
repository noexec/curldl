"""Logging and tracing utilities for internal use"""
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
        """Top-level logger for unhandled exceptions, can be assigned to ``sys.excepthook``.
        The exception is logged at ``CRITICAL`` level, ad traceback at ``DEBUG`` level.
        :param exc_type: exception type (expected: ``exc.__class__``)
        :param exc: exception object
        :param trace_back: exception traceback (expected: ``exc.__traceback__``)
        """
        log.critical('%s: %s', exc_type.__name__, exc)
        if log.isEnabledFor(logging.DEBUG):
            log.debug(''.join(traceback.format_exception(exc_type, value=exc, tb=trace_back)).rstrip('\n'))

    @classmethod
    def trace_exception(cls, exc: BaseException, msg: str) -> None:
        """Logging helper to trace an exception.
        The exception is logged at ``ERROR`` level, ad traceback at ``DEBUG`` level.
        :param exc: exception object
        :param msg: message to prepend when logging the exception
        """
        log.error('%s: %s: %s', msg, exc.__class__.__name__, exc)
        if log.isEnabledFor(logging.DEBUG):
            log.debug(''.join(traceback.format_exception(exc.__class__, value=exc, tb=exc.__traceback__)).rstrip('\n'))
