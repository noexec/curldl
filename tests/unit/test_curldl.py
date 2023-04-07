"""Curldl class unit tests"""
from __future__ import annotations

import hashlib
import http
import http.client
import http.server
import logging
import os
import pathlib
import socket
import socketserver
import sys
import threading
from typing import Callable

import pycurl
import pytest
import werkzeug.exceptions
from _pytest.logging import LogCaptureFixture
from pytest_httpserver import HTTPServer
from pytest_mock import MockerFixture
from werkzeug import Request, Response

import curldl
from curldl import util

BASE_TIMESTAMP = 1678901234


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


def make_range_response_handler(path: str, data: bytes, *, statuses: list[bool] | None = None,
                                timestamp: int | float | None = None) -> Callable[[Request], Response]:
    """Create werkzeug handler that handles regular (200) or byte range (206/416) requests.
    If timestamp is not specified, different timestamp is sent for each request"""
    status_idx = -1

    def range_response_handler_cb(request: Request) -> Response:
        """Respond with a Content-Range if requested"""
        assert request.path == path

        nonlocal status_idx
        status_idx += 1
        if statuses and not statuses[status_idx]:
            return Response('Should cause RuntimeException', status=http.client.SERVICE_UNAVAILABLE)

        response = Response(data, mimetype='application/octet-stream')
        sent_timestamp = timestamp if timestamp is not None else BASE_TIMESTAMP + status_idx * 10
        response.last_modified = util.Time.timestamp_to_dt(sent_timestamp)
        return response.make_conditional(request.environ, accept_ranges=True, complete_length=len(data))

    return range_response_handler_cb


@pytest.mark.parametrize('size', [None, 100])
@pytest.mark.parametrize('digests', [None, {'sha1': '50E483690EC481F4AF7F6fb524b2b99eb1716565'}])
@pytest.mark.parametrize('progress', [False, True])
@pytest.mark.parametrize('fake_tty', [False, True])
@pytest.mark.parametrize('verbose', [False, True])
@pytest.mark.parametrize('log_level', [logging.WARNING, logging.INFO, logging.DEBUG])
def test_successful_download(tmp_path: pathlib.Path, httpserver: HTTPServer, caplog: LogCaptureFixture,
                             mocker: MockerFixture, size: int | None, digests: dict[str, str] | None,
                             progress: bool, fake_tty: bool, verbose: bool, log_level: int) -> None:
    """One-shot successful download, exercising all possible parameters"""
    caplog.set_level(log_level)
    if fake_tty:
        mocker.patch.object(sys.stderr, 'isatty', lambda: True)

    file_data = b'x' * 100
    httpserver.expect_oneshot_request('/file.txt', method='GET').respond_with_data(file_data)

    dl = curldl.Curldl(basedir=tmp_path, progress=progress, verbose=verbose)
    dl.get(httpserver.url_for('/file.txt'), 'file.txt', size=size, digests=digests)
    httpserver.check()
    assert read_file_content(tmp_path / 'file.txt') == file_data


@pytest.mark.parametrize('size', [0, 1, 99, 101])
def test_failed_size_check(tmp_path: pathlib.Path, httpserver: HTTPServer, caplog: LogCaptureFixture,
                           size: int) -> None:
    """Download that fails file size verification"""
    caplog.set_level(logging.DEBUG)

    file_data = b'x' * 100
    httpserver.expect_oneshot_request('/file.txt', method='GET').respond_with_data(file_data)

    dl = curldl.Curldl(basedir=tmp_path)
    with pytest.raises(ValueError):
        dl.get(httpserver.url_for('/file.txt'), 'file.txt', size=size)

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

    dl = curldl.Curldl(basedir=tmp_path)
    with pytest.raises(ValueError):
        dl.get(httpserver.url_for('/file.txt'), 'file.txt', digests=digests)

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
            return Response('Redirect (fails PycURL)', status=http.HTTPStatus.TEMPORARY_REDIRECT,
                            headers={'Location': httpserver.url_for('/elsewhere')})
        return Response(b'xxx')

    dl = curldl.Curldl(basedir=tmp_path, retry_wait_sec=0, retry_attempts=retries_left, max_redirects=0)
    httpserver.expect_request('/file.txt', method='GET').respond_with_handler(eventual_response_handler_cb)
    dl.get(httpserver.url_for('/file.txt'), 'file.txt')

    httpserver.check()
    assert read_file_content(tmp_path / 'file.txt') == b'xxx'


def test_redirected_download(tmp_path: pathlib.Path, httpserver: HTTPServer) -> None:
    """Download that succeeds after several redirects, also check file timestamp"""
    max_redirects = 5

    def redirect_response_handler_cb(request: Request) -> Response:
        """Redirect several times, then respond"""
        if request.path != '/file.txt' + ('+' * max_redirects):
            return Response('Redirect (PycURL should follow)', status=http.HTTPStatus.TEMPORARY_REDIRECT,
                            headers=[('Location', httpserver.url_for(request.path + '+'))])
        return Response(b'x' * 4096, mimetype='application/octet-stream',
                        headers={'Last-Modified': 'Fri, 13 Feb 2009 23:31:30 GMT'})

    for redirect_idx in range(max_redirects + 1):
        httpserver.expect_ordered_request(
            '/file.txt' + ('+' * redirect_idx), method='GET').respond_with_handler(redirect_response_handler_cb)

    dl = curldl.Curldl(basedir=tmp_path, verbose=True, max_redirects=max_redirects)
    dl.get(httpserver.url_for('/file.txt'), 'file.txt')
    httpserver.check()

    file_stat = os.stat(tmp_path / 'file.txt')
    assert file_stat.st_mtime == file_stat.st_atime == 1234567890
    assert read_file_content(tmp_path / 'file.txt') == b'x' * 4096


@pytest.mark.parametrize('size, part_size', [(100, 50), (101, 0), (51, 51), (51, 50), (0, 0), (150, 200)])
@pytest.mark.parametrize('min_part_bytes', [0, 50, 51])
@pytest.mark.parametrize('verify_file', [False, True])
@pytest.mark.parametrize('timestamp', [1234567890, None])
def test_partial_download(tmp_path: pathlib.Path, httpserver: HTTPServer, caplog: LogCaptureFixture,
                          size: int, part_size: int, min_part_bytes: int, verify_file: bool,
                          timestamp: int | None) -> None:
    """Download a partial download that succeeds after a rollback, possibly with unchanged timestamp"""
    caplog.set_level(logging.DEBUG)

    file_data = os.urandom(size)
    httpserver.expect_request('/abc', method='GET').respond_with_handler(
        make_range_response_handler('/abc', file_data, timestamp=timestamp, statuses=[True, False, True]))

    dl = curldl.Curldl(basedir=tmp_path, verbose=True, min_part_bytes=min_part_bytes, retry_attempts=0)

    def download_and_possibly_verify() -> None:
        """Download file and verify its size/digest according to test parameter"""
        dl.get(httpserver.url_for('/abc'), 'file.bin', size=(size if verify_file else None),
               digests=({'sha1': compute_hex_digest(file_data, 'sha1')} if verify_file else None))

    # Request #1: should succeed
    download_and_possibly_verify()
    httpserver.check()

    partial_timestamp = os.stat(tmp_path / 'file.bin').st_mtime
    assert read_file_content(tmp_path / 'file.bin') == file_data
    os.rename(tmp_path / 'file.bin', tmp_path / 'file.bin.part')
    os.truncate(tmp_path / 'file.bin.part', part_size)
    os.utime(tmp_path / 'file.bin.part', times=(partial_timestamp, partial_timestamp))

    # Request #2 on partial file: generally fails with 503
    # Rolls back to existing partial file if verification data is present
    with pytest.raises(pycurl.error) as ex_info:
        download_and_possibly_verify()
    assert ex_info.value.args[0] == pycurl.E_HTTP_RETURNED_ERROR
    httpserver.check()

    assert ((tmp_path / 'file.bin.part').exists() ==
            (min_part_bytes <= part_size and (verify_file or min_part_bytes == 0 or min_part_bytes < part_size < size)))
    if verify_file and min_part_bytes <= part_size <= size:
        assert (tmp_path / 'file.bin.part').stat().st_size == part_size
    assert not (tmp_path / 'file.bin').exists()

    # Request #3: should succeed unless weird conditions
    if verify_file and part_size >= size > 0:
        with pytest.raises(pycurl.error):
            download_and_possibly_verify()
        assert isinstance(httpserver.handler_errors[0], werkzeug.exceptions.RequestedRangeNotSatisfiable)
        httpserver.check_assertions()
        return

    download_and_possibly_verify()
    httpserver.check()

    assert os.stat(tmp_path / 'file.bin').st_mtime == (timestamp or BASE_TIMESTAMP + 2 * 10)
    assert read_file_content(tmp_path / 'file.bin') == file_data


@pytest.mark.parametrize('size', [0, 1024])
@pytest.mark.parametrize('verify_file', [False, True])
@pytest.mark.parametrize('timestamp1', [0, 1234567890, 1678901234])
@pytest.mark.parametrize('timestamp2', [0, 1234567890, 1678901234, 1456789012.6789])
def test_repeated_download(tmp_path: pathlib.Path, httpserver: HTTPServer, caplog: LogCaptureFixture,
                           size: int, verify_file: bool, timestamp1: int, timestamp2: int | float) -> None:
    """One download after another, with a possibly unmodified source file; also verifies User-Agent header"""
    caplog.set_level(logging.DEBUG)
    dl = curldl.Curldl(basedir=tmp_path, verbose=True, user_agent='curl/0.0.0')
    data1, data2 = os.urandom(size), os.urandom(size)

    def make_response_handler(timestamp: int | float, data: bytes) -> Callable[[Request], Response]:
        """Create werkzeug handler for If-Modified-Since request header"""
        def response_handler_cb(request: Request) -> Response:
            """Returns 304 Not Modified response if timestamp is not newer than one in request"""
            assert request.user_agent.string == 'curl/0.0.0'
            if request.if_modified_since and util.Time.timestamp_to_dt(timestamp) <= request.if_modified_since:
                return Response('Should not update downloaded file', status=http.client.NOT_MODIFIED)
            response = Response(data)
            response.last_modified = util.Time.timestamp_to_dt(timestamp)
            return response
        return response_handler_cb

    def download_and_possibly_verify(data: bytes) -> None:
        """Download file and verify its size/digest according to test parameter and expected data"""
        dl.get(httpserver.url_for('/file.txt'), 'file.txt', size=(size if verify_file else None),
               digests=({'sha1': compute_hex_digest(data, 'sha1')} if verify_file else None))

    httpserver.expect_ordered_request('/file.txt').respond_with_handler(make_response_handler(timestamp1, data1))
    httpserver.expect_ordered_request('/file.txt').respond_with_handler(make_response_handler(timestamp2, data2))

    download_and_possibly_verify(data1)
    httpserver.check()
    assert os.stat(tmp_path / 'file.txt').st_mtime == timestamp1
    assert read_file_content(tmp_path / 'file.txt') == data1

    download_and_possibly_verify(data2)
    httpserver.check()
    if timestamp1 < timestamp2 and not verify_file:
        assert os.stat(tmp_path / 'file.txt').st_mtime == int(timestamp2)
        assert read_file_content(tmp_path / 'file.txt') == data2
    else:
        assert os.stat(tmp_path / 'file.txt').st_mtime == timestamp1
        assert read_file_content(tmp_path / 'file.txt') == data1


def test_aborted_download(tmp_path: pathlib.Path, caplog: LogCaptureFixture) -> None:
    """An aborted server connection that did not send HTTP status"""
    caplog.set_level(logging.DEBUG)
    dl = curldl.Curldl(basedir=tmp_path, verbose=True, retry_attempts=0)

    class DisconnectingHTTPServer(http.server.BaseHTTPRequestHandler):
        """HTTP Server that closes the connection after reading the request"""

        def do_GET(self) -> None:  # pylint: disable=invalid-name
            """Close connection without processing"""
            self.connection.shutdown(socket.SHUT_RDWR)

    with socketserver.TCPServer(('localhost', 0), DisconnectingHTTPServer) as httpd:
        hostname, port = httpd.server_address
        assert isinstance(hostname, str)
        url = f'http://{hostname}:{port}/path'

        threading.Thread(target=httpd.handle_request, daemon=True).start()
        with pytest.raises(pycurl.error) as ex_info:
            dl.get(url, 'some-file.txt')

        assert ex_info.value.args[0] == pycurl.E_GOT_NOTHING


@pytest.mark.parametrize('size', [100, 5000])
@pytest.mark.parametrize('specify_size', [False, True])
@pytest.mark.parametrize('always_keep_part_size', [0, 50, 2499, 2501, 8000])
def test_partial_download_keep(tmp_path: pathlib.Path, httpserver: HTTPServer, caplog: LogCaptureFixture,
                               size: int, specify_size: bool, always_keep_part_size: int) -> None:
    """Verify policy of keeping partial download in absence of verification data"""
    caplog.set_level(logging.DEBUG)
    with open(tmp_path / 'file.txt.part', 'wb') as part_file:
        part_file.write(b'x' * (size // 2))

    httpserver.expect_oneshot_request('/file.txt').respond_with_handler(
        make_range_response_handler('/file.txt', b'y' * size))

    dl = curldl.Curldl(basedir=tmp_path, verbose=True, retry_attempts=0, min_part_bytes=0,
                       always_keep_part_bytes=always_keep_part_size)
    dl.get(httpserver.url_for('/file.txt'), 'file.txt', size=(size if specify_size else None))
    httpserver.check()

    assert not (tmp_path / 'file.txt.part').exists()
    assert read_file_content(tmp_path / 'file.txt') == ((b'x' * (size // 2) + b'y' * (size // 2))
                                                        if specify_size or always_keep_part_size <= size // 2
                                                        else b'y' * size)


@pytest.mark.parametrize('scheme_str', ['file', 'gopher', 'https', 'ftp'])
def test_disallowed_schemes(tmp_path: pathlib.Path, caplog: LogCaptureFixture, scheme_str: str) -> None:
    """Verify disallowed schemes are rejected by PycURL"""
    caplog.set_level(logging.DEBUG)

    scheme = getattr(pycurl, 'PROTO_' + scheme_str.upper())
    default_enabled = scheme in curldl.Curldl.DEFAULT_ALLOWED_PROTOCOLS
    assert bool(curldl.Curldl(basedir=tmp_path)._allowed_protocols_bitmask  # pylint: disable=protected-access
                & scheme) == default_enabled

    dl = curldl.Curldl(basedir=tmp_path, min_part_bytes=0, allowed_protocols_bitmask=
                       ((pycurl.PROTO_TFTP | pycurl.PROTO_DICT) if default_enabled else 0))
    with pytest.raises(pycurl.error) as ex_info:
        dl.get(f'{scheme_str}://{"example.com" if scheme_str != "file" else ""}/test', 'test')

    assert ex_info.value.args[0] == pycurl.E_UNSUPPORTED_PROTOCOL
    assert not (tmp_path / 'test').exists()


@pytest.mark.parametrize('disable_resume', [False, True])
@pytest.mark.parametrize('allowed_protocols', [pycurl.PROTO_FILE, pycurl.PROTO_ALL])
def test_file_scheme_partial_download(tmp_path: pathlib.Path, caplog: LogCaptureFixture, mocker: MockerFixture,
                                      disable_resume: bool, allowed_protocols: int) -> None:
    """Verify that a partial download via file:// URL is successful (or not) once FILE scheme is allowed"""
    caplog.set_level(logging.DEBUG)
    if disable_resume:
        mocker.patch.object(curldl.Curldl, 'RESUME_FROM_SCHEMES', curldl.Curldl.RESUME_FROM_SCHEMES - {'file'})

    with open(tmp_path / 'file.txt', 'wb') as file:
        file.write(b'x' * 512)

    dl = curldl.Curldl(basedir=tmp_path, allowed_protocols_bitmask=allowed_protocols)
    dl.get((tmp_path / 'file.txt').absolute().as_uri(), 'file.out')
    assert read_file_content(tmp_path / 'file.out') == b'x' * 512

    with open(tmp_path / 'file.txt', 'wb') as file:
        file.write(b'y' * 512)
    os.rename(tmp_path / 'file.out', tmp_path / 'file.out.part')
    os.truncate(tmp_path / 'file.out.part', 256)

    dl.get((tmp_path / 'file.txt').absolute().as_uri(), 'file.out', size=512)
    assert read_file_content(tmp_path / 'file.out') == (b'y' if disable_resume else b'x') * 256 + b'y' * 256


@pytest.mark.parametrize('allowed_protocols', [pycurl.PROTO_FILE | pycurl.PROTO_HTTPS, pycurl.PROTO_ALL])
def test_file_scheme_unsuccessful_download(tmp_path: pathlib.Path, caplog: LogCaptureFixture,
                                           allowed_protocols: int) -> None:
    """Verify that a non-HTTP error of allowed scheme does not confuse Curldl"""
    caplog.set_level(logging.DEBUG)

    dl = curldl.Curldl(basedir=tmp_path, allowed_protocols_bitmask=allowed_protocols)
    with pytest.raises(pycurl.error) as ex_info:
        dl.get((tmp_path / 'file.txt').absolute().as_uri(), 'file.txt')

    assert ex_info.value.args[0] == pycurl.E_FILE_COULDNT_READ_FILE
    assert not (tmp_path / 'txt').exists()


@pytest.mark.parametrize('allowed_protocols',
                         [pycurl.PROTO_SMTP, pycurl.PROTO_SMTP | pycurl.PROTO_DICT, pycurl.PROTO_ALL])
def test_smtp_scheme_bailout(tmp_path: pathlib.Path, caplog: LogCaptureFixture, allowed_protocols: int) -> None:
    """Verify that non-0 non-HTTP response code does not confuse Curldl"""
    caplog.set_level(logging.DEBUG)
    dl = curldl.Curldl(basedir=tmp_path, allowed_protocols_bitmask=allowed_protocols, retry_attempts=0)

    class SMTPMockServer(socketserver.StreamRequestHandler):
        """SMTP server that immediately sends a bad hello message"""
        def handle(self) -> None:
            """Sends a bad message that is reflected in curl's response status"""
            self.wfile.write(b'555\r\n')
            self.connection.shutdown(socket.SHUT_RDWR)

    with socketserver.TCPServer(('localhost', 0), SMTPMockServer) as smtpd:
        threading.Thread(target=smtpd.handle_request, daemon=True).start()
        with pytest.raises(pycurl.error) as ex_info:
            dl.get(f'smtp://localhost:{smtpd.server_address[1]}/test', 'smtp.txt')
        assert ex_info.value.args[0] == pycurl.E_FTP_WEIRD_SERVER_REPLY

    assert not (tmp_path / 'smtp.txt').exists()
    assert list(log_record for log_record in caplog.get_records('call') if 'SMTP 555:' in log_record.message)


def test_configuration_callback(tmp_path: pathlib.Path, httpserver: HTTPServer) -> None:
    """Verify that configuration callback is invoked by Curldl and has effect"""
    def curl_configuration_cb(curl: pycurl.Curl) -> None:
        """Changes User-Agent header"""
        curl.setopt(pycurl.USERAGENT, 'changed-user-agent')

    def response_handler_cb(request: Request) -> Response:
        """Returns 304 Not Modified response if timestamp is not newer than one in request"""
        assert request.user_agent.string == 'changed-user-agent'
        return Response(b'xyz')

    httpserver.expect_oneshot_request('/abc').respond_with_handler(response_handler_cb)

    dl = curldl.Curldl(basedir=tmp_path, retry_attempts=0, curl_config_callback=curl_configuration_cb)
    dl.get(httpserver.url_for('/abc'), 'abc.txt')

    httpserver.check()
    assert read_file_content(tmp_path / 'abc.txt') == b'xyz'
