"""CLI entry point functional tests"""
from __future__ import annotations

import argparse
import inspect
import logging
import os.path
import pathlib
import subprocess  # nosec
import sys
from importlib import metadata

import pytest
from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture
from pytest_httpserver import HTTPServer
from pytest_mock import MockerFixture

import curldl
from curldl import cli

PACKAGE_NAME = curldl.__package__
ENTRY_POINT = PACKAGE_NAME


def patch_system_environment(mocker: MockerFixture, arguments: list[str]) -> None:
    """Patch sys.argv and make sys.excepthook available for modification"""
    mocker.patch.object(sys, 'argv', [PACKAGE_NAME] + arguments)
    mocker.patch.object(sys, 'excepthook')


def patch_logger_config(mocker: MockerFixture, expected_log_level: str) -> None:
    """Replace logging.basicConfig() with verifier of expected configured log level"""
    def logging_basic_config_mock(level: int) -> None:
        assert level == getattr(logging, expected_log_level.upper())
    mocker.patch.object(logging, 'basicConfig', logging_basic_config_mock)


@pytest.mark.parametrize('use_entry_point', [False, True])
@pytest.mark.parametrize('arguments, should_succeed', [('-h', True), ('--help', True), ('--no-such-argument', False)])
def test_run_cli_module(use_entry_point: bool, arguments: str, should_succeed: bool) -> None:
    """Verify that running the module via entry point and via __main__.py works, test success and failure"""
    package_base_path = pathlib.Path(inspect.getfile(curldl)).parent / os.path.pardir
    command = ENTRY_POINT if use_entry_point else f'python -m {PACKAGE_NAME}'
    result = subprocess.run(f'{command} {arguments}'.split(),   # nosec
                            check=False, text=True, encoding='ascii', capture_output=True,
                            env=dict(os.environ, PYTHONPATH=str(package_base_path)))
    assert (result.returncode == 0) == should_succeed
    if not should_succeed:
        result.stdout, result.stderr = result.stderr, result.stdout
    assert result.stdout.startswith('usage:') and not result.stderr


@pytest.mark.parametrize('argument', ['-V', '--version'])
@pytest.mark.parametrize('use_metadata', [True, False])
def test_get_version(mocker: MockerFixture, capsys: CaptureFixture[str], argument: str, use_metadata: bool) -> None:
    """Verify version number is correctly retrieved from both package and TOML sources"""
    mock_version = '1.0.0.mock'

    def metadata_version_mock(distribution_name: str) -> str:
        assert distribution_name == PACKAGE_NAME
        if use_metadata:
            return mock_version
        raise metadata.PackageNotFoundError

    patch_system_environment(mocker, [argument])
    mocker.patch.object(metadata, 'version', metadata_version_mock)

    with pytest.raises(SystemExit if use_metadata else metadata.PackageNotFoundError) as ex_info:
        cli.main()

    outputs = capsys.readouterr()
    if use_metadata:
        assert isinstance(ex_info.value, SystemExit) and ex_info.value.code == 0
        assert outputs.out == f'{PACKAGE_NAME} {mock_version}\n' and not outputs.err
    else:
        assert not outputs.out


@pytest.mark.parametrize('specify_output_size_and_digest', [False, True])
@pytest.mark.parametrize('log_level', ['warning', 'info', 'debug'])
@pytest.mark.parametrize('verbose', [False, True])
@pytest.mark.parametrize('long_opt', [False, True])
def test_download_file(mocker: MockerFixture, tmp_path: pathlib.Path, httpserver: HTTPServer,
                       specify_output_size_and_digest: bool, log_level: str, verbose: bool, long_opt: bool) -> None:
    """Verify an example file is successfully downloaded using all supported CLI arguments"""
    file_data, file_path = b'x' * 128, tmp_path / 'dir' / 'file.txt'
    file_digest = '150fa3fbdc899bd0b8f95a9fb6027f564d953762'

    arguments: list[str] = [['-b', '--basedir'][long_opt], str(file_path.parent), ['-p', '--progress'][long_opt]]
    if specify_output_size_and_digest:
        file_path = file_path.parent / 'dir-manual' / 'file-manual.txt'
        arguments += [['-o', '--output'][long_opt], os.path.join('dir-manual', 'file-manual.txt')]
        arguments += [['-s', '--size'][long_opt], str(len(file_data))]
        arguments += [['-a', '--algo'][long_opt], 'sha1', ['-d', '--digest'][long_opt], file_digest]
    if log_level != 'info':
        arguments += [['-l', '--log'][long_opt], log_level]
    if verbose:
        arguments += [['-v', '--verbose'][long_opt]]

    request_handler = httpserver.expect_oneshot_request('/location/file.txt;a=b,c=d',
                                                        query_string={'x': '1', 'y': '2'}, method='GET')
    request_handler.respond_with_data(file_data, content_type='text/plain')
    arguments += [httpserver.url_for('/location/file.txt;a=b,c=d?y=2&x=1#fragment')]

    patch_logger_config(mocker, 'debug' if verbose else log_level)
    patch_system_environment(mocker, arguments)
    status_code = cli.main()
    assert status_code == 0

    httpserver.check()
    assert file_path.is_file()
    with open(file_path, 'rb') as file:
        assert file.read() == file_data


@pytest.mark.parametrize('specify_output_size', [False, True])
@pytest.mark.parametrize('specify_output_digest', [False, True])
def test_download_multiple_files(mocker: MockerFixture, caplog: LogCaptureFixture,
                                 tmp_path: pathlib.Path, httpserver: HTTPServer,
                                 specify_output_size: bool, specify_output_digest: bool) -> None:
    """Verify that multiple file arguments are downloaded and verification functions correctly,
    (including that digest verification is attempted on all files)"""
    caplog.set_level(logging.DEBUG)

    url_count = 5
    file_datas = [bytes(chr(ord('x') + idx), 'ascii') * 128 for idx in range(url_count)]
    file_names = [f'file{idx}.txt' for idx in range(url_count)]
    file_digest = '150fa3fbdc899bd0b8f95a9fb6027f564d953762'
    should_succeed = not specify_output_digest

    arguments = ['-b', str(tmp_path), '-l', 'debug', '-v', '-p']
    if specify_output_size:
        arguments += ['-s', str(128)]
    if specify_output_digest:
        arguments += ['-a', 'sha1', '-d', file_digest]

    for idx in range(url_count):
        httpserver.expect_ordered_request(
            url_path := f'/loc1/loc2/{file_names[idx]};a=b', query_string={'c': 'd'}).respond_with_data(file_datas[idx])
        arguments += [httpserver.url_for(url_path + '?c=d#id')]

    patch_logger_config(mocker, 'debug')
    patch_system_environment(mocker, arguments)

    if not should_succeed:
        with pytest.raises(ValueError):
            cli.main()
    else:
        status_code = cli.main()
        assert status_code == 0

    httpserver.check()
    for idx in range(url_count):
        file_path = tmp_path / file_names[idx]
        assert file_path.exists() == should_succeed or idx == 0
        if file_path.exists():
            with open(file_path, 'rb') as file:
                assert file.read() == file_datas[idx]


def test_multiple_downloads_with_output_file(mocker: MockerFixture, tmp_path: pathlib.Path,
                                             httpserver: HTTPServer) -> None:
    """Verify that specifying output with multiple files results in exception and now download is attempted"""
    arguments = ['-b', str(tmp_path), '-o', 'file.txt', '-l', 'critical',
                 httpserver.url_for('/file1.txt'), httpserver.url_for('/file2.txt')]

    patch_logger_config(mocker, 'critical')
    patch_system_environment(mocker, arguments)

    with pytest.raises(argparse.ArgumentError):
        cli.main()

    httpserver.check()
    assert not os.listdir(tmp_path)
