"""jyotirganita — placeholder release (name reservation).

A deterministic, fully parameterized pañcāṅgam computation engine for the
scientific study of Indian calendrical traditions — historical almanacs,
inscriptions, and siddhantic astronomy.

This distribution is a name reservation only. It exposes no functionality
beyond ``__version__``. The computation engine is under active development;
the first functional public release will be version 1.0.0.

See https://github.com/thomas-mathew-lab/jyotirganita for project status.
"""

__version__ = "0.0.1"

__all__ = ["__version__"]

_REPO_URL = "https://github.com/thomas-mathew-lab/jyotirganita"


def __getattr__(name: str) -> object:
    """Explain that this release is an empty placeholder.

    Any attribute access other than the handful defined above lands here,
    so users who try to call into the engine get a clear explanation rather
    than a bare ``AttributeError``.
    """
    raise AttributeError(
        f"jyotirganita {__version__} is a placeholder release that reserves the "
        f"package name on PyPI; it provides no {name!r} and no computational "
        f"functionality at all. The pañcāṅgam engine is under active "
        f"development and will arrive in version 1.0.0. Track progress at "
        f"{_REPO_URL}."
    )
