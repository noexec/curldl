"""Command-line interface, should be called via main module:
    python -m curldl"""
import argparse
import logging
import sys
from importlib import metadata

from curldl.util import Log

log = logging.getLogger(__name__)


class CommandLine:
    """Command-line interface"""

    def __init__(self):
        """Initialize argument parser and unhandled exception hook"""
        sys.excepthook = Log.trace_unhandled_exception
        self.args = self._parse_arguments()

        self._configure_logger()
        log.debug('Configured: %s', self.args)

    def _configure_logger(self):
        loglevel = getattr(logging, self.args.log.upper())
        assert isinstance(loglevel, int)
        logging.basicConfig(level=loglevel)

    @staticmethod
    def _parse_arguments() -> argparse.Namespace:
        parser = argparse.ArgumentParser(prog='python -m curldl',
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        parser.add_argument('--basedir', help='base download folder', default='.')
        parser.add_argument('--log', help='logging level', choices=['debug', 'info', 'warning', 'error', 'critical'],
                            default='info')
        parser.add_argument('--progress', help='log progress to stderr', action='store_true')
        parser.add_argument('--verbose', help='log metadata and headers at debug level', action='store_true')
        parser.add_argument('--version', help='show curldl version', action='store_true')

        return parser.parse_args()

    def main(self) -> object:
        """Command-line program entry point"""

        if self.args.version:
            print(self._get_package_version())
            return

        # dl = Downloader(self.args.basedir, progress=self.args.progress, verbose=self.args.verbose)
        # dl.download('http://noexec.org/public/papers/finch.pdf', 'finch.pdf',
        #             expected_size=2345384, expected_digests={'sha1': '085a927353d94b2de1a3936dc511785ae9c65464'})
        # dl.download('https://noexec.org/assets/test', 'test')
        # dl.download('https://mirror.asergo.com/ubuntu-iso/22.10/ubuntu-22.10-desktop-amd64.iso',
        #             'ubuntu-22.10-desktop-amd64.iso',
        #             expected_size=4071903232,
        #             expected_digests={'sha256': 'b98f13cd86839e70cb7757d46840230496b3febea309dd73bd5f81383474e47b'})

    @staticmethod
    def _get_package_version() -> str:
        try:
            return metadata.version(__package__)
        except metadata.PackageNotFoundError:
            return 'develop'
