#!/usr/bin/env python3
"""skel4_recombine.py MINED_DIR OUT_DIR N_PER_DOMAIN — recombine mined skeletons within a domain into new skeleton_spec v2 files.
Pools per domain: rule atoms, deliverable atoms per app, app combos. New skeleton = an anchor's apps + either one deliverable atom swapped
for a pool atom allowed on those apps, or the rule atom(s) swapped for pool rules whose carrier the apps host, or one atom added.
Dedupe on (apps, kinds, archetypes, rule_shape). Counts jittered ±30%. Originals are copied into OUT_DIR too."""
import json, glob, os, sys, random, collections, hashlib, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); V = json.load(open(f"{HERE}/vocab.json"))
src, out, N = sys.argv[1], sys.argv[2], int(sys.argv[3]); os.makedirs(out, exist_ok=True); rng = random.Random(924)
S = [json.load(open(f)) for f in sorted(glob.glob(f"{src}/*/mine_*.json"))]
by = collections.defaultdict(list)
for s in S: by[s["domain"]].append(s)
def key(s): return (tuple(sorted(s["apps"])), tuple(sorted(a["kind"] for a in s["deliverable_atoms"])), tuple(sorted(r["archetype"] for r in s["rule_atoms"])), hashlib.md5(" ".join(r["rule_shape"] for r in s["rule_atoms"]).encode()).hexdigest()[:8])
CARRIER_HOSTS = {app for hosts in V["carriers"].values() for app in hosts}
for item in S:
    if not set(item["apps"]).intersection(CARRIER_HOSTS):
        raise ValueError("App combination has no declared policy-carrier host: " + item["skeleton_id"])
seen = {key(s) for s in S}
for s in S: shutil.copy(f"{src}/{s['domain']}/{s['skeleton_id']}.json", out)
CT = {"policy_sheet": "policy worksheet", "policy_mail": "policy e-mail in the inbox", "notes_field": "policy text in a notes/description field", "policy_doc": "policy document in the wiki", "card_description": "policy text in a board card's description", "pinned_channel_message": "pinned policy message in the team channel"}
def jitter(x, lo, hi): return max(lo, min(hi, round(x * rng.uniform(0.7, 1.3)))) if x > 0 else 0
def chain(s):
    per = [a for a in s["deliverable_atoms"] if a["pos"] > 1 or a["kind"] not in ("send_email", "post_channel", "send_dm", "llm_call")]; summ = [a for a in s["deliverable_atoms"] if a not in per]
    c = [f"read the {CT[s['rule_atoms'][0]['carrier']]} to learn the business rule", "scan the records the rule applies to and select the ones it covers; at least 2 look-alike records must be skipped"]
    if per: c.append("for each selected record: " + ", ".join(f"{a['kind']} in {a['app']}" for a in per))
    if summ: c.append("finish with: " + ", ".join(f"{a['kind']} in {a['app']}" for a in summ))
    return c
cp = lambda o: json.loads(json.dumps(o))
for dom, L in by.items():
    rules = [r for s in L for r in s["rule_atoms"]]; atoms = [a for s in L for a in s["deliverable_atoms"]]; made = tries = 0
    while made < N and tries < N * 60:
        tries += 1; anchor = rng.choice(L); s = cp(anchor); apps = list(s["apps"]); kinds = {x["kind"] for x in s["deliverable_atoms"]}; m = rng.random()
        if m < 0.5:
            i = rng.randrange(len(s["deliverable_atoms"])); cand = [a for a in atoms if a["app"] in apps and a["kind"] not in kinds]
            if not cand: continue
            s["deliverable_atoms"][i] = cp(rng.choice(cand))
        elif m < 0.85:
            cand = [r for r in rules if any(h in apps for h in V["carriers"][r["carrier"]]) and r["rule_shape"] not in {x["rule_shape"] for x in s["rule_atoms"]}]
            if not cand: continue
            s["rule_atoms"] = [cp(rng.choice(cand))] + ([] if rng.random() < 0.7 else [cp(rng.choice(cand))])
        else:
            if len(s["deliverable_atoms"]) >= 3: continue
            cand = [a for a in atoms if a["app"] in apps and a["kind"] not in kinds]
            if not cand: continue
            s["deliverable_atoms"].append(cp(rng.choice(cand)))
        for a in s["deliverable_atoms"]: a["pos"] = jitter(a["pos"], 1, 12); a["neg"] = jitter(a["neg"], 0, 10)
        k = key(s)
        if k in seen: continue
        seen.add(k); made += 1
        s["skeleton_id"] = f"rc_{dom}_{made:04d}"; s["source"] = f"recombined:{anchor['skeleton_id']}"; s["n_intents"] = len(s["deliverable_atoms"])
        s["predicate_budget"] = max(8, sum(a["pos"] + a["neg"] for a in s["deliverable_atoms"])); s["n_distractors_min"] = rng.choice([2, 2, 3, 3, 4]); s["chain"] = chain(s)
        json.dump(s, open(f"{out}/{s['skeleton_id']}.json", "w"), ensure_ascii=False, indent=1)
    print(dom, "recombined", made, "tries", tries)
print("total files", len(glob.glob(f"{out}/*.json")))
