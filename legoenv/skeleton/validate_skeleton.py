#!/usr/bin/env python3
"""validate_skeleton.py FILE_OR_DIR... [--strict] — check skeleton_spec v2 files against the schema, the vocabulary and the real specs:
  schema keys/types · apps exist (base_specs/<app>.spec.json) · each atom's app is in apps and its kind has a write tool in that spec ·
  check_kinds in vocab · archetypes/carriers in vocab · carrier has a host app in apps · counts consistent · dataset_hint slugs on disk.
Exit 0 when every file passes; prints one line per file (OK / FAIL: reasons)."""
import json, os, re, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); V = json.load(open(f"{HERE}/vocab.json")); S = json.load(open(f"{HERE}/skeleton_schema.json"))
BASES = "/builder/smoke/pack/base_specs"; DP = ("/builder/datapool", "/builder/datapool_ext")
_tools = {}; _IDX = json.load(open(f"{HERE}/spec_tools.json")) if os.path.exists(f"{HERE}/spec_tools.json") else {}
def tools(app):
    if app not in _tools:
        p = f"{BASES}/{app}.spec.json"
        _tools[app] = [t["tool"] for t in json.load(open(p))["tools"]] if os.path.exists(p) else (_IDX[app]["tools"] if app in _IDX and _IDX[app].get("onboarded") else None)
    return _tools[app]
def check(s, strict=False):
    e = []
    for k in S["required"]:
        if k not in s: e.append(f"missing {k}")
    if e: return e
    for k, prop in S["properties"].items():
        if k in s and prop.get("type") and not isinstance(s[k], {"string": str, "array": list, "object": dict, "integer": int, "boolean": bool}[prop["type"]]): e.append(f"{k}: wrong type")
    if not re.fullmatch(S["properties"]["skeleton_id"]["pattern"], s["skeleton_id"]): e.append("skeleton_id pattern")
    if s["domain"] not in V["domains"]: e.append(f"domain {s['domain']} not in vocab")
    if not 1 <= len(s["apps"]) <= 6: e.append(f"apps: 1-6 (got {len(s['apps'])})")
    if len(set(s["apps"])) != len(s["apps"]): e.append("apps: duplicates")
    for a in s["apps"]:
        if a in V["apps"]:
            if tools(a) is None: e.append(f"app {a}: no spec on disk")
        elif a in _IDX: pass          # release spec, not onboarded yet: allowed; atoms must name tools explicitly (checked below)
        else: e.append(f"app {a}: not in vocab and not a release spec (see spec_tools.json)")
    for i, a in enumerate(s["deliverable_atoms"]):
        for k in ("app", "kind", "pos", "neg", "check_kinds"):
            if k not in a: e.append(f"atom{i}: missing {k}")
        if e: continue
        if a["app"] not in s["apps"]: e.append(f"atom{i}: app {a['app']} not in apps")
        kt = V["kind_tools"].get(a["kind"])
        if a["app"] not in V["apps"]:   # not-yet-onboarded release spec: the atom must name real write tools of that spec
            spec_tools = set(_IDX[a["app"]]["tools"]) if a["app"] in _IDX else set(); wr = set(_IDX[a["app"]]["write"]) if a["app"] in _IDX else set()
            if not a.get("tools"): e.append(f"atom{i}: app {a['app']} is not onboarded — list the write tools that realize kind {a['kind']} in 'tools'")
            elif not all(t in spec_tools for t in a["tools"]): e.append(f"atom{i}: tools not in {a['app']} spec: {[t for t in a['tools'] if t not in spec_tools][:3]}")
            elif not any(t in wr for t in a["tools"]): e.append(f"atom{i}: none of {a['tools'][:3]} is a write tool in {a['app']}")
            if not (kt or a["kind"].startswith("other:")): e.append(f"atom{i}: kind {a['kind']} not in vocab (use other:<name> for a new kind)")
        elif not kt: e.append(f"atom{i}: kind {a['kind']} not in vocab")
        elif a["app"] not in kt: e.append(f"atom{i}: kind {a['kind']} not defined for {a['app']} (allowed: {','.join(kt)})")
        elif tools(a["app"]) is not None and not any(re.search(kt[a["app"]], t) for t in tools(a["app"])): e.append(f"atom{i}: no tool matching /{kt[a['app']]}/ in {a['app']} spec")
        if not (1 <= a["pos"] <= 30) or not (0 <= a["neg"] <= 30): e.append(f"atom{i}: pos/neg range")
        for c in a["check_kinds"]:
            if c not in V["check_kinds"]: e.append(f"atom{i}: check_kind {c} not in vocab")
    for i, r in enumerate(s["rule_atoms"]):
        if r.get("archetype") not in V["archetypes"]: e.append(f"rule{i}: archetype {r.get('archetype')} not in vocab")
        hosts = V["carriers"].get(r.get("carrier"))
        if hosts is None: e.append(f"rule{i}: carrier {r.get('carrier')} not in vocab")
        elif not any(h in s["apps"] for h in hosts):
            cf = r.get("carrier_field", "")   # non-onboarded host: name Entity.field of a release spec in apps
            ent, _, fld = cf.partition(".")
            ok = any(app in _IDX and ent in _IDX[app]["entities"] and fld in _IDX[app]["entities"][ent] for app in s["apps"] if app not in V["apps"])
            if not ok: e.append(f"rule{i}: carrier {r['carrier']} needs one of {hosts} in apps, or carrier_field 'Entity.field' of a non-onboarded app in apps")
        if strict and not (r.get("rule_shape") or "").strip(): e.append(f"rule{i}: rule_shape empty")
        if re.search(r"\b\d{2,}\b", r.get("rule_shape") or ""): e.append(f"rule{i}: rule_shape contains a literal number")
    if s["n_intents"] > len(s["deliverable_atoms"]): e.append("n_intents > atoms")
    if s["n_distractors_min"] < 2: e.append("n_distractors_min < 2")
    if s["predicate_budget"] < 8: e.append("predicate_budget < 8")
    if len(s["chain"]) < 2: e.append("chain too short")
    for slug in s.get("dataset_hint", []):
        if any(os.path.isdir(d) for d in DP) and not any(os.path.isdir(f"{d}/{slug}") for d in DP): e.append(f"dataset_hint {slug} not on disk")
    return e
if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; strict = "--strict" in sys.argv
    files = [f for a in args for f in (sorted(glob.glob(f"{a}/*.json")) if os.path.isdir(a) else [a])]
    bad = 0
    for f in files:
        try: errs = check(json.load(open(f)), strict)
        except Exception as ex: errs = [f"unreadable: {ex}"]
        if errs: bad += 1
        if errs or len(files) <= 30: print(("FAIL " if errs else "OK   ") + os.path.basename(f) + ("" if not errs else ": " + "; ".join(errs[:4])))
    print(f"{len(files) - bad}/{len(files)} valid"); sys.exit(1 if bad else 0)
