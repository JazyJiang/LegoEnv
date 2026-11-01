#!/usr/bin/env python3
"""make_targets.py --screen TSV --datasets DIR --out DIR [--vocab FILE] [--seen TSV] - from the spec screen (screen_specs.py) and the
tagged dataset cards (profile_datasets.py + tag_datasets.py) write
  DIR/onboard_targets.tsv : specs to onboard (relevance >= 2, not onboarded yet), under-covered domains first;
  DIR/dataset_gaps.tsv    : per domain, usable business datasets and which archetypes lack data (< 3 datasets).
--seen: optional two-column TSV (app, count) of apps already used in existing packs; those rank first."""
import argparse, csv, json, glob, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--screen", required=True, help="spec_screen.tsv")
ap.add_argument("--datasets", required=True, help="directory of dataset cards")
ap.add_argument("--out", required=True)
ap.add_argument("--vocab", default=os.path.join(HERE, "..", "..", "..", "skeleton", "vocab.json"))
ap.add_argument("--seen")
A = ap.parse_args(); os.makedirs(A.out, exist_ok=True)
V = json.load(open(A.vocab))
rows = list(csv.DictReader(open(A.screen), delimiter="\t"))
SEEN = {r[0]: int(r[1]) for r in csv.reader(open(A.seen), delimiter="\t") if len(r) >= 2 and r[1].isdigit()} if A.seen else {}
have = collections.Counter(d for r in rows if r["onboarded"] == "1" for d in r["domains"].split(",") if d)
cand = [r for r in rows if r["relevance"].isdigit() and int(r["relevance"]) >= 2 and r["onboarded"] == "0"]
def score(r):
    ds = [d for d in r["domains"].split(",") if d]; rare = min((have[d] for d in ds), default=99)
    return (0 if r["app"] in SEEN else 1, rare, -int(r["relevance"]), {"low": 0, "medium": 1, "high": 2}.get(r["risk"], 1), int(r["tools"]))
cand.sort(key=score)
with open(os.path.join(A.out, "onboard_targets.tsv"), "w") as fo:
    fo.write("rank\tapp\tseen_in_packs\trelevance\tcategory\tdomains\tcarriers\tkinds\ttools\trisk\n")
    for i, r in enumerate(cand, 1): fo.write(f"{i}\t{r['app']}\t{SEEN.get(r['app'], 0)}\t{r['relevance']}\t{r['category']}\t{r['domains']}\t{r['carriers']}\t{r['kinds']}\t{r['tools']}\t{r['risk']}\n")
dom_specs = collections.Counter(d for r in cand for d in r["domains"].split(",") if d)
cards = [json.load(open(f)) for f in glob.glob(os.path.join(A.datasets, "*.json"))]
biz = [c for c in cards if c.get("business_usable")]
dom_ds = collections.defaultdict(list)
for c in biz:
    for d in c.get("domains", []): dom_ds[d].append(c)
with open(os.path.join(A.out, "dataset_gaps.tsv"), "w") as fo:
    fo.write("domain\tusable_datasets\tspecs_onboarded\tspecs_candidate\tarchetypes_missing\texample_slugs\n")
    for d in V["domains"] + sorted((set(dom_ds) | set(dom_specs)) - set(V["domains"])):
        ds = dom_ds.get(d, []); arch = collections.Counter(a for c in ds for a in c["archetypes_supported"])
        missing = [a for a in V["archetypes"] if arch[a] < 3]
        fo.write(f"{d}\t{len(ds)}\t{have[d]}\t{dom_specs[d]}\t{','.join(missing)}\t{','.join(c['slug'] for c in ds[:4])}\n")
print("onboard targets", len(cand), "| top 15:", ", ".join(f"{r['app']}({r['domains'].split(',')[0]})" for r in cand[:15]))
print("business datasets", len(biz), "| per domain:", {d: len(v) for d, v in sorted(dom_ds.items(), key=lambda x: -len(x[1]))})
