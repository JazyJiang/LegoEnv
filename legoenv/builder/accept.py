#!/usr/bin/env python3.12
"""accept.py <packdir> <taskdir> : runtime acceptance of a sample pack after the gold run.
  runnable   : Env(fork.spec.json) builds; the gold witness replays (ok steps) with every step ok
  judgeable  : contract on seed -> expect_seed; on replayed final and on the dumped final -> expect_final
  resettable : env.reset() restores the seed state byte-for-byte
  non-vacuous: every positive postcondition flips to False when some write step (or every write of one tool) is dropped
               (witnessed_by); positives with an upper bound (count lte/lt) that survive the drop are classified "bounded";
               every negative flips to False in a constructed counter-example state (falsified_by: insert / mutate / delete rows,
               see falsify()). Unfalsified negatives are counted as vacuous_negatives.
  --strict   : also fail when vacuous_negatives > 0 (required for new packs)
  distractor : per group, the four guards of distractor_apply (u_check / fairness / verifier_recheck / invariants) with the IR judge
Writes <packdir>/accept/report.json ($ACC_REPORT overrides the name) and prints a summary. Exit 1 if any hard check fails.
Usage: accept.py <packdir> <taskdir> [--strict]
"""
import json, sys, os, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "LegoEnv/runtime")); import runtime
sys.path.insert(0, str(Path(__file__).resolve().parent)); from argnorm import normalize
READ_PFX = ("list", "search", "get", "find", "show", "read", "view", "browse", "query", "fetch", "sign_in", "auth_login", "identity", "table_fetchall", "calendar_get")

def judge(pred, state, now): return bool(runtime.eval_node(pred, runtime._StateView(state, now), None, None, site="postcondition"))
def base_tool(t): return t.split("__", 1)[1] if "__" in t else t
def is_write(spec, tool):
    t = next((x for x in spec["tools"] if x["tool"] == tool), None)
    fam = (t or {}).get("family", "") or ""
    if fam.startswith(("crud.insert", "crud.update", "crud.delete", "update.", "crud.upsert", "action.")): return True
    if fam.startswith(("search", "crud.fetch", "guard.", "auth.")): return False
    return not base_tool(tool).startswith(READ_PFX)

def _created_id(obs):
    """(entity, id) the original run got back from a write step, parsed from the witness obs text."""
    try: o = json.loads(obs) if isinstance(obs, str) else (obs or {})
    except Exception: return None
    r = o.get("result") if isinstance(o, dict) else None
    if isinstance(r, dict):
        i = r.get("id", r.get("_id"))
        if isinstance(i, int): return (o.get("entity"), i)
    return None

def replay(spec, steps, tolerant=True):
    """replay witness steps on a (possibly different) world. Id-tolerant: ids the original run received from write steps
    (parsed from each step's `obs`) are remapped to the ids this replay receives, so a witness recorded on world W still
    replays on W' (rows added/removed by distractor groups shift auto-ids)."""
    env = runtime.Env(spec); log = []; idmaps = {}   # per system prefix: ids are only unique within one system's entity space
    for i, w in enumerate(steps):
        args = normalize(spec, w["tool"], w.get("args") or {})
        pfx = w["tool"].split("__")[0] if "__" in w["tool"] else ""
        idmap = idmaps.get(pfx, {})
        if tolerant and idmap:
            def remap(v):
                if isinstance(v, dict): return {k: remap(x) for k, x in v.items()}
                if isinstance(v, list): return [remap(x) for x in v]
                if isinstance(v, int) and not isinstance(v, bool) and v in idmap: return idmap[v]
                return v
            args = {k: (remap(v) if ("id" in k.lower() or isinstance(v, (dict, list))) else v) for k, v in args.items()}
        r = env.call(w["tool"], args)
        log.append({"i": i, "tool": w["tool"], "ok": bool(r.get("ok")), "err": None if r.get("ok") else str(r.get("error"))[:200]})
        got = _created_id(json.dumps(r, default=str)); had = _created_id(w.get("obs")) if w.get("obs") else None
        if got and had and got[1] != had[1]: idmaps.setdefault(pfx, {})[had[1]] = got[1]
    return env, log

def contract_eval(contract, state, now):
    out = {}
    for p in contract["postconditions"]:
        try: out[p["id"]] = judge(p["pred"], state, now)
        except Exception as e: out[p["id"]] = f"ERR {e}"
    return out

def build_rows_from_pred(pred, seed, _k=[0]):
    """for a count(select) negative: construct rows (possibly across entities) that make the select non-empty.
    Returns list of (entity, row) to insert, or None. Sub-selects (`in`/`eq` on a select) are satisfied by an existing seed value
    or, failing that, by constructing the inner row recursively."""
    inserts = []
    def new_id():
        _k[0] += 1; return 10**6 + _k[0]
    def build(sel):
        row = {"id": new_id()}
        def put(col, v):
            if "." in col:
                h, _, t = col.partition("."); row.setdefault(h, {})[t] = v
            else: row[col] = v
        def walk(n):
            k = n.get("node")
            if k == "and": return all(walk(a) for a in n["args"])
            if k == "or": return any(walk(a) for a in n["args"])      # satisfy the first constructible branch
            if k != "field": return False
            op, v = n["op"], n.get("value")
            if isinstance(v, dict) and v.get("node") == "select":
                col = v.get("get", {}).get("col") or "id"; w = v.get("where")
                vals = [r.get(col) for r in seed.get(v["entity"], []) if (w is None or judge_row(w, r))]
                if op in ("in", "eq"):
                    if vals: put(n["col"], vals[0]); return True
                    inner = build(v)
                    if inner is None: return False
                    put(n["col"], inner.get(col)); return True
                if op == "nin": put(n["col"], 999999); return True
                return False
            if op in ("eq", "icontains", "contains", "startswith", "endswith"):
                if n["col"] in ("attendees", "to", "rcpt_to", "mailbox_ids", "cc"):
                    put(n["col"], v if isinstance(v, list) else ([{"email": v}] if n["col"] in ("to", "cc") else [v]))
                else:
                    put(n["col"], v if op == "eq" else (str(v) + "x" if op == "startswith" else "x" + str(v) + "x"))
                return True
            if op == "in" and isinstance(v, list) and v: put(n["col"], v[0]); return True
            if op == "nin": put(n["col"], 999999); return True
            return False
        ok = walk(sel.get("where") or {"node": "and", "args": []})
        if not ok: return None
        inserts.append((sel["entity"], row)); return row
    return inserts if build(pred["select"]) is not None else None

def build_row_from_pred(pred, seed):
    ins = build_rows_from_pred(pred, seed)
    return ins

def judge_row(where, r):
    import grammar as G
    try: return G.eval_pred(where, r, lambda v, row: G.UNKNOWN) is True
    except Exception: return False


# ─────────────────────────── counter-example search (non-vacuity of negatives) ───────────────────────────
# A negative is non-vacuous when SOME plausible state makes it False. The search mutates the replayed final state:
#   insert  — new rows (bare, or cloned from an existing row) built to satisfy the select's where (DNF branch by branch;
#             sub-selects are satisfied by existing values or by building the inner row too)
#   mutate  — change fields of an existing row until it matches (covers "record unchanged" invariants and <dynamic> sheet edits)
#   delete  — drop matching rows (covers count >= n / "record still exists" invariants)
# Top-level shapes: count, and (break one arm), or (break every arm), not (make the inner true); literals: every FIELD_OP,
# NOT(substring) inside where, several substring ops on one column, JSON-path columns (<dynamic>.col).
import re, itertools
import grammar as G
LISTCOLS_OBJ = {"to", "cc", "bcc", "from", "reply_to"}
LISTCOLS = {"attendees", "rcpt_to", "mailbox_ids", "participants", "recipients", "labels", "tags"} | LISTCOLS_OBJ
FAIL = object(); _fid = [0]
SCHEMA = {}   # entity -> set of declared columns; set by falsify(); counter-examples may only touch declared entities/columns
def _fresh_id():
    _fid[0] += 1; return 10**6 + _fid[0]
def _sv(st, now): return runtime._StateView(st, now)
def _rows(sel, st, now):
    r = runtime._select_rows({k: v for k, v in sel.items() if k != "get"}, _sv(st, now), None, None)
    return [] if r is G.UNKNOWN else r
def _getcol(row, col): return G._get_col(row, col)
def _putcol(row, col, v):
    if "." in col:
        h, _, t = col.partition("."); d = row.get(h)
        if isinstance(d, str):
            try: d = json.loads(d)
            except Exception: d = {}
        if not isinstance(d, dict): d = {}
        d = dict(d); d[t] = v; row[h] = d
    else: row[col] = v
def _is_num(v): return isinstance(v, (int, float)) and not isinstance(v, bool)
def _alt(v):
    if _is_num(v): return v + 1
    if v is None: return "x"
    if isinstance(v, str):
        try: float(v); return str(int(float(v)) + 1) if float(v).is_integer() else str(float(v) + 1)
        except ValueError: return v + "_x"
    return "x"
def _alt_not_in(lst):
    lst = [x for x in (lst or []) if x is not None]
    if lst and all(_is_num(x) for x in lst): return max(lst) + 1
    return "zz_other"
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
def _shift(v, d):
    """value one step above (d=+1) / below (d=-1) v, same type/format where possible"""
    if _is_num(v): return v + d
    if isinstance(v, str):
        if _ISO.match(v):
            from datetime import datetime as _dt, timedelta as _td
            fmt = "%Y-%m-%dT%H:%M:%S" if len(v) >= 19 and v[10] == "T" else ("%Y-%m-%d %H:%M:%S" if len(v) >= 19 else "%Y-%m-%d")
            try: return (_dt.strptime(v[:19] if len(v) >= 19 else v[:10], fmt) + _td(days=d)).strftime(fmt) + (v[19:] if len(v) > 19 else "")
            except ValueError: pass
        try: f = float(v); return str(int(f) + d) if f.is_integer() else str(f + d)
        except ValueError: pass
        return v + "~" if d > 0 else (v[:-1] if v else v)
    return v
def _satisfies(op, a, b):
    try:
        r = G.FIELD_OPS[op][1](a) if G.FIELD_OPS[op][0] == 1 else G.FIELD_OPS[op][1](a, b)
        return r is True
    except Exception: return False

def _dnf(n, limit=48):
    """where → list of conjunctions of literals: field nodes, or {"neg": field} for NOT(substring op)"""
    if not n: return [[]]
    k = n.get("node")
    if k == "and":
        out = [[]]
        for a in n["args"]: out = [x + y for x in out for y in _dnf(a, limit)][:limit]
        return out
    if k == "or": return [c for a in n["args"] for c in _dnf(a, limit)][:limit]
    if k == "not":
        inner = n["args"][0]
        if inner.get("node") == "field":
            m = G.negate(inner)
            return [[m]] if m.get("node") == "field" else [[{"neg": inner}]]
        if inner.get("node") in ("and", "or", "not"): return _dnf(G.negate(inner), limit)
        return [[{"unsupported": inner}]]
    if k == "field": return [[n]]
    return [[{"unsupported": n}]]

def _resolve(v, row, st, now):
    if isinstance(v, dict) and v.get("node") != "select":
        r = runtime._resolver(_sv(st, now), None, None)(v, row); return FAIL if r is G.UNKNOWN else r
    return v

def _materialize(conj, base, st, now, ins, depth=0, ent=None):
    """row satisfying every literal of conj, starting from base (a fresh or existing row); inner rows needed by sub-selects go to ins"""
    if SCHEMA and ent not in SCHEMA: return None
    row = copy.deepcopy(base); cons = {}
    for lit in conj:
        if "unsupported" in lit: return None
        f = lit.get("neg") or lit
        if SCHEMA and f["col"].split(".")[0] not in SCHEMA.get(ent, ()): return None     # undeclared column: no tool can ever write it
        cons.setdefault(f["col"], []).append((("not_" + f["op"]) if "neg" in lit else f["op"], f.get("value")))
    for col, cl in cons.items():
        cur = _getcol(row, col); vals = []
        for op, v in cl:
            if isinstance(v, dict) and v.get("node") == "select":
                got = runtime._select_rows(v, _sv(st, now), None, None)
                got = [] if got is G.UNKNOWN else got
                if not got and op in ("in", "eq") and depth < 3:     # build the inner row the sub-select needs
                    gcol = (v.get("get") or {}).get("col") or "id"
                    for c2 in _dnf(v.get("where"))[:6]:
                        inner = _materialize(c2, {"id": _fresh_id()}, st, now, ins, depth + 1, v["entity"])
                        if inner is not None:
                            if gcol not in inner: inner[gcol] = _fresh_id()
                            ins.append((v["entity"], inner)); got = [inner.get(gcol)]; break
                v = got
            else:
                v = _resolve(v, row, st, now)
                if v is FAIL: return None
            vals.append((op, v))
        ops = {op for op, _ in vals}
        cand = cur
        eqs = [v for op, v in vals if op == "eq"]; ins_ = [v for op, v in vals if op == "in"]
        if eqs: cand = eqs[0][0] if isinstance(eqs[0], list) and eqs[0] and not isinstance(cur, list) else eqs[0]
        elif ins_:
            if not ins_[0]: return None
            cand = cur if cur in ins_[0] else ins_[0][0]
        lows = [(v, op == "gt") for op, v in vals if op in ("gt", "gte") and v is not None]
        highs = [(v, op == "lt") for op, v in vals if op in ("lt", "lte") and v is not None]
        if lows or highs:
            ok_now = cand is not None and all(_satisfies("gt" if s else "gte", cand, v) for v, s in lows) and all(_satisfies("lt" if s else "lte", cand, v) for v, s in highs)
            if not ok_now:
                if lows:
                    v, s = max(lows, key=lambda x: (_num_key(x[0]), x[1])); cand = _shift(v, +1) if s else v
                else:
                    v, s = min(highs, key=lambda x: (_num_key(x[0]), not x[1])); cand = _shift(v, -1) if s else v
        for op, v in vals:
            if op == "ne" and (cand is None or cand == v): cand = _alt(v)
            if op == "nin" and (cand is None or (isinstance(v, list) and cand in v)): cand = _alt_not_in(v if isinstance(v, list) else [])
        if "is_null" in ops: cand = None
        if "is_not_null" in ops and cand is None: cand = 1 if col.endswith("id") else "x"
        subs = [v for op, v in vals if op in ("contains", "icontains")]; pre = [v for op, v in vals if op == "startswith"]; suf = [v for op, v in vals if op == "endswith"]
        if subs or pre or suf:
            if isinstance(cand, list) or (cand is None and col.split(".")[-1] in LISTCOLS):
                lst = list(cand or []); objs = (lst and isinstance(lst[0], dict)) or col.split(".")[-1] in LISTCOLS_OBJ
                for frag in pre + subs + suf: lst.append({"email": str(frag), "name": str(frag)} if objs else frag)
                cand = lst
            else:
                text = "" if cand in (None, "") or isinstance(cand, (dict, list)) else str(cand)
                if pre and text.startswith(str(pre[0])): text = text[len(str(pre[0])):]
                cand = " ".join([str(x) for x in pre] + ([text] if text else []) + [str(x) for x in subs] + [str(x) for x in suf])
                if not pre and not text and subs: cand = "x " + cand
        for op, v in vals:
            if op.startswith("not_") and v is not None:
                if isinstance(cand, list): cand = [x for x in cand if str(v).lower() not in str(x).lower()]
                elif cand is not None:
                    s = str(cand)
                    if op == "not_startswith" and s.startswith(str(v)): s = "zz" + s
                    elif op == "not_endswith" and s.endswith(str(v)): s = s + "zz"
                    elif op in ("not_icontains", "not_contains"): s = re.sub(re.escape(str(v)), "zz", s, flags=re.I if op == "not_icontains" else 0)
                    cand = s
                if cand is None: cand = "zz"
        _putcol(row, col, cand)
    return row

def _num_key(v):
    n = G._num(v); return n if n is not None else float("-inf")

def _row_candidates(sel, st, now, want_new):
    """(entity, row_or_None, mutated_row, inner_inserts) — mutated_row is a new row (row_or_None None) or an edit of an existing row"""
    ent = sel["entity"]; existing = st.get(ent, []) or []
    conjs = _dnf(sel.get("where"))
    def score(r, conj): return sum(1 for lit in conj if "col" in lit and _satisfies(lit["op"], _getcol(r, lit["col"]), lit.get("value")) if not isinstance(lit.get("value"), dict))
    for conj in conjs:
        ranked = sorted(existing, key=lambda r: -score(r, conj))
        order = [("mutate", r) for r in ranked[:4]] + ([("clone", existing[0])] if existing else []) + [("bare", None)] + [("mutate", r) for r in ranked[4:25]]
        for how, r in order:
            ins = []
            if how == "mutate": new = _materialize(conj, r, st, now, ins, 0, ent)
            elif how == "clone":
                b = copy.deepcopy(r); b["id"] = _fresh_id()
                if "_id" in b: b["_id"] = f"ro_x{_fid[0]}"
                new = _materialize(conj, b, st, now, ins, 0, ent)
            else: new = _materialize(conj, {"id": _fresh_id()}, st, now, ins, 0, ent)
            if new is not None: yield how, r, new, ins

def _apply(st, ent, orig, new, ins):
    st2 = copy.deepcopy(st)
    for e, row in ins: st2.setdefault(e, []).append(row)
    if orig is None: st2.setdefault(ent, []).append(new)
    else:
        lst = st2.get(ent, []); k = next((i for i, r in enumerate(st.get(ent, [])) if r is orig), None)
        if k is None: return None
        lst[k] = new
    return st2

def _count_states(p, st, now, want, budget):
    """states in which count node p evaluates to `want`"""
    sel = p["select"]; ent = sel["entity"]; cur = len(_rows(sel, st, now)); op, n = p["op"], p["n"]
    targets = sorted({c for c in (0, cur - 1, cur + 1, n - 1, n, n + 1, cur + 2) if c >= 0 and _satisfies(op, c, n) == want}, key=lambda c: abs(c - cur))
    for c in targets:
        if budget[0] <= 0: return
        if c < cur:                                   # delete matching rows
            st2 = copy.deepcopy(st); hit = [id(r) for r in _rows(sel, st2, now)]; drop = set(hit[: cur - c])
            st2[ent] = [r for r in st2.get(ent, []) if id(r) not in drop]; budget[0] -= 1
            yield st2, {"strategy": "delete", "entity": ent, "n": cur - c}
        elif c > cur:                                 # add / edit rows until the count is reached
            for how, orig, new, ins in _row_candidates(sel, st, now, True):
                if budget[0] <= 0: return
                st2 = _apply(st, ent, orig, new, ins); budget[0] -= 1
                if st2 is None: continue
                extra = c - cur - 1; k = 0
                while extra > 0 and k < 60:          # more rows needed: clone the constructed row with fresh ids
                    r2 = copy.deepcopy(new); r2["id"] = _fresh_id()
                    if "_id" in r2: r2["_id"] = f"ro_x{_fid[0]}"
                    st2[ent].append(r2); extra -= 1; k += 1
                yield st2, {"strategy": how if orig is None else "mutate", "entity": ent, "row": new, "inner": [{"entity": e, "row": r} for e, r in ins]}

def _states(p, st, now, want, budget):
    k = p.get("node")
    if k == "count": yield from _count_states(p, st, now, want, budget)
    elif k == "not": yield from _states(p["args"][0], st, now, not want, budget)
    elif k in ("and", "or"):
        breaks_one = (k == "and") != want      # and→False / or→True: one arm suffices
        if breaks_one:
            for a in p["args"]: yield from _states(a, st, now, want, budget)
        else:                                   # every arm must take the value: chain arm by arm on a small beam
            beam = [(st, [])]
            for a in p["args"]:
                nxt = []
                for s, why in beam:
                    try:
                        if judge_tv(a, s, now) == want: nxt.append((s, why)); continue
                    except Exception: pass
                    for s2, w2 in itertools.islice(_states(a, s, now, want, budget), 6):
                        try:
                            if judge_tv(a, s2, now) == want: nxt.append((s2, why + [w2]))
                        except Exception: pass
                        if len(nxt) >= 3: break
                beam = nxt[:3]
                if not beam: return
            for s, why in beam: yield s, {"strategy": "all_arms", "steps": why}

def judge_tv(pred, state, now):
    return bool(runtime.eval_node(pred, runtime._StateView(state, now), None, None, site="postcondition"))

def falsify(pred, st, now, budget=400, schema=None):
    """→ description of a state making pred False, or None. schema: {entity: {columns}} of the world spec"""
    global SCHEMA
    SCHEMA = schema or {}
    b = [budget]
    try:
        for s2, why in _states(pred, st, now, False, b):
            try:
                if judge_tv(pred, s2, now) is False: return why
            except Exception: continue
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    return None

def has_upper_bound(p):
    k = p.get("node")
    if k == "count": return p["op"] in ("lt", "lte")
    if k in ("and", "or", "not"): return any(has_upper_bound(a) for a in p["args"])
    return False

def shape(p):
    """compact operator shape of a predicate, for reports"""
    k = p.get("node")
    if k == "count": return f"count[{p['op']} {p['n']}]({shape(p['select'])})"
    if k == "select": return f"{p['entity'].split('__')[-1]}:{shape(p.get('where') or {})}"
    if k in ("and", "or"): return f"{k}(" + ",".join(shape(a) for a in p["args"]) + ")"
    if k == "not": return "not(" + shape(p["args"][0]) + ")"
    if k == "field":
        v = p.get("value"); return f"{p['col']} {p['op']}" + (f" ({shape(v)})" if isinstance(v, dict) and v.get("node") == "select" else "")
    return k or "?"

def main(packdir, taskdir, strict=False):
    world = json.load(open(f"{packdir}/06_distractor/fork.spec.json")); baseline = json.load(open(f"{packdir}/03_spec/template.spec.json"))
    contract = json.load(open(f"{packdir}/05_verifier/contract.json")); groups = json.load(open(f"{packdir}/06_distractor/distractor_patch.json"))
    now = world.get("now")
    wit = [json.loads(l) for l in open(f"{taskdir}/run/witness_env.jsonl")]
    steps = [{"tool": w["tool"], "args": w["args"], "obs": w.get("obs")} for w in wit if w.get("ok")]
    dumped = json.load(open(f"{taskdir}/run/state_env.json"))["state"]
    R = {"tid": contract.get("proposal_id"), "n_witness": len(wit), "n_ok_steps": len(steps)}
    # runnable
    env, log = replay(world, steps)
    R["runnable"] = {"all_ok": all(l["ok"] for l in log), "failed": [l for l in log if not l["ok"]]}
    # judgeable
    seed = runtime.Env(world).state
    ev_seed, ev_final, ev_dump = contract_eval(contract, seed, now), contract_eval(contract, env.state, now), contract_eval(contract, dumped, now)
    exp = {p["id"]: (p.get("expect_seed", False), p.get("expect_final", True)) for p in contract["postconditions"]}
    R["judgeable"] = {"seed_bad": [k for k, v in ev_seed.items() if v != exp[k][0]], "final_bad": [k for k, v in ev_final.items() if v != exp[k][1]],
                      "dumped_bad": [k for k, v in ev_dump.items() if v != exp[k][1]], "final_pass": all(v is True for v in ev_final.values()),
                      "per_pred": {k: {"seed": ev_seed[k], "final": ev_final[k], "dumped": ev_dump[k]} for k in ev_seed}}
    final_state = copy.deepcopy(env.state)
    schema = {e["name"]: {c["name"] for c in e.get("columns", [])} for e in world.get("entities", [])}
    for ent, rows in final_state.items():      # columns that rows actually carry (flat sheet cells are data, not declared columns)
        if ent in schema:
            for r in rows or []: schema[ent].update(r.keys())   # counter-examples are built on the replayed final state
    # resettable
    env.reset(); R["resettable"] = json.dumps(env.state, sort_keys=True, default=str) == json.dumps(seed, sort_keys=True, default=str)
    # non-vacuous
    writes = [i for i, s in enumerate(steps) if is_write(world, s["tool"])]
    nv = {}
    tools_written = list(dict.fromkeys(steps[i]["tool"] for i in writes))
    for p in contract["postconditions"]:
        pid = p["id"]
        if p.get("expect_seed", False) is False:   # positive: some dropped write (or every write of one tool) must flip it
            hit = None
            for i in writes:
                e2, _ = replay(world, steps[:i] + steps[i + 1:])
                try:
                    if judge(p["pred"], e2.state, now) is False: hit = {"dropped_step": i, "tool": steps[i]["tool"]}; break
                except Exception: pass
            if hit is None:
                for tool in tools_written:
                    e2, _ = replay(world, [s_ for s_ in steps if s_["tool"] != tool])
                    try:
                        if judge(p["pred"], e2.state, now) is False: hit = {"dropped_tool": tool, "n": sum(1 for s_ in steps if s_["tool"] == tool)}; break
                    except Exception: pass
            nv[pid] = {"kind": "positive", "witnessed_by": hit, "bounded": bool(hit is None and has_upper_bound(p["pred"]))}
        else:                                       # negative: some counter-example state must flip it
            res = {"kind": "negative", "falsified_by": None, "shape": shape(p["pred"])}
            why = falsify(p["pred"], final_state, now, schema=schema)
            if isinstance(why, dict) and "error" in why: res["error"] = why["error"]
            elif why: res["falsified_by"] = why
            nv[pid] = res
    R["non_vacuous"] = nv
    R["non_vacuous_summary"] = {"positives_witnessed": sum(1 for v in nv.values() if v["kind"] == "positive" and v["witnessed_by"]),
                                "positives": sum(1 for v in nv.values() if v["kind"] == "positive"),
                                "negatives_falsified": sum(1 for v in nv.values() if v["kind"] == "negative" and v["falsified_by"]),
                                "negatives": sum(1 for v in nv.values() if v["kind"] == "negative"),
                                "positives_bounded": sum(1 for v in nv.values() if v["kind"] == "positive" and v.get("bounded"))}
    R["vacuous_negatives"] = sum(1 for v in nv.values() if v["kind"] == "negative" and not v["falsified_by"])
    R["strict"] = bool(strict)
    # distractor guards (mirror of distractor_apply.guards, IR judge)
    piv = contract["pivot_rows"]; D = []
    positives = [p for p in contract["postconditions"] if not p.get("expect_seed", False)]
    for g in groups:
        pv = piv[g["pivot_index"]]; key = pv["key"]
        trial = copy.deepcopy(baseline)
        for blk in g["group"]: trial["seed_state"].setdefault(blk["entity"], []).extend(copy.deepcopy(blk["rows"]))
        tst = runtime.Env(trial).state
        # invariants: the gold witness was recorded on the full fork world, so ids of agent-created rows depend on every group's rows.
        # Leave-one-out world (fork minus this group) keeps those ids stable: the witness must still replay and the contract still hold.
        loo = copy.deepcopy(world)
        for blk in g["group"]:
            ids = {(r.get("id"), r.get("_id")) for r in blk["rows"]}
            loo["seed_state"][blk["entity"]] = [r for r in loo["seed_state"].get(blk["entity"], []) if (r.get("id"), r.get("_id")) not in ids]
        hits = [r for r in tst.get(pv["entity"], []) if all(str(r.get(k)) == str(v) for k, v in key.items())]
        u_check = len(hits) == 1
        tgt = next((b for b in g["group"] if b.get("role") == "target"), g["group"][0])
        fairness = bool(tgt["rows"]) and all(any(str(r.get(k)) != str(v) for k, v in key.items()) for r in tgt["rows"])
        try: vr = all(judge(p["pred"], tst, now) is False for p in positives)
        except Exception as e: vr = f"ERR {e}"
        e3, log3 = replay(loo, steps)
        try: inv = all(judge(p["pred"], e3.state, now) is True for p in contract["postconditions"])
        except Exception as e: inv = f"ERR {e}"
        D.append({"group_id": g.get("group_id"), "pivot_index": g["pivot_index"], "u_check": u_check, "fairness": fairness, "verifier_recheck_seed_false": vr,
                  "invariants_replay_true(leave_one_out)": inv, "replay_all_ok": all(l["ok"] for l in log3), "passed": bool(u_check and fairness and vr is True and inv is True)})
    R["distractor"] = D
    hard = R["runnable"]["all_ok"] and not R["judgeable"]["seed_bad"] and not R["judgeable"]["final_bad"] and R["resettable"] and all(d["passed"] for d in D)
    R["passed_nonstrict"] = bool(hard)
    if strict: hard = hard and R["vacuous_negatives"] == 0
    R["passed"] = bool(hard)
    os.makedirs(f"{packdir}/accept", exist_ok=True); json.dump(R, open(f"{packdir}/accept/" + os.environ.get("ACC_REPORT", "report.json"), "w"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: R[k] for k in ("n_witness", "n_ok_steps", "resettable", "non_vacuous_summary", "vacuous_negatives", "strict", "passed")}, ensure_ascii=False))
    print("runnable:", R["runnable"]["all_ok"], R["runnable"]["failed"][:3])
    print("judgeable seed_bad:", R["judgeable"]["seed_bad"], "final_bad:", R["judgeable"]["final_bad"], "dumped_bad:", R["judgeable"]["dumped_bad"])
    for d in D: print("distractor", d)
    for k, v in nv.items():
        if v["kind"] == "positive" and not v["witnessed_by"]: print("BOUNDED" if v.get("bounded") else "VACUOUS?", k, v)
        if v["kind"] == "negative" and not v["falsified_by"]: print("VACUOUS?", k, v)
    if strict and R["vacuous_negatives"]: print(f"STRICT FAIL: {R['vacuous_negatives']} negative(s) could not be falsified — rewrite them (see SKILL lessons)")
    sys.exit(0 if hard else 1)

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(a[0], a[1], strict="--strict" in sys.argv[1:])
