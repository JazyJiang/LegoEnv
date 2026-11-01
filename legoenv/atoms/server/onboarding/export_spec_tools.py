#!/usr/bin/env python3
"""export_spec_tools.py [--base-specs DIR] [--release-specs DIR ...] [--out FILE] - write spec_tools.json:
{app: {"tools", "write", "search", "entities": {name: [columns]}, "text_fields", "auth", "onboarded", "about"}}
for every compiled spec (compiler output repo_specs/, not onboarded) and every onboarded base spec (default legoenv/apps/base_specs).
validate_skeleton.py and the mining agent read it from legoenv/skeleton/, so they can run without the specs themselves."""
import argparse, json, glob, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--base-specs", default=os.path.join(HERE, "..", "..", "..", "apps", "base_specs"), help="onboarded <app>.spec.json files")
ap.add_argument("--release-specs", nargs="*", default=[], help="compiled, not yet onboarded <app>.spec.json files")
ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "..", "skeleton", "spec_tools.json"))
A = ap.parse_args()
out = {}
files = [f for d in A.release_specs for f in sorted(glob.glob(os.path.join(d, "*.spec.json")))] + sorted(glob.glob(os.path.join(A.base_specs, "*.spec.json")))
for f in files:
    app = os.path.basename(f)[:-10]
    try: s = json.load(open(f))
    except Exception: continue
    tools = s.get("tools", []); fam = lambda t: str(t.get("family", "") or "")
    ents = {e["name"]: [c["name"] for c in e.get("columns", [])] for e in s.get("entities", [])}
    text = [f"{e['name']}.{c['name']}" for e in s.get("entities", []) for c in e.get("columns", []) if str(c.get("type", "")).lower() in ("text", "string") and re.search(r"desc|note|body|comment|content|remark|memo|message|summary|detail", c["name"], re.I)]
    out[app] = {"tools": [t["tool"] for t in tools], "write": [t["tool"] for t in tools if fam(t).startswith(("crud.insert", "crud.update", "crud.delete", "action", "update.", "crud.upsert"))],
                "search": [t["tool"] for t in tools if fam(t).startswith("search")], "entities": ents, "text_fields": text[:40], "auth": bool(s.get("auth")),
                "onboarded": os.path.exists(os.path.join(A.base_specs, f"{app}.spec.json")), "about": str(s.get("about") or s.get("summary") or "")[:300]}
json.dump(out, open(A.out, "w"), ensure_ascii=False)
print("specs", len(out), "onboarded", sum(v["onboarded"] for v in out.values()), "->", A.out)
