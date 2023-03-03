"""Filesystem utilities"""
from __future__ import annotations

import logging
import os

from curldl.util.crypt import Cryptography
from curldl.util.time import Time

log = logging.getLogger(__name__)


class FileSystem:
    """Filesystem utilities"""

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
    def create_directory_for_path(cls, path: str) -> None:
        """Create all path components for path, except for last"""
        path_dir = os.path.dirname(path)
        if not os.path.exists(path_dir):
            log.info('Creating directory: %s', path_dir)
            os.makedirs(path_dir)

    @classmethod
    def verify_size_and_digests(cls, path: str, expected_size: int | None = None,
                                expected_digests: dict[str, str] | None = None) -> None:
        """Verify file size and digests and raise ValueError in case of mismatch.
            expected_digests is a dict of hash algorithms and digests to check
            (see Cryptography.verify_digest())."""
        if expected_size is not None:
            cls.verify_size(path, expected_size=expected_size)
        for algo, digest in expected_digests.items() if expected_digests else {}:
            Cryptography.verify_digest(path, algo=algo, expected_digest=digest)

    @classmethod
    def verify_size(cls, path: str, expected_size: int) -> None:
        """Verify file size and raise ValueError in case of mismatch"""
        path_size = os.path.getsize(path)
        if path_size != expected_size:
            raise ValueError(f'Size mismatch for {path}: {path_size:,} instead of {expected_size:,} bytes')
        log.debug('Successfully verified file size of %s', path)

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
        if log.isEnabledFor(logging.DEBUG):
            log.debug('Timestamping %s with %s', path, Time.timestamp_to_dt(timestamp))
        os.utime(path, times=(timestamp, timestamp))
