"""CLI entry point functional tests"""
import inspect
import os.path
import pathlib
import subprocess

import pytest

import curldl


@pytest.mark.parametrize('help_switch', ['-h', '--help', '--help --no-such-argument'])
def test_run_cli_module(help_switch: str) -> None:
    """Verify that running the module via __main__.py works"""
    package_base_path = pathlib.Path(inspect.getfile(curldl)).parent / os.path.pardir
    result = subprocess.run(f'python -m {curldl.__package__} {help_switch}',
                            check=True, shell=True, text=True, encoding='ascii', capture_output=True,
                            env=dict(os.environ, PYTHONPATH=str(package_base_path)))
    assert result.stdout.startswith('usage:') and not result.stderr
