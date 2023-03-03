"""Main functional tests"""
import curldl


def test_nothing() -> None:
    """Nothing"""
    curldl.Downloader(basedir='.')
