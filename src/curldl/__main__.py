"""This script is invoked when running the main module, as in:
python -m curldl
"""
from curldl import cli

if __name__ == '__main__':
    raise SystemExit(cli.CommandLine().main())
