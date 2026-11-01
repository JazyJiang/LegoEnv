#!/usr/bin/env python3
"""Render the full canonical builder prompt locally; never start an agent."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject_metadata(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {'check_kind_from_ab', 'benchmark_task', 'benchmark_task_id', 'assertion_name'}:
                raise ValueError('Evaluation-derived metadata is not accepted as builder input.')
            reject_metadata(value)
    elif isinstance(obj, list):
        for value in obj:
            reject_metadata(value)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--skeleton', type=Path, required=True)
    p.add_argument('--contract', type=Path, required=True,
                   help='Reviewed local contract directory with the original validator and tool index.')
    p.add_argument('--base-specs', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    skeleton_path = a.skeleton.resolve(strict=True)
    contract = a.contract.resolve(strict=True)
    skeleton = json.loads(skeleton_path.read_text())
    reject_metadata(skeleton)
    if not re.fullmatch(r'[A-Za-z0-9_\-]+', skeleton['skeleton_id']):
        raise ValueError('Invalid skeleton identity for local rendering.')
    # Load only the explicit contract. Override filesystem locations, leaving
    # every original strict predicate intact. No arbitrary source tree is searched.
    source = contract / 'validate_skeleton.py'
    spec = importlib.util.spec_from_file_location('explicit_original_contract', source)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    validator.BASES = str(a.base_specs.resolve(strict=True)) if a.base_specs else str(contract / 'not_bundled_base_specs')
    validator.DP = ()
    errors = validator.check(skeleton, strict=True)
    if errors:
        raise ValueError('Original strict validator rejected skeleton: ' + '; '.join(errors))
    template = ROOT / 'prompts/BUILDER.md'
    text = template.read_text()
    if '{SK}' not in text or '{SKELETON_JSON}' not in text:
        raise ValueError('The canonical template is missing an expected placeholder.')
    # Substitute the identifier before inserting JSON, so business text inside
    # the JSON can never be altered by a second replacement pass.
    rendered = text.replace('{SK}', skeleton['skeleton_id']).replace(
        '{SKELETON_JSON}', json.dumps(skeleton, ensure_ascii=False, indent=2))
    out = a.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    receipt = out.with_name(out.name + '.receipt.json')
    if out.exists() or receipt.exists():
        raise FileExistsError('Choose a new output path; an existing prompt or receipt will not be overwritten.')
    with out.open('x') as f:
        f.write(rendered)
    result = {'schema_version': 1, 'skeleton_id': skeleton['skeleton_id'],
              'skeleton_sha256': sha(skeleton_path), 'template_sha256': sha(template),
              'original_validator_sha256': sha(source), 'rendered_prompt_sha256': sha(out),
              'original_strict_passed': True, 'strict_checks_modified': False,
              'path_globals_bound_to_explicit_contract': True,
              'model_requests': 0, 'agent_started': False, 'package_built': False,
              'datasets_selected_or_injected': False,
              'execution_dependencies': 'Supply the reviewed builder stack, approved examples, skills, datasets and endpoint separately.'}
    with receipt.open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
