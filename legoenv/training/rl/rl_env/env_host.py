"""Serve one LegoEnv world over stdin/stdout JSON lines (one request, one reply per line).

Run as a child process by `episode.EnvHost`: `python env_host.py <adapter_root>` where
<adapter_root> holds `collect_oai.py` (default `training/rl/envlib/`). Operations:
  reset      {pack_set, id, task_path, spec_path, system_path} -> {system, user, tools, ...}
             fresh world from the pack's seed state; system/user are the policy's first messages
  call       {name, arguments} -> {obs, info}     execute one tool call against the world
  verify     {} -> {pass, verifier_error, stats}  evaluate the task verifier on the current state
  gold_next  {i} -> the i-th reference (witness) step as a tool call, or {done: true}
  close      {} -> exit
Diagnostic prints go to stderr so stdout carries only protocol lines.
"""
import copy
import json
import os
import sys
import traceback
_PROTO = os.fdopen(os.dup(1), 'w', buffering=1, encoding='utf-8')
os.dup2(2, 1)
sys.stdout = sys.stderr
ENVLIB_ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.environ['ENVLIB_ROOT']
_TRAJGEN = ENVLIB_ROOT
sys.path.insert(0, _TRAJGEN)
import collect_oai as C
assert os.path.realpath(C.__file__).startswith(os.path.realpath(_TRAJGEN)), C.__file__
runtime = C.runtime
apistyle = C.apistyle

class Host:

    def __init__(self):
        self.task = self.spec = self.ex = None

    def reset(self, req):
        row = {'pack_set': req.get('pack_set', 'ours'), 'id': req['id'], 'task_path': req['task_path'], 'spec_path': req['spec_path'], 'system_path': req.get('system_path') or '-'}
        task, spec, system, user = C.load_pack(row)
        cat = apistyle.Catalog(spec)
        system, user, rw = C.load_pack_api(row, task, spec, cat)
        tools = copy.deepcopy(C.API_TOOLS)
        ex = C.ApiExec(spec, cat).set_witness(task.get('witness'))
        self.task, self.spec, self.cat, self.ex = (task, spec, cat, ex)
        info = {'n_all': len(spec.get('tools', [])), 'n_endpoints': len(cat.endpoints), 'rewrite': {k: v for k, v in rw.items() if isinstance(v, int)}, 'leftover_refs': cat.leftover_refs(system) + cat.leftover_refs(user[len(task.get('goal_nl') or ''):])}
        return {'system': system, 'user': user, 'tools': tools, 'tools_info': info, 'env_id': spec.get('env_id') or task.get('env_id'), 'n_witness': len(task.get('witness') or [])}

    def call(self, req):
        obs, info = self.ex.call(req['name'], req.get('arguments'))
        return {'obs': obs, 'info': info}

    def verify(self, req):
        vp, verr = (None, None)
        try:
            vp = bool(runtime.Verifier().eval(self.task['verifier'], self.ex.env.state))
        except Exception as e:
            verr = f'{type(e).__name__}: {str(e)[:300]}'
        ex = self.ex
        stats = {'n_tool_calls': ex.n_calls, 'n_invalid_calls': ex.n_invalid, 'n_failed_calls': ex.n_failed, 'n_clipped_obs': ex.n_clipped, 'n_coerced_json_args': ex.n_coerced, 'n_exec_exceptions': ex.n_exc}
        api = ex.stats()
        wt = {s['tool'] for s in self.task.get('witness', [])}
        stats.update(n_search=api['n_search'], n_fetch=api['n_fetch'], n_route_404=api['n_route_404'], witness_endpoints=len(wt), witness_endpoints_hit=len(wt & set(api['routed'])))
        return {'pass': vp, 'verifier_error': verr, 'stats': stats}

    def gold_next(self, req):
        wit = self.task.get('witness') or []
        i = int(req['i'])
        if i >= len(wit):
            return {'done': True}
        st = wit[i]
        args = st.get('args') or {}
        if C._has_dollar(args):
            runtime._SESSION.clear()
            sf = getattr(self.ex.env, 'session_for', None)
            runtime._SESSION.update(sf(st['tool']) if sf else self.ex.env.session)
            args = {k: runtime.resolve(v, self.ex.env.state) for k, v in args.items()}
        m, url, params, body = self.cat.request_for(st['tool'], args)
        call = {'method': m, 'url': url, 'params': None if params is None else json.dumps(params, ensure_ascii=False), 'body': None if body is None else json.dumps(body, ensure_ascii=False)}
        return {'done': False, 'name': 'api_fetch', 'arguments': call, 'tool': st['tool']}

def main():
    host = Host()
    ops = {'reset': host.reset, 'call': host.call, 'verify': host.verify, 'gold_next': host.gold_next}
    _PROTO.write(json.dumps({'ok': True, 'ready': True, 'pid': os.getpid()}) + '\n')
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            op = req.get('op')
            if op == 'close':
                _PROTO.write(json.dumps({'ok': True}) + '\n')
                break
            if op != 'reset' and host.ex is None:
                raise RuntimeError(f'op {op!r} before reset')
            rep = {'ok': True, **ops[op](req)}
        except Exception as e:
            rep = {'ok': False, 'error': f'{type(e).__name__}: {str(e)[:500]}', 'trace': traceback.format_exc()[-3000:]}
        _PROTO.write(json.dumps(rep, ensure_ascii=False, default=str) + '\n')
if __name__ == '__main__':
    main()
