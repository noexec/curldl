"""Command-line interface, should be called via main module:
    python -m curldl"""
import argparse
import logging
import os
import sys
import urllib.parse
from importlib import metadata

import toml

import curldl
from curldl import Downloader
from curldl.util import Log, Cryptography

log = logging.getLogger(__name__)


class CommandLine:
    """Command-line interface"""

    def __init__(self):
        """Initialize argument parser and unhandled exception hook"""
        sys.excepthook = Log.trace_unhandled_exception
        self.args = self._parse_arguments()
        log.debug('Configured: %s', self.args)

    @staticmethod
    def _configure_logger(args: argparse.Namespace) -> None:
        debug_log_level = 'debug'
        if args.verbose and args.log != debug_log_level:
            args.log = debug_log_level.capitalize()

        loglevel = getattr(logging, args.log.upper())
        assert isinstance(loglevel, int)
        logging.basicConfig(level=loglevel)

        if args.log == debug_log_level.capitalize():
            log.debug('Raising logging level to DEBUG')

    @classmethod
    def _parse_arguments(cls) -> argparse.Namespace:
        """Parse command-line arguments"""
        parser = argparse.ArgumentParser(prog=__package__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        log_choices = ['debug', 'info', 'warning', 'error', 'critical']
        hash_algos = Cryptography.get_available_digests()
        version = '%(prog)s ' + cls._get_package_version()

        parser.add_argument('-V', '--version', action='version', version=version, help='show program version and exit')

        parser.add_argument('-b', '--basedir', default='.', help='base download folder')
        parser.add_argument('-o', '--output', help='basedir-relative path to the downloaded file')
        parser.add_argument('-s', '--size', help='expected download file size')

        parser.add_argument('-a', '--algo', choices=hash_algos, default='sha256',
                            metavar='ALGO', help='digest algorithm' + ', '.join(hash_algos))
        parser.add_argument('-d', '--digest', help='expected hexadecimal digest value')

        parser.add_argument('-p', '--progress', action='store_true', help='log progress to stderr')
        parser.add_argument('-l', '--log', choices=log_choices, default='info',
                            metavar='LEVEL', help='logging level: ' + ', '.join(log_choices))
        parser.add_argument('-v', '--verbose', action='store_true', help='log metadata and headers (implies -l debug)')

        parser.add_argument('url', help='URL to download')

        args = parser.parse_args()
        cls._configure_logger(args)

        return cls._infer_arguments(args)

    @classmethod
    def _infer_arguments(cls, args: argparse.Namespace) -> argparse.Namespace:
        """Infer missing arguments"""
        if not args.output:
            url_path = urllib.parse.unquote(urllib.parse.urlparse(args.url).path)
            args.output = os.path.basename(url_path)
            log.info('Saving output to: %s', args.output)

        return args

    def main(self) -> object:
        """Command-line program entry point"""

        downloader = Downloader(self.args.basedir, progress=self.args.progress, verbose=self.args.verbose)
        downloader.download('http://noexec.org/public/papers/finch.pdf', 'finch.pdf', expected_size=2345384,
                            expected_digests={'sha1': '085a927353d94b2de1a3936dc511785ae9c65464'})

    @staticmethod
    def _get_package_version() -> str:
        """Retrieve package version from metadata, with support for uninstalled development sources"""
        try:
            return metadata.version(__package__)
        except metadata.PackageNotFoundError:
            pyproject = os.path.join(curldl.ROOT_DIR, os.path.pardir, os.path.pardir, 'pyproject.toml')
            return toml.load(pyproject)['project']['version']


def main() -> object:
    """Command-line static entry point, suitable for install-time script generation"""
    return CommandLine().main()
