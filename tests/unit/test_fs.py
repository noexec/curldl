"""FileSystem class unit tests"""
from __future__ import annotations

import logging
import os.path
import pathlib
import sys
from contextlib import contextmanager
from typing import Iterator

import pytest
from _pytest.logging import LogCaptureFixture

from curldl.util import FileSystem


def create_simple_file(file_path: pathlib.Path, file_size: int, *, create_dirs: bool = False) -> None:
    """Create file of given size filled with the letter 'x'"""
    assert not os.path.exists(file_path)
    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'wb') as tmp_file:
        tmp_file.write(b'x' * file_size)


@contextmanager
def current_working_directory(path: str | os.PathLike[str]) -> Iterator[None]:
    """Temporarily change cwd, usage: with current_working_directory(path): ..."""
    cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(cwd)


def make_os_independent_path(path: str) -> str:
    """Make a path OS-independent (converts slashes if necessary)"""
    if path.endswith('/'):
        return str(pathlib.PurePath(path) / '@')[:-1]
    return str(pathlib.PurePath(path))


np = make_os_independent_path


@pytest.mark.parametrize('rel_path', ['file.txt', 'dir1/dir2/file.txt', 'dir/../file', '../{}/dir1/../dir2/file.txt'])
@pytest.mark.parametrize('create_file', [False, True])
def test_verify_rel_path_is_safe(tmp_path: pathlib.Path, rel_path: str, create_file: bool) -> None:
    """Verify arbitrary safe relative paths, also verify str argument"""
    rel_path_exp = rel_path.format(tmp_path.name)
    if create_file:
        create_simple_file(tmp_path / rel_path_exp, 128, create_dirs=True)

    FileSystem.verify_rel_path_is_safe(tmp_path, pathlib.Path(rel_path_exp))
    FileSystem.verify_rel_path_is_safe(str(tmp_path), np(rel_path_exp))

    FileSystem.verify_rel_path_is_safe(np('/'), np(rel_path.format('../../../..')))
    with current_working_directory(tmp_path):
        FileSystem.verify_rel_path_is_safe(np('.'), pathlib.Path(rel_path_exp))
        FileSystem.verify_rel_path_is_safe(np('./test'), np(rel_path.format('test')))


@pytest.mark.parametrize('rel_path', ['../file.txt', '/file', 'dir/', '.', '..', '/', '', '../{}/../../dir2/file.txt'])
@pytest.mark.parametrize('base_dir_exists', [True, False])
def test_verify_rel_path_is_unsafe(tmp_path: pathlib.Path, rel_path: str, base_dir_exists: bool) -> None:
    """Verify arbitrary unsafe relative paths"""
    if not base_dir_exists:
        tmp_path = tmp_path / 'no_such_directory'
    rel_path = np(rel_path.format(tmp_path.name))
    with pytest.raises(ValueError):
        FileSystem.verify_rel_path_is_safe(tmp_path, rel_path)


@pytest.mark.parametrize('base_dir, rel_file, rel_link, link_content',
                         [('.', 'dir1/file.txt', 'dir1/dir2/link.txt', '../file.txt'),
                          ('dir1', 'dir1/file.txt', 'dir1/dir2/link.txt', '../file.txt'),
                          ('.', 'dir1/file.txt', 'dir2/link.txt', '../dir1/file.txt'),
                          ('dir1', 'dir1/file.txt', 'dir1/dir2/link.txt', '../../dir1/file.txt'),
                          ('./.', 'dir1/dir2/file.txt', 'dir1/link.txt', 'dir2/file.txt'),
                          ('/', 'dir 1/dir 2/a file.txt', 'dir 1/a link.txt', '../dir 1/dir 2/a file.txt')])
@pytest.mark.parametrize('abs_link', [False, True])
def test_verify_symlink_is_safe(tmp_path: pathlib.Path,
                                base_dir: str, rel_file: str, rel_link: str, link_content: str,
                                abs_link: bool) -> None:
    """Verify safe relative and absolute, real and provisional (unsafe) symlinks"""
    base_path, file_path, link_path = tmp_path / base_dir, tmp_path / rel_file, tmp_path / rel_link
    file_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to((link_path.parent / link_content).absolute() if abs_link else np(link_content))

    with pytest.raises(ValueError):
        FileSystem.verify_rel_path_is_safe(base_path, link_path)
    create_simple_file(file_path, 5)
    FileSystem.verify_rel_path_is_safe(base_path, link_path)


@pytest.mark.parametrize('base_dir, rel_file, rel_link, link_content',
                         [('.', 'dir1/file.txt', 'dir1/dir2/link.txt', '../file1.txt'),
                          ('.', 'dir1/file.txt', 'dir1/dir2/link.txt', '..'),
                          ('dir1/dir2', 'dir1/file.txt', 'dir1/dir2/link.txt', '../file.txt'),
                          ('dir1', 'dir1/file.txt', 'dir2/link.txt', '../dir1/file.txt'),
                          ('dir1/dir2', 'dir1/file.txt', 'dir1/dir2/link.txt', '../../dir1/file.txt'),
                          ('/', 'file.txt', 'link.txt', os.path.devnull),
                          (('dir1', 'dir1/file.txt', 'dir1/link.txt', '../dir2/../dir1/file.txt')
                           if sys.platform != 'win32' else ('/', 'file.txt', 'link.txt', 'Q:/file.txt'))])
def test_verify_rel_symlink_is_unsafe(tmp_path: pathlib.Path,
                                      base_dir: str, rel_file: str, rel_link: str, link_content: str) -> None:
    """Verify unsafe relative symlinks"""
    base_path, file_path, link_path = tmp_path / base_dir, tmp_path / rel_file, tmp_path / rel_link
    file_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(np(link_content))
    create_simple_file(file_path, 5)
    with pytest.raises(ValueError):
        FileSystem.verify_rel_path_is_safe(base_path, link_path)


@pytest.mark.parametrize('rel_file', ['file.txt', 'dir1/dir2/dir3/file.txt', 'dir1/../dir2/dir3/file.txt'])
def test_create_directory_for_path(tmp_path: pathlib.Path, rel_file: str) -> None:
    """Create directories for correct paths, also verify str argument"""
    file_path = tmp_path / rel_file
    FileSystem.create_directory_for_path(file_path)
    FileSystem.create_directory_for_path(str(file_path))
    assert file_path.parent.is_dir()
    assert file_path.resolve().parent.is_dir()
    assert not file_path.exists()


def test_create_directory_for_bad_path(tmp_path: pathlib.Path) -> None:
    """Fail creating directories for path containing existing file"""
    file1_path = tmp_path / 'dir1' / 'file1.txt'
    file2_path = file1_path / 'dir2' / 'file2.txt'
    create_simple_file(file1_path, 0, create_dirs=True)
    with pytest.raises(NotADirectoryError if sys.platform != 'win32' else FileNotFoundError):
        FileSystem.create_directory_for_path(file2_path)


@pytest.mark.parametrize('algos', [None, [], ['sha1'], ['sha256'], ['sha1', 'sha256']])
def test_verify_size_and_digests(tmp_path: pathlib.Path, algos: list[str] | None) -> None:
    """Verify arbitrary file size and multiple digests, also verify str, None and uppercase arguments"""
    create_simple_file(tmp_file_path := tmp_path / 'file.txt', 253)
    base_digests = {
        'sha1': 'DE4FCC1C5AFF0C2F455660a4548916c22a817f68',
        'sha256': '1329e1bd71a6a7b275594ffb7ac73e14C4205C25A39EFB2F0E3F2A1B6C7B5856'
    }
    digests = None
    if algos is not None:
        digests = {algo: digest for algo, digest in base_digests.items() if algo in algos}

    FileSystem.verify_size_and_digests(tmp_file_path, size=253, digests=digests)
    FileSystem.verify_size_and_digests(str(tmp_file_path), digests=digests)


@pytest.mark.parametrize('algos', [['sha1'], ['sha256'], ['sha1', 'sha256']])
def test_verify_bad_size_and_digests(tmp_path: pathlib.Path, algos: list[str]) -> None:
    """Verify arbitrary incorrect file size and possibly unsupported multiple digests"""
    create_simple_file(tmp_file_path := tmp_path / 'file.txt', 253)
    base_digests = {
        'sha1': 'de4fcc1c5aff0c2f455660a4548916c22a817f68',
        'sha256': '1329e1bd71a6a7b275594ffb7ac73e14c4205c25a39efb2f0e3f2a1b6c7b5856'
    }
    digests = {algo: digest for algo, digest in base_digests.items() if algo in algos}

    with pytest.raises(ValueError):
        FileSystem.verify_size_and_digests(tmp_file_path, size=256)

    FileSystem.verify_size_and_digests(tmp_file_path, digests=digests)

    last_algo = tuple(digests.keys())[-1]
    with pytest.raises(ValueError):
        FileSystem.verify_size_and_digests(tmp_file_path,
                                           digests=dict(digests, **{last_algo + 'x': digests[last_algo]}))

    digests[last_algo] = digests[last_algo][:-1] + '0'
    with pytest.raises(ValueError):
        FileSystem.verify_size_and_digests(tmp_file_path, digests=digests)


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


@pytest.mark.parametrize('tmp_file_timestamp', [-0.1, -1, -500])
def test_set_negative_file_timestamp(tmp_path: pathlib.Path, tmp_file_timestamp: int | float) -> None:
    """Negative file timestamp should be ignored"""
    create_simple_file(tmp_file_path := tmp_path / 'file.txt', 0)
    tmp_file_stat_before = os.stat(tmp_file_path)
    FileSystem.set_file_timestamp(tmp_file_path, tmp_file_timestamp)
    tmp_file_stat_after = os.stat(tmp_file_path)
    assert tmp_file_stat_before == tmp_file_stat_after


@pytest.mark.parametrize('tmp_path_timestamp', [7200, 1234567890.123456])
def test_set_directory_timestamp(tmp_path: pathlib.Path, caplog: LogCaptureFixture,
                                 tmp_path_timestamp: int | float) -> None:
    """Set arbitrary integer and floating-point directory timestamp, also verify str argument and cover DEBUG log"""
    caplog.set_level(logging.DEBUG)
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
