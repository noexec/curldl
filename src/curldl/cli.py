"""Command-line interface, should be called via main module: python -m curldl"""
import argparse
import logging
import os
import sys
import urllib.parse
from importlib import metadata

from curldl import Curldl
from curldl.util import Log, Cryptography

log = logging.getLogger(__name__)


class CommandLine:
    """Command-line interface, exposed via module entry point"""

    def __init__(self) -> None:
        """Initialize argument parser and unhandled exception hook"""
        sys.excepthook = Log.trace_unhandled_exception
        self.args = self._parse_arguments()
        log.debug('Configured: %s', self.args)

    @staticmethod
    def _configure_logger(args: argparse.Namespace) -> None:
        """Configure logger according to command-line arguments.
        Specifying `verbose` argument raises the log level to `debug`.
        :param args: command-line arguments
        """
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
        """Parse command-line arguments
        :return: arguments after configuring the logger and possibly inferring other arguments
        """
        parser = argparse.ArgumentParser(prog=__package__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        log_choices = ['debug', 'info', 'warning', 'error', 'critical']
        hash_algos = Cryptography.get_available_digests()
        version = '%(prog)s ' + cls._get_package_version()

        parser.add_argument('-V', '--version', action='version', version=version, help='show program version and exit')

        parser.add_argument('-b', '--basedir', default='.', help='base download folder')
        output_arg = parser.add_argument('-o', '--output', nargs=1, help='basedir-relative path to the '
                                         'downloaded file, infer from URL if unspecified')
        parser.add_argument('-s', '--size', type=int, help='expected download file size')

        parser.add_argument('-a', '--algo', choices=hash_algos, default='sha256',
                            metavar='ALGO', help='digest algorithm: ' + ', '.join(hash_algos))
        parser.add_argument('-d', '--digest', help='expected hexadecimal digest value')

        parser.add_argument('-p', '--progress', action='store_true', help='visualize progress on stderr')
        parser.add_argument('-l', '--log', choices=log_choices, default='info',
                            metavar='LEVEL', help='logging level: ' + ', '.join(log_choices))
        parser.add_argument('-v', '--verbose', action='store_true', help='log metadata and headers (implies -l debug)')

        parser.add_argument('url', nargs='+', help='URL(s) to download')

        args = parser.parse_args()
        cls._configure_logger(args)

        return cls._infer_arguments(output_arg, args)

    @classmethod
    def _infer_arguments(cls, output_arg: argparse.Action, args: argparse.Namespace) -> argparse.Namespace:
        """Infer missing arguments
        :param output_arg: `output` argument to infer
        :param args: arguments to extend
        :return: input arguments after inferring missing ones
        :raises argparse.ArgumentError: multiple URLs are specified with ``output`` argument
        """
        if not args.output:
            args.output = [os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(url).path)) for url in args.url]
            log.info('Saving download(s) to: %s', ', '.join(args.output))

        elif len(args.output) != len(args.url):
            raise argparse.ArgumentError(output_arg, 'Cannot specify output file when downloading multiple URLs')

        return args

    def main(self) -> object:
        """Command-line program entry point
        :return: program exit status
        """
        dl = Curldl(self.args.basedir, progress=self.args.progress, verbose=self.args.verbose)
        for url, output in zip(self.args.url, self.args.output):
            dl.get(url, rel_path=output, size=self.args.size,
                   digests=self.args.digest and {self.args.algo: self.args.digest})
        return 0

    @staticmethod
    def _get_package_version() -> str:
        """Retrieve package version from metadata, raising error for uninstalled development sources
        :return: package version string
        :raises metadata.PackageNotFoundError: version is not available, e.g. when package is not installed
        """
        try:
            return metadata.version(__package__)
        except metadata.PackageNotFoundError:
            log.error('Generated version not available, install package as usual or in editable mode')
            raise


def main() -> object:
    """Command-line static entry point, suitable for install-time script generation
    :return: program exit status
    """
    return CommandLine().main()
