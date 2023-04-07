"""Cryptographic utilities for internal use"""
from __future__ import annotations

import hashlib
import logging
import os

log = logging.getLogger(__name__)


class Cryptography:
    """Cryptographic utilities"""

    FILE_CHUNK_BYTES = 8 * 1024 ** 2

    @staticmethod
    def get_available_digests() -> list[str]:
        """Returns list of fixed-size digest algorithms in :mod:`hashlib`.
        Uses :attr:`hashlib.algorithms_guaranteed` because :attr:`hashlib.algorithms_available` may
        result in runtime errors due to deprecated algorithms being hidden by OpenSSL.
        :return: guaranteed algorithms in :mod:`hashlib` that produce a fixed-size digest
        """
        return sorted(algo for algo in hashlib.algorithms_guaranteed
                      if hashlib.new(algo).digest_size != 0)

    @classmethod
    def verify_digest(cls, path: str | os.PathLike[str], algo: str, digest: str) -> None:
        """Verify file digest and raise :class:`ValueError` in case of mismatch.
        :param path: input file path
        :param algo: hash algorithm name accepted by :func:`hashlib.new`
        :param digest: hexadecimal digest string to verify
        :raises ValueError: ``digest`` has incorrect length or fails verification
        """
        hash_obj = hashlib.new(algo)
        digest_name = hash_obj.name.upper()

        log.debug('Computing %s-bit %s for %s', hash_obj.digest_size * 8, digest_name, path)
        if hash_obj.digest_size*2 != len(digest):
            raise ValueError(f'Expected {digest_name} for {path} has length != {hash_obj.digest_size} B')

        with open(path, 'rb') as path_obj:
            while chunk := path_obj.read(cls.FILE_CHUNK_BYTES):
                hash_obj.update(chunk)

        if hash_obj.hexdigest().lower() != digest.lower():
            raise ValueError(f'{digest_name} mismatch for {path}')
        log.info('Successfully verified %s of %s', digest_name, path)
