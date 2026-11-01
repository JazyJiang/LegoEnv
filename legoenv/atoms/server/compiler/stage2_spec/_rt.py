"""Put the deterministic runtime on ``sys.path`` for the stage-2 modules.

The compiler was developed against the runtime that now lives in
``legoenv/builder/legacy_runtime/`` (the base specs in ``legoenv/apps/base_specs``
were probed with it).  ``legoenv/runtime/`` exposes the same API
(``grammar``, ``runtime.Env``); point ``LEGOENV_RUNTIME_DIR`` at it to use it instead.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.path.abspath(os.environ.get("LEGOENV_RUNTIME_DIR") or os.path.join(
    HERE, "..", "..", "..", "..", "builder", "legacy_runtime"))

for _p in (HERE, RUNTIME_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)
