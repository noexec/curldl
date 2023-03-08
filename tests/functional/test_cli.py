"""CLI entry point functional tests"""
import inspect
import os.path
import pathlib

import pytest
from cli_test_helpers import shell  # type: ignore
from pytest_mock import MockerFixture

import curldl


@pytest.mark.parametrize('help_switch', ['-h', '--help', '--help --no-such-argument'])
def test_run_cli_module(mocker: MockerFixture, help_switch: str) -> None:
    """Verify that running the module via __main__.py works"""
    package_base_path = pathlib.Path(inspect.getfile(curldl)).parent / os.path.pardir
    mocker.patch.dict(os.environ, {'PYTHONPATH': str(package_base_path)})
    result = shell(f'python -m {curldl.__package__} {help_switch}')
    assert result.exit_code == 0
    assert result.stdout.startswith('usage:') and result.stderr == ''
