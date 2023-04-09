[![Tests with Coverage and Static Analysis](https://github.com/noexec/curldl/actions/workflows/tests.yml/badge.svg)](https://github.com/noexec/curldl/actions/workflows/tests.yml)

# Introduction

The __curldl__ Python module safely and reliably downloads files with [PycURL](https://pycurl.io/), which in turn is a wrapper for [libcurl](https://curl.se/libcurl/) file transfer library. The purpose of __curldl__ is providing a straightforward API for downloading files with the following features:

* Multi-protocol support: protocol support is delegated to [curl](https://curl.se/) in as protocol-neutral way as possible. This means that there is no reliance on HTTP-specific header and statuses, for example. If a feature like download resuming and _if-modified-since_ condition is supported by the underlying protocol, it can be used by _curldl_.
* If a partial download is abandoned, most chances are that it may be resumed later (supported for HTTP(S), FTP(S) and FILE protocols). A `.part` extension is added to the partial download file, and it is renamed to the target file name once the download completes.
* If the downloaded file exists, it is not downloaded again unless the timestamp of file on server is newer (supported for HTTP(S), FTP(S), RTSP and FILE protocols). Note that file download may be skipped before timestamp is considered due to file size matching the expected file size (see below).
* Downloads are configured relative to a base directory, and relative download path is verified not to escape the base directory directly, via symlinks, or otherwise.
* Downloaded file size and/or cryptographic digest(s) can be verified upon download completion. This verification, together with the relative path safety above, allows for easy implementation of mirroring scripts — e.g., when relative path, file size and digest are located in a downloaded XML file.
* Speed: since native _libcurl_ writes directly to the output stream file descriptor, there are no transfers of large chunks of data inside Python interpreter.


# Installation

The only requirement for _curldl_ is Python 3.8+. Install the package as follows:
```shell
pip install curldl
```

If you encounter a build failure during installation of _pycurl_ dependency, the following should help:
* On Linux, install one of:
    * _pycurl_ package from distribution repo — e.g., on Ubuntu run `sudo apt install python3-pycurl`
    * _libcurl_ development files with `sudo apt install build-essential libcurl4-openssl-dev`
* On Windows, install an unofficial _pycurl_ build since official builds are not available at the moment — e.g., by [Christoph Gohlke](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pycurl), or use _Conda_ (see below).
* On Windows and macOS, use _Conda_ or _Miniconda_ with [conda-forge](https://conda-forge.org/) channel. For instance, see runtime dependencies in the following [test environment](https://github.com/noexec/curldl/blob/develop/misc/conda/test-environment.yml).

Overall, _curldl_ is expected to have no issues in any environment with Python 3.8+ (CPython or PyPy) — see Testing section below.


# Usage

Most examples below use the _curldl_ wrapper script instead of Python code. Of course, in all cases it is easy to write a few lines of code with identical functionality — see the first example. Also, note that inline documentation is available for all functions.


## Simple Download

The following code snippet downloads a file and verifies its size and SHA-1 digest. A progress bar is shown on _stderr_ while download is in progress.

```python
import curldl, os
dl = curldl.Curldl(basedir='downloads', progress=True)
dl.get('https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz', 'linux-0.01.tar.gz',
       size=73091, digests={'sha1': '566b6fb6365e25f47b972efa1506932b87d3ca7d'})
assert os.path.exists('downloads/linux-0.01.tar.gz')
```

If verification fails, the partial download is removed; otherwise it is renamed to the target file after being timestamped with _last-modified_ timestamp received from the server.

A similar result is achieved on command-line by running the CLI wrapper script, which is useful for quickly testing _curldl_ functionality:

```shell
curldl -b downloads -s 73091 -a sha1 -d 566b6fb6365e25f47b972efa1506932b87d3ca7d \
       -p -l debug https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz
```

The corresponding log output:

```text
INFO:curldl.cli:Saving download(s) to: linux-0.01.tar.gz
DEBUG:curldl.cli:Configured: Namespace(basedir='downloads', output=['linux-0.01.tar.gz'], size=73091, algo='sha1', digest='566b6fb6365e25f47b972efa1506932b87d3ca7d', progress=True, log='debug', verbose=False, url=['https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz'])
INFO:curldl.util.fs:Creating directory: downloads
INFO:curldl.curldl:Downloading https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz to downloads/linux-0.01.tar.gz.part
INFO:curldl.curldl:Finished downloading downloads/linux-0.01.tar.gz.part 0 -> 73,091 B (HTTPS 200: OK) [0:00:01]
DEBUG:curldl.util.fs:Timestamping downloads/linux-0.01.tar.gz.part with 1993-10-30 00:00:00+00:00
DEBUG:curldl.util.fs:Successfully verified file size of downloads/linux-0.01.tar.gz.part
DEBUG:curldl.util.crypt:Computing 160-bit SHA1 for downloads/linux-0.01.tar.gz.part
INFO:curldl.util.crypt:Successfully verified SHA1 of downloads/linux-0.01.tar.gz.part
DEBUG:curldl.curldl:Partial download of downloads/linux-0.01.tar.gz passed verification (73091 / {'sha1': '566b6fb6365e25f47b972efa1506932b87d3ca7d'})
DEBUG:curldl.curldl:Moving downloads/linux-0.01.tar.gz.part to downloads/linux-0.01.tar.gz
```

Note that renaming of `downloads/linux-0.01.tar.gz.part` to `downloads/linux-0.01.tar.gz` is the very last action of `Curldl.get()` method.


## Repeated Download

Running the same command again doesn't actually result in a server request since file size matches (digest is not checked since it would be time-prohibitive when mirroring large repositories):

```text
INFO:curldl.cli:Saving download(s) to: linux-0.01.tar.gz
DEBUG:curldl.cli:Configured: Namespace(basedir='downloads', output=['linux-0.01.tar.gz'], size=73091, algo='sha1', digest='566b6fb6365e25f47b972efa1506932b87d3ca7d', progress=True, log='debug', verbose=False, url=['https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz'])
DEBUG:curldl.curldl:Skipping update of downloads/linux-0.01.tar.gz since it has the expected size 73,091 B
```

We can also request the same file without providing an expected size:

```shell
curldl -b downloads -p -l debug ftp://ftp.hosteurope.de/mirror/ftp.kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz
```

In this case, the download is skipped due to _if-modified-since_ check:

```text
INFO:curldl.cli:Saving download(s) to: linux-0.01.tar.gz
DEBUG:curldl.cli:Configured: Namespace(basedir='downloads', output=['linux-0.01.tar.gz'], size=None, algo='sha256', digest=None, progress=True, log='debug', verbose=False, url=['ftp://ftp.hosteurope.de/mirror/ftp.kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz'])
INFO:curldl.curldl:Downloading ftp://ftp.hosteurope.de/mirror/ftp.kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz to downloads/linux-0.01.tar.gz.part
DEBUG:curldl.curldl:Will update downloads/linux-0.01.tar.gz.part if modified since 1993-10-30 00:00:00+00:00
INFO:curldl.curldl:Discarding downloads/linux-0.01.tar.gz.part because it is not more recent
DEBUG:curldl.curldl:Removing downloads/linux-0.01.tar.gz.part since size of 0 B is below threshold or removal requested
```

Note that FTP protocol was used this time — _curldl_ is protocol-agnostic when using the underlying _libcurl_ functionality.


## Resuming Download

If a download is interrupted, it will be resumed on the next attempt (which may also be a retry according to the configured retry policy). Here is what happens when _Ctrl-C_ is used to send SIGINT signal to the Python process:

```shell
curldl -b downloads -p https://releases.ubuntu.com/22.04.2/ubuntu-22.04.2-live-server-amd64.iso
```

```text
INFO:curldl.cli:Saving download(s) to: ubuntu-22.04.2-live-server-amd64.iso
INFO:curldl.curldl:Downloading https://releases.ubuntu.com/22.04.2/ubuntu-22.04.2-live-server-amd64.iso to downloads/ubuntu-22.04.2-live-server-amd64.iso.part
ubuntu-22.04.2-live-server-amd64.iso:  13%|██▋                  | 244M/1.84G [00:06<00:38, 44.7MB/s]^CCRITICAL:curldl.util.log:KeyboardInterrupt:
ERROR:curldl.curldl:Download interrupted downloads/ubuntu-22.04.2-live-server-amd64.iso.part 0 -> 259,981,312 B (42: Callback aborted / HTTPS 200: OK) [0:00:07]
CRITICAL:curldl.util.log:error: (42, 'Callback aborted')
```

Attempting the download again resumes the download:

```text
INFO:curldl.cli:Saving download(s) to: ubuntu-22.04.2-live-server-amd64.iso
INFO:curldl.curldl:Resuming download of https://releases.ubuntu.com/22.04.2/ubuntu-22.04.2-live-server-amd64.iso to downloads/ubuntu-22.04.2-live-server-amd64.iso.part at 259,981,312 B
INFO:curldl.curldl:Finished downloading downloads/ubuntu-22.04.2-live-server-amd64.iso.part 259,981,312 -> 1,975,971,840 B (HTTPS 206: Partial Content) [0:01:24]
```

Note, however, that we didn't provide a size or digest for verification. Since the downloaded file is timestamped only once download completes, how does _curldl_ know that the file wasn't changed on the server in the meantime? The answer is that _curldl_ simply avoids removing large partial downloads in such cases — see inline documentation for _always_keep_part_bytes_ constructor parameter of _Curldl_.


## Escaping Base Directory

Attempts to escape base directory are prevented, e.g.:

```shell
curldl --basedir . http://example.com/ --output ../file.txt
```

```text
CRITICAL:curldl.util.log:ValueError: Relative path ../file.txt escapes base path /home/user/curldl
```

_curldl_ performs rather extensive checks to prevent base directory escaping — see _FileSystem_ class implementation and unit tests for details.


# Testing

A simplified configuration matrix covered by [CI/CD test + build pipeline](https://github.com/noexec/curldl/actions/workflows/tests.yml) at the time of writing this document is presented below:

| Platform    | CPython 3.8           | PyPy 3.8 | PyPy 3.9 | CPython 3.9 | CPython 3.10   | CPython 3.11 |
|-------------|-----------------------|----------|----------|-------------|----------------|--------------|
| Ubuntu-x64  | venv, conda, platform | venv     | venv     | venv        | venv, platform | venv, conda  |
| Windows-x64 | venv, conda           |          |          |             |                | venv, conda  |
| Windows-x86 | venv                  |          |          |             |                | venv         |
| macOS-x64   | conda                 |          |          |             |                | conda        |

In the table:
* _venv_ — virtual environment with all package dependencies and [editable package install](https://pip.pypa.io/en/stable/topics/local-project-installs/);
* _conda_ — _Miniconda_ with package dependencies installed from _mini-forge_ channel, and _curldl_ as editable package install;
* _platform_ — as many dependencies as possible satisfied via Ubuntu package repository, and _curldl_ as _wheel_ install.

The CI/CD pipeline succeeds only if _curldl_ package successfully builds and passes all the [pytest](https://pytest.org/) test cases with 100% [code coverage](https://coverage.readthedocs.io/), as well as [Pylint](https://pylint.readthedocs.io/), [Mypy](https://mypy-lang.org/) and [Bandit](https://bandit.readthedocs.io/) static code analysis. Note that the testing code is also covered by these restrictions.

In order to run tests locally with Python interpreter available in the system, install the _venv_ environment and run _pytest_ with static code analysis, code coverage and security checks as follows:
```shell
./venv.sh install-venv
./venv.sh pytest
./venv.sh misc/scripts/run-bandit.sh
```

`venv.sh` is a convenience _venv_ wrapper that also enables some additional Python checks; you can simply activate the _venv_ environment instead. Testing with _Conda_ is possible as well — see the [CI/CD pipeline execution](https://github.com/noexec/curldl/actions) for details.

# License

This project is released under the [GNU LGPL License Version 3](https://github.com/noexec/curldl/blob/develop/LICENSE.md) or any later version.
