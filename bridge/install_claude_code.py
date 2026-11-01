#!/usr/bin/env python3
"""Download a pinned official npm native package; verify before extracting."""
import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent


def verified_binary(archive, integrity, version, destination):
    algorithm, expected = integrity.split('-', 1)
    digest = hashlib.new(algorithm)
    with archive.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(part)
    if not hmac.compare_digest(base64.b64encode(digest.digest()).decode(), expected):
        raise ValueError('Official package integrity mismatch; nothing was extracted')
    with tarfile.open(archive, 'r:gz') as package:
        metadata = package.extractfile('package/package.json')
        if metadata is None or json.load(metadata)['version'] != version:
            raise ValueError('Package version differs from the lock')
        members = [m for m in package.getmembers()
                   if m.isfile() and Path(m.name).name in {'claude', 'claude.exe'}]
        if len(members) != 1:
            raise ValueError('Expected one native Claude executable')
        source = package.extractfile(members[0])
        if source is None:
            raise ValueError('Native executable is absent')
        with destination.open('xb') as target:
            shutil.copyfileobj(source, target)
        destination.chmod(0o755)


def main():
    lock = json.loads((HERE/'claude_code.lock.json').read_text())
    machine = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=sorted(lock['native_packages']),
                        default='linux-' + machine if machine else None)
    parser.add_argument('--dest', type=Path, required=True,
                        help='New private local directory; no binary is bundled with the repository')
    parser.add_argument('--download-only', action='store_true')
    args = parser.parse_args()
    if args.platform not in lock['native_packages']:
        parser.error('Select a supported Linux glibc platform explicitly')
    args.dest.mkdir(parents=True, exist_ok=False)
    entry = lock['native_packages'][args.platform]
    archive = args.dest/'claude-code.tgz'
    with urllib.request.urlopen(entry['url'], timeout=180) as response, archive.open('xb') as target:
        shutil.copyfileobj(response, target)
    binary = args.dest/'claude'
    verified_binary(archive, entry['integrity'], lock['version'], binary)
    receipt = {'version': lock['version'], 'platform': args.platform,
               'official_tarball': entry['url'], 'integrity_verified': True,
               'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
               'version_command_executed': not args.download_only}
    if not args.download_only:
        version = subprocess.check_output([str(binary.resolve()), '--version'], text=True,
            timeout=30, env={**os.environ, 'DISABLE_AUTOUPDATER': '1',
                             'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'}).strip()
        if version.split()[0] != lock['version']:
            raise ValueError('Executable version differs from the lock')
        receipt['observed_version'] = version
    (args.dest/'INSTALL_RECEIPT.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'binary': str(binary.resolve()), **receipt}))


if __name__ == '__main__':
    main()
