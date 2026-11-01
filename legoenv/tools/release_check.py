#!/usr/bin/env python3
"""Verify the code-only inventory without certifying data or model results."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path('provenance/CODE_MANIFEST.json')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def check(root):
    manifest = json.loads((root / MANIFEST).read_text())
    rows = manifest['files']
    expected = {}
    for row in rows:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Inventory path is outside the code directory.')
        if row['path'] in expected:
            raise ValueError('Duplicate inventory path: ' + row['path'])
        expected[row['path']] = row
    actual = {}
    for path in root.rglob('*'):
        if '__pycache__' in path.parts or path.suffix in {'.pyc', '.pyo'}:
            continue
        if path.is_symlink():
            raise ValueError('Inventory contains a symlink: ' + str(path.relative_to(root)))
        if path.is_file() and path != root / MANIFEST:
            actual[str(path.relative_to(root))] = path
    if set(actual) != set(expected):
        raise ValueError('Inventory mismatch: missing=%d extra=%d' % (
            len(set(expected) - set(actual)), len(set(actual) - set(expected))))
    for name, row in expected.items():
        path = actual[name]
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('Source identity mismatch: ' + name)
        if path.suffix == '.py':
            ast.parse(path.read_text(), filename=name)
    identities = json.loads((root / 'prompts/IDENTITIES.json').read_text())
    for name, row in identities['templates'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Template path is outside the prompt directory.')
        if sha(root / 'prompts' / name) != row['sha256']:
            raise ValueError('Canonical prompt identity mismatch: ' + name)
    return {
        'passed': True,
        'scope': 'code_only',
        'payload_files': len(rows),
        'payload_bytes': sum(row['bytes'] for row in rows),
        'canonical_prompt_hashes_verified': True,
        'model_or_network_requests': 0,
        'data_release_verified': False,
        'new_official_performance_results': False,
        'public_release_authorised_or_published': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json-out', type=Path)
    args = parser.parse_args()
    if args.json_out:
        destination = args.json_out.resolve()
        if ROOT == destination or ROOT in destination.parents:
            parser.error('Keep the check receipt outside the sealed code directory.')
    result = check(ROOT)
    if args.json_out:
        destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
