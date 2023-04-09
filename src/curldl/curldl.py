"""Interface for PycURL functionality"""
from __future__ import annotations

import http.client
import logging
import operator
import os.path
import urllib.parse
from functools import reduce
from typing import Callable, BinaryIO, NoReturn

import pycurl
import tenacity
from tqdm import tqdm

from curldl.util import FileSystem, Time

log = logging.getLogger(__name__)


class Curldl:
    """Interface for downloading functionality of PycURL.
    Basic usage example::

        import curldl, os
        dl = curldl.Curldl(basedir='downloads', progress=True)
        dl.get('https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz', 'linux-0.01.tar.gz',
               size=73091, digests={'sha1': '566b6fb6365e25f47b972efa1506932b87d3ca7d'})
        assert os.path.exists('downloads/linux-0.01.tar.gz')

    For a more in-depth guide, refer to the package documentation.
    """

    DOWNLOAD_RETRY_ERRORS = {
        pycurl.E_COULDNT_RESOLVE_PROXY, pycurl.E_COULDNT_RESOLVE_HOST, pycurl.E_COULDNT_CONNECT,
        pycurl.E_FTP_ACCEPT_FAILED, pycurl.E_FTP_ACCEPT_TIMEOUT, pycurl.E_FTP_CANT_GET_HOST,
        pycurl.E_HTTP2, pycurl.E_PARTIAL_FILE, pycurl.E_FTP_PARTIAL_FILE, pycurl.E_HTTP_RETURNED_ERROR,
        pycurl.E_OPERATION_TIMEDOUT, pycurl.E_FTP_PORT_FAILED, pycurl.E_SSL_CONNECT_ERROR,
        pycurl.E_TOO_MANY_REDIRECTS, pycurl.E_GOT_NOTHING, pycurl.E_SEND_ERROR, pycurl.E_RECV_ERROR, pycurl.E_SSH,
        # TODO: Add once available: E_HTTP2_STREAM, E_HTTP3, E_QUIC_CONNECT_ERROR, E_PROXY, E_UNRECOVERABLE_POLL
    }
    """``libcurl`` errors accepted by download retry policy"""

    DEFAULT_ALLOWED_PROTOCOLS = {
        pycurl.PROTO_HTTP, pycurl.PROTO_HTTPS,
        pycurl.PROTO_FTP, pycurl.PROTO_FTPS,
        pycurl.PROTO_SFTP
    }
    """URL schemes allowed by default, can be changed with ``allowed_protocols_bitmask`` constructor parameter"""

    RESUME_FROM_SCHEMES = {'http', 'https', 'ftp', 'ftps', 'file'}
    """URL schemes supported by :attr:`pycurl.RESUME_FROM`. SFTP is not included because its implementation is buggy
    (total download size is reduced twice by initial size). Scheme is extracted via :mod:`urllib` from initial URL,
    but there are no security implications since it is only used for removing partial downloads."""

    VERBOSE_LOGGING = {
        pycurl.INFOTYPE_TEXT: 'TEXT',
        pycurl.INFOTYPE_HEADER_IN: 'IHDR',
        pycurl.INFOTYPE_HEADER_OUT: 'OHDR',
    }
    """Info types logged by :attr:`pycurl.DEBUGFUNCTION` callback during verbose logging"""

    def __init__(self, basedir: str | os.PathLike[str], *, progress: bool = False, verbose: bool = False,
                 user_agent: str = 'curl', retry_attempts: int = 3, retry_wait_sec: int | float = 2,
                 timeout_sec: int | float = 120, max_redirects: int = 5, allowed_protocols_bitmask: int = 0,
                 min_part_bytes: int = 64 * 1024, always_keep_part_bytes: int = 64 * 1024 ** 2,
                 curl_config_callback: Callable[[pycurl.Curl], None] | None = None) -> None:
        """Initialize a PycURL-based downloader with a single :class:`pycurl.Curl` instance
        that is reused and reconfigured for each download. The resulting downloader
        object should be therefore not shared among several threads.
        :param basedir: base directory path for downloaded file
        :param progress: show progress bar on :attr:`sys.stderr`
        :param verbose: enable verbose logging information from ``libcurl`` at ``DEBUG`` level
        :param user_agent: ``User-Agent`` header for HTTP(S) protocols
        :param retry_attempts: number of download retry attempts in case of failure in :attr:`DOWNLOAD_RETRY_ERRORS`
        :param retry_wait_sec: seconds to wait between download retry attempts
        :param timeout_sec: timeout seconds for ``libcurl`` operation
        :param max_redirects: maximum number of redirects allowed in HTTP(S) protocols
        :param allowed_protocols_bitmask: bitmask of allowed protocols, e.g. :attr:`pycurl.PROTO_HTTP`; default is
            `or` of values in :attr:`DEFAULT_ALLOWED_PROTOCOLS`
        :param min_part_bytes: partial downloads below this size are removed after unsuccessful download attempt;
            set to ``0`` to disable removal of unsuccessful partial downloads
        :param always_keep_part_bytes: do not remove partial downloads of this size or larger when resuming download
            even if no size or digest is provided for verification; set to ``0`` to never remove existing partial
            downloads
        :param curl_config_callback: pass a callback to further configure a :class:`pycurl.Curl` object
        """
        self._basedir = basedir

        self._progress = progress
        self._verbose = verbose
        self._user_agent = user_agent

        self._retry_attempts = retry_attempts
        self._retry_wait_sec = retry_wait_sec

        self._timeout_sec = timeout_sec
        self._max_redirects = max_redirects
        self._allowed_protocols_bitmask = (allowed_protocols_bitmask
                                           or reduce(operator.or_, self.DEFAULT_ALLOWED_PROTOCOLS))

        self._min_part_bytes = min_part_bytes
        self._always_keep_part_bytes = always_keep_part_bytes

        self._curl_config_callback = curl_config_callback
        self._unconfigured_curl = pycurl.Curl()

    def _get_configured_curl(self, url: str, path: str, *,
                             timestamp: int | float | None = None) -> tuple[pycurl.Curl, int]:
        """Reconfigure :class:`pycurl.Curl` instance for requested download and return the instance.
        Methods should not work with :attr:`_unconfigured_curl` directly, only with instance returned
        by this method.
        :param url: URL to download
        :param path: resolved download file path
        :param timestamp: last-modified timestamp of an already downloaded ``path``, if it exists;
            used for skipping not-modified-since downloads with HTTP(S), FTP(S), FILE and RTSP protocols
        :return: :class:`pycurl.Curl` instance configured for requested download and initial download offset
            (i.e., file size to resume)
        """
        curl = self._unconfigured_curl
        curl.reset()

        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.USERAGENT, self._user_agent)

        curl.setopt(pycurl.FAILONERROR, True)
        curl.setopt(pycurl.OPT_FILETIME, True)
        curl.setopt(pycurl.TIMEOUT, self._timeout_sec)

        curl.setopt(pycurl.FOLLOWLOCATION, True)
        curl.setopt(pycurl.MAXREDIRS, self._max_redirects)
        curl.setopt(pycurl.REDIR_PROTOCOLS,
                    ((self._get_url_scheme(url) == 'http') and pycurl.PROTO_HTTP) | pycurl.PROTO_HTTPS)

        curl.setopt(pycurl.PROTOCOLS, self._allowed_protocols_bitmask)
        curl.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_ANYSAFE)
        curl.setopt(pycurl.PROXYAUTH, pycurl.HTTPAUTH_ANYSAFE)
        curl.setopt(pycurl.USE_SSL, pycurl.USESSL_TRY)

        curl.setopt(pycurl.VERBOSE, self._verbose)
        curl.setopt(pycurl.DEBUGFUNCTION, self._curl_debug_cb)

        if initial_size := FileSystem.get_file_size(path):
            log.info('Resuming download of %s to %s at %s B', url, path, f'{initial_size:,}')
            curl.setopt(pycurl.RESUME_FROM, initial_size)
        else:
            log.info('Downloading %s to %s', url, path)

        if timestamp is not None:
            curl.setopt(pycurl.TIMEVALUE, round(timestamp))
            curl.setopt(pycurl.TIMECONDITION, pycurl.TIMECONDITION_IFMODSINCE)
            log.debug('Will update %s if modified since %s', path, Time.timestamp_to_dt(timestamp))

        if self._curl_config_callback:
            self._curl_config_callback(curl)

        return curl, initial_size

    def _perform_curl_download(self, curl: pycurl.Curl, write_stream: BinaryIO, progress_bar: tqdm[NoReturn]) -> None:
        """Complete pycurl.Curl configuration and start downloading
        :param curl: configured :class:`pycurl.Curl` instance
        :param write_stream: output stream to write to (a file opened in binary write mode)
        :param progress_bar: progress bar to use; :attr:`pycurl.XFERINFOFUNCTION` is configured if enabled
        """
        curl.setopt(pycurl.WRITEDATA, write_stream)

        # disable is already finalized after tty detection
        if not progress_bar.disable:
            curl.setopt(pycurl.XFERINFOFUNCTION, self._get_curl_progress_callback(progress_bar))
            curl.setopt(pycurl.NOPROGRESS, False)

        curl.perform()

    @staticmethod
    def _get_curl_progress_callback(progress_bar: tqdm[NoReturn]) -> Callable[[int, int, int, int], None]:
        """Constructs a progress bar-updating callback for :attr:`pycurl.XFERINFOFUNCTION`
        :param progress_bar: progress bar to use, must be enabled
        :return: :attr:`pycurl.XFERINFOFUNCTION` callback
        """
        def curl_progress_cb(download_total: int, downloaded: int, upload_total: int, uploaded: int) -> None:
            """Progress callback for :attr:`pycurl.XFERINFOFUNCTION`, only called if :attr:`pycurl.NOPROGRESS` is ``0``
            :param download_total: total bytes to download; initial file size is not included if resuming;
                equal to ``0`` when download is just being started and download size is not yet available
            :param downloaded: bytes downloaded so far; initial file size is not included if resuming
            :param upload_total: unused
            :param uploaded: unused
            """
            if download_total != 0:
                progress_bar.total = download_total + progress_bar.initial
            progress_bar.update(downloaded + progress_bar.initial - progress_bar.n)
        return curl_progress_cb

    @classmethod
    def _curl_debug_cb(cls, debug_type: int, debug_msg: bytes) -> None:
        """Callback for :attr:`pycurl.DEBUGFUNCTION` that logs ``libcurl`` messages at ``DEBUG`` level
        :param debug_type: :class:`pycurl.Curl`-supplied info type, e.g. :attr:`pycurl.INFOTYPE_HEADER_IN`
        :param debug_msg: :class:`pycurl.Curl`-supplied debug message
        """
        debug_type = cls.VERBOSE_LOGGING.get(debug_type)
        if not debug_type:
            return
        debug_msg = debug_msg[:-1].decode('ascii', 'replace')
        log.debug('curl: [%s] %s', debug_type, debug_msg)

    def get(self, url: str, rel_path: str, *, size: int | None = None, digests: dict[str, str] | None = None) -> None:
        """Download a URL to ``basedir``-relative path and verify its expected size and digests.
        Resume a partial download with ``.part`` extension if exists and supported by protocol,
        and retry failures according to retry policy. The downloaded file is removed in case of
        size or digest mismatch, and :class:`ValueError` is raised.
        :param url: URL to download
        :param rel_path: ``basedir``-relative output file path
        :param size: expected file size in bytes, or ``None`` to ignore
        :param digests: mapping of digest algorithms to expected hexadecimal digest strings, or ``None`` to ignore
        (see :func:`curldl.util.FileSystem.verify_size_and_digests`)
        :raises ValueError: relative path escapes base directory or is otherwise unsafe
        (see :func:`curldl.util.FileSystem.verify_rel_path_is_safe`),
        or file size mismatch, or one of digests fails verification
        :raises pycurl.error: PycURL error when downloading after retries are exhausted
        """
        path, path_partial = [self._prepare_full_path(rel_path + rel_ext) for rel_ext in ('', '.part')]

        if FileSystem.get_file_size(path, default=-1) == size:
            log.debug('Skipping update of %s since it has the expected size %s B', path, f'{size:,}')
            return

        if_modified_since_timestamp = None
        if os.path.exists(path) and size is None:
            if_modified_since_timestamp = os.path.getmtime(path)

        if os.path.exists(path_partial):
            if self._get_url_scheme(url) not in self.RESUME_FROM_SCHEMES:
                log.info('Removing partial download of %s since resume is not supported for URL', path)
                os.remove(path_partial)
            elif size is None and not digests and os.path.getsize(path_partial) < self._always_keep_part_bytes:
                log.info('Removing partial download of %s since no size/digest to compare to', path)
                os.remove(path_partial)

        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_attempt(self._retry_attempts),
            wait=tenacity.wait_fixed(self._retry_wait_sec),
            retry=(tenacity.retry_if_exception_type(pycurl.error) &
                   tenacity.retry_if_exception(lambda error: error.args[0] in self.DOWNLOAD_RETRY_ERRORS)),
            before_sleep=tenacity.before_sleep_log(log, logging.DEBUG),
            reraise=True
        ):
            with attempt:
                self._download_partial(url, path_partial, timestamp=if_modified_since_timestamp,
                                       description=os.path.basename(path))
        if not os.path.exists(path_partial):
            return

        try:
            FileSystem.verify_size_and_digests(path_partial, size=size, digests=digests)
            log.debug('Partial download of %s passed verification (%s / %s)', path, size, digests)
        except ValueError:
            log.info('Removing partial download of %s due to size/digest mismatch', path)
            os.remove(path_partial)
            raise

        log.debug('Moving %s to %s', path_partial, path)
        os.replace(path_partial, path)

    def _download_partial(self, url: str, path: str, *,
                          timestamp: int | float | None = None, description: str | None = None) -> None:
        """Start or resume a partial download of a URL to resolved path.
        If timestamp of an already downloaded file is provided, remove the partial file
        if the URL content is not more recent than the timestamp. This method should be
        invoked with a retry policy.
        :param url: URL to download
        :param path: resolved path of a partial download file
        :param timestamp: last-modified timestamp of an already downloaded ``path``, if it exists
        :param description: description string for progress bar (e.g., base name of downloaded file)
        :raises pycurl.error: PycURL error when downloading, may result in a retry according to policy
        """
        curl, initial_size = self._get_configured_curl(url, path, timestamp=timestamp)

        def log_partial_download(message_prefix: str, *, error: pycurl.error | None = None) -> None:
            """Log information about partially downloaded file at ``INFO`` or ``ERROR`` log level
            :param message_prefix: log message prefix
            :param error: PycURL exception, implies ``ERROR`` log level"""
            if log.isEnabledFor(log_level := logging.ERROR if error else logging.INFO):
                log.log(log_level, message_prefix + f' {path} {initial_size:,} -> {os.path.getsize(path):,} B'
                        f' ({self._get_response_status(curl, url, error)})'
                        f' [{Time.timestamp_delta(curl.getinfo(pycurl.TOTAL_TIME))}]')

        try:
            with open(path, 'ab') as path_stream, \
                 tqdm(unit='B', unit_scale=True, unit_divisor=1024, miniters=1, desc=description,
                      disable=(not self._progress or None), leave=False, dynamic_ncols=True, colour='blue',
                      initial=initial_size) as progress_bar:
                self._perform_curl_download(curl, path_stream, progress_bar)

        except pycurl.error as ex:
            log_partial_download('Download interrupted', error=ex)
            self._discard_file(path)
            raise

        if curl.getinfo(pycurl.CONDITION_UNMET):
            log.info('Discarding %s because it is not more recent', path)
            self._discard_file(path, force_remove=True)
            return

        log_partial_download('Finished downloading')
        FileSystem.set_file_timestamp(path, curl.getinfo(pycurl.INFO_FILETIME))

    def _prepare_full_path(self, rel_path: str) -> str:
        """Verify that ``basedir``-relative path is safe and create the required directories
        :param rel_path: ``basedir``-relative path
        :return: resulting complete path
        :raises ValueError: relative path escapes base directory or is otherwise unsafe
            (see :func:`curldl.util.FileSystem.verify_rel_path_is_safe`)
        """
        FileSystem.verify_rel_path_is_safe(self._basedir, rel_path)
        path = os.path.join(self._basedir, rel_path)
        FileSystem.create_directory_for_path(path)
        return path

    @classmethod
    def _get_response_status(cls, curl: pycurl.Curl, url: str, error: pycurl.error | None) -> str:
        """Format response code and description from cURL with a possible error
        :param curl: :class:`pycurl.Curl` instance to extract response code from
        :param url: a URL to extract scheme protocol from if :attr:`pycurl.EFFECTIVE_URL` is unavailable
        :param error: PycURL exception instance
        :return: formatted string that includes a response code and its meaning, if available
        """
        scheme = cls._get_url_scheme(curl.getinfo(pycurl.EFFECTIVE_URL) or url)
        descr = 'No Status'
        if code := curl.getinfo(pycurl.RESPONSE_CODE):
            descr = 'No Description'
            if scheme in ['http', 'https']:
                descr = http.client.responses.get(code, 'Unrecognized HTTP Status Code')

        # pylint: disable=consider-using-f-string
        error_descr = '{}: {} / '.format(error.args[0], error.args[1] or 'No Description') if error else ''
        return '{}{} {}{}'.format(error_descr, scheme.upper(), f'{code}: ' if code else '', descr)

    @staticmethod
    def _get_url_scheme(url: str) -> str:
        """Return URL scheme (lowercase)
        :param url: a URL to extract URL scheme part from
        :return: lowercase protocol scheme, e.g. `http`
        """
        return urllib.parse.urlparse(url).scheme.lower()

    def _discard_file(self, path: str, *, force_remove: bool = False) -> None:
        """If file size is below a threshold, it is removed. This is also done if force_remove is True.
        :param path: file path to remove if its size is below ``min_part_bytes``
        :param force_remove: unconditionally remove the file
        """
        file_size = os.path.getsize(path)
        if force_remove or file_size < self._min_part_bytes:
            log.debug('Removing %s since size of %s B is below threshold or removal requested', path, f'{file_size:,}')
            os.remove(path)
