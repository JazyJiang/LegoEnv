#!/usr/bin/env python3
"""Check runtime installation dependencies without starting a model."""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['runtime'], default='runtime')
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    checks = [{'check': 'python_at_least_3_12', 'passed': sys.version_info >= (3, 12)}]
    for rel in ['tools/pipeline.py', 'tools/collect.py', 'tools/preflight.py',
                'runtime/runtime.py', 'runtime/grammar.py',
                'runtime/mcp_server.py', 'sampling/apistyle.py']:
        file = ROOT/rel
        try:
            ast.parse(file.read_text(), filename=rel)
            checks.append({'check': 'python_source', 'file': rel, 'passed': True})
        except (OSError, SyntaxError):
            checks.append({'check': 'python_source', 'file': rel, 'passed': False})
    # Import in a child without site packages or PYTHONPATH. No HTTP request or
    # corpus loading is necessary for the minimal inline-state runtime.
    code = ('import sys; sys.path[:0]=[sys.argv[1],sys.argv[2]]; '
            'import runtime, grammar, mcp_server, apistyle')
    imported = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code,
        str(ROOT/'runtime'), str(ROOT/'sampling')],
        capture_output=True, text=True, timeout=30)
    checks.append({'check': 'inline_runtime_imports_with_stdlib_only', 'passed': imported.returncode == 0})
    result = {'passed': all(c['passed'] for c in checks), 'mode': args.mode, 'checks': checks,
              'model_or_network_requests': 0}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
