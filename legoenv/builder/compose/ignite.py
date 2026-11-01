"""Deterministic namespace composition extracted without business changes.
Unused model clients, provider configuration and legacy generators are excluded.
"""
import mvgen
def account_options(nspec, env_pfx, limit=5):
    """Discover login-capable accounts among the rows that already exist in the world (no synthetic persona).
    → [{env, entity, username_col, password_col, username, password, id}]

    These rows are real accounts welded in by the data agent, so real data already hangs off them. The old persona
    approach inserted a new row id=990001 that cloned the tenant columns under a new id, so every owner_id still pointed
    at the original account and the persona logged in to an empty world (mvgen.py:152). Discovery avoids this entirely."""
    a = nspec.get("auth") or {}
    ae, uc, pc = a.get("account_entity"), a.get("username_col"), a.get("password_col")
    if not (ae and uc and pc):
        return []
    out = []
    for r in (nspec.get("seed_state") or {}).get(ae, []):
        u, w = r.get(uc), r.get(pc)
        if u in (None, "") or w in (None, ""):
            continue
        out.append({"env": env_pfx, "entity": ae, "username_col": uc, "password_col": pc,
                    "username": u, "password": w, "id": r.get("id")})
        if len(out) >= limit:
            break
    return out

def merge_world(specs, log=print):
    """k (seeded) repo specs -> one merged world spec: namespace + auth merge.

    No persona is injected any more (review v2). Populating accounts is the data agent's job; the singleton persona
    structure could neither express "one task needs several accounts" nor stop login from degenerating into copying a line
    from the prompt. ignite only discovers which accounts the world holds; the caller decides which one a task uses."""
    pfx, seen = [], set()
    for s in specs:
        p = mvgen.slug(s.get("env_id"))
        while p in seen:
            p += "2"
        seen.add(p); pfx.append(p)
    ns = [mvgen.namespace(s, p) for s, p in zip(specs, pfx)]
    aes = [(n.get("auth") or {}).get("account_entity") for n in ns]
    a0 = (ns[0].get("auth") or {}) if ns else {}
    merged = {
        "env_id": "__".join(pfx),
        "about": "Cross-system workspace: " +
                 "; ".join("%s__ (%s)" % (p, n.get("domain") or p) for p, n in zip(pfx, ns)) +
                 ". Each system has its own accounts; the same person may hold an account in several.",
        "entities": sum((n["entities"] for n in ns), []),
        "tools": sum((n["tools"] for n in ns), []),
        # There can be only one global auth block, taken from the first repo. Login no longer depends on it: every
        # login/register tool carries its own repo's account table and column names in its verify (runtime._auth_cols prefers the tool).
        # The global block is now read only by owner injection (_account_entity), a single-repo assumption that predates
        # the persona work; it is neither widened nor pretended solved here.
        "auth": {"account_entity": a0.get("account_entity"),
                 "username_col": a0.get("username_col", "username"),
                 "password_col": a0.get("password_col", "password"),
                 "session_fields": _union_sessions(ns)},
        "seed_state": _union_dicts(n["seed_state"] for n in ns),
        "seed_sources": _union_dicts(n["seed_sources"] for n in ns),
        "joint_sources": _union_dicts(n["joint_sources"] for n in ns),
    }
    # Every login/register tool is anchored to its own repo's account table and credential column names.
    # Measured over 242 repos with account candidates, (username_col, password_col) has 64 combinations; trusting only the
    # global pair would lock 55% of the repos out of the merged world. The old code could hard-code email/password only
    # because inject_persona added those two merged columns to the synthetic account row (mvgen.py:156); real accounts lack them.
    accounts = []
    for n, p, ae in zip(ns, pfx, aes):
        a = n.get("auth") or {}
        own = {x["tool"] for x in n["tools"]}
        for t in merged["tools"]:
            if t["tool"] not in own:
                continue
            if _is_login(t) or _is_register(t):
                v = t.setdefault("exec_spec", {}).setdefault("verify", {})
                if _is_login(t) and ae:
                    v["entity"] = ae
                if a.get("username_col"):
                    v["username_col"] = a["username_col"]
                if a.get("password_col"):
                    v["password_col"] = a["password_col"]
        accounts.extend(account_options(n, p))
    merged["_accounts"] = accounts
    return merged, pfx, aes

def _union_sessions(ns):
    out = {}
    for n in reversed(ns):
        out.update((n.get("auth") or {}).get("session_fields") or {})
    return out

def _union_dicts(ds):
    out = {}
    for d in ds:
        out.update(d or {})
    return out

def _is_login(t):
    fam = (t.get("family") or "").lower()
    return fam.startswith("guard.auth") or "login" in (t.get("tool") or "").lower()

def _is_register(t):
    fam = (t.get("family") or "").lower()
    return fam.startswith("auth.register") or "register" in (t.get("tool") or "").lower()
