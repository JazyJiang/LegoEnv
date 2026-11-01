#!/usr/bin/env python3
"""profile_datasets.py --roots DIR [DIR ...] --out DIR - deterministic dataset cards for every dataset slug under the roots.

A root holds one directory per dataset slug: <root>/<slug>/raw/** (csv, tsv, jsonl, ndjson, json, parquet, *.csv.gz, *.jsonl.gz ...)
and an optional <root>/<slug>/meta.json ({"size_bytes", "n_rows_exact" | "n_rows_est", "source": {"id_or_url", "license"} | "<url>"}).
Card = which tables have >= 8 rows, per-column type (numeric / date / category / text / id / contact / entity), n_distinct, fill,
examples, which rule archetypes the table can support, size, licence. Samples at most 5000 rows per file and the 12 largest files.
Writes <out>/<slug>.json (schema: dataset_card_schema.json) and <out>/datasets.tsv. Parquet needs pyarrow; other formats need only the stdlib."""
import argparse, json, os, sys, glob, csv, re, collections, datetime as dt
ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--roots", nargs="+", required=True, help="directories that contain one sub-directory per dataset slug")
ap.add_argument("--out", required=True, help="output directory for the cards")
A = ap.parse_args()
csv.field_size_limit(1 << 28)
ROOTS = [os.path.abspath(r) for r in A.roots]; OUT = A.out
os.makedirs(OUT, exist_ok=True); MAXR = 5000
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$|^\d{1,2}/\d{1,2}/\d{2,4}$"); MAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I); NUM = re.compile(r"^-?\$?[\d,]+(\.\d+)?%?$")
def rows_of(path):
    ext = path.lower().rsplit(".", 1)[-1]
    try:
        if ext in ("csv", "tsv"):
            with open(path, newline="", encoding="utf-8", errors="replace") as f:
                r = csv.DictReader(f, delimiter="\t" if ext == "tsv" else ","); out = []
                for i, row in enumerate(r):
                    if i >= MAXR: break
                    out.append(row)
                return out
        if ext in ("jsonl", "ndjson"):
            out = []
            with open(path, encoding="utf-8", errors="replace") as f:
                for i, l in enumerate(f):
                    if i >= MAXR: break
                    try: j = json.loads(l)
                    except Exception: continue
                    if isinstance(j, dict): out.append(j)
            return out
        if ext == "json":
            j = json.load(open(path, encoding="utf-8", errors="replace"))
            if isinstance(j, dict):
                for v in j.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict): j = v; break
            return [x for x in j[:MAXR] if isinstance(x, dict)] if isinstance(j, list) else []
        if ext == "parquet":
            import pyarrow.parquet as pq
            b = next(pq.ParquetFile(path).iter_batches(batch_size=MAXR), None)
            return json.loads(json.dumps(b.to_pylist(), default=str)) if b is not None else []
        if ext == "gz" and path.lower().endswith((".csv.gz", ".jsonl.gz", ".tsv.gz", ".ndjson.gz")):
            import gzip, io
            inner = path[:-3]; iext = inner.lower().rsplit(".", 1)[-1]
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
                if iext in ("csv", "tsv"):
                    r = csv.DictReader(f, delimiter="\t" if iext == "tsv" else ","); out = []
                    for i, row in enumerate(r):
                        if i >= MAXR: break
                        out.append(row)
                    return out
                out = []
                for i, l in enumerate(f):
                    if i >= MAXR: break
                    try: j = json.loads(l)
                    except Exception: continue
                    if isinstance(j, dict): out.append(j)
                return out
    except Exception as e:
        return {"error": str(e)[:120]}
    return []
def col_profile(rows, c):
    vals = [r.get(c) for r in rows]; vals = [v for v in vals if v not in (None, "", [], {})]
    if not vals: return None
    s = [str(v) for v in vals[:2000]]; nd = len(set(s)); n = len(vals)
    num = sum(1 for v in vals[:2000] if isinstance(v, (int, float)) and not isinstance(v, bool) or (isinstance(v, str) and NUM.match(v.strip()))) / len(s)
    date = sum(1 for x in s if DATE.match(x.strip())) / len(s); mail = sum(1 for x in s if MAIL.match(x.strip())) / len(s)
    if mail > 0.8: t = "contact"
    elif date > 0.8: t = "date"
    elif num > 0.9: t = "id" if nd == len(s) and re.search(r"(^|_)(id|no|number|code)$", c, re.I) else "numeric"
    elif nd <= max(12, n * 0.05) and nd >= 2: t = "category"
    elif nd == len(s) and re.search(r"(^|_)(id|uuid|key|code|number)$", c, re.I): t = "id"
    elif re.search(r"name|title|subject|email|phone|company|customer|vendor|owner|assignee", c, re.I) and nd > 12: t = "entity"
    else: t = "text"
    ex = sorted(set(s), key=len)[:3]
    return {"name": c, "type": t, "n_distinct": nd, "fill": round(n / max(1, len(rows)), 2), "examples": [e[:40] for e in ex], **({"top": collections.Counter(s).most_common(6)} if t == "category" else {})}
def archetypes(cols):
    ty = collections.Counter(c["type"] for c in cols); a = []
    if ty["numeric"]: a += ["threshold_routing", "tiering", "budget_quota"]
    if ty["date"]: a += ["deadline_escalation"]
    if ty["category"]: a += ["exclusion", "compliance_flag", "approval_chain"]
    if ty["id"] or ty["entity"]: a += ["reconciliation"]
    return sorted(set(a))
idx = []
for root in ROOTS:
    for d in sorted(glob.glob(f"{root}/*/")):
        if os.path.abspath(d.rstrip("/")) == os.path.abspath(OUT): continue
        slug = os.path.basename(d.rstrip("/")); meta = {}
        try: meta = json.load(open(f"{d}/meta.json"))
        except Exception: pass
        raw = f"{d}/raw"; tables = []
        files = sorted([f for f in glob.glob(f"{raw}/**/*", recursive=True) if os.path.isfile(f) and f.lower().rsplit(".", 1)[-1] in ("csv", "tsv", "jsonl", "ndjson", "json", "parquet", "gz")], key=os.path.getsize, reverse=True)[:12]
        for f in files:
            rows = rows_of(f)
            if isinstance(rows, dict) or len(rows) < 8: continue
            cols = [p for c in list(rows[0].keys())[:60] if (p := col_profile(rows, c))]
            tables.append({"file": os.path.relpath(f, d), "rows_sampled": len(rows), "rows_est": (lambda v: v if isinstance(v, (int, dict)) or v is None else None)(meta.get("n_rows_exact") or meta.get("n_rows_est")), "columns": cols,
                           "numeric_cols": [c["name"] for c in cols if c["type"] == "numeric"], "date_cols": [c["name"] for c in cols if c["type"] == "date"],
                           "category_cols": [c["name"] for c in cols if c["type"] == "category"], "contact_cols": [c["name"] for c in cols if c["type"] in ("contact", "entity")],
                           "archetypes_supported": archetypes(cols)})
        src = meta.get("source") if isinstance(meta.get("source"), dict) else {"id_or_url": meta.get("source")}
        card = {"slug": slug, "path": d.rstrip("/"), "size_bytes": meta.get("size_bytes"), "license": src.get("license"), "source": src.get("id_or_url"),
                "domains": [], "tables": tables, "archetypes_supported": sorted({a for t in tables for a in t["archetypes_supported"]}), "usable": bool(tables), "profiled": dt.date.today().isoformat()}
        json.dump(card, open(f"{OUT}/{slug}.json", "w"), ensure_ascii=False, indent=1)
        idx.append(f"{slug}\t{int(card['usable'])}\t{len(tables)}\t{','.join(card['archetypes_supported'])}\t{sum(len(t['contact_cols']) for t in tables)}\t{card['size_bytes']}")
open(f"{OUT}/datasets.tsv", "w").write("slug\tusable\tn_tables\tarchetypes\tcontact_cols\tsize_bytes\n" + "\n".join(idx) + "\n")
print("cards", len(idx), "usable", sum(1 for l in idx if l.split("\t")[1] == "1"))
