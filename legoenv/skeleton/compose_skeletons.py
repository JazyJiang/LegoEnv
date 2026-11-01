#!/usr/bin/env python3
"""compose_skeletons.py --intents FILE --rules FILE --out DIR --per-domain N [--seed 924] [--domains d1,d2] [--vocab PATH]
Compose new skeleton_spec v2 files directly from the published atom pools (intent atoms + rule atoms), without mined skeletons.
Per domain: the app set comes from the intent atoms tagged with that domain. One skeleton = 1-2 rule atoms tagged with the domain
(any rule when the domain has fewer than 5) + 1-3 intent atoms with distinct kinds on 1-4 distinct apps, where every atom's kind is
defined for its app in vocab.kind_tools and every rule's carrier has a host app in apps (a host app from the domain's app set is
added when no intent app hosts it). Dedupe on (apps, kinds, archetypes, rule_shape hash) as in skel4_recombine.py; counts are
jittered +-30% and clamped to the schema ranges. Output files are named cp_<domain>_NNNN.json."""
import argparse, collections, hashlib, json, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
# kept identical to skel4_recombine.py
CT = {"policy_sheet": "policy worksheet", "policy_mail": "policy e-mail in the inbox", "notes_field": "policy text in a notes/description field", "policy_doc": "policy document in the wiki", "card_description": "policy text in a board card's description", "pinned_channel_message": "pinned policy message in the team channel"}
SUMMARY_KINDS = ("send_email", "post_channel", "send_dm", "llm_call")
NEWSPECS = {"vikunja", "mantisbt", "outline", "listmonk", "cloudreve", "directus", "mastodon", "chatwoot", "misskey"}


def key(s):
    return (tuple(sorted(s["apps"])), tuple(sorted(a["kind"] for a in s["deliverable_atoms"])), tuple(sorted(r["archetype"] for r in s["rule_atoms"])),
            hashlib.md5(" ".join(r["rule_shape"] for r in s["rule_atoms"]).encode()).hexdigest()[:8])


def jitter(rng, x, lo, hi):
    return max(lo, min(hi, round(x * rng.uniform(0.7, 1.3)))) if x > 0 else lo


def chain(s):
    per = [a for a in s["deliverable_atoms"] if a["pos"] > 1 or a["kind"] not in SUMMARY_KINDS]; summ = [a for a in s["deliverable_atoms"] if a not in per]
    carriers = list(dict.fromkeys(CT[r["carrier"]] for r in s["rule_atoms"]))
    c = [f"read the {' and the '.join(carriers)} to learn the business rule", "scan the records the rule applies to and select the ones it covers; at least 2 look-alike records must be skipped"]
    if per: c.append("for each selected record: " + ", ".join(f"{a['kind']} in {a['app']}" for a in per))
    if summ: c.append("finish with: " + ", ".join(f"{a['kind']} in {a['app']}" for a in summ))
    return c, bool(per), bool(summ)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--intents", required=True); ap.add_argument("--rules", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--per-domain", type=int, required=True); ap.add_argument("--seed", type=int, default=924)
    ap.add_argument("--domains", default="", help="comma-separated; default: every vocab domain"); ap.add_argument("--vocab", default=f"{HERE}/vocab.json")
    A = ap.parse_args()
    V = json.load(open(A.vocab)); rng = random.Random(A.seed); os.makedirs(A.out, exist_ok=True)
    load = lambda p: [json.loads(l) for l in open(p) if l.strip()]
    # constraint 1 and vocabulary membership are enforced on the pools up front
    I = [a for a in load(A.intents) if a["app"] in V["kind_tools"].get(a["kind"], {}) and all(c in V["check_kinds"] for c in a["check_kinds"])]
    R = [r for r in load(A.rules) if r["archetype"] in V["archetypes"] and r["carrier"] in V["carriers"] and (r.get("rule_shape") or "").strip()]
    domains = [d for d in A.domains.split(",") if d] or V["domains"]
    seen, total, blocked = set(), 0, []
    for dom in domains:
        ints = [a for a in I if dom in a["domains"]]; dapps = sorted({a["app"] for a in ints})
        rules = [r for r in R if dom in r["domains"]]
        if len(rules) < 5: rules = R
        hosted = [r for r in rules if set(V["carriers"][r["carrier"]]) & set(dapps)]
        if not ints or not hosted:
            blocked.append(f"{dom}: " + ("no intent atoms" if not ints else "no rule carrier hosted by the domain's apps")); print(dom, "composed 0 tries 0"); continue
        by_app = collections.defaultdict(list)
        for a in ints: by_app[a["app"]].append(a)
        made = tries = 0
        while made < A.per_domain and tries < A.per_domain * 60:
            tries += 1
            rs = [rng.choice(hosted)]
            if rng.random() >= 0.7:
                r2 = rng.choice(hosted)
                if r2["rule_shape"] != rs[0]["rule_shape"]: rs.append(r2)
            n = rng.choice([1, 2, 2, 2, 3, 3, 3]); atoms, apps = [], []
            # half the time anchor the first intent on an app that hosts the first rule's carrier, so the rule and the writes share an app
            host_apps = [h for h in V["carriers"][rs[0]["carrier"]] if h in by_app]
            if host_apps and rng.random() < 0.5: atoms.append(rng.choice(by_app[rng.choice(host_apps)]))
            for _ in range(n * 4):
                if len(atoms) >= n: break
                a = rng.choice(ints)
                if a["kind"] in {x["kind"] for x in atoms}: continue
                if a["app"] not in {x["app"] for x in atoms} and len({x["app"] for x in atoms}) >= 4: continue
                atoms.append(a)
            if not atoms: continue
            apps = list(dict.fromkeys(a["app"] for a in atoms)); ok = True
            for r in rs:
                hosts = V["carriers"][r["carrier"]]
                if any(h in apps for h in hosts): continue
                cand = [h for h in hosts if h in dapps]
                if not cand or len(apps) >= 4: ok = False; break
                apps.append(rng.choice(cand))
            if not ok: continue
            da = [{"app": a["app"], "kind": a["kind"], "pos": jitter(rng, a["pos"], 1, 12), "neg": jitter(rng, a["neg"], 0, 10), "check_kinds": list(a["check_kinds"])} for a in atoms]
            ra = [{"archetype": r["archetype"], "carrier": r["carrier"], "has_exception": bool(r.get("has_exception")), "rule_shape": r["rule_shape"]} for r in rs]
            s = {"skeleton_id": "", "domain": dom, "source": "composed:" + ",".join(a["id"] for a in atoms) + "+" + ",".join(r["id"] for r in rs),
                 "apps": apps, "standin_apps": {}, "needs_newspecs": bool(set(apps) & NEWSPECS), "deliverable_atoms": da, "rule_atoms": ra}
            k = key(s)
            if k in seen: continue
            seen.add(k); made += 1
            s["skeleton_id"] = f"cp_{dom}_{made:04d}"; s["n_intents"] = len(da); s["n_distractors_min"] = rng.choice([2, 2, 3, 3, 4])
            s["predicate_budget"] = min(60, max(8, sum(a["pos"] + a["neg"] for a in da)))
            s["chain"], per, summ = chain(s)
            s["delivery_shape"] = "per-record actions + one summary message" if per and summ else ("per-record actions" if per else "one summary message")
            s["dataset_hint"] = []
            json.dump(s, open(f"{A.out}/{s['skeleton_id']}.json", "w"), ensure_ascii=False, indent=1)
        total += made; print(dom, "composed", made, "tries", tries)
    print("total composed", total, "->", A.out)
    for b in blocked: print("blocked", b)


if __name__ == "__main__":
    main()
