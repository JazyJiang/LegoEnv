#!/usr/bin/env python3
"""tag_datasets.py --cards DIR [endpoint flags] - a model tags every usable dataset card with business domains and with what
business records it looks like. Fills card["domains"], card["records_like"], card["business_usable"], card["tag_why"] in place.
Endpoint flags: --base-url (or OPENAI_BASE_URL), --model (or OPENAI_MODEL), --api-key-env, --extra-body, --max-tokens."""
import argparse, json, glob, os, re, sys, concurrent.futures as cf, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from llm_client import add_endpoint_args, chat
ap = add_endpoint_args(argparse.ArgumentParser(description=__doc__.splitlines()[0]))
ap.add_argument("--cards", required=True, help="directory of dataset cards written by profile_datasets.py")
ap.add_argument("--workers", type=int, default=8)
A = ap.parse_args()
P = """A real-world tabular dataset will be used to seed business records in a training environment. Classify it.
slug: {slug}
source: {src}
tables (name, sampled columns with types and examples):
{tables}
Answer ONE JSON object: {{"domains": [<1-3 of: sales, marketing, operations, support, finance, hr, legal, procurement, logistics, healthcare, education, real_estate, manufacturing, nonprofit, hospitality, government, it_ops, research, media, other>],
 "records_like": "<what business records these rows resemble, e.g. 'customer accounts with tier and spend', 'support tickets with priority and SLA', 'invoices with due dates'>",
 "business_usable": true|false,   // false when rows are not business records (news text, images, chat logs, benchmarks)
 "why": "<one sentence>"}}"""
def one(f):
    c = json.load(open(f))
    if not c.get("usable"): return None
    tb = "\n".join(f"- {t['file']} ({t['rows_sampled']} rows): " + ", ".join(f"{col['name']}[{col['type']}:{'|'.join(str(e) for e in col.get('examples', [])[:2])}]" for col in t["columns"][:14]) for t in c["tables"][:3])
    err = None
    for _ in range(3):
        try:
            out = chat(A, P.format(slug=c["slug"], src=c.get("source"), tables=tb[:3500]))
            j = json.loads(re.search(r"\{.*\}", out, re.S).group(0)); c["domains"] = j.get("domains", []); c["records_like"] = j.get("records_like", ""); c["business_usable"] = bool(j.get("business_usable")); c["tag_why"] = j.get("why", "")
            json.dump(c, open(f, "w"), ensure_ascii=False, indent=1); return c
        except Exception as e: err = e
    return {"slug": c["slug"], "error": type(err).__name__}
res = [r for r in cf.ThreadPoolExecutor(A.workers).map(one, sorted(glob.glob(f"{A.cards}/*.json"))) if r]
ok = [r for r in res if "error" not in r]; print("tagged", len(ok), "errors", len(res) - len(ok), "business_usable", sum(1 for r in ok if r.get("business_usable")))
print("domains:", collections.Counter(d for r in ok if r.get("business_usable") for d in r.get("domains", [])).most_common(20))
