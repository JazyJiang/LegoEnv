#!/usr/bin/env python3
"""Deterministically synthesized seeds **for the probe only**.

WARNING: **these rows must never be written to disk, and must never reach the center agent stage.**

Seeds come in two layers:
  (1) probe seed  det-synthesized (this file)  **in memory only**, discarded after the run — checks L1/L2/L3
  (2) real data   data agent                   injected at work-order time — the task content, accounts included

An earlier version had the Build Spec agent write a layer of smoke seeds, but Ignite wipes them
wholesale at work-order time. That both burned agent turns and produced a fictional data source
that never reaches any task, so it has been removed from the main flow.

So this module only offers `synth(spec) -> seed_state`, and **no entry point that writes back into
the spec**. Callers must deepcopy the spec themselves before inserting it (see build_probe.under_test).

Why det seeding is **actually better than real data** for wall-hit tests: the probe holds the State
predicate, so it can construct both a "satisfied" and a "violated" world precisely. Real data only
offers whatever it happens to contain — the wall you want to hit may not be hittable at all.

What it cannot provide is **semantic plausibility** (title filled with text_1, undeclared business
invariants), so:
  · L2 catches no_op — it only asks "did anything change", independent of value plausibility (yes)
  · L3 catches fake walls — by construction, which is exactly its strength (yes)
  · "is this task interesting" — not its job; that is the center stage's work with real data (no)
"""
import re

_EMAIL_RE = re.compile(r"(?i)^(e?mail|email_address|user_email)$")
_PW_RE = re.compile(r"(?i)^(password|passwd|password_hash|password_digest|"
                    r"encrypted_password|hashed_password|pass)$")
_NAMEISH = re.compile(r"(?i)(name|title|label|subject|slug|handle|username)")
_URLISH = re.compile(r"(?i)(url|link|href|uri)")
# Deterministic clock: aligned with the runtime's default _now; do not introduce a second time base
_T0 = "2025-06-01T00:00:00"
_NOW = "2026-01-01T00:00:00"


def _ent_name(e):
    return e.get("name") or e.get("entity")


def _cols(e):
    return [c for c in (e.get("columns") or []) if isinstance(c, dict) and c.get("name")]


def _pk(e):
    return next((c["name"] for c in _cols(e) if c.get("pk")), None)


def _order(specs_entities):
    """FK topological order: parents before children. **Cycle-safe** — self- and mutual references
    like `User.created_by → User` are common in real schemas; whatever cannot be topologically
    sorted is appended in declaration order (its FKs get None or a self-reference)."""
    names = [_ent_name(e) for e in specs_entities]
    idx = {n: i for i, n in enumerate(names)}
    dep = {}
    for e in specs_entities:
        n = _ent_name(e)
        d = set()
        for c in _cols(e):
            fk = c.get("fk_to")
            if isinstance(fk, str) and "." in fk:
                t = fk.split(".", 1)[0]
                if t in idx and t != n:
                    d.add(t)
        dep[n] = d
    out, done = [], set()
    for _ in range(len(names)):
        moved = False
        for n in names:
            if n in done:
                continue
            if dep[n] <= done:
                out.append(n)
                done.add(n)
                moved = True
        if not moved:
            break
    out += [n for n in names if n not in done]      # cyclic ones fall back to declaration order
    return out


def _val(col, i, ent, account_hint):
    """The value of one cell. Type-aligned + name hints — the name hints are not there to "look
    real", but so that **format-constrained columns** like email/password are accepted by the
    runtime's login logic."""
    name, t = col["name"], col.get("type", "text")
    if col.get("enum"):
        return col["enum"][i % len(col["enum"])]
    if t == "bool":
        return i % 2 == 0
    if t == "int":
        v = i + 1
        lo, hi = col.get("min"), col.get("max")
        if isinstance(lo, int) and v < lo:
            v = lo
        if isinstance(hi, int) and v > hi:
            v = hi
        return v
    if t == "float":
        return float(i + 1)
    if t == "datetime":
        return _T0
    if t == "json":
        return {}
    if t == "id":
        return i + 1
    # text
    if _EMAIL_RE.match(name):
        return "probe%d@example.test" % (i + 1)
    if _PW_RE.match(name):
        return account_hint or "probe-pw"
    if _URLISH.search(name):
        return "https://example.test/%s/%d" % (ent.lower(), i + 1)
    if _NAMEISH.search(name):
        v = "%s %d" % (ent, i + 1)
    else:
        v = "%s_%d" % (name, i + 1)
    mx = col.get("max")
    return v[:mx] if isinstance(mx, int) and mx > 0 else v


def synth(spec, n=3, account_password="probe-pw"):
    """→ seed_state. **Returns a new dict; does not modify the spec.**

    Guarantees:
      · FKs point at parent rows that really exist (topological order + rotating parent ids)
      · `nullable:false` columns always have a value
      · `enum` columns draw from the set
      · table-level unique constraints vary per row
      · the first row of the account entity is the one that **can log in** (email + plaintext password)
      · ownership is testable: FKs to the account entity put **the first row under account#1 and
        rotate the rest** — an owner-scoped search must see both "mine" and "not mine", otherwise
        that scope cannot be verified
    """
    ents = [e for e in (spec.get("entities") or []) if isinstance(e, dict) and _ent_name(e)]
    by = {_ent_name(e): e for e in ents}
    auth = spec.get("auth") or {}
    acc_ent = auth.get("account_entity")
    if acc_ent not in by:
        cands = (spec.get("_auth_candidates") or [])
        acc_ent = cands[0]["entity"] if cands and cands[0].get("entity") in by else None
    state, ids = {}, {}
    for name in _order(ents):
        e = by[name]
        cols = _cols(e)
        pk = _pk(e)
        rows = []
        uniq = [c["cols"] for c in (e.get("constraints") or [])
                if isinstance(c, dict) and c.get("kind") == "unique" and c.get("cols")]
        for i in range(n):
            r = {}
            if pk:
                r[pk] = i + 1
            if "id" not in r:
                r["id"] = i + 1                    # the runtime locates rows by id in many places; always provide one
            for c in cols:
                cn = c["name"]
                if cn in r:
                    continue
                fk = c.get("fk_to")
                if isinstance(fk, str) and "." in fk:
                    te, _, tc = fk.partition(".")
                    if te == name:
                        # Self-reference (User.created_by → User): point at the previous row
                        # already inserted; the first row must stay empty — pointing at itself
                        # would break "parent before child".
                        r[cn] = (i if i > 0 else None) if c.get("nullable") is not False else 1
                        continue
                    # **The FK target column is not necessarily the pk** (Account.currency_code →
                    # Currency.code). Recording only pks would make such FKs point at a nonexistent
                    # value — L1 reports it as dangling right away.
                    pool = [x.get(tc) for x in (state.get(te) or []) if x.get(tc) is not None]
                    if not pool:
                        # Parent table not built yet (cycle) or empty — leave it empty if nullable;
                        # if not nullable, self-reference, otherwise the runtime's FK guard rejects the row.
                        r[cn] = None if c.get("nullable") is not False else (i + 1)
                    elif te == acc_ent:
                        # Ownership: the first row belongs to the login account, the rest rotate —
                        # so an owner-scoped search has both hits and misses, and that scope is verifiable.
                        r[cn] = pool[0] if i == 0 else pool[i % len(pool)]
                    else:
                        r[cn] = pool[i % len(pool)]
                    continue
                if c.get("nullable") is True and not c.get("pk") and i == n - 1:
                    r[cn] = None                   # leave one row with NULL to test NULL semantics
                    continue
                r[cn] = _val(c, i, name, account_password if name == acc_ent else None)
            # Vary unique keys per row so the seed does not violate itself — **except FK columns**:
            # their value comes from the parent row. Suffixing it creates a dangling FK (observed:
            # two repos, artalk/octoprint, were rejected wholesale because of this), and it does not
            # achieve the goal anyway — making an FK column unique means picking different parent rows
            # (already rotated by i above).
            fkcols = {c["name"] for c in cols if isinstance(c.get("fk_to"), str)}
            for uc in uniq:
                for col in uc:
                    if col in fkcols:
                        continue
                    if col in r and isinstance(r[col], str):
                        r[col] = "%s#%d" % (r[col], i + 1)
            rows.append(r)
        if name == acc_ent:
            uc = auth.get("username_col") or next(
                (c["name"] for c in cols if _EMAIL_RE.match(c["name"])), None)
            pc = auth.get("password_col") or next(
                (c["name"] for c in cols if _PW_RE.match(c["name"])), None)
            for i, r in enumerate(rows):
                if uc:
                    r[uc] = "probe%d@example.test" % (i + 1)
                if pc:
                    r[pc] = account_password
        state[name] = rows
        ids[name] = [r.get(pk or "id") for r in rows]      # only used for ownership rotation
    return state


def login_args(spec):
    """→ (tool_name, args) | (None, None). The probe's first step; if it fails, nothing after it is meaningful."""
    auth = spec.get("auth") or {}
    uc = auth.get("username_col") or "email"
    pc = auth.get("password_col") or "password"
    for t in (spec.get("tools") or []):
        if (t.get("family") or "").startswith("guard.auth"):
            v = (t.get("exec_spec") or {}).get("verify") or {}
            uc = v.get("username_col") or uc
            pc = v.get("password_col") or pc
            return t.get("tool"), {uc: "probe1@example.test", pc: "probe-pw"}
    return None, None
