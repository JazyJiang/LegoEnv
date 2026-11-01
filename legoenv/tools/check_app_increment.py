#!/usr/bin/env python3
"""Portable deterministic integration checks. Never calls an LLM or network."""
import argparse
import concurrent.futures
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import builder_workspace

PIN = '800eb606b13bf12859e0687e3551ec3b251ae624a9bae4dabe4b072bdc4fd40a'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + '\n')


def reference(root, app):
    runtime_path = root / 'runtime/runtime.py'
    assert sha(runtime_path) == PIN
    os.environ['ENVLIB_COLUMN_DEFAULTS'] = '1'
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(runtime_path.parent))
    ms = importlib.util.spec_from_file_location('runtime', runtime_path)
    runtime = importlib.util.module_from_spec(ms)
    sys.modules['runtime'] = runtime
    ms.loader.exec_module(runtime)
    p = root / 'app_examples' / app
    spec, task = json.loads((p / 'spec.json').read_text()), json.loads((p / 'task.json').read_text())
    review_path = p / 'REVIEW.json'
    if not review_path.exists():
        review_path = p / 'NATIVE_QUALIFICATION.json'
    review = json.loads(review_path.read_text())
    assert sha(p / 'task.json') == review['task_sha256'] and sha(p / 'spec.json') == review['spec_sha256']
    card = json.loads((root / 'apps/adapters' / app / 'capability_card.json').read_text())
    base = json.loads((root / 'apps/base_specs' / (app + '.spec.json')).read_text())
    prefix = base['env_id'] + '__'
    allowed = {prefix + t for tools in card['kinds'].values() for t in tools}
    declared = {e['name'] for e in spec['entities']}
    env = runtime.Env(copy.deepcopy(spec))
    verifier = runtime.Verifier()
    initial = verifier.eval(task['verifier'], env.state) is True
    changed = 0
    steps = []
    for st in task.get('witness') or []:
        before = copy.deepcopy(env.state)
        response = env.call(st['tool'], st.get('args', {}))
        ok = isinstance(response, dict) and response.get('ok') is True
        keys = [k for k in env.state.keys() | before.keys() if k in declared and k.startswith(prefix) and env.state.get(k) != before.get(k)]
        if st['tool'] in allowed and keys and ok:
            changed += 1
        steps.append({'tool': st['tool'], 'ok': ok, 'changed_declared_target_entities': len(keys)})
        if not ok:
            break
    final = verifier.eval(task['verifier'], env.state) is True
    reset = verifier.eval(task['verifier'], runtime.Env(copy.deepcopy(spec)).state) is True
    passed = bool(steps) and len(steps) == len(task['witness']) and all(s['ok'] for s in steps) and not initial and final and not reset and changed > 0
    return {'app': app, 'passed': passed, 'seed_verifier': initial, 'final_verifier': final,
            'reset_verifier': reset, 'declared_target_write_calls': changed, 'steps': steps,
            'task_sha256': sha(p / 'task.json'), 'spec_sha256': sha(p / 'spec.json'), 'runtime_sha256': PIN}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--replay-one')
    a = ap.parse_args()
    root = a.root.resolve()
    if a.replay_one:
        try:
            result = reference(root, a.replay_one)
        except Exception as exc:
            result = {'app': a.replay_one, 'passed': False, 'error_type': type(exc).__name__}
        print(json.dumps(result))
        return 0 if result['passed'] else 1
    assert a.out and 1 <= a.workers <= 16
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ['TOKEN', 'SECRET', 'API_KEY', 'PROXY', 'PYTHONHOME', 'PYTHONPATH'])}
    env.update(PYTHONDONTWRITEBYTECODE='1', ENVLIB_COLUMN_DEFAULTS='1', CUDA_VISIBLE_DEVICES='')
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '/usr/bin:/bin')
    qualification = json.loads((root / 'APP_QUALIFICATION.json').read_text())
    assert qualification['all180_qualification_complete'] is True
    entries = qualification['fixtures']
    assert len(entries) == 180 and len({r['app'] for r in entries}) == 180
    before = {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    with tempfile.TemporaryDirectory(prefix='legoenv_app_check_') as temporary:
        stack = Path(temporary) / 'workspace'
        builder_workspace.stage(root, stack)
        work = stack / 'smoke'
        cards = sorted((work / 'pack/newspecs3').glob('*/capability_card.json'))
        assert len(cards) == 193

        def onboard(card):
            app = card.parent.name
            try:
                result = subprocess.run([sys.executable, str(work / 'pack_dpsk/contract/onboard_check.py'), app], cwd=work,
                                        env=env, capture_output=True, text=True, timeout=600)
                row = {'app': app, 'passed': result.returncode == 0, 'returncode': result.returncode}
                # Detailed observations remain outside the publication payload.
                (out / (app + '.onboard.stdout')).write_text(result.stdout)
                (out / (app + '.onboard.stderr')).write_text(result.stderr)
            except subprocess.TimeoutExpired:
                row = {'app': app, 'passed': False, 'error_type': 'TimeoutExpired'}
            save(out / (app + '.onboard.json'), row)
            return row

        with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
            onboarding = list(pool.map(onboard, cards))
        module_path = work / 'pack_dpsk/contract/validate_skeleton.py'
        ms = importlib.util.spec_from_file_location('composed_app_validator', module_path)
        mod = importlib.util.module_from_spec(ms)
        ms.loader.exec_module(mod)
        mod.BASES = str(work / 'pack/base_specs')
        skeletons = [{'app': e['app'], 'errors': mod.check(json.loads((root / 'app_examples' / e['app'] / 'skeleton.json').read_text()), strict=True)} for e in entries]

    def replay(entry):
        app = entry['app']
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--root', str(root), '--replay-one', app],
                                env=env, capture_output=True, text=True, timeout=600)
        try:
            row = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            row = {'app': app, 'passed': False, 'error_type': 'WorkerDidNotProduceResult'}
        row['returncode'] = result.returncode
        save(out / (app + '.reference.json'), row)
        return row

    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        references = list(pool.map(replay, entries))
    after = {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    summary = {'at_unix': time.time(), 'model_requests': 0, 'CPU_only': True,
        'onboard_total': len(onboarding), 'onboard_passed': sum(x['passed'] for x in onboarding),
        'skeleton_total': len(skeletons), 'skeleton_passed': sum(not x['errors'] for x in skeletons),
        'reference_total': len(references), 'reference_passed': sum(x['passed'] for x in references),
        'inputs_unchanged': before == after, 'runtime_sha256': PIN,
        'onboarding': onboarding, 'skeleton_checks': skeletons,
        'scope': 'Local registration, original strict skeleton validation, and reference replay. Not complete upstream service behavior or teacher success rate.'}
    summary['passed'] = summary['onboard_passed'] == 193 and summary['skeleton_passed'] == summary['reference_passed'] == 180 and before == after
    save(out / 'FINISHED.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ['onboarding', 'skeleton_checks']}))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
