"""Stable package facade for the deterministic LegoEnv runtime.

Most callers add ``runtime/`` to ``sys.path`` and import ``runtime.py`` as a
top-level module.  Other entry points import from the repository root, where
Python resolves this directory as the ``runtime`` package instead.  Export the
implementation namespace in both cases so import order cannot change the API.
"""
from . import runtime as _implementation


__all__ = [
    name for name in vars(_implementation)
    if not name.startswith("_")
]


def __getattr__(name):
    return getattr(_implementation, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_implementation)))
