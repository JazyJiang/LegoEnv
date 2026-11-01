#!/usr/bin/env python3
"""Assemble the builder agent's working directory from the repository layout.

The builder agent, its prompts (prompts/BUILDER.md, builder/SKILL.md) and the
adapter modules address files through a fixed workspace layout that is mounted
at /builder inside the isolated namespace:

    smoke/pack/            builder/*.py, builder/batches, builder/examples/*,
                           apps/base_specs, apps/adapters (as newspecs*)
    smoke/pack_dpsk/       builder/dklib.py, prompts/BUILDER.md, skeleton/ (as contract/,
                           with atoms/workflow/CONTRACT.md and atoms/server/onboarding/ONBOARD_BRIEF.md)
    smoke/.claude/skills/  builder/SKILL.md
    LegoEnv/               builder/legacy_runtime/ (as runtime/) and builder/compose/ (as compose/)

Those in-workspace names (``smoke``, ``pack_dpsk``, ``newspecs3.<app>.register``)
are part of the agent's prompt and import contract, so they are recreated here
instead of being renamed in the repository.

The builder keeps its own runtime version (builder/legacy_runtime/). It is an
older revision of legoenv/runtime/ with different guard behavior (for example
foreign-key guards), and the builder's admission checks were run against it.
"""
from pathlib import Path
import shutil

IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc')
# Multi-app registration modules (imported as ``newspecs.register`` and
# ``newspecs2.register``); every other adapter directory is one app.
WAVES = {'wave1': 'newspecs', 'wave2': 'newspecs2'}
PACK_FILES = ['packlib.py', 'accept.py', 'emit_task.py', 'fill_witness.py', 'argnorm.py']


def _copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=IGNORE)
    else:
        shutil.copyfile(src, dst)


def stage(root, dest):
    """Create ``dest/smoke`` and ``dest/LegoEnv`` from the legoenv package ``root``."""
    root, dest = Path(root).resolve(), Path(dest)
    smoke, pack, dk = dest / 'smoke', dest / 'smoke/pack', dest / 'smoke/pack_dpsk'
    for name in PACK_FILES:
        _copy(root / 'builder' / name, pack / name)
    _copy(root / 'builder/batches', pack / 'batches')
    for example in sorted((root / 'builder/examples').iterdir()):
        if example.is_dir():
            _copy(example, pack / example.name)
    _copy(root / 'apps/base_specs', pack / 'base_specs')
    for adapter in sorted((root / 'apps/adapters').iterdir()):
        if not adapter.is_dir():
            continue
        if adapter.name in WAVES:
            _copy(adapter, pack / WAVES[adapter.name])
        else:
            _copy(adapter, pack / 'newspecs3' / adapter.name)
    _copy(root / 'builder/dklib.py', dk / 'dklib.py')
    _copy(root / 'prompts/BUILDER.md', dk / 'BUILDER.md')
    _copy(root / 'skeleton', dk / 'contract')
    _copy(root / 'atoms/workflow/CONTRACT.md', dk / 'contract/CONTRACT.md')
    _copy(root / 'atoms/server/onboarding/ONBOARD_BRIEF.md', dk / 'contract/ONBOARD_BRIEF.md')
    _copy(root / 'builder/SKILL.md', smoke / '.claude/skills/build_pack/SKILL.md')
    _copy(root / 'apps/APPS.md', smoke / 'PUBLICATION_APPS.md')
    library = dest / 'LegoEnv'
    _copy(root / 'builder/legacy_runtime', library / 'runtime')
    _copy(root / 'builder/compose/mvgen.py', library / 'compose/mvgen.py')
    _copy(root / 'builder/compose/ignite.py', library / 'compose/ignite.py')
    return dest


if __name__ == '__main__':
    import argparse
    import json
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--out', type=Path, required=True, help='New directory for the staged workspace.')
    a = p.parse_args()
    if a.out.exists():
        p.error('Choose a new output directory.')
    stage(Path(__file__).resolve().parents[1], a.out)
    print(json.dumps({'staged': str(a.out.resolve())}))
