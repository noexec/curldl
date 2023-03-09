"""CLI entry point functional tests"""
import inspect
import os.path
import pathlib
import subprocess
import sys
from importlib import metadata

import pytest
import toml
from _pytest.capture import CaptureFixture
from pytest_mock import MockerFixture

import curldl
from curldl import cli

PACKAGE_NAME = curldl.__package__


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

    mocker.patch.object(sys, 'argv', [PACKAGE_NAME, argument])
    mocker.patch.object(metadata, 'version', metadata_version_mock)
    mocker.patch.object(toml, 'load', toml_load_mock)

    with pytest.raises(SystemExit) as ex_info:
        cli.main()
        assert ex_info.value.code == 0

    outputs = capsys.readouterr()
    assert outputs.out == f'{PACKAGE_NAME} {mock_version}\n' and not outputs.err
