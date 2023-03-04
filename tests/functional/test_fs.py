"""FileSystem class functional tests"""
from __future__ import annotations

import os.path
import pathlib

import pytest

from curldl.util import FileSystem


def create_simple_file(file_path: pathlib.Path, file_size: int) -> None:
    """Create file of given size filled with the letter 'x'"""
    assert not os.path.exists(file_path)
    with open(file_path, 'wb') as tmp_file:
        tmp_file.write(b'x' * file_size)


@pytest.mark.parametrize('tmp_file_size', [0, 1, 1024, 1025, 4096])
def test_verify_size(tmp_path: pathlib.Path, tmp_file_size: int) -> None:
    """Verify arbitrary file size, also verify str argument"""
    create_simple_file(tmp_file_path := tmp_path / 'file.txt', tmp_file_size)
    FileSystem.verify_size(tmp_file_path, tmp_file_size)
    FileSystem.verify_size(str(tmp_file_path), tmp_file_size)


@pytest.mark.parametrize('tmp_file_size', [0, 1, 1024, 1025, 4096])
def test_verify_size_incorrect(tmp_path: pathlib.Path, tmp_file_size: int) -> None:
    """Verify arbitrary wrong file size"""
    create_simple_file(tmp_file_path := tmp_path / 'file.txt', tmp_file_size)
    with pytest.raises(ValueError):
        FileSystem.verify_size(tmp_file_path, tmp_file_size + 1)
    with pytest.raises(ValueError):
        FileSystem.verify_size(tmp_file_path, tmp_file_size - 1)


def test_verify_size_non_file(tmp_path: pathlib.Path) -> None:
    """Verify non-file size fails"""
    with pytest.raises(ValueError):
        FileSystem.verify_size(tmp_path, 0)
    with pytest.raises(ValueError):
        FileSystem.verify_size(tmp_path, os.path.getsize(tmp_path))


def test_verify_size_nonexistent_file(tmp_path: pathlib.Path) -> None:
    """Verify nonexistent file size fails"""
    with pytest.raises(FileNotFoundError):
        FileSystem.verify_size(tmp_path / 'no_such_file.txt', 0)


@pytest.mark.parametrize('tmp_file_size', [0, 1, 1024, 1025, 4096])
def test_get_file_size(tmp_path: pathlib.Path, tmp_file_size: int) -> None:
    """Get arbitrary file size, also verify str argument and default parameter"""
    create_simple_file(tmp_file_path := tmp_path / 'file.txt', tmp_file_size)
    assert FileSystem.get_file_size(tmp_file_path, 333) == tmp_file_size
    assert FileSystem.get_file_size(str(tmp_file_path)) == tmp_file_size


def test_get_file_size_non_file(tmp_path: pathlib.Path) -> None:
    """Non-file file size returns default parameter"""
    assert FileSystem.get_file_size(tmp_path) == 0
    assert FileSystem.get_file_size(tmp_path, -1) == -1


def test_get_file_size_nonexistent_file(tmp_path: pathlib.Path) -> None:
    """Non-file file size returns default parameter"""
    assert FileSystem.get_file_size(tmp_path / 'no_such_file.txt') == 0
    assert FileSystem.get_file_size(tmp_path / 'no_such_file.txt', -1) == -1


@pytest.mark.parametrize('tmp_file_timestamp', [0, 1, 7200, 1234567890, 1234567890.123456])
def test_set_file_timestamp(tmp_path: pathlib.Path, tmp_file_timestamp: int | float) -> None:
    """Set arbitrary integer and floating-point file timestamp"""
    create_simple_file(tmp_file_path := tmp_path / 'file.txt', 0)
    FileSystem.set_file_timestamp(tmp_file_path, tmp_file_timestamp)
    tmp_file_stat = os.stat(tmp_file_path)
    assert tmp_file_stat.st_atime == tmp_file_stat.st_mtime == tmp_file_timestamp


@pytest.mark.parametrize('tmp_path_timestamp', [7200, 1234567890.123456])
def test_set_directory_timestamp(tmp_path: pathlib.Path, tmp_path_timestamp: int | float) -> None:
    """Set arbitrary integer and floating-point directory timestamp, also verify str argument"""
    FileSystem.set_file_timestamp(str(tmp_path), tmp_path_timestamp)
    tmp_file_stat = os.stat(tmp_path)
    assert tmp_file_stat.st_atime == tmp_file_stat.st_mtime == tmp_path_timestamp


@pytest.mark.parametrize('tmp_file_timestamp', [7200, 1234567890.123456])
def test_set_symlink_timestamp(tmp_path: pathlib.Path, tmp_file_timestamp: int | float) -> None:
    """Set arbitrary integer and floating-point file timestamp via symlink"""
    create_simple_file(tmp_file_path := tmp_path / 'file.txt', 0)
    os.symlink('file.txt', tmp_symlink_path := tmp_path / 'symlink.txt')

    FileSystem.set_file_timestamp(tmp_symlink_path, tmp_file_timestamp)
    tmp_file_stat, tmp_symlink_stat = os.stat(tmp_file_path), os.stat(tmp_symlink_path)
    tmp_symlink_nofollow_stat = os.stat(tmp_symlink_path, follow_symlinks=False)

    assert tmp_file_stat == tmp_symlink_stat
    assert tmp_symlink_stat.st_atime == tmp_symlink_stat.st_mtime == tmp_file_timestamp
    assert tmp_symlink_nofollow_stat.st_mtime > tmp_file_timestamp + 1e6
