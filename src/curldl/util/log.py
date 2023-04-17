"""Logging and tracing utilities for internal use"""
from __future__ import annotations

import logging
import sys
import traceback
import types
from typing import Type

log = logging.getLogger(__name__)


class Log:
    """Logging and tracing utilities"""

    @classmethod
    def setup_exception_logging_hooks(cls) -> None:
        """Assigns exception logging hooks: :func:`sys.excepthook`, :func:`sys.unraisablehook`."""
        sys.excepthook = cls.trace_unhandled_exception
        sys.unraisablehook = cls.trace_unraisable_exception

    @classmethod
    def trace_unhandled_exception(cls, exc_type: Type[BaseException], exc: BaseException,
                                  trace_back: types.TracebackType | None) -> None:
        """Top-level logger for unhandled exceptions, can be assigned to :func:`sys.excepthook`.
        The exception is logged at ``CRITICAL`` level, ad traceback at ``DEBUG`` level.

        :param exc_type: exception type (expected: ``exc.__class__``)
        :param exc: exception object
        :param trace_back: exception traceback (expected: ``exc.__traceback__``)
        """
        cls._trace_exception_details(loglevel=logging.CRITICAL, exc=exc, exc_type=exc_type, trace_back=trace_back)

    @classmethod
    def trace_unraisable_exception(cls, unraisable: sys.UnraisableHookArgs) -> None:
        """Top-level logger for unraisable exceptions, can be assigned to :func:`sys.unraisablehook`

        :param unraisable: container with the unraisable exception attributes
        """
        msg = f'{unraisable.err_msg}: {unraisable.object}' if unraisable.err_msg else str(unraisable.object)
        cls._trace_exception_details(loglevel=logging.ERROR, exc=unraisable.exc_value, exc_type=unraisable.exc_type,
                                     trace_back=unraisable.exc_traceback, msg=msg)

    @classmethod
    def trace_exception(cls, exc: BaseException, msg: str) -> None:
        """Logging helper to trace an exception.
        The exception is logged at ``ERROR`` level, ad traceback at ``DEBUG`` level.

        :param exc: exception object
        :param msg: message to prepend when logging the exception
        """
        cls._trace_exception_details(loglevel=logging.ERROR, exc=exc, exc_type=exc.__class__,
                                     trace_back=exc.__traceback__, msg=msg)

    @staticmethod
    def _trace_exception_details(*, loglevel: int, exc: BaseException | None, exc_type: Type[BaseException],
                                 trace_back: types.TracebackType | None, msg: str | None = None) -> None:
        """Generic logger for exception details

        :param loglevel: logging level for main message, auxiliary message is logged at ``DEBUG`` level
        :param exc: exception object
        :param exc_type: exception type (class)
        :param trace_back: exception traceback
        :param msg: extra exception message, prepended to main message if specified
        """
        msg_prefix = f'{msg}: ' if msg else ''
        log.log(loglevel, '%s%s: %s', msg_prefix, exc_type.__name__, exc)
        if log.isEnabledFor(logging.DEBUG):
            log.debug(''.join(traceback.format_exception(exc_type, value=exc, tb=trace_back)).rstrip('\n'))
