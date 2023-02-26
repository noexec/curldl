"""Safely and reliably download files with PycURL

Usage:
    import curldl
    (use curldl.Downloader...)
"""
import os

from curldl.curldl import Downloader

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
