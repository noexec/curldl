"""Cryptographic utilities"""
from __future__ import annotations

import hashlib
import logging
import os

log = logging.getLogger(__name__)


class Cryptography:
    """Filesystem utilities"""

    FILE_CHUNK_BYTES = 8 * 1024 ** 2

    @staticmethod
    def get_available_digests() -> list[str]:
        """Returns lists of fixed-size digest algorithms in hashlib"""
        return sorted(algo for algo in hashlib.algorithms_available
                      if hashlib.new(algo).digest_size != 0)

    @classmethod
    def verify_digest(cls, path: str | os.PathLike[str], algo: str, digest: str) -> None:
        """Verify file digest and raise ValueError in case of mismatch.
        :param path: file path
        :param algo: hash algorithm name accepted by hashlib.new()
        :param digest: hexadecimal string"""
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
