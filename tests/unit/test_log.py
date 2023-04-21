"""Log class unit tests"""
from __future__ import annotations

import gc
import logging
import sys
import threading

import pytest
from _pytest.logging import LogCaptureFixture
from pytest_mock import MockerFixture

from curldl.util import Log

LOG_PACKAGE = "curldl.util.log"


def verify_debug_log_records(
    log_level: int, log_records: list[tuple[str, int, str]]
) -> None:
    """Verify correct log lines are produced at DEBUG log level"""
    if log_level != logging.DEBUG:
        assert len(log_records) == 1
        return

    assert len(log_records) == 2
    assert log_records[1][:-1] == (LOG_PACKAGE, logging.DEBUG)

    traceback_msg: str = log_records[1][-1]
    assert traceback_msg.startswith("Traceback ")
    assert "ValueError: test_exception" in traceback_msg
    assert not traceback_msg.endswith("\n")


@pytest.mark.parametrize("log_level", [logging.INFO, logging.DEBUG])
def test_trace_exception(caplog: LogCaptureFixture, log_level: int) -> None:
    """Verify correct log lines are produced when tracing an exception"""
    caplog.set_level(log_level)
    try:
        raise ValueError("test_exception")
    except ValueError as exc:
        Log.trace_exception(exc, "test_message")

    assert caplog.record_tuples[0] == (
        LOG_PACKAGE,
        logging.ERROR,
        "test_message: ValueError: test_exception",
    )
    verify_debug_log_records(log_level, caplog.record_tuples)


@pytest.mark.parametrize("log_level", [logging.WARNING, logging.DEBUG])
def test_trace_unhandled_exception(caplog: LogCaptureFixture, log_level: int) -> None:
    """Verify appropriate log lines are produced when tracing an unhandled exception"""
    caplog.set_level(log_level)
    try:
        raise ValueError("test_exception")
    except ValueError as exc:
        Log.trace_unhandled_exception(exc.__class__, exc, exc.__traceback__)

    assert caplog.record_tuples[0] == (
        LOG_PACKAGE,
        logging.CRITICAL,
        "ValueError: test_exception",
    )
    verify_debug_log_records(log_level, caplog.record_tuples)


@pytest.mark.parametrize("log_level", [logging.WARNING, logging.DEBUG])
def test_trace_unraisable_exception(
    caplog: LogCaptureFixture, mocker: MockerFixture, log_level: int
) -> None:
    """Verify appropriate log lines are produced when tracing an unraisable exception"""

    class DestructorRaiser:
        """Raises an (unraisable) exception in destructor"""

        def __del__(self) -> None:
            """Raise an exception that cannot be handled via try/except clause"""
            raise ValueError("test_exception")

    caplog.set_level(log_level)
    mocker.patch.object(sys, "unraisablehook")
    sys.unraisablehook = Log.trace_unraisable_exception

    obj = DestructorRaiser()
    del obj
    gc.collect()

    assert caplog.record_tuples[0] == (
        LOG_PACKAGE,
        logging.ERROR,
        str(DestructorRaiser.__del__) + ": ValueError: test_exception",
    )
    verify_debug_log_records(log_level, caplog.record_tuples)


@pytest.mark.parametrize("log_level", [logging.WARNING, logging.DEBUG])
def test_trace_thread_exception(
    caplog: LogCaptureFixture, mocker: MockerFixture, log_level: int
) -> None:
    """Verify appropriate log lines are produced when tracing a thread exception"""

    def thread_raiser() -> None:
        """Raise a thread exception that cannot be handled via try/except clause"""
        raise ValueError("test_exception")

    caplog.set_level(log_level)
    mocker.patch.object(threading, "excepthook")
    threading.excepthook = Log.trace_thread_exception

    thread = threading.Thread(target=thread_raiser, daemon=True, name="ThreadRaiser")
    thread.start()
    thread.join()
    thread_str = str(thread).replace("stopped", "started")

    assert caplog.record_tuples[0] == (
        LOG_PACKAGE,
        logging.ERROR,
        thread_str + ": ValueError: test_exception",
    )
    verify_debug_log_records(log_level, caplog.record_tuples)


def test_trace_unhandled_exception_type(mocker: MockerFixture) -> None:
    """Statically verify that the function is assignable to
    ``sys.excepthook`` (mypy)"""
    mocker.patch.object(sys, "excepthook")
    sys.excepthook = Log.trace_unhandled_exception


def test_trace_unraisable_exception_type(mocker: MockerFixture) -> None:
    """Statically verify that the function is assignable to
    ``sys.unraisablehook`` (mypy)"""
    mocker.patch.object(sys, "unraisablehook")
    sys.unraisablehook = Log.trace_unraisable_exception


def test_trace_thread_exception_type(mocker: MockerFixture) -> None:
    """Statically verify that the function is assignable to
    ``sys.unraisablehook`` (mypy)"""
    mocker.patch.object(threading, "excepthook")
    threading.excepthook = Log.trace_thread_exception
