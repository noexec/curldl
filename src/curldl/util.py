"""General-purpose utilities"""
from __future__ import annotations

import datetime
import email
import hashlib
import logging
import os
import traceback
import types


class Utilities:
    """General-purpose utilities"""
    FILE_CHUNK_BYTES = 8 * 1024 ** 2
    log = logging.getLogger('util')

    @classmethod
    def trace_unhandled_exception(cls, exc_type, exc: BaseException, trace_back: types.TracebackType) -> None:
        """Top-level logger for unhandled exceptions, can be assigned to sys.excepthook"""
        cls.log.critical('%s: %s', exc_type.__name__, exc)
        if cls.log.isEnabledFor(logging.DEBUG):
            cls.log.debug(''.join(traceback.format_exception(exc_type, value=exc, tb=trace_back)))

    @classmethod
    def trace_exception(cls, exc: BaseException, msg: str) -> None:
        """Logging helper to trace an exception, including traceback at lower level"""
        cls.log.error('%s: %s: %s', msg, exc.__class__.__name__, exc)
        if cls.log.isEnabledFor(logging.DEBUG):
            cls.log.debug(''.join(traceback.format_exception(exc)))

    @staticmethod
    def verify_rel_path_is_safe(basedir: str, rel_path: str) -> None:
        """Verify that a relative path does not escape base directory
        and either does not exist or is a file or a symlink to one"""
        base = os.path.abspath(basedir)
        path = os.path.abspath(os.path.join(basedir, rel_path))
        if base != os.path.commonpath((base, path)):
            raise ValueError(f'Relative path {rel_path} escapes base path {basedir}')
        if os.path.exists(path) and not os.path.isfile(path):
            raise ValueError(f'Not a file or symlink to file: {path}')

    @classmethod
    def create_directory_for_path(cls, path: str):
        """Create all path components for path, except for last"""
        path_dir = os.path.dirname(path)
        if not os.path.exists(path_dir):
            cls.log.info('Creating directory: %s', path_dir)
            os.makedirs(path_dir)

    @classmethod
    def verify_size_and_digests(cls, path: str, expected_size: int | None = None,
                                expected_digests: dict[str, str] | None = None) -> None:
        """Verify file size and digests and raise ValueError in case of mismatch.
            expected_digests is a dict of hash algorithms and digests to check
            (see verify_digest())."""
        if expected_size is not None:
            cls.verify_size(path, expected_size=expected_size)
        for algo, digest in expected_digests.items() if expected_digests else {}:
            cls.verify_digest(path, algo=algo, expected_digest=digest)

    @classmethod
    def verify_size(cls, path: str, expected_size: int) -> None:
        """Verify file size and raise ValueError in case of mismatch"""
        path_size = os.path.getsize(path)
        if path_size != expected_size:
            raise ValueError(f'Size mismatch for {path}: {path_size:,} instead of {expected_size:,} bytes')
        cls.log.debug('Successfully verified file size of %s', path)

    @classmethod
    def verify_digest(cls, path: str, algo: str, expected_digest: str) -> None:
        """Verify file digest and raise ValueError in case of mismatch.
            algo is a hash algorithm name accepted by hashlib.new()
            expected_digest is a hexadecimal string"""
        hashobj = hashlib.new(algo)
        digest_name = hashobj.name.upper()

        cls.log.debug('Computing %s-bit %s for %s', hashobj.digest_size * 8, digest_name, path)
        if hashobj.digest_size*2 != len(expected_digest):
            raise ValueError(f'Expected {digest_name} for {path} has length != {hashobj.digest_size} bytes')

        with open(path, 'rb') as pathobj:
            while chunk := pathobj.read(cls.FILE_CHUNK_BYTES):
                hashobj.update(chunk)

        if hashobj.hexdigest().lower() != expected_digest.lower():
            raise ValueError(f'{digest_name} mismatch for {path}')
        cls.log.info('Successfully verified %s of %s', digest_name, path)

    @staticmethod
    def get_file_size(path: str, default: int = 0) -> int:
        """Returns file size, or default if it does not exist or is not a file"""
        return os.path.getsize(path) if os.path.isfile(path) else default

    @classmethod
    def set_file_timestamp(cls, path: str, timestamp: int | float) -> None:
        """Sets file timestamp to a POSIX timestamp.
        If timestamp is negative, does nothing."""
        if timestamp < 0:
            return
        if cls.log.isEnabledFor(logging.DEBUG):
            cls.log.debug('Timestamping %s with %s', path, cls.timestamp_to_dt(timestamp))
        os.utime(path, times=(timestamp, timestamp))

    @staticmethod
    def timestamp_to_dt(timestamp: int | float):
        """Convert POSIX timestamp to datetime in UTC timezone"""
        return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)

    @staticmethod
    def timestamp_to_http_date(timestamp: int | float):
        """Convert POSIX timestamp to HTTP date in GMT timezone"""
        return email.utils.formatdate(round(timestamp), usegmt=True)

    @staticmethod
    def timestamp_delta(timestamp_delta: int | float):
        """Convert POSIX timestamp difference to a printable datetime duration"""
        return datetime.timedelta(seconds=round(timestamp_delta))
