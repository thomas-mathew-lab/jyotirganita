"""jyotirganita: a Python library for traditional and modern Indian calendrical astronomy.

Versions are numbered as ``CHANGELOG.md`` describes: a
patch changes no computed value, a minor version may, and a major version
may break code that uses the package.

The inverse search is not re-exported here, because ``jyotirganita.search``
is its subpackage: ``from jyotirganita.search import open_search, search``.
"""

from typing import Any

__version__ = "1.0.0"

#: the public API, re-exported from ``jyotirganita/api.py`` on first use
API = (
    "day",
    "eclipses",
    "generate",
    "open_config",
    "positions",
    "sankrantis",
)
__all__ = ["API", "__version__", *API]


def __getattr__(name: str) -> Any:
    if name in API:
        from jyotirganita import api

        return getattr(api, name)
    raise AttributeError(f"module 'jyotirganita' has no attribute {name!r}")
