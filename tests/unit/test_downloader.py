"""Downloader class unit tests"""
from __future__ import annotations

import hashlib
import http
import logging
import pathlib

import pytest
from _pytest.logging import LogCaptureFixture
from pytest_httpserver import HTTPServer
from pytest_mock import MockerFixture
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
                             mocker: MockerFixture,
                             size: int | None, digests: dict[str, str] | None,
                             progress: bool, verbose: bool, log_level: int) -> None:
    """One-shot successful download, exercising all possible parameters"""
    caplog.set_level(log_level)
    mocker.patch.object(curldl.Downloader, 'PROGRESS_SEC', 0)

    file_data = b'x' * 100
    httpserver.expect_oneshot_request('/file.txt', method='GET').respond_with_data(file_data)

    downloader = curldl.Downloader(basedir=tmp_path, progress=progress, verbose=verbose)
    downloader.download(httpserver.url_for('/file.txt'), 'file.txt', expected_size=size, expected_digests=digests)
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
        downloader.download(httpserver.url_for('/file.txt'), 'file.txt', expected_size=size)

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
        downloader.download(httpserver.url_for('/file.txt'), 'file.txt', expected_digests=digests)

    httpserver.check()
    assert not (tmp_path / 'file.txt').exists()
    assert not (tmp_path / 'file.txt.part').exists()


def test_successful_download_after_failure(tmp_path: pathlib.Path, httpserver: HTTPServer,
                                           caplog: LogCaptureFixture, mocker: MockerFixture) -> None:
    """Download that succeeds after initial failure"""
    caplog.set_level(logging.DEBUG)

    mocker.patch.object(curldl.Downloader, 'RETRY_WAIT_SEC', 0)
    mocker.patch.object(curldl.Downloader, 'RETRY_ATTEMPTS', 5)
    mocker.patch.object(curldl.Downloader, 'MAX_REDIRECTS', 0)
    retries_left = curldl.Downloader.RETRY_ATTEMPTS

    def eventual_response_handler_cb(request: Request) -> Response:
        """Fail curl with a redirect in first RETRY_ATTEMPTS-1 requests, then respond"""
        nonlocal retries_left
        retries_left -= 1
        if retries_left != 0:
            return Response("Redirect (fails PycURL)", status=http.HTTPStatus.TEMPORARY_REDIRECT,
                            headers=[('Location', httpserver.url_for('/elsewhere'))])
        return Response(b'xxx')

    httpserver.expect_request('/file.txt', method='GET').respond_with_handler(eventual_response_handler_cb)

    downloader = curldl.Downloader(basedir=tmp_path)
    downloader.download(httpserver.url_for('/file.txt'), 'file.txt')

    httpserver.check()
    assert read_file_content(tmp_path / 'file.txt') == b'xxx'
