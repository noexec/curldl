"""Logging and tracing utilities"""
import logging
import traceback
import types

log = logging.getLogger(__name__)


class Log:
    """Logging and tracing utilities"""

    @classmethod
    def trace_unhandled_exception(cls, exc_type, exc: BaseException, trace_back: types.TracebackType) -> None:
        """Top-level logger for unhandled exceptions, can be assigned to sys.excepthook"""
        log.critical('%s: %s', exc_type.__name__, exc)
        if log.isEnabledFor(logging.DEBUG):
            log.debug(''.join(traceback.format_exception(exc_type, value=exc, tb=trace_back)))

    @classmethod
    def trace_exception(cls, exc: BaseException, msg: str) -> None:
        """Logging helper to trace an exception, including traceback at lower level"""
        log.error('%s: %s: %s', msg, exc.__class__.__name__, exc)
        if log.isEnabledFor(logging.DEBUG):
            log.debug(''.join(traceback.format_exception(exc)))
