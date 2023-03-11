"""CLI entry point functional tests"""
import inspect
import logging
import os.path
import pathlib
import subprocess
import sys
from importlib import metadata

import pytest
import toml
from _pytest.capture import CaptureFixture
from pytest_httpserver import HTTPServer
from pytest_mock import MockerFixture

import curldl
from curldl import cli

PACKAGE_NAME = curldl.__package__


def patch_system_environment(mocker: MockerFixture, arguments: list[str]) -> None:
    """Patch sys.argv and make sys.excepthook available for modification"""
    mocker.patch.object(sys, 'argv', [PACKAGE_NAME] + arguments)
    mocker.patch.object(sys, 'excepthook')


def patch_logger_config(mocker: MockerFixture, expected_log_level: str) -> None:
    """Replace logging.basicConfig() with verifier of expected configured log level"""
    def logging_basic_config_mock(level: int) -> None:
        assert level == getattr(logging, expected_log_level.upper())
    mocker.patch.object(logging, 'basicConfig', logging_basic_config_mock)


@pytest.mark.parametrize('arguments, should_succeed', [('-h', True), ('--help', True), ('--no-such-argument', False)])
def test_run_cli_module(arguments: str, should_succeed: bool) -> None:
    """Verify that running the module via __main__.py works, test success and failure"""
    package_base_path = pathlib.Path(inspect.getfile(curldl)).parent / os.path.pardir
    result = subprocess.run(f'python -m {PACKAGE_NAME} {arguments}',
                            check=False, shell=True, text=True, encoding='ascii', capture_output=True,
                            env=dict(os.environ, PYTHONPATH=str(package_base_path)))
    assert (result.returncode == 0) == should_succeed
    if not should_succeed:
        result.stdout, result.stderr = result.stderr, result.stdout
    assert result.stdout.startswith('usage:') and not result.stderr


@pytest.mark.parametrize('argument', ['-V', '--version'])
@pytest.mark.parametrize('use_metadata', [True, False])
def test_get_version(mocker: MockerFixture, capsys: CaptureFixture[str], argument: str, use_metadata: bool) -> None:
    """Verify version number is correctly retrieved from both package and TOML sources"""
    mock_version = '1.0.0-mock'

    def metadata_version_mock(distribution_name: str) -> str:
        assert distribution_name == PACKAGE_NAME
        if use_metadata:
            return mock_version
        raise metadata.PackageNotFoundError

    def toml_load_mock(file_path: str) -> dict[str, dict[str, str]]:
        assert file_path.endswith('pyproject.toml')
        return {'project': {'version': mock_version}}

    patch_system_environment(mocker, [argument])
    mocker.patch.object(metadata, 'version', metadata_version_mock)
    mocker.patch.object(toml, 'load', toml_load_mock)

    with pytest.raises(SystemExit) as ex_info:
        cli.main()
    assert ex_info.value.code == 0
    outputs = capsys.readouterr()
    assert outputs.out == f'{PACKAGE_NAME} {mock_version}\n' and not outputs.err


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

    httpserver.check()  # type: ignore[no-untyped-call]
    assert file_path.is_file()
    with open(file_path, 'rb') as file:
        assert file.read() == file_data
