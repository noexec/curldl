"""Interface for PycURL functionality"""
from __future__ import annotations

import http
import http.client
import logging
import os.path
from typing import Callable, BinaryIO, NoReturn

import pycurl
import tenacity
from tqdm import tqdm

from curldl.util import FileSystem, Time

log = logging.getLogger(__name__)


class Downloader:
    """Interface for downloading functionality of PycURL"""
    SUPPORTED_VERBOSITY = {
        pycurl.INFOTYPE_TEXT: 'TEXT',
        pycurl.INFOTYPE_HEADER_IN: 'IHDR',
        pycurl.INFOTYPE_HEADER_OUT: 'OHDR',
    }

    DOWNLOAD_ABORT = {
        pycurl.E_WRITE_ERROR,
        pycurl.E_ABORTED_BY_CALLBACK,
    }

    def __init__(self, basedir: str | os.PathLike[str], *, progress: bool = False, verbose: bool = False,
                 user_agent: str = 'curl', retry_attempts: int = 3, retry_wait_sec: int | float = 2,
                 timeout_sec: int | float = 120, max_redirects: int = 5,
                 min_part_bytes: int = 64 * 1024, min_always_keep_part_bytes: int = 64 * 1024 ** 2) -> None:
        """Initialize a PycURL-based downloader with a single pycurl.Curl instance
        that is reused and reconfigured for each download. The resulting downloader
        object should be therefore not shared between several threads."""
        self._basedir = basedir

        self._progress = progress
        self._verbose = verbose
        self._user_agent = user_agent

        self._retry_attempts = retry_attempts
        self._retry_wait_sec = retry_wait_sec

        self._timeout_sec = timeout_sec
        self._max_redirects = max_redirects

        self._min_part_bytes = min_part_bytes
        self._min_always_keep_part_bytes = min_always_keep_part_bytes

        self._unconfigured_curl = pycurl.Curl()

    def _get_configured_curl(self, url: str, path: str, *,
                             timestamp: int | float | None = None) -> tuple[pycurl.Curl, int]:
        """Reconfigure pycurl.Curl instance for requested download and return the instance.
        Methods should not work with unconfigured instance directly, only with this one."""
        curl = self._unconfigured_curl
        curl.reset()

        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.USERAGENT, self._user_agent)

        curl.setopt(pycurl.FAILONERROR, True)
        curl.setopt(pycurl.OPT_FILETIME, True)
        curl.setopt(pycurl.FOLLOWLOCATION, True)
        curl.setopt(pycurl.MAXREDIRS, self._max_redirects)
        curl.setopt(pycurl.TIMEOUT, self._timeout_sec)

        curl.setopt(pycurl.VERBOSE, self._verbose)
        curl.setopt(pycurl.DEBUGFUNCTION, self._curl_debug_cb)

        if initial_size := FileSystem.get_file_size(path):
            log.info('Resuming download of %s to %s at %s bytes', url, path, f'{initial_size:,}')
            curl.setopt(pycurl.RESUME_FROM, initial_size)
        else:
            log.info('Downloading %s to %s', url, path)

        if timestamp is not None:
            curl.setopt(pycurl.TIMEVALUE, round(timestamp))
            curl.setopt(pycurl.TIMECONDITION, pycurl.TIMECONDITION_IFMODSINCE)
            log.debug('Will update %s if modified since %s', path, Time.timestamp_to_dt(timestamp))

        return curl, initial_size

    def _perform_curl_download(self, curl: pycurl.Curl, write_stream: BinaryIO, progress_bar: tqdm[NoReturn]) -> None:
        """Complete pycurl.Curl configuration and start downloading"""
        curl.setopt(pycurl.WRITEDATA, write_stream)

        # disable is already finalized after tty detection
        if not progress_bar.disable:
            curl.setopt(pycurl.XFERINFOFUNCTION, self._get_curl_progress_callback(progress_bar))
            curl.setopt(pycurl.NOPROGRESS, False)

        curl.perform()

    def _get_curl_progress_callback(self, progress_bar: tqdm[NoReturn]) -> Callable[[int, int, int, int], None]:
        """Constructs a callback for XFERINFOFUNCTION"""
        def curl_progress_cb(download_total: int, downloaded: int, upload_total: int, uploaded: int) -> None:
            """Progress callback for XFERINFOFUNCTION, only called if NOPROGRESS=0"""
            if download_total != 0:
                progress_bar.total = download_total + progress_bar.initial
            progress_bar.update(downloaded + progress_bar.initial - progress_bar.n)
        return curl_progress_cb

    def _curl_debug_cb(self, debug_type: int, debug_msg: bytes) -> None:
        """Callback for DEBUGFUNCTION"""
        debug_type = self.SUPPORTED_VERBOSITY.get(debug_type)
        if not debug_type:
            return
        debug_msg = debug_msg[:-1].decode('ascii', 'replace')
        log.debug('curl: [%s] %s', debug_type, debug_msg)

    def download(self, url: str, rel_path: str, *, size: int | None = None,
                 digests: dict[str, str] | None = None) -> None:
        """Download a URL to basedir-relative path and verify its expected size and digests.
        See Utilities.verify_size_and_digests() for format of expected digests."""
        path, path_partial = [self._prepare_full_path(rel_path + rel_ext) for rel_ext in ('', '.part')]

        if FileSystem.get_file_size(path, default=-1) == size:
            log.debug('Skipping update of %s since it has the expected size %s bytes', path, f'{size:,}')
            return

        if_modified_since_timestamp = None
        if os.path.exists(path) and size is None:
            if_modified_since_timestamp = os.path.getmtime(path)

        if (size is None and not digests and os.path.exists(path_partial)
                and os.path.getsize(path_partial) < self._min_always_keep_part_bytes):
            log.info('Removing existing partial download of %s since no size/digest to compare to', path)
            os.remove(path_partial)

        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_attempt(self._retry_attempts),
            wait=tenacity.wait_fixed(self._retry_wait_sec),
            retry=(tenacity.retry_if_exception_type(pycurl.error) &
                   tenacity.retry_if_exception(lambda error: error.args[0] not in self.DOWNLOAD_ABORT)),
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

        log.debug('Renaming %s to %s', path_partial, path)
        os.rename(path_partial, path)

    def _download_partial(self, url: str, path: str, *,
                          timestamp: int | float | None = None, description: str | None = None) -> None:
        """Start or resume a partial download of a URL to absolute path.

        If timestamp of an already downloaded file is provided, remove the partial file
        if the URL content is not more recent than the timestamp.

        In case of runtime error or unexpected HTTP status, rollback to initial file size."""
        curl, initial_size = self._get_configured_curl(url, path, timestamp=timestamp)

        def log_partial_download(message_prefix: str) -> None:
            """Log information about partially downloaded file"""
            if log.isEnabledFor(logging.INFO):
                code, descr = self._get_response_status(curl)
                log.info(message_prefix + f' {path} {initial_size:,} -> {os.path.getsize(path):,} bytes'
                         f' ({code} {descr}) [{Time.timestamp_delta(curl.getinfo(pycurl.TOTAL_TIME))}]')

        try:
            with open(path, 'ab') as path_stream, \
                 tqdm(unit='B', unit_scale=True, unit_divisor=1024, miniters=1, desc=description,
                      disable=(not self._progress or None), leave=False, dynamic_ncols=True, colour='blue',
                      initial=initial_size) as progress_bar:
                self._perform_curl_download(curl, path_stream, progress_bar)

        except pycurl.error as error:
            response_code, response_descr = self._get_response_status(curl)
            # HTTP 416: Rare case of resuming from fully downloaded .part
            if response_code != http.HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE:
                if error.args[0] in self.DOWNLOAD_ABORT:
                    log_partial_download('Interrupted while downloading')
                else:
                    log.warning('Was downloading %s, but HTTP status is (%s %s)', path, response_code, response_descr)
                    self._rollback_file(path, initial_size)
                raise

        if curl.getinfo(pycurl.CONDITION_UNMET):
            log.info('Discarding %s because it is not more recent', path)
            self._rollback_file(path, initial_size, force_remove=True)
        else:
            log_partial_download('Finished downloading')
            FileSystem.set_file_timestamp(path, curl.getinfo(pycurl.INFO_FILETIME))

    def _prepare_full_path(self, rel_path: str) -> str:
        """Verify that basedir-relative path is safe and create the required directories"""
        FileSystem.verify_rel_path_is_safe(self._basedir, rel_path)
        path = os.path.join(self._basedir, rel_path)
        FileSystem.create_directory_for_path(path)
        return path

    def _get_response_status(self, curl: pycurl.Curl) -> tuple[int, str]:
        """Retrieve HTTP response code and description from cURL.
        Note that cURL returns 0 if response code is not ready yet."""
        response_descr = 'Failed to Start Downloading'
        if response_code := curl.getinfo(pycurl.RESPONSE_CODE):
            response_descr = http.client.responses.get(response_code, 'Unknown Status')
        return response_code, response_descr

    def _rollback_file(self, path: str, initial_size: int, *, force_remove: bool = False) -> None:
        """Truncate file at path to its original size. If the post-truncation file size
        is below a threshold, it is removed. This is also done if force_remove is True."""
        current_size = os.path.getsize(path)
        assert current_size >= initial_size

        if initial_size < self._min_part_bytes or force_remove:
            log.debug('Removing %s instead of truncating back to %s bytes', path, f'{initial_size:,}')
            os.remove(path)
        elif initial_size < current_size:
            log.warning('Truncating %s back to %s bytes', path, f'{initial_size:,}')
            os.truncate(path, initial_size)
