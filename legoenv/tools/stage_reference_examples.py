#!/usr/bin/env python3
"""Copy the two reviewed examples into a new location in an existing builder stack."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stack', type=Path, required=True, help='Staged workspace smoke/ directory (tools/builder_workspace.py) containing pack and pack_dpsk.')
    p.add_argument('--examples', type=Path, required=True,
                   help='Approved external example directory containing IDENTITIES.json and both packages.')
    a = p.parse_args()
    stack = a.stack.resolve()
    if not all((stack / name).is_file() for name in ['pack/packlib.py', 'pack_dpsk/dklib.py']):
        raise ValueError('Provide a reviewed full builder stack, not an empty directory.')
    source = a.examples.resolve()
    rows = json.loads((source / 'IDENTITIES.json').read_text())['files']
    for r in rows:
        relative = Path(r['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Reference example identity path must stay inside its directory.')
        path = source / r['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != r['sha256']:
            raise ValueError('Reference example identity mismatch: ' + r['path'])
    names = ['clean_quality_review', 'clean_leave_closeout']
    targets = [stack / 'pack' / name for name in names]
    if any(t.exists() for t in targets):
        raise FileExistsError('Reference examples already exist; refusing to overwrite either example.')
    for name, target in zip(names, targets):
        shutil.copytree(source / name, target)
    print(json.dumps({'staged': names, 'previous_files_overwritten': False,
                      'builds_executed': False, 'model_requests': 0,
                      'next_step': 'Run from the stack root with its reviewed dependencies and real datasets.'}))


if __name__ == '__main__':
    main()
