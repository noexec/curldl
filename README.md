[![Tests with Coverage and Static Analysis](https://github.com/noexec/curldl/actions/workflows/tests.yml/badge.svg)](https://github.com/noexec/curldl/actions/workflows/tests.yml)

# Introduction

The __curldl__ Python module safely and reliably downloads files with [PycURL](https://pycurl.io/), which in turn is a wrapper for [libcurl](https://curl.se/libcurl/) file transfer library. The purpose of __curldl__ is providing a straightforward API for downloading files with the following features:

* Multi-protocol support: protocol support is delegated to [curl](https://curl.se/) in as protocol-neutral way as possible. This means that there is no reliance on HTTP-specific header and statuses, for example. If a feature like download resuming and _if-modified-since_ condition is supported by the underlying protocol, it can be used by _curldl_.
* If a partial download is abandoned, most chances are that it may be resumed later (supported for HTTP(S), FTP(S) and FILE protocols). A `.part` extension is added to the partial download file, and it is renamed to the target file name once the download completes.
* If the downloaded file exists, it is not downloaded again unless the timestamp of file on server is newer (supported for HTTP(S), FTP(S), RTSP and FILE protocols). Note that file download may be skipped before timestamp is considered due to file size matching the expected file size (see below).
* Downloads are configured relative to a base directory, and relative download path is verified not to escape the base directory directly, via symlinks, or otherwise.
* Downloaded file size and/or cryptographic digest(s) can be verified upon download completion. This verification, together with the relative path safety above, allows for easy implementation of mirroring scripts — e.g., when relative path, file size and digest are located in a downloaded XML file.


# Installation

The only requirement for _curldl_ is Python 3.8+. Install it as follows:
```shell
pip install curldl
```

If you encounter a build failure during installation of _pycurl_ dependency, the following should help:
* On Linux, install one of:
    * _pycurl_ package from distribution repo — e.g., on Ubuntu run `sudo apt install python3-pycurl`
    * _libcurl_ development files with `sudo apt install build-essential libcurl4-openssl-dev`
* On Windows, install an unofficial _pycurl_ build since official builds are not available at the moment — e.g., [here](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pycurl), or use _Conda_ (see below).
* On Windows and MacOS, use _Conda_ or _Miniconda_ with [conda-forge](https://conda-forge.org/) channel. For instance, see runtime dependencies in the following [test environment](https://github.com/noexec/curldl/blob/develop/misc/conda/test-environment.yml).

Overall, _curldl_ is expected to have no issues in any environment with Python 3.8+ (CPython or PyPy). Here is the simplified configuration matrix covered by [CI/CD pipeline](https://github.com/noexec/curldl/actions/workflows/tests.yml) at the time of writing this document:

| Platform      | CPython 3.8           | PyPy 3.8 | CPython 3.9 | PyPy 3.9 | CPython 3.10   | CPython 3.11 |
|---------------|-----------------------|----------|-------------|----------|----------------|--------------|
| Ubuntu / x64  | venv, conda, platform | venv     | venv        | venv     | venv, platform | venv, conda  |
| Windows / x64 | venv, conda           |          |             |          |                | venv, conda  |
| Windows / x86 | venv                  |          |             |          |                | venv         |
| MacOS / x64   | conda                 |          |             |          |                | conda        |

In this table, _venv_ is a virtual environment with [editable package install](https://pip.pypa.io/en/stable/topics/local-project-installs/), _conda_ is a _Miniconda_ install with _mini-forge_ channel, and _platform_ is a _wheel_ package install with as much dependencies as possible installed via Ubuntu packages repository.


# Usage

Here is a basic usage example:

```python
import curldl, os
dl = curldl.Curldl(basedir='downloads', progress=True)
dl.get('https://kernel.org/pub/linux/kernel/Historic/linux-0.01.tar.gz', 'linux-0.01.tar.gz',
       size=73091, digests={'sha1': '566b6fb6365e25f47b972efa1506932b87d3ca7d'})
assert os.path.exists('downloads/linux-0.01.tar.gz')
```


# Testing

To run tests locally under current Python version, install the _venv_ environment and run _pytest_ with static code analysis, code coverage and security checks as follows:
```shell
./venv.sh install-venv
./venv.sh pytest
./venv.sh misc/scripts/run-bandit.sh
```

# License

This project is released under the [GNU LGPL License Version 3](https://github.com/noexec/curldl/blob/develop/LICENSE.md) or any later version.
