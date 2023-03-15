"""Downloader class unit tests"""
from __future__ import annotations

import hashlib
import http
import http.client
import logging
import os
import pathlib

import pytest
from _pytest.logging import LogCaptureFixture
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

import curldl


def compute_hex_digest(data: bytes, algo: str) -> str:
    """Compute digest for given input"""
    assert algo in hashlib.algorithms_available
    digest = hashlib.new(algo)
    digest.update(data)
    return digest.hexdigest()


def read_file_content(file_path: pathlib.Path) -> bytes:
    """Read complete contents of a file"""
    assert file_path.is_file()
    with open(file_path, 'rb') as file:
        return file.read()


@pytest.mark.parametrize('size', [None, 100])
@pytest.mark.parametrize('digests', [None, {'sha1': '50E483690EC481F4AF7F6fb524b2b99eb1716565'}])
@pytest.mark.parametrize('progress', [False, True])
@pytest.mark.parametrize('verbose', [False, True])
@pytest.mark.parametrize('log_level', [logging.WARNING, logging.INFO, logging.DEBUG])
def test_successful_download(tmp_path: pathlib.Path, httpserver: HTTPServer, caplog: LogCaptureFixture,
                             size: int | None, digests: dict[str, str] | None,
                             progress: bool, verbose: bool, log_level: int) -> None:
    """One-shot successful download, exercising all possible parameters"""
    caplog.set_level(log_level)

    file_data = b'x' * 100
    httpserver.expect_oneshot_request('/file.txt', method='GET').respond_with_data(file_data)

    downloader = curldl.Downloader(basedir=tmp_path, progress=progress, verbose=verbose, progress_sec=0)
    downloader.download(httpserver.url_for('/file.txt'), 'file.txt', size=size, digests=digests)
    httpserver.check()
    assert read_file_content(tmp_path / 'file.txt') == file_data


@pytest.mark.parametrize('size', [0, 1, 99, 101])
def test_failed_size_check(tmp_path: pathlib.Path, httpserver: HTTPServer, caplog: LogCaptureFixture,
                           size: int) -> None:
    """Download that fails file size verification"""
    caplog.set_level(logging.DEBUG)

    file_data = b'x' * 100
    httpserver.expect_oneshot_request('/file.txt', method='GET').respond_with_data(file_data)

    downloader = curldl.Downloader(basedir=tmp_path)
    with pytest.raises(ValueError):
        downloader.download(httpserver.url_for('/file.txt'), 'file.txt', size=size)

    httpserver.check()
    assert not (tmp_path / 'file.txt').exists()
    assert not (tmp_path / 'file.txt.part').exists()


@pytest.mark.parametrize('digests', [{'sha1': '50E483690EC481F4AF7F6fb524b2b99eb1716564'}])
def test_failed_digest_check(tmp_path: pathlib.Path, httpserver: HTTPServer, caplog: LogCaptureFixture,
                             digests: dict[str, str]) -> None:
    """Download that fails file digest verification"""
    caplog.set_level(logging.DEBUG)

    file_data = b'x' * 100
    httpserver.expect_oneshot_request('/file.txt', method='GET').respond_with_data(file_data)

    downloader = curldl.Downloader(basedir=tmp_path)
    with pytest.raises(ValueError):
        downloader.download(httpserver.url_for('/file.txt'), 'file.txt', digests=digests)

    httpserver.check()
    assert not (tmp_path / 'file.txt').exists()
    assert not (tmp_path / 'file.txt.part').exists()


def test_successful_download_after_failure(tmp_path: pathlib.Path, httpserver: HTTPServer,
                                           caplog: LogCaptureFixture) -> None:
    """Download that succeeds after initial failure"""
    caplog.set_level(logging.DEBUG)
    retries_left = 5

    def eventual_response_handler_cb(request: Request) -> Response:
        """Fail curl with a redirect in first RETRY_ATTEMPTS-1 requests, then respond"""
        nonlocal retries_left
        retries_left -= 1
        if retries_left != 0:
            return Response("Redirect (fails PycURL)", status=http.HTTPStatus.TEMPORARY_REDIRECT,
                            headers={'Location': httpserver.url_for('/elsewhere')})
        return Response(b'xxx')

    downloader = curldl.Downloader(basedir=tmp_path, retry_wait_sec=0, retry_attempts=retries_left, max_redirects=0)
    httpserver.expect_request('/file.txt', method='GET').respond_with_handler(eventual_response_handler_cb)
    downloader.download(httpserver.url_for('/file.txt'), 'file.txt')

    httpserver.check()
    assert read_file_content(tmp_path / 'file.txt') == b'xxx'


def test_redirected_download(tmp_path: pathlib.Path, httpserver: HTTPServer) -> None:
    """Download that succeeds after several redirects, also check file timestamp"""
    max_redirects = 5

    def redirect_response_handler_cb(request: Request) -> Response:
        """Redirect several times, then respond"""
        if request.path != '/file.txt' + ('+' * max_redirects):
            return Response(http.client.responses[status := http.HTTPStatus.TEMPORARY_REDIRECT], status=status,
                            headers=[('Location', httpserver.url_for(request.path + '+'))])
        return Response(b'x' * 4096, mimetype='application/octet-stream',
                        headers={'Last-Modified': 'Fri, 13 Feb 2009 23:31:30 GMT'})

    for redirect_idx in range(max_redirects + 1):
        httpserver.expect_ordered_request(
            '/file.txt' + ('+' * redirect_idx), method='GET').respond_with_handler(redirect_response_handler_cb)

    downloader = curldl.Downloader(basedir=tmp_path, verbose=True, max_redirects=max_redirects)
    downloader.download(httpserver.url_for('/file.txt'), 'file.txt')
    httpserver.check()

    file_stat = os.stat(tmp_path / 'file.txt')
    assert file_stat.st_mtime == file_stat.st_atime == 1234567890
    assert read_file_content(tmp_path / 'file.txt') == b'x' * 4096
