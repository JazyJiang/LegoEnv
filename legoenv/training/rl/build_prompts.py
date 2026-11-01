import argparse
import collections
import concurrent.futures as cf
import hashlib
import json
import os
import random
import re
import shutil
import sys
import time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rl_env import paths
DEF_JUDGED = []
DEF_RESULTS = ''
VALID_FINISH = {'stop', 'max_turns', 'length'}
PACK_SET_ALIAS = {'dk_b1r': 'dk_b1'}
DOMAINS = ['real_estate', 'it_ops', 'manufacturing', 'logistics', 'healthcare', 'education', 'procurement', 'legal', 'government', 'hospitality', 'nonprofit', 'operations', 'marketing', 'support', 'finance', 'sales', 'hr']

def norm_pack_set(ps):
    return PACK_SET_ALIAS.get(ps, ps)

def domain_of(skeleton_id):
    s = str(skeleton_id or '')
    m = re.match('^(rc\\d*|c_mine|mine)_(.*)$', s)
    rest = m.group(2) if m else s
    for d in DOMAINS:
        if rest == d or rest.startswith(d + '_'):
            return d
    return 'unknown'

def family_of(skeleton_id):
    m = re.match('^(rc\\d*|c_mine|mine)_', str(skeleton_id or ''))
    return m.group(1) if m else 'unknown'

def aggregate(rows):
    packs = {}
    seen = set()
    for r in rows:
        ps = norm_pack_set(r.get('pack_set', ''))
        key = (ps, r['id'])
        dk = r.get('path') or (ps, r['id'], r.get('sample'))
        if dk in seen:
            continue
        seen.add(dk)
        p = packs.setdefault(key, {'n_rows': 0, 'n_valid': 0, 'passes': 0, 'finish': collections.Counter(), 'paths': []})
        p['n_rows'] += 1
        fin = r.get('finish')
        p['finish'][fin] += 1
        if r.get('path'):
            p['paths'].append(r['path'])
        if fin in VALID_FINISH:
            p['n_valid'] += 1
            p['passes'] += 1 if r.get('pass') is True else 0
    return packs

def select(packs, min_valid=4, min_pass=1, max_pass8=6, min_pass8=1):
    out = {}
    for key, p in packs.items():
        n, k = (p['n_valid'], p['passes'])
        if n < min_valid or k < min_pass or k * 8 > max_pass8 * n or (k * 8 < min_pass8 * n):
            continue
        out[key] = p
    return out

def pack_tsvs_for(rows):
    runs = set()
    for r in rows:
        pth = r.get('path') or ''
        if '/episodes/' in pth:
            runs.add(pth.split('/episodes/')[0])
    tsvs = []
    for run in sorted(runs):
        rc = os.path.join(run, 'run_config.json')
        if os.path.exists(rc):
            t = json.load(open(rc, encoding='utf-8')).get('packs')
            if t and os.path.exists(t):
                tsvs.append(t)
    return tsvs

def read_pack_tsvs(tsvs):
    m = {}
    for t in tsvs:
        for line in open(t, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line.strip() or line.startswith('#'):
                continue
            c = line.split('\t')
            tp, sp = (c[1], c[2])
            sysf = c[3] if len(c) > 3 and c[3] else '-'
            pid = os.path.basename(tp)[:-len('.task.json')]
            v = (tp, sp, sysf)
            if pid in m and m[pid] != v:
                raise SystemExit(f'pack {pid} has two different file sets in {tsvs}: {m[pid]} vs {v}')
            m[pid] = v
    return m

def files_from_episode(path):
    ep = json.load(open(path, encoding='utf-8'))
    return (ep['task_path'], ep['spec_path'], ep.get('system_path') or '-')

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()

def external_raw_paths(spec):
    out = []
    for key in ('seed_sources', 'joint_sources'):
        srcs = spec.get(key) or {}
        items = srcs.values() if isinstance(srcs, dict) else srcs
        for s in items:
            for x in s if isinstance(s, list) else [s]:
                if isinstance(x, dict) and x.get('raw_path'):
                    out.append(x['raw_path'])
    return out

def stage_pack(tid, files, stage_dir):
    d = os.path.join(stage_dir, tid)
    os.makedirs(d, exist_ok=True)
    out = {}
    for name, src in zip(('task.json', 'spec.json', 'system_append.txt'), files):
        if src == '-':
            out[name] = '-'
            continue
        dst = os.path.join(d, name)
        if not (os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src) and (sha256(dst) == sha256(src))):
            tmp = f'{dst}.tmp.{os.getpid()}'
            shutil.copyfile(src, tmp)
            os.replace(tmp, dst)
        out[name] = dst
    return (out['task.json'], out['spec.json'], out['system_append.txt'])

def _gold_one(rec):
    from rl_env.local_rollout import GoldPolicy, NoopPolicy, run_episode
    t0 = time.time()
    out = {'tid': rec['tid']}
    try:
        res, tr = run_episode(rec, GoldPolicy(), max_turns=400)
        out.update(gold_reward=res.get('reward'), gold_pass=res.get('pass'), gold_finish=res.get('finish'), gold_turns=res.get('turns'), gold_invalid=(res.get('stats') or {}).get('n_invalid_calls'), gold_infra=res.get('infra_error'))
        res, _ = run_episode(rec, NoopPolicy(), max_turns=2)
        out.update(noop_reward=res.get('reward'), noop_infra=res.get('infra_error'))
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'[:500]
    out['secs'] = round(time.time() - t0, 2)
    return out

def gold_check(records, workers):
    res = {}
    with cf.ProcessPoolExecutor(workers) as pool:
        futs = {pool.submit(_gold_one, r): r['tid'] for r in records}
        for i, f in enumerate(cf.as_completed(futs)):
            r = f.result()
            res[r['tid']] = r
            if (i + 1) % 100 == 0:
                print(f'  gold-check {i + 1}/{len(records)}', flush=True)
    return res

def pick_smoke(records, n=32, seed=0):
    rng = random.Random(seed)
    by_dom = collections.defaultdict(list)
    for r in records:
        by_dom[r['domain']].append(r)
    for v in by_dom.values():
        rng.shuffle(v)
        v.sort(key=lambda r: r['teacher_pass8'])
    doms = sorted(by_dom)
    rng.shuffle(doms)
    chosen, want = ([], 1)
    while len(chosen) < n and any(by_dom.values()):
        for d in doms:
            if len(chosen) >= n:
                break
            pool = by_dom[d]
            if not pool:
                continue
            j = min(range(len(pool)), key=lambda i: (abs(pool[i]['teacher_pass8'] - want), i))
            chosen.append(pool.pop(j))
            want = want % 6 + 1
    return sorted(chosen, key=lambda r: r['tid'])

def build(a):
    rows = []
    for f in a.judged:
        with open(f, encoding='utf-8') as fh:
            rows += [json.loads(l) for l in fh if l.strip()]
    packs = aggregate(rows)
    sel = select(packs, a.min_valid, a.min_pass, a.max_pass8, a.min_pass8)
    files = read_pack_tsvs(a.packs_tsv or pack_tsvs_for(rows))
    stats = collections.Counter()
    drop = collections.Counter()
    records = []
    for (ps, tid), p in sorted(sel.items()):
        f = files.get(tid)
        if f is None and p['paths']:
            try:
                f = files_from_episode(p['paths'][0])
            except Exception:
                f = None
        if f is None:
            drop['no_pack_files'] += 1
            continue
        if any((x != '-' and (not os.path.isfile(x)) for x in f)):
            drop['pack_file_missing'] += 1
            continue
        spec = json.load(open(f[1], encoding='utf-8'))
        ext = external_raw_paths(spec)
        if ext:
            drop['external_raw_sources'] += 1
            continue
        res_path = os.path.join(a.results, tid + '.json')
        skel = json.load(open(res_path, encoding='utf-8')).get('skeleton_id') if os.path.exists(res_path) else None
        if skel is None:
            stats['no_results_json'] += 1
        src = {'task': f[0], 'spec': f[1], 'system': f[2]}
        if a.stage_dir:
            f = stage_pack(tid, f, a.stage_dir)
            f = tuple((x if x == '-' else paths.resolve(x) for x in f))
        rec = {'tid': tid, 'pack_set': ps, 'domain': domain_of(skel), 'skeleton_id': skel, 'skeleton_family': family_of(skel), 'task_path': f[0], 'spec_path': f[1], 'system_path': f[2], 'teacher_pass': p['passes'], 'teacher_n': p['n_valid'], 'teacher_pass8': round(8 * p['passes'] / p['n_valid'], 2), 'teacher_rows': p['n_rows'], 'teacher_finish': dict(p['finish']), 'src': src, 'sha256': {'task': sha256(src['task']), 'spec': sha256(src['spec'])}}
        records.append(rec)
    os.makedirs(a.out_dir, exist_ok=True)
    gold = {}
    if a.gold_check:
        print(f'gold-check {len(records)} packs with {a.gold_check} workers ...', flush=True)
        gold = gold_check(records, a.gold_check)
        with open(os.path.join(a.out_dir, 'gold_check.jsonl'), 'w', encoding='utf-8') as fh:
            for tid in sorted(gold):
                fh.write(json.dumps(gold[tid], ensure_ascii=False) + '\n')
        for r in records:
            g = gold.get(r['tid'], {})
            r['gold_ok'] = bool(g.get('gold_reward') == 1.0 and g.get('noop_reward') == 0.0)

    def dump(path, recs):
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + '\n')
        os.replace(tmp, path)
    dump(os.path.join(a.out_dir, 'prompts.jsonl'), records)
    smoke_pool = [r for r in records if r.get('gold_ok', True)]
    smoke = pick_smoke(smoke_pool, a.smoke_n, a.seed)
    dump(os.path.join(a.out_dir, 'prompts_smoke.jsonl'), smoke)
    all_hist = collections.Counter((round(8 * p['passes'] / p['n_valid'], 2) for p in packs.values() if p['n_valid']))
    st = {'judged_files': a.judged, 'judged_rows': len(rows), 'packs_judged': len(packs), 'packs_16_attempts': sum((1 for p in packs.values() if p['n_rows'] > 8)), 'finish_counts': dict(sum((p['finish'] for p in packs.values()), collections.Counter())), 'packs_no_valid_attempt': sum((1 for p in packs.values() if not p['n_valid'])), 'selection': {'min_valid': a.min_valid, 'min_pass': a.min_pass, 'min_pass8': a.min_pass8, 'max_pass8': a.max_pass8}, 'excluded_by_rate': {'passes_0': sum((1 for p in packs.values() if p['n_valid'] and (not p['passes']))), 'below_min_rate_but_solved': sum((1 for p in packs.values() if p['passes'] and p['passes'] * 8 < a.min_pass8 * p['n_valid'])), 'above_max_rate': sum((1 for p in packs.values() if p['n_valid'] and p['passes'] * 8 > a.max_pass8 * p['n_valid'])), 'too_few_valid': sum((1 for p in packs.values() if p['n_valid'] < a.min_valid))}, 'packs_selected_by_passrate': len(sel), 'dropped': dict(drop), 'prompts': len(records), 'smoke': len(smoke), 'pass8_hist_all_packs': {str(k): all_hist[k] for k in sorted(all_hist)}, 'pass8_hist_selected': {str(k): v for k, v in sorted(collections.Counter((r['teacher_pass8'] for r in records)).items())}, 'raw_pass_hist_selected': {f'{k}/{n}': v for (k, n), v in sorted(collections.Counter(((r['teacher_pass'], r['teacher_n']) for r in records)).items())}, 'per_domain': dict(collections.Counter((r['domain'] for r in records)).most_common()), 'per_family': dict(collections.Counter((r['skeleton_family'] for r in records)).most_common()), 'per_pack_set': dict(collections.Counter((r['pack_set'] for r in records)).most_common()), 'smoke_per_domain': dict(collections.Counter((r['domain'] for r in smoke)).most_common()), 'smoke_pass8': {str(k): v for k, v in sorted(collections.Counter((r['teacher_pass8'] for r in smoke)).items())}, 'notes': dict(stats)}
    if gold:
        gs = collections.Counter()
        for g in gold.values():
            gs['gold_pass'] += g.get('gold_reward') == 1.0
            gs['gold_fail'] += g.get('gold_reward') == 0.0
            gs['gold_error_or_infra'] += bool(g.get('error') or g.get('gold_infra'))
            gs['noop_zero'] += g.get('noop_reward') == 0.0
            gs['noop_nonzero'] += g.get('noop_reward') not in (0.0, None)
        st['gold_check'] = dict(gs)
    with open(os.path.join(a.out_dir, 'prompts.stats.json'), 'w') as fh:
        json.dump(st, fh, indent=1)
    with open(os.path.join(a.out_dir, 'prompts.stats.txt'), 'w') as fh:
        for k, v in st.items():
            fh.write(f'{k}: {json.dumps(v, ensure_ascii=False)}\n')
    print(json.dumps({k: st[k] for k in ('judged_rows', 'packs_judged', 'excluded_by_rate', 'packs_selected_by_passrate', 'dropped', 'prompts', 'smoke', 'pass8_hist_selected', 'per_domain') + (('gold_check',) if gold else ())}, indent=1))
    return st

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--judged', nargs='+', required=True)
    ap.add_argument('--packs-tsv', nargs='*', default=None, help="pack list TSVs (pack_set, task, spec, system); default: from the collect runs' run_config.json")
    ap.add_argument('--results', default=DEF_RESULTS, help='dir with <tid>.json holding skeleton_id')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--stage-dir', default='', help='copy pack files here (shared disk); output paths become GPU paths')
    ap.add_argument('--min-valid', type=int, default=4)
    ap.add_argument('--min-pass', type=int, default=1)
    ap.add_argument('--min-pass8', type=float, default=1)
    ap.add_argument('--max-pass8', type=float, default=6)
    ap.add_argument('--smoke-n', type=int, default=32)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--gold-check', type=int, default=0, metavar='WORKERS', help="replay every selected pack's witness through the RL env (expect reward 1) and a no-op (expect 0)")
    a = ap.parse_args(argv)
    build(a)
if __name__ == '__main__':
    main()
