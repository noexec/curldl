"""curldl functional tests"""
from __future__ import annotations

import logging
import os
import pathlib

import pycurl
import pytest
from _pytest.logging import LogCaptureFixture
from pytest_httpserver import HTTPServer

from unit.test_curldl import compute_hex_digest, read_file_content
import curldl
from curldl import util


@pytest.mark.parametrize('requests, file_path',
                         [([1], 'file.bin'), ([1, -1], '../file.bin'), ([3, -2], 'dir1/dir2/some%20file.bin'),
                          ([2, -2, 1, -3, 4], './dir1/dir2/../dir3/dir 4/some  file.bin')])
@pytest.mark.parametrize('size, algos', [(None, None), (0, ['sha1']), (1, None), (None, ['sha256']),
                                         (1500, ['sha1', 'sha256', 'sha3_512'])])
@pytest.mark.parametrize('progress, verbose, log_level',
                         [(False, False, logging.WARNING), (True, True, logging.INFO), (False, True, logging.DEBUG)])
def test_file_downloads(tmp_path: pathlib.Path, httpserver: HTTPServer, caplog: LogCaptureFixture,
                        requests: list[int], file_path: str, size: int | None, algos: list[str] | None,
                        progress: bool, verbose: bool, log_level: int) -> None:
    """One or more successful or 404, one-shot or sequence, safe or unsafe file download attempts"""
    caplog.set_level(log_level)
    dl = curldl.Curldl(basedir=tmp_path / 'base', progress=progress, verbose=verbose, retry_attempts=0)

    file_content = os.urandom(200 if size is None else size)
    file_digests = {algo: compute_hex_digest(file_content, algo) for algo in algos} if algos else None
    try:
        util.FileSystem.verify_rel_path_is_safe(tmp_path / 'base', file_path)
        file_path_is_safe = True
    except ValueError:
        file_path_is_safe = False

    for req_id, req_count in enumerate(requests):
        for file_suffix in (f'.{req_id}.{req_subid}' for req_subid in range(abs(req_count))):
            file_local_path = tmp_path / 'base' / (file_path + file_suffix)
            httpserver.expect_oneshot_request(
                '/location/filename' + file_suffix, method='GET').respond_with_data(file_content)

            if req_count > 0 and file_path_is_safe:
                dl.get(httpserver.url_for('/location/filename') + file_suffix,
                       file_path + file_suffix, size=size, digests=file_digests)
                assert read_file_content(file_local_path) == file_content

            else:
                with pytest.raises(pycurl.error if file_path_is_safe else ValueError):
                    dl.get(httpserver.url_for('/location/filename') + file_suffix + '.404',
                           file_path + file_suffix, size=size, digests=file_digests)
                assert not file_local_path.exists()

                if file_path_is_safe:
                    with pytest.raises(AssertionError):
                        httpserver.check()
                    httpserver.clear()

            httpserver.check()
