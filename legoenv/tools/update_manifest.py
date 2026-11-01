#!/usr/bin/env python3
"""Regenerate provenance/CODE_MANIFEST.json from the files under legoenv/.

Uses the same inventory rules as tools/release_check.py (skips __pycache__,
*.pyc/*.pyo and the manifest itself; refuses symlinks). Non-file metadata in an
existing manifest is kept; files_count and source_manifest_sha256 are recomputed.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path('provenance/CODE_MANIFEST.json')
SOURCE = Path('provenance/SOURCE_MANIFEST.json')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    target = ROOT / MANIFEST
    old = json.loads(target.read_text()) if target.exists() else {}
    rows = []
    for path in sorted(ROOT.rglob('*'), key=lambda p: str(p.relative_to(ROOT))):
        if '__pycache__' in path.parts or path.suffix in {'.pyc', '.pyo'}:
            continue
        if path.is_symlink():
            raise SystemExit('Refusing symlink: ' + str(path.relative_to(ROOT)))
        if path.is_file() and path != target:
            rows.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    manifest = {'files': rows}
    for key, value in old.items():
        if key != 'files':
            manifest[key] = value
    manifest['files_count'] = len(rows)
    if (ROOT / SOURCE).exists():
        manifest['source_manifest_sha256'] = sha(ROOT / SOURCE)
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(MANIFEST), 'files_count': len(rows)}))


if __name__ == '__main__':
    main()
