#!/usr/bin/env python3
"""cards_to_vocab.py [--cards DIR] [--vocab FILE] [--out FILE] - merge every PASSED capability card (<cards>/<app>/capability_card.json,
default legoenv/apps/adapters) into legoenv/skeleton/vocab.json: apps, app_role, kind_tools[kind][app] (regex built from the card's tool list),
carriers[carrier] hosts, plus vocab.onboarded_by_card. Idempotent; prints what changed. --out defaults to --vocab (in place).
Run after each onboard_check.py PASS, then re-run export_spec_tools.py."""
import argparse, json, glob, re, os
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--cards", default=os.path.join(HERE, "..", "..", "..", "apps", "adapters"))
ap.add_argument("--vocab", default=os.path.join(HERE, "..", "..", "..", "skeleton", "vocab.json"))
ap.add_argument("--out")
A = ap.parse_args()
V = json.load(open(A.vocab)); changed = []
for f in sorted(glob.glob(os.path.join(A.cards, "*", "capability_card.json"))):
    c = json.load(open(f)); app = c["app"]
    if not c.get("smoke", {}).get("passed"): print("skip (smoke not passed):", app); continue
    if app not in V["apps"]: V["apps"].append(app); changed.append(f"app {app}")
    if V["app_role"].get(app) != c["role"]: V["app_role"][app] = c["role"]; changed.append(f"role {app}")
    for kind, tl in c["kinds"].items():
        k = kind[6:] if kind.startswith("other:") else kind
        V["kind_tools"].setdefault(k, {}); rx = "^(?:" + "|".join(re.escape(t) for t in tl) + ")$"
        if V["kind_tools"][k].get(app) != rx: V["kind_tools"][k][app] = rx; changed.append(f"kind {k}@{app}")
    for car in c["carriers"]:
        V["carriers"].setdefault(car, [])
        if app not in V["carriers"][car]: V["carriers"][car].append(app); changed.append(f"carrier {car}@{app}")
    V.setdefault("onboarded_by_card", {})[app] = {"domains": c.get("domains", []), "check_kinds": c.get("check_kinds", []), "date": c["smoke"].get("date")}
json.dump(V, open(A.out or A.vocab, "w"), ensure_ascii=False, indent=1); print("changes:", len(changed)); [print(" ", x) for x in changed[:40]]
