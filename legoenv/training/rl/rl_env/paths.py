"""Resolve user-supplied paths without machine-specific mount aliases."""
import os


def rl_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve(path):
    if not path or path == "-" or os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(rl_root(), path))

