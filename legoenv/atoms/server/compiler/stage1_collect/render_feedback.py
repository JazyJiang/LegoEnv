#!/usr/bin/env python3
"""Render one feedback-round prompt from a work order written by ``contract_check.py``.

    python3 render_feedback.py <work_order.json> <edge_topup.md template> <collect/<repo>.json>

Prints the filled template (``legoenv/atoms/server/prompts/edge_topup.md``) on
stdout; ``feedback_round.sh`` sends it as a new user turn into the agent's original
session. Violations are grouped by priority tier (tiers are assigned in code by
``contract_check.rule_tier``, not left for the model to infer), each rule shows its
full occurrence count next to at most 8 examples, and ops that appear under several
tiers are listed once so the agent re-reads that code only once.
"""
import json
import os
import sys

MAX_EXAMPLES = 8

TITLE = {1: "the file itself is unreadable",
         2: "unfixed = this repo yields zero tools",
         3: "the only source code anyone downstream sees",
         4: "self-contradictory (visible without reading code)",
         5: "no position taken (unknown / null / [] all count; omitting does not)",
         6: "shape and closed vocabularies (mechanical, but downstream has to guess)",
         7: "needs the code re-read (slowest per fix, hence last — not least important)"}


def _tiers(order):
    tiers = order.get("violation_tiers") or {}
    if tiers:
        return tiers
    # Older work orders have no tiers; tiers are a pure function of the rule name.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import contract_check as _CC
        return {r: t for r, t in ((r, _CC.rule_tier(r)) for r in (order.get("violations") or {})) if t}
    except Exception:
        return {}


def _group_examples(ex):
    """Cluster examples by their shared trailing remedy text and print that remedy once.

    Examples of one rule often fall into a few causes whose remedy paragraph is
    identical; clustering on the last 100 characters (which lie inside the shared
    remedy) separates the causes, and the common suffix of each cluster is printed
    once instead of eight times."""
    groups = []
    for y in ex:
        key = y[-100:]
        for g in groups:
            if g[0] == key:
                g[1].append(y)
                break
        else:
            groups.append((key, [y]))
    parts = []
    for _key, ys in groups:
        suf = ""
        if len(ys) > 1:
            k, s0 = 0, ys[0]
            while k < len(s0) and all(len(y) > k and y[-1 - k] == s0[-1 - k] for y in ys):
                k += 1
            if k >= 120:
                # The common suffix may start mid-word; move to the next space.
                p = len(s0) - k
                while p < len(s0) and s0[p] != " ":
                    p += 1
                if len(s0) - p >= 120:
                    k = len(s0) - p
                    suf = s0[p:].lstrip()
                    ys = [y[:len(y) - k].rstrip(" —:·*") for y in ys]
        parts.append(("; ".join(ys), suf))
    return parts


def render(order, template, collect_file):
    lines = []
    for m in order["missing"]:
        h = (" — " + "; ".join(m["hints"])) if m.get("hints") else ""
        e = (" on %s" % m["entity"]) if m.get("entity") else ""
        lines.append("- `%s` (%s%s, %s)%s" % (m["id_local"], m["op"], e, m.get("locator"), h))
    note = ("\n> This list shows the first %d of %d missing in this repo. Do the listed ones, "
            "then **apply the same judgement to the rest**.\n"
            % (len(order["missing"]), order["n_missing"])) if order.get("truncated") else ""
    totals = order.get("violation_totals") or {}
    tiers = _tiers(order)
    by_tier = {}
    for r, ex in (order.get("violations") or {}).items():
        n = totals.get(r, len(ex))          # full count; older orders only have the examples
        shown = min(len(ex), MAX_EXAMPLES)  # report what is actually printed, not what is stored
        more = ("(**only %d shown; this rule has %d occurrence(s)** — the examples are a sample, "
                "not the list)" % (shown, n) if n > shown else "")
        parts = _group_examples([str(x) for x in ex[:MAX_EXAMPLES]])
        line = "- **%s** — **%d occurrence(s)**%s:" % (r, n, more)
        if len(parts) == 1 and not parts[0][1]:
            line += " " + parts[0][0] + (" …" if len(ex) > MAX_EXAMPLES else "")
        else:
            for body, suf in parts:
                line += "\n  - %s" % body
                if suf:
                    line += "\n    ↳ all of these: %s" % suf
            if len(ex) > MAX_EXAMPLES:
                line += "\n  - …"
        by_tier.setdefault(tiers.get(r) or 9, []).append((n, line))
    vl = []
    for k in sorted(by_tier):
        vl.append("\n### Tier %s · %s" % (k, TITLE.get(k, "UNFILED (**this is a bug — give it a tier**)")))
        for _n, line in sorted(by_tier[k], key=lambda p: -p[0]):
            vl.append(line)
    # The same op often shows up in several tiers; list those so it is fixed in one pass.
    where = {}
    for r, ex in (order.get("violations") or {}).items():
        tr = tiers.get(r) or 9
        for x in ex:
            idl = str(x).split("(")[0].split(":")[0].split("/")[0].strip()
            if idl and "." in idl:
                where.setdefault(idl, set()).add(tr)
    multi = sorted((k, sorted(v)) for k, v in where.items() if len(v) > 1)
    if multi:
        vl.append("\n### The same op appears under several tiers")
        vl.append("Fixing one of these once may clear a line in each of them — read the code for it "
                  "**once** and address every tier it shows up in, instead of coming back to the same "
                  "operation from three different lists.")
        for idl, ts in multi[:20]:
            vl.append("- `%s` — tiers %s" % (idl, ", ".join(str(t) for t in ts)))
        if len(multi) > 20:
            vl.append("- … and %d more (this is a sample, not the list)" % (len(multi) - 20))
    gc, gs = order.get("guard_coverage"), order.get("n_guard_silent")
    gc_s = ("%.0f%%" % (gc * 100)) if isinstance(gc, (int, float)) else "not measured in this work order"
    gs_s = str(gs) if isinstance(gs, int) else "an unknown number of"
    nm = order["n_mutating"]
    return (template.replace("__VIOLATIONS__", "\n".join(vl) or "(none)")
            .replace("__COVERAGE__", "%.0f%%" % (order["coverage"] * 100))
            .replace("__GUARD_COVERAGE__", gc_s).replace("__N_GUARD_SILENT__", gs_s)
            .replace("__N_COVERED__", str(nm - order["n_missing"])).replace("__N_MUTATING__", str(nm))
            .replace("__MISSING_LIST__", "\n".join(lines)).replace("__TRUNCATION_NOTE__", note)
            .replace("__N_VIOLATIONS__", str(order.get("n_violations", "an unknown number of")))
            .replace("__OUT__", collect_file))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__.split("\n\n")[1])
    o = json.load(open(sys.argv[1], encoding="utf-8"))
    t = open(sys.argv[2], encoding="utf-8").read()
    print(render(o, t, sys.argv[3]))
