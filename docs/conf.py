import subprocess  # nosec
from importlib import metadata

project = "curldl"
copyright = "2023, Michael Orlov"

release = metadata.version(project)
version = ".".join(release.split(".")[:2])
release = ".".join(release.split(".")[:3])

nitpicky = True

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}

exclude_patterns = ["CHANGELOG.md", "changelog.d/**"]

suppress_warnings = ["autosectionlabel.*"]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
]

myst_linkify_fuzzy_links = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "pycurl": ("http://pycurl.io/docs/latest/", None),
    "tenacity": ("https://tenacity.readthedocs.io/en/latest/", None),
}

nitpick_ignore = [
    ("py:class", "sys.UnraisableHookArgs"),
    ("py:class", "_thread._ExceptHookArgs"),
    ("py:class", "tqdm"),
    ("py:exc", "argparse.ArgumentError"),
    ("py:exc", "metadata.PackageNotFoundError"),
    ("py:class", "pycurl.error"),
    ("py:exc", "pycurl.error"),
]

html_theme = "furo"

html_theme_options = {"navigation_with_keys": True, "top_of_page_button": None}

autoclass_content = "both"

autodoc_default_options = {
    "members": True,
    "private-members": True,
    "undoc-members": True,
    "member-order": "bysource",
}

autodoc_typehints = "both"
autodoc_typehints_description_target = "documented"

subprocess.run(
    f"sphinx-apidoc -feM -o api ../src/curldl".split(),  # nosec
    check=True,
    text=True,
    encoding="ascii",
)
