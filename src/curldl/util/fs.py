"""Filesystem utilities for internal use"""
from __future__ import annotations

import logging
import os

from curldl.util.crypt import Cryptography
from curldl.util.time import Time

log = logging.getLogger(__name__)


class FileSystem:
    """Filesystem utilities, include cryptographic digest verification wrappers"""

    @staticmethod
    def verify_rel_path_is_safe(basedir: str | os.PathLike[str], rel_path: str | os.PathLike[str]) -> None:
        """Verify that a relative path does not escape base directory
        and either does not exist or is a file or a symlink to one
        :param basedir: base directory path
        :param rel_path: path relative to base directory
        :raises ValueError: relative path escapes base directory before or after symlink resolution,
        resulting path is a dangling symlink, is not a file or a symlink to file
        """
        base = os.path.abspath(basedir)
        path = os.path.abspath(os.path.join(basedir, rel_path))
        base_real, path_real = os.path.realpath(base), os.path.realpath(path)

        # os.path.commonpath() also raises ValueError for different-drive paths on Windows
        if base != os.path.commonpath((base, path)):
            raise ValueError(f'Relative path {rel_path} escapes base path {base}')
        if base_real != os.path.commonpath((base_real, path_real)):
            raise ValueError(f'Relative path {rel_path} escapes base path {base} after resolving symlinks')
        if base == path or base_real == path_real:
            raise ValueError(f'Relative path {rel_path} does not extend {base}')

        if os.path.islink(path) and not os.path.exists(path):
            raise ValueError(f'Path is a dangling symlink: {path}')
        if os.path.exists(path) and not os.path.isfile(path):
            raise ValueError(f'Exists and not a file or symlink to file: {path}')

        if str(rel_path).endswith(os.path.sep) or (os.path.altsep and str(rel_path).endswith(os.path.altsep)):
            raise ValueError(f'Path can only point to a directory: {rel_path}')

    @classmethod
    def create_directory_for_path(cls, path: str | os.PathLike[str]) -> None:
        """Create all path components for path, except for last
        :param path: file path
        """
        path_dir = os.path.dirname(path)
        if not os.path.exists(path_dir):
            log.info('Creating directory: %s', path_dir)
            os.makedirs(path_dir)

    @classmethod
    def verify_size_and_digests(cls, path: str | os.PathLike[str], *, size: int | None = None,
                                digests: dict[str, str] | None = None) -> None:
        """Verify file size and digests and raise :class:`ValueError` in case of mismatch.
        ``digests`` is a dict of hash algorithms and digests to check
        (see :func:`curldl.util.crypt.Cryptography.verify_digest`).
        :param path: input file path
        :param size: expected file size in bytes, or ``None`` to ignore
        :param digests: mapping of digest algorithms to expected hexadecimal digest strings, or ``None`` to ignore
        :raises ValueError: not a file or file size mismatch or one of digests fails verification
        """
        if size is not None:
            cls.verify_size(path, size=size)
        for algo, digest in digests.items() if digests else {}:
            Cryptography.verify_digest(path, algo=algo, digest=digest)

    @classmethod
    def verify_size(cls, path: str | os.PathLike[str], size: int) -> None:
        """Verify file size and raise :class:`ValueError` in case of mismatch or if not a file
        :param path: input file path
        :param size: expected file size in bytes
        :raises ValueError: not a file or file size mismatch
        """
        path_size = os.path.getsize(path)
        if not os.path.isfile(path):
            raise ValueError(f'Not a file: {path}')
        if path_size != size:
            raise ValueError(f'Size mismatch for {path}: {path_size:,} instead of {size:,} B')
        log.debug('Successfully verified file size of %s', path)

    @staticmethod
    def get_file_size(path: str | os.PathLike[str], default: int = 0) -> int:
        """Returns file size, or ``default`` if it does not exist or is not a file
        :param path: input file path
        :param default: value to return if ``path`` does not exist or is not a file (e.g., a directory)
        :return: input file size
        """
        return os.path.getsize(path) if os.path.isfile(path) else default

    @classmethod
    def set_file_timestamp(cls, path: str | os.PathLike[str], timestamp: int | float) -> None:
        """Sets file timestamp to a POSIX timestamp. If timestamp is negative, does nothing.
        :param path: filesystem path, must exist; symlinks are followed
        :param timestamp: POSIX UTC-based timestamp to store as last-modified
        and last-accessed file time if non-negative
        """
        if timestamp < 0:
            return
        if log.isEnabledFor(logging.DEBUG):
            log.debug('Timestamping %s with %s', path, Time.timestamp_to_dt(timestamp))
        os.utime(path, times=(timestamp, timestamp))
