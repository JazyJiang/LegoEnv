"""t02lib.py — small helpers for batch tgt_02 build scripts (private to this batch; not a shared file)."""
import itertools, re
from packlib import *

def money_forms(x, dec=2):
    """text forms of an amount: 1234.5 -> ['1234.50', '1,234.50'] (dec=0 -> ['1235', '1,235'])"""
    s = f"{x:.{dec}f}"; c = f"{x:,.{dec}f}"
    return list(dict.fromkeys([s, c]))
def int_forms(*vals):
    out = []
    for v in vals: out += [str(int(v)), f"{int(v):,}"]
    return list(dict.fromkeys(out))
def mail_any(addr, *groups):
    """a mail submitted to addr whose body contains one form out of EVERY group (groups = lists of alternative strings)."""
    combos = list(itertools.product(*groups)) if groups else [()]
    cnts = [CNT(sent_to(addr, *c)) for c in combos]
    return cnts[0] if len(cnts) == 1 else OR(*cnts)
def cell(col, op, v):
    """a sheet cell condition matching both seeded flat cells and agent-written <dynamic> cells"""
    return OR(F(col, op, v), F(f"<dynamic>.{col}", op, v))
def rows(tid, *conds):
    return SEL(NS("budibase", "DynamicRow"), AND(F("tableId", "eq", tid), *conds))
def slug(x): return re.sub(r"[^a-z0-9]+", "-", str(x).lower()).strip("-")
def noise_mails(n, seed):
    """enron ham mails without the _src key (World.inbox rejects unknown keys)"""
    return [{k: v for k, v in m.items() if k != "_src"} for m in enron_mails(n, seed=seed)]
def sheet_ids_as_text(spec):
    """budibase sheet/table ids are strings (ws_*), but mcp_server maps input type 'id' to JSON integer → the tclaude client rejects
    {"sourceId": "ws_x"} as __unparsedToolInput (nordic_spa attempt 1 burnt 60 turns). Retype those args as text (runtime compares values as-is)."""
    n = 0
    for t in spec["tools"]:
        if not t["tool"].startswith(NS("budibase", "")): continue
        for k, v in (t.get("input_schema") or {}).items():
            if k in ("sourceId", "tableId", "_id", "appId", "workspaceId", "viewId") and isinstance(v, dict) and v.get("type") == "id":
                v["type"] = "text"; n += 1
    return spec
SIGNIN = " Sign in to each system with the credentials in your environment notes before you use it."   # tclaude runs often skipped sign-in and reported 'no credentials'
def login_hint(persona, pw="pw-operations"):
    """tclaude gold runs sometimes arrive WITHOUT the --append-system-prompt text (agent: 'there are no environment notes in my context'),
    so the credentials also go into the task prompt itself."""
    return (f" Your login for every system is {persona} / {pw}. All systems share one login session, so sign in to a system again right before "
            "you use it whenever you have signed into another system since.")
def loose_forms(x):
    """amount forms that also match a number the agent wrote as a JSON float (4154.2 for 4154.20): trailing zeros stripped, with/without thousands separator"""
    out = []
    for s in money_forms(x):
        if "." in s: s = s.rstrip("0").rstrip(".")
        out.append(s)
    return list(dict.fromkeys(out))
def prune_tools(spec, app, keep_regex):
    """drop an app's tools whose (unprefixed) name does not match keep_regex. 4-app worlds with misskey (338 tools) + espocrm (222) carry ~360 KB of tool
    schemas: the tclaude run 'autocompact-thrashed' after 22 turns (anthropic_grafana_moves attempt 1). Returns (spec, n_dropped)."""
    p = NS(app, ""); rx = re.compile(keep_regex); before = len(spec["tools"])
    spec["tools"] = [t for t in spec["tools"] if not t["tool"].startswith(p) or rx.search(t["tool"][len(p):])]
    return spec, before - len(spec["tools"])
