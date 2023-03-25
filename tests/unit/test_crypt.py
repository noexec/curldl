"""Cryptography class unit tests"""
import hashlib
import pathlib

import pytest
from pytest_mock import MockerFixture

from curldl.util import Cryptography
from .test_fs import create_simple_file


def test_get_available_digests() -> None:
    """Verify that returned digests are exhaustive list of simple-constructible hashlib digests"""
    algos = set(Cryptography.get_available_digests())
    for algo in algos:
        digest = hashlib.new(algo)
        digest.update(b'test')
        assert len(digest.digest()) == digest.digest_size > 0
        assert len(digest.hexdigest()) == digest.digest_size * 2

    for algo in hashlib.algorithms_guaranteed - algos:
        digest = hashlib.new(algo)
        digest.update(b'test')
        with pytest.raises(TypeError):
            digest.digest()


@pytest.mark.parametrize('algo, digest',
                         [('sha1', 'e391dfa532390c5c3aa17D83F07480F12C564274'),
                          ('sha256', '67BA149E81413097CCBF64478AD47083bf4a77402b63804074fc8ebb73f685b5')])
@pytest.mark.parametrize('chunk_size', [1, 128, 355, Cryptography.FILE_CHUNK_BYTES, Cryptography.FILE_CHUNK_BYTES * 2])
def test_verify_digest(tmp_path: pathlib.Path, mocker: MockerFixture, algo: str, digest: str, chunk_size: int) -> None:
    """Verify arbitrary correct and incorrect value / length file digest, also verify str argument"""
    create_simple_file(file_path := tmp_path / 'file.txt', 1500)
    mocker.patch.object(Cryptography, 'FILE_CHUNK_BYTES', chunk_size)

    Cryptography.verify_digest(file_path, algo, digest)
    Cryptography.verify_digest(str(file_path), algo, digest)

    with pytest.raises(FileNotFoundError):
        Cryptography.verify_digest(tmp_path / 'no_such_file.txt', algo, digest)

    with pytest.raises(ValueError):
        Cryptography.verify_digest(file_path, algo + 'x', digest)
    with pytest.raises(ValueError):
        Cryptography.verify_digest(file_path, algo, digest[:-1] + '0')
    with pytest.raises(ValueError):
        Cryptography.verify_digest(file_path, algo, digest[:-1])
    with pytest.raises(ValueError):
        Cryptography.verify_digest(file_path, algo, '')
