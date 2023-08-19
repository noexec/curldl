# Introduction

The __curldl__ Python module safely and reliably downloads files with [PycURL](http://pycurl.io/), which in turn is a wrapper for [libcurl](https://curl.se/libcurl/) file transfer library. The purpose of __curldl__ is providing a straightforward API for downloading files with the following features:

* Multi-protocol support: protocol support is delegated to [curl](https://curl.se/) in as protocol-neutral way as possible. This means that there is no reliance on HTTP-specific header and statuses, for example. If a feature like download resuming and _if-modified-since_ condition is supported by the underlying protocol, it can be used by _curldl_.
* If a partial download is abandoned, most chances are that it may be resumed later (supported for HTTP(S), FTP(S) and FILE protocols). A `.part` extension is added to the partial download file, and it is renamed to the target file name once the download completes.
* If the downloaded file exists, it is not downloaded again unless the timestamp of file on server is newer (supported for HTTP(S), FTP(S), RTSP and FILE protocols). Note that file download may be skipped before timestamp is considered due to file size matching the expected file size (see below).
* Downloads are configured relative to a base directory, and relative download path is verified not to escape the base directory directly, via symlinks, or otherwise.
* Downloaded file size and/or cryptographic digest(s) can be verified upon download completion. This verification, together with the relative path safety above, allows for easy implementation of mirroring scripts — e.g., when relative path, file size and digest are located in a downloaded XML file.
* Speed: since native _libcurl_ writes directly to the output stream file descriptor, there are no transfers of large chunks of data inside Python interpreter.


# Usage

Most examples below use the _curldl_ wrapper script instead of Python code. Of course, in all cases it is easy to write a few lines of code with identical functionality — see the first example. Also, note that inline documentation is available for all functions.


## Simple Download

The following code snippet downloads a file and verifies its size and SHA-1 digest. A progress bar is shown on _stderr_ while download is in progress.

```python
import curldl, os
dl = curldl.Curldl(basedir="downloads", progress=True)
dl.get("https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz",
       "linux-0.01.tar.gz", size=73091,
       digests={"sha1": "566b6fb6365e25f47b972efa1506932b87d3ca7d"})
assert os.path.exists("downloads/linux-0.01.tar.gz")
```

If verification fails, the partial download is removed; otherwise it is renamed to the target file after being timestamped with _last-modified_ timestamp received from the server.

A similar result is achieved on command-line by running the CLI wrapper script, which is useful for quickly testing _curldl_ functionality:

```shell
curldl -b downloads -s 73091 -a sha1 -d 566b6fb6365e25f47b972efa1506932b87d3ca7d \
       -p -l debug https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz
```

The corresponding (redacted) log output:

```text
Saving download(s) to: linux-0.01.tar.gz
Creating directory: downloads
Downloading https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz
            to downloads/linux-0.01.tar.gz.part
Finished downloading downloads/linux-0.01.tar.gz.part 0 -> 73,091 B
            (HTTPS 200: OK) [0:00:01]
Timestamping downloads/linux-0.01.tar.gz.part with 1993-10-30 00:00:00+00:00
Successfully verified file size of downloads/linux-0.01.tar.gz.part
Successfully verified SHA1 of downloads/linux-0.01.tar.gz.part
Partial download of downloads/linux-0.01.tar.gz passed verification
            (73091 / {'sha1': '566b6fb6365e25f47b972efa1506932b87d3ca7d'})
Moving downloads/linux-0.01.tar.gz.part to downloads/linux-0.01.tar.gz
```

Note that renaming of `downloads/linux-0.01.tar.gz.part` to `downloads/linux-0.01.tar.gz` is the very last action of `Curldl.get()` method. If the target filename exists, the download succeeded and passed verification, if requested.


## Repeated Download

Running the same command again doesn't actually result in a server request since file size matches (digest is not checked since it would be time-prohibitive when mirroring large repositories):

```text
Saving download(s) to: linux-0.01.tar.gz
Skipping update of downloads/linux-0.01.tar.gz since it has
         the expected size 73,091 B
```

We can also request the same file without providing an expected size:

```python
import curldl
dl = curldl.Curldl(basedir="downloads", progress=True)
dl.get("ftp://ftp.hosteurope.de/mirror/ftp.kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz",
       "linux-0.01.tar.gz")
```

In this case, the download is skipped due to _If-Modified-Since_ check:

```text
Will update downloads/linux-0.01.tar.gz.part
     if modified since 1993-10-30 00:00:00+00:00
Discarding downloads/linux-0.01.tar.gz.part because
     it is not more recent
```

Note that FTP protocol was used this time — _curldl_ is entirely protocol-agnostic when using the underlying _libcurl_ functionality.


## Resuming Download

If a download is interrupted, it will be resumed on the next attempt (which may also be a retry according to the configured retry policy). Here is what happens when _Ctrl-C_ is used to send a SIGINT signal to the Python process. This example also demonstrates how to construct a filename from a URL (CLI interface does the same when `--output` switch is omitted).

```python
import curldl, os, urllib.parse as uparse
dl = curldl.Curldl(basedir="downloads", progress=True)
url = "https://releases.ubuntu.com/22.04.2/ubuntu-22.04.2-live-server-amd64.iso"
filename = os.path.basename(uparse.unquote(uparse.urlparse(url).path))
dl.get(url, filename)
```

The corresponding (redacted) log output:

```text
Downloading https://releases.ubuntu.com/22.04.2/ubuntu-22.04.2-live-server-amd64.iso
            to downloads/ubuntu-22.04.2-live-server-amd64.iso.part
ubuntu-22.04.2-live-server-amd64.iso:  13%|██▋                  | 244M/1.84G
            [00:06<00:38, 44.7MB/s] ^C KeyboardInterrupt:
Download interrupted downloads/ubuntu-22.04.2-live-server-amd64.iso.part 0 -> 259,981,312 B
            (42: Callback aborted / HTTPS 200: OK) [0:00:07]
```

Attempting the same download again resumes the download:

```text
Resuming download of https://releases.ubuntu.com/22.04.2/ubuntu-22.04.2-live-server-amd64.iso
         to downloads/ubuntu-22.04.2-live-server-amd64.iso.part at 259,981,312 B
Finished downloading downloads/ubuntu-22.04.2-live-server-amd64.iso.part
         259,981,312 -> 1,975,971,840 B (HTTPS 206: Partial Content) [0:01:24]
```

Note, however, that we didn't provide a size or digest for verification. Since the downloaded file is timestamped only once download completes, how does _curldl_ know that the file wasn't changed on the server in the meantime? The answer is that _curldl_ simply avoids removing large partial downloads in such cases — see documentation for _always_keep_part_bytes_ constructor parameter of _Curldl_.


## Enabling Additional Protocols

By default, _curldl_ enables the following protocols:

- HTTP(S)
- FTP(S)
- SFTP

In order to enable a different set of protocols, use the `allowed_protocols_bitmask` constructor argument. For instance, the code below downloads a _file://_ URI:

```python
import curldl, pycurl, pathlib
protocols = pycurl.PROTO_FILE | pycurl.PROTO_HTTPS
dl = curldl.Curldl(basedir="downloads", allowed_protocols_bitmask=protocols)
file_uri = pathlib.Path(__file__).absolute().as_uri()
dl.get(file_uri, "current_source.py")
```

To enable all protocols, use `allowed_protocols_bitmask=pycurl.PROTO_ALL`. Note, however, that there might be security repercussions.


## Escaping Base Directory

Attempts to escape base directory are prevented, e.g.:

```python
import curldl, os
dl = curldl.Curldl(basedir=os.curdir)
dl.get("http://example.com/", os.path.join(os.pardir, "file.txt"))
```

The above results in:

```text
ValueError: Relative path ../file.txt escapes base path /home/user/curldl
```

_curldl_ performs extensive checks to prevent escaping the base download directory — see _FileSystem_ class implementation and unit tests for details.


# Installation

The only requirement for _curldl_ is Python 3.8+. Install the package as follows:
```shell
pip install curldl
```

If you encounter a build failure during installation of _pycurl_ dependency, the following should help:
* On Linux, install one of:
    * _pycurl_ package from distribution repo — e.g., on Ubuntu run `sudo apt install python3-pycurl`
    * _libcurl_ development files with `sudo apt install build-essential libcurl4-openssl-dev`
* On Windows, install an unofficial _pycurl_ build since official builds are not available at the moment — e.g., from [Christoph Gohlke](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pycurl)'s packages, or use _Conda_ (see below).
* On Windows and macOS, use _Conda_ or _Miniconda_ with [conda-forge](https://conda-forge.org/) channel. For instance, see runtime dependencies in the following [test environment](https://github.com/noexec/curldl/blob/develop/misc/conda/test-environment.yml).

Overall, _curldl_ is expected to not have any issues in any environment with Python 3.8+ (CPython or PyPy) — see the [Testing](#testing) section below.


# Testing

A simplified configuration matrix covered by [CI/CD test + build pipeline](https://github.com/noexec/curldl/actions/workflows/ci.yml) at the time of writing this document is presented below:

| Platform    | CPython 3.8           | CPython 3.9, PyPy 3.8+3.10 | CPython 3.10   | CPython 3.11 |
|-------------|-----------------------|----------------------------|----------------|--------------|
| Ubuntu-x64  | venv, conda, platform | venv                       | venv, platform | venv, conda  |
| Windows-x64 | venv, conda           |                            |                | venv, conda  |
| Windows-x86 | venv                  |                            |                | venv         |
| macOS-x64   | conda                 |                            |                | conda        |

In the table:
* _venv_ — virtual environment with all package dependencies and [editable package install](https://pip.pypa.io/en/stable/topics/local-project-installs/); on Ubuntu includes tests with minimal versions of package dependencies;
* _conda_ — _Miniconda_ with package dependencies installed from _mini-forge_ channel, and _curldl_ as editable package install;
* _platform_ — as many dependencies as possible satisfied via Ubuntu package repository, and _curldl_ as _wheel_ install.

The CI/CD pipeline succeeds only if _curldl_ package successfully builds and passes all the [pytest](https://pytest.org/) test cases with 100% [code coverage](https://coverage.readthedocs.io/), as well as [Pylint](https://pylint.readthedocs.io/), [Mypy](https://mypy-lang.org/) and [Bandit](https://bandit.readthedocs.io/) static code analysis. Code style checks are also a part of the pipeline. Note that the testing code is also covered by these restrictions.


# Development

## Python Environment

The following commands install and activate a _venv_ environment in Linux, using the available Python 3 interpreter:
```shell
./venv.sh install-venv
. venv/bin/activate
```

`venv.sh` is a convenience _venv_ wrapper that also enables some additional Python checks; you can use it to run Python code, or just activate the _venv_ environment instead as shown above.


## Running Tests

Use _pytest_ in order to run all test cases:
```shell
./venv.sh pytest
```

In addition to the actual tests, pytest executes _Pylint_, _Mypy_, code coverage and code formatting plugins (_black_ and _isort_). Thus, make sure that all new code is covered by tests.

Testing with _Conda_ is possible as well — see the [CI/CD pipeline execution](https://github.com/noexec/curldl/actions) for details.


## Code Formatting

Reformat the code with _black_ and _isort_ by running the following scripts:
```shell
misc/scripts/run-black.sh
misc/scripts/run-isort.sh
```

This is only necessary if the tests fail due to code formatting.


## Changelog Entries

Upon authoring a set of code or documentation changes, prepare a changelog fragment using [towncrier](https://towncrier.readthedocs.io/) as follows:
```shell
towncrier create -c "Extend package usage documentation" 54.doc.md
```

The command above creates a changelog fragment file in `docs/changelog.d`. See the output of `towncrier create --help` for supported fragment types. Note also that `54` above is the number of GitHub [pull request](https://github.com/noexec/curldl/pull/54), which is used to format a pull request link when generating the combined changelog. So creation of new fragment needs to be done _after_ opening a pull request.

When releasing a new version, the changelog file can be updated as follows:
```shell
towncrier build --version 1.x.y [--draft]
```

Add _--draft_ option for a dry run first, because otherwise fragment files will be removed, and changelog file extended with the new entries.


# Changelog

See the [Changelog](https://github.com/noexec/curldl/blob/develop/docs/CHANGELOG.md) file for a summary of changes in each release.


# License

This project is released under the [GNU LGPL License Version 3](https://github.com/noexec/curldl/blob/develop/LICENSE.md) or any later version.


[![PyPI](https://img.shields.io/pypi/v/curldl)](https://pypi.org/project/curldl/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/curldl)](https://pypi.org/project/curldl/)
[![GitHub Workflow Status](https://github.com/noexec/curldl/actions/workflows/ci.yml/badge.svg)](https://github.com/noexec/curldl/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/noexec/curldl/branch/develop/graph/badge.svg?token=QOA9KZ9A44)](https://codecov.io/gh/noexec/curldl)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Read the Docs](https://img.shields.io/readthedocs/curldl)](https://curldl.readthedocs.io/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/imports-isort-1674b1.svg?labelColor=ef8336)](https://pycqa.github.io/isort/)
[![GitHub](https://img.shields.io/github/license/noexec/curldl)](https://github.com/noexec/curldl/blob/develop/LICENSE.md)
