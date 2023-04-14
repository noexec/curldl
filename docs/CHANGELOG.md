curldl 1.0.0 (2023-04-09)
=========================

Features
--------

- Extend CI/CD workflow to build and publish to PyPI on version tag ([#33](https://github.com/noexec/curldl/pull/33))
- Extend CI/CD workflow with Conda tests on Windows, Ubuntu and macOS platforms; Add entry point wrapper test ([#36](https://github.com/noexec/curldl/pull/36))
- Add wrappers for directly running Pylint, mypy and Bandit static analyzers ([#38](https://github.com/noexec/curldl/pull/38))
- Rename `Downloader.download()` to `Curldl.get()` ([#40](https://github.com/noexec/curldl/pull/40))
- Add usage documentation to README and code docstrings ([#44](https://github.com/noexec/curldl/pull/44))


Bugfixes
--------

- Re-enable local version parts in setuptools-scm ([#35](https://github.com/noexec/curldl/pull/35))


curldl 0.1.0 (2023-04-03)
=========================

Features
--------

- Initialize curldl module with a basic pytest and pylint tests ([#8](https://github.com/noexec/curldl/pull/8))
- Replace example download in CLI with command line arguments; add type hinting verification via pytest --mypy ([#9](https://github.com/noexec/curldl/pull/9))
- Implement functionality tests with full code coverage and refactor code ([#12](https://github.com/noexec/curldl/pull/12))
- Add install functionality to venv wrapper script; add bandit security checks ([#16](https://github.com/noexec/curldl/pull/16))
- Integrate tqdm for download progress bar ([#17](https://github.com/noexec/curldl/pull/17))
- Enhance CLI to support multiple URLs ([#19](https://github.com/noexec/curldl/pull/19))
- Generalize download functionality to non-HTTP URL schemes ([#22](https://github.com/noexec/curldl/pull/22))
- Add PycURL callback parameter to Download class; Extend non-HTTP protocol tests ([#23](https://github.com/noexec/curldl/pull/23))
- Add CI/CD tests workflow for Ubuntu with CPython and PyPy ([#26](https://github.com/noexec/curldl/pull/26))
- Add CI/CD tests workflow for Windows with CPython; Upgrade tests for Windows platform ([#29](https://github.com/noexec/curldl/pull/29))
- Integrate automatic git tag-based versioning ([#32](https://github.com/noexec/curldl/pull/32))


Bugfixes
--------

- Fix partial download renaming on Windows platform; Fix FileSystem and Downloader class tests on Windows platform ([#29](https://github.com/noexec/curldl/pull/29))
