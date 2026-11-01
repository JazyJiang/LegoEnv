#!/usr/bin/env python3
"""Deterministic probe for Build Spec. The rule across the whole pipeline is "run it for real
before claiming anything", and the spec is no exception — this is op-first applied to itself at
the very first stage.

Four layers:
  L0 structure  no execution, checked against the declarations only: required family keys /
                phantom columns / writes to audit columns / pk / addressability / evidence
  L1 builds     runtime.Env(spec) + the seed satisfies its own declared pk / fk / nullable / unique
  L2 drives     after login, call each tool once and classify by the before/after diff of env.state
  L3 hits walls for every **declared** wall, call once in violation; it must be hit, and it must
                be that wall

NOTE: **L1-L3 use throwaway det-synthesized seeds (build_seed.synth) that exist only in memory.**
  They are never written to disk and never reach the center agent stage — see the seed layers
  described at the top of build_seed.
  `build_report` must **not include sample rows** either: the agent reads this report, and if rows
  were included it might copy junk rows into its own draft seed — contamination leaking in through
  the report.

Three disciplines (same as the rest of the pipeline):
  · det does not preempt the node's decision — `no_op` only reports "the call succeeded but the
    state did not change"; whether to fix exec_spec or demote it to a read tool is for its author,
    who knows why it was written that way.
  · if it cannot be checked, degrade honestly — failing to construct a violation is the probe's
    limitation, not the checked object's fault; mark it `unverifiable`.
  · always log truncations and skips — silently testing less is falsely claiming "full coverage".
"""
import os, sys, json, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rt  # noqa: E402,F401  (puts the runtime directory on sys.path)
import grammar as GRAM  # noqa: E402
import build_seed as BS

# family → **required keys** of exec_spec. Only keys the runtime actually reads and has no fallback
# for — every extra key is a false alarm, and false alarms drown out the real ones. Checked against
# each executor's body: ex_field_set does not read exec_spec.fields at all (it takes args and
# filters by _writable), and ex_fetch / ex_delete fall back to `{"id": args["id"]}` for lookup_by.
FAM_KEYS = {
    "crud.insert":            ("entity", "fields"),
    "crud.upsert":            ("entity", "key", "insert_fields"),
    "crud.fetch":             ("entity",),
    "crud.delete":            ("entity",),
    "crud.delete_cascade":    ("entity", "cascade"),
    "crud.soft_delete":       ("entity", "set"),
    "update.field_set":       ("entity",),
    "update.status_transition": ("entity", "status_col"),
    "update.relation_link":   ("relation_type",),
    "search":                 ("entity",),
    "search.aggregate":       ("entity", "aggregate"),
    # the three below are legacy alias names (338 live specs still use them); ranking now goes through exec_spec.rank
    "search.filtered_list":   ("entity",),
    "search.keyword_weighted": ("entity",),
    "search.semantic":        ("entity",),
    "guard.auth":             ("verify",),
    "guard.logout":           (),
    "guard.permission":       (),
    "auth.register":          ("entity", "fields"),
    "action.trigger":         ("target",),
    "action.emit":            ("channel",),
    "action.probe":           (),
}
# These families must locate a row before they can act. If they cannot → the executor raises
# "target row does not exist" or silently changes nothing; the latter is L2's no_op: the call
# succeeds, the world does not change, and static checks cannot catch it.
_ADDRESSED = ("crud.fetch", "crud.delete", "crud.delete_cascade", "crud.soft_delete",
              "update.field_set", "update.status_transition")
_READONLY = ("search", "search.", "crud.fetch", "guard.permission", "guard.logout", "action.probe")


def _is_read(fam):
    return any(fam.startswith(p) if p.endswith(".") else fam == p for p in _READONLY)


def _card(v):
    """card → {op, n} | None. **A string is the collection side's standard form** (51 of 60
    collects use `"card": "exists"`), and the runtime has long accepted both via `_CARD_ALIAS` —
    only the probe lacked it, so it crashed on the most common form and a repo's 40-minute run
    was wasted.

    NOTE: the alias table is **taken directly from the runtime**. The bug here was exactly "one
    contract implemented separately in two places"; another copy would miss a side again the next
    time an alias is added.

    NOTE: non-objects must **not** all be treated as empty either: treating `"exists"` as empty
    drops the cardinality requirement, setup takes the wrong branch → a fake wall is reported →
    the agent is pushed to delete a correct guard. **Trading a crash for a silent wrong answer is
    worse than the crash.**
    """
    if isinstance(v, dict):
        return v
    if v is None:
        return {"op": "gte", "n": 1}
    try:
        import runtime
        a = runtime._CARD_ALIAS.get(v) if isinstance(v, str) else None
    except Exception:
        a = None
    return dict(a) if isinstance(a, dict) else None


def _cols(spec):
    return {(e.get("name") or e.get("entity")):
            {c["name"] for c in (e.get("columns") or []) if isinstance(c, dict) and c.get("name")}
            for e in (spec.get("entities") or []) if isinstance(e, dict)}


def _audit(spec):
    return {(e.get("name") or e.get("entity")):
            {c["name"] for c in (e.get("columns") or []) if isinstance(c, dict) and c.get("audit")}
            for e in (spec.get("entities") or []) if isinstance(e, dict)}


# ── L0: structure ────────────────────────────────────────────────────────────

def _iso(out, who, fn, *a):
    """Run one static check that **can only break itself**.

    A malformed exec_spec makes the traversal code raise (observed: target written as a string,
    card written as an unknown alias). This used to crash the whole repo — the agent's 40 minutes
    of output lost, with not a single diagnostic, which is worse than failing it.
    Now: the exception is recorded in place as one err, **the exception text itself is the
    diagnostic for the agent**, and the remaining tools still run.
    """
    try:
        return fn(*a)
    except Exception as ex:
        out.append(("err", who, "static check raised here %s: %s — the runtime most likely cannot read this shape either"
                    % (type(ex).__name__, str(ex)[:90])))
        return None


def l0(spec):
    """→ [(severity, who, problem)]. severity: err must be fixed / warn is recorded."""
    out = []
    cols, audit = _cols(spec), _audit(spec)
    for e in (spec.get("entities") or []):
        name = e.get("name") or e.get("entity")
        cl = [c for c in (e.get("columns") or []) if isinstance(c, dict)]
        if not any(c.get("pk") for c in cl):
            out.append(("err", name, "no pk — delete_cascade falls back to 'id' when finding child rows; "
                                     "if the primary key is not named id it silently hits the wrong rows"))
        for c in cl:
            fk = c.get("fk_to")
            if isinstance(fk, str) and "." in fk:
                te, _, tc = fk.partition(".")
                if te not in cols:
                    out.append(("err", name, "%s.fk_to points at nonexistent entity %s" % (c["name"], te)))
                elif tc not in cols[te]:
                    out.append(("err", name, "%s.fk_to points at %s, which has no column %s" % (c["name"], te, tc)))
        for cn in (e.get("constraints") or []):
            if not isinstance(cn, dict):
                continue
            if cn.get("kind") == "unique":
                miss = [x for x in (cn.get("cols") or []) if x not in cols.get(name, ())]
                if miss:
                    out.append(("err", name, "unique constraint references nonexistent columns %s" % miss))
            elif cn.get("kind") == "check":
                c = (cn.get("left") or {}).get("col")
                if c not in cols.get(name, ()):
                    out.append(("err", name, "check constraint references nonexistent column %r" % c))
    for t in (spec.get("tools") or []):
        try:
            tn, fam = t.get("tool"), t.get("family")
            es = t.get("exec_spec") or {}
            if fam not in FAM_KEYS:
                out.append(("err", tn, "family %r is not in the runtime executor table" % fam))
                continue
            for k in FAM_KEYS[fam]:
                v = es.get(k)
                if v is None or v == "" or v == [] or v == {}:
                    out.append(("err", tn, "%s is missing exec_spec.%s (the runtime would use None to look up the table / modify rows)" % (fam, k)))
            ent = es.get("entity") or t.get("entity")
            if fam in _ADDRESSED:
                rk = es.get("row_key") or es.get("lookup_by") or {}
                ins = t.get("input_schema") or {}
                pk = next((c["name"] for e in (spec.get("entities") or [])
                           if (e.get("name") or e.get("entity")) == ent
                           for c in (e.get("columns") or []) if isinstance(c, dict) and c.get("pk")), None)
                if not rk and "id" not in ins and (pk is None or pk not in ins):
                    out.append(("err", tn, "%s cannot locate a row: no row_key/lookup_by, and no id/%s in the inputs"
                                % (fam, pk or "pk")))
            if ent and ent not in cols:
                out.append(("err", tn, "entity %r is not in entities" % ent))
            elif ent:
                for key in ("fields", "insert_fields", "search_fields"):
                    for c in (es.get(key) or []):
                        if isinstance(c, str) and c not in cols[ent]:
                            out.append(("err", tn, "exec_spec.%s: %r is a phantom column" % (key, c)))
                        elif isinstance(c, str) and c in audit.get(ent, ()):
                            out.append(("warn", tn, "writable fields include audit column %r" % c))
                for key in ("set", "set_on_create", "set_on_exists"):
                    for c in (es.get(key) or {}):
                        if c not in cols[ent]:
                            out.append(("err", tn, "exec_spec.%s writes phantom column %r" % (key, c)))
                for c in (es.get("lookup_by") or es.get("row_key") or {}):
                    if c not in cols[ent]:
                        out.append(("err", tn, "%r in lookup_by/row_key is a phantom column" % c))
                sc = es.get("status_col")
                if fam == "update.status_transition" and sc and sc not in cols[ent]:
                    out.append(("err", tn, "status_col %r is a phantom column" % sc))
                for k, v in ((es.get("scope") or {}).items()):
                    if k in ("owner_col", "visibility_col") and v not in cols[ent]:
                        out.append(("err", tn, "scope.%s %r is a phantom column" % (k, v)))
            g = t.get("guards") or {}
            for gi, grp in enumerate(_dnf_of(g)):
                for st in grp:
                    if not isinstance(st, dict):
                        out.append(("err", tn, "preconditions[%d] is unreadable (neither a State nor "
                                               "a reconstructible Count tree)" % gi))
                        continue
                    pe = st.get("entity")
                    if pe not in cols:
                        out.append(("err", tn, "guard references nonexistent entity %r" % pe))
                        continue
                    for cl2 in (st.get("scope") or []):
                        if isinstance(cl2, dict) and cl2.get("col") not in cols[pe]:
                            out.append(("err", tn, "guard %s.%r is a phantom column" % (pe, cl2.get("col"))))
            if es.get("_record_undeclared"):
                # The dispatch record lands on a table not in entities → **the verifier cannot
                # assert this effect**. By design, "non-state effects are assertable because the
                # runtime projects them into state" — projecting onto a table nobody declared is no
                # projection at all.
                out.append(("warn", tn, "dispatch record lands on an undeclared table; the verifier cannot see this effect — "
                                        "either add an entity, or accept that tasks based on it are unverifiable"))
            # `_evidence` only accepts a dict: the agent sometimes writes a quoted string (observed
            # 4%). A string is not machine-readable evidence, so count it as "absent" — this drives
            # the feedback round to fix it into the contract shape. A wrong shape must never crash the repo.
            _ev = t.get("_evidence")
            _ev = _ev if isinstance(_ev, dict) else {}
            if g.get("preconditions") and not _ev.get("edges"):
                out.append(("warn", tn, "has guards but no _evidence.edges — a wall without evidence must not be written"))
            # Added in v3: no structural effect, not a search family, yet carries preconditions —
            # very likely a **permission checker** collected as an operation, so the wall is
            # attached to the wrong place (it belongs on the operations it gates).
            # Such failures used to be silent: the join succeeds, the wall sits in the wrong place,
            # and bookkeeping does not catch it.
            if g.get("preconditions") and _is_read(fam) and fam not in ("search",
                                                                        "search.filtered_list",
                                                                        "search.keyword_weighted",
                                                                        "search.semantic",
                                                                        "crud.fetch"):
                out.append(("warn", tn, "no structural effect but has guards — likely a permission checker; the wall may be attached to the wrong tool"))
            # action.trigger is an **escape hatch**, and an escape hatch that declares no side
            # effect at all is an empty shell: the caller cannot tell whether it took effect.
            # 20 of 91 live ones (22%) are like this, matching the observed 20.9% no_op rate.
            # This should be caught at build time, not discovered at L2 as "called but the world
            # did not change".
            if fam == "action.trigger" and not [k for k in ("set", "spawn", "dispatch_events")
                                                if (t.get("exec_spec") or {}).get(k)]:
                out.append(("err", tn, "action.trigger declares no side effect (set / spawn / "
                                       "dispatch_events) — an action that changes nothing is meaningless"))
        except Exception as _ex:
            # A malformed exec_spec / guards makes the traversal code raise. This used to crash
            # the **whole repo**: the agent's 40 minutes of output lost, with not a single
            # diagnostic — worse than failing it. Now only this one tool is lost, and **the
            # exception text itself is the diagnostic for the agent**.
            out.append(("err", t.get("tool"), "static check raised on this tool %s: %s — the runtime most likely cannot read this shape either" % (type(_ex).__name__, str(_ex)[:90])))
    return out


# ── Probe world: deepcopy + synthesized seeds, **no write-back path** ────────────────────
def under_test(spec, n=3):
    """→ a **new** spec (with synthesized seeds + synthesized auth). The original spec is not
    touched by a single byte. These seeds exist only in this process's memory; they are never
    written to disk and never reach center."""
    s = copy.deepcopy(spec)
    if not (s.get("auth") or {}).get("account_entity"):
        cands = s.get("_auth_candidates") or []
        if cands:
            c = cands[0]
            s["auth"] = {"account_entity": c["entity"], "username_col": c["username_col"],
                         "password_col": c["password_col"]}
            # Synthesized auth must carry session_fields too, otherwise $session.<col> never
            # resolves in the candidate round — the baseline drops for no reason, and the cause is
            # not in the object under test.
            _sf = [x for x in (s.get("_session_fields") or [])
                   if x in {cc.get("name") for e in (s.get("entities") or [])
                            if isinstance(e, dict) and e.get("name") == c["entity"]
                            for cc in (e.get("columns") or []) if isinstance(cc, dict)}]
            if _sf:
                s["auth"]["session_fields"] = {x: x for x in _sf}
    s["seed_state"] = BS.synth(s, n=n)
    s.setdefault("now", "2026-01-01T00:00:00")
    return s


def _hk(v):
    """Make hashable. When a column holds a list/dict, use its JSON string as a stable key — so
    the check **reaches a verdict** instead of raising and failing the whole repo. The runtime has
    a twin implementation with the same name (also born from a crash on a json column)."""
    if isinstance(v, (list, dict)):
        try:
            return json.dumps(v, sort_keys=True, ensure_ascii=False, default=str)
        except Exception:
            return repr(v)
    return v


# ── L1: builds + seed is self-consistent ──────────────────────────────────────────────
def l1(spec):
    """→ (ok, why, env|None)."""
    try:
        import runtime
    except Exception as ex:
        return False, "cannot import runtime: %s" % ex, None
    try:
        env = runtime.Env(copy.deepcopy(spec))
    except Exception as ex:
        return False, "runtime.Env(spec) failed to build: %s: %s" % (type(ex).__name__, str(ex)[:160]), None
    bad = []
    for e in (spec.get("entities") or []):
        name = e.get("name") or e.get("entity")
        rows = env.state.get(name) or []
        for c in (e.get("columns") or []):
            if not isinstance(c, dict):
                continue
            if c.get("nullable") is False and not c.get("pk"):
                k = sum(1 for r in rows if r.get(c["name"]) is None)
                if k:
                    bad.append("%s.%s is declared nullable:false but %d synthesised rows came out empty — nothing in the spec can supply that column" % (name, c["name"], k))
            fk = c.get("fk_to")
            if isinstance(fk, str) and "." in fk:
                te, _, tc = fk.partition(".")
                # NOTE: a column may hold a list/dict (agent-written seeds are not guaranteed to be
                #   well formed). Putting it straight into a set raises TypeError and crashes the
                #   whole repo — after the agent has finished, wasting the whole round.
                #   Semantically, a list/dict in an FK column is not a valid reference anyway, so
                #   count it as **dangling**.
                tv = {_hk(r.get(tc)) for r in (env.state.get(te) or [])}
                d = [r for r in rows if r.get(c["name"]) is not None
                     and _hk(r.get(c["name"])) not in tv]
                if d:
                    bad.append("%s.%s has %d dangling FK values (pointing at rows that do not exist in %s) — either %s produced no rows at all, or fk_to names a column %s does not have" % (name, c["name"], len(d), te, te, te))
        for cn in (e.get("constraints") or []):
            if isinstance(cn, dict) and cn.get("kind") == "unique":
                ck, seen, dup = cn.get("cols") or [], set(), 0
                for r in rows:
                    k = tuple(_hk(r.get(x)) for x in ck)
                    if any(v is None for v in k):
                        continue
                    if k in seen:
                        dup += 1
                    seen.add(k)
                if dup:
                    bad.append("%s: the unique(%s) constraint is already violated %d times by the synthesised rows — the columns you declared unique cannot actually be made distinct" % (name, ",".join(ck), dup))
    return (not bad), "; ".join(bad[:6]), env


# ── Argument synthesis ────────────────────────────────────────────────────────────
def _mkargs(spec, env, t, existing=True):
    """Synthesize the arguments for one call of a tool.

    **This is the main source of false negatives**: if a parameter that feeds row_key / lookup_by
    is given a value absent from the seed, the result is "target row does not exist" — which looks
    exactly like "exec_spec is wrong". So such parameters always **take the real value from the
    seed's first row**. Same for FK parameters: use `_binds` (param → Entity.col) to find the target
    table and pull a real id from it.
    """
    es = t.get("exec_spec") or {}
    ent = es.get("entity") or t.get("entity")
    binds = t.get("_binds") or {}
    ins = t.get("input_schema") or {}
    colmap = {}
    for e in (spec.get("entities") or []):
        colmap[(e.get("name") or e.get("entity"))] = {
            c["name"]: c for c in (e.get("columns") or []) if isinstance(c, dict) and c.get("name")}
    # which inputs are used to locate the target row
    keyargs = {}
    for k in ("row_key", "lookup_by", "subject_key"):
        for col, v in (es.get(k) or {}).items():
            if isinstance(v, dict) and isinstance(v.get("$arg"), str):
                keyargs[v["$arg"]] = (ent, col)
    # target also comes as a bare string (7 in the live pufferpanel spec). The runtime accepts it,
    # so the probe must too — otherwise the probe raises AttributeError here and it gets labelled
    # "the runtime cannot read it", even though the runtime can: **that is a false positive, and it
    # drives the agent to fix something that is not broken.**
    _tg = es.get("target")
    _tg = {"entity": _tg} if isinstance(_tg, str) else (_tg if isinstance(_tg, dict) else {})
    for col, v in (_tg.get("lookup_by") or {}).items():
        if isinstance(v, dict) and isinstance(v.get("$arg"), str):
            keyargs[v["$arg"]] = (_tg.get("entity") or ent, col)
    args = {}
    for p, ty in ins.items():
        # `input_schema` has two legal shapes: flat {param: "type"} and rich
        # {param: {type, description, required}}. **det emits the flat one, the agent returns
        # the rich one** (live: 43977 rich / 908 flat), and this code used to treat the whole dict
        # as the type — `_distinct({"type":"int"}, "qty", 1)` returned `'probe_qty'`, a string put
        # into an int column. Silent, and **only on drafts**, i.e. in the feedback round: the probe
        # uses the wrong type → the tool is recorded as error or writes a wrong value → the agent
        # fixes something that is not broken. Observed: ~4000 parameters affected (id 1409 /
        # int 881 / json 843 / bool 587 ...), exactly those with null binds and no column to fall back on.
        if isinstance(ty, dict):
            ty = ty.get("type") or "text"
        if p in keyargs:
            te, col = keyargs[p]
            rows = env.state.get(te) or []
            if rows and existing:
                args[p] = rows[0].get(col)
                continue
            args[p] = 999999 if ty in ("int", "id") else "no-such-row"
            continue
        b = binds.get(p)
        if not b and ent and p in (colmap.get(ent) or {}):
            b = "%s.%s" % (ent, p)          # fall back to the column name when binds is missing (same name = same column)
        if isinstance(b, str) and "." in b:
            te, _, tc = b.partition(".")
            cd = (colmap.get(te) or {}).get(tc) or {}
            fk = cd.get("fk_to")
            if isinstance(fk, str) and "." in fk:          # FK param: pull a parent id that really exists
                pe, _, pc = fk.partition(".")
                rows = env.state.get(pe) or []
                args[p] = rows[0].get(pc) if rows else 1
                continue
            if cd.get("enum"):
                args[p] = cd["enum"][0]
                continue
            if cd.get("type"):
                ty = cd["type"]
        args[p] = _distinct(ty, p, _cur(env, ent, binds.get(p)))
    return args


def _cur(env, ent, bind):
    """Current value of the target row (seed's first row) in the column this parameter binds to."""
    if isinstance(bind, str) and "." in bind:
        te, _, tc = bind.partition(".")
    else:
        te, tc = ent, None
    rows = env.state.get(te) or []
    return rows[0].get(tc) if rows and tc else None


def _distinct(ty, name, cur):
    """Build a legal value **different from the current value**. The whole point of the write
    probe is "did the world change after the call"; passing the current value would produce a
    no_op that is an artifact of the probe, not a defect of the spec."""
    if ty == "bool":
        return not bool(cur)
    if ty in ("int", "id"):
        v = 987654
        return v + 1 if cur == v else v
    if ty == "float":
        return 987.5 if cur != 987.5 else 988.5
    if ty == "json":
        return {"probe": 1} if cur != {"probe": 1} else {"probe": 2}
    if ty == "datetime":
        return "2026-07-04T12:00:00" if cur != "2026-07-04T12:00:00" else "2026-07-05T12:00:00"
    v = "probe_%s" % name
    return v + "_2" if cur == v else v


def _setup_value(v, env, args):
    """A Value in a guard State → what to put in the column during setup. → (ok, value).

    `{col}` is an in-row comparison (this column vs another column of the same row) and cannot be
    set independently — give up on this State instead of filling in an arbitrary value to paper
    over the wall. Papering over it means the tool is let through for a false reason, and L2 then
    reports a wrote that **does not hold**.
    """
    if not isinstance(v, dict):
        return True, v
    if "lit" in v:
        return True, v["lit"]
    if "sym" in v:
        return (True, getattr(env, "_now", None)) if v["sym"] == "$now" else (False, None)
    if "col" in v:
        return False, None
    r = v.get("ref")
    if not isinstance(r, str):
        return False, None
    head, _, tail = r.partition(".")
    if head == "$arg" or head == "$subject":
        return (tail in (args or {})), (args or {}).get(tail)
    if head == "$actor":
        return True, env.session.get("account_id")
    if head == "$session":
        return (tail in env.session), env.session.get(tail)
    return False, None


_NOPE = object()



def _solve_expr(e, row, resolve1):
    """Set up `{"expr": {col, op, by}}`: **solve for one free column only**. → (value, free column) | (_NOPE, why)

    Real guards are almost always unary (`balance >= price * qty`: price/qty are fixed, solve for
    balance). General constraint solving is out of scope — two free variables **loudly report
    "cannot set up"**, same as with `or`/`not` trees ("cannot set up beats setting up wrong").
    **The language's completeness must not be trimmed to the solver's ability**, and vice versa:
    when the solver cannot solve, it must say so instead of quietly laying down a row that does
    not satisfy.
    """
    if not isinstance(e, dict):
        return _NOPE, "expr has the wrong shape"
    c = e.get("col")
    if c is None:
        return _NOPE, "expr does not say which column it is based on"
    a = row.get(c, None)
    b = resolve1(e.get("by"))
    if b is None or b is GRAM.UNKNOWN:
        return _NOPE, "expr's by cannot be resolved (two free variables?)"
    if a is None:
        return _NOPE, "column %r that expr is based on has no value in this row yet" % c
    try:
        op = e.get("op")
        if op == "+": return a + b, c
        if op == "-": return a - b, c
        if op == "*": return a * b, c
        if op == "/": return (_NOPE, "division by zero") if not b else (a / b, c)
    except TypeError:
        return _NOPE, "expr operand types do not match"
    return _NOPE, "unknown arithmetic operator %r" % e.get("op")


def _satisfying(op, val):
    """Build a value satisfying `col <op> val`. → value | _NOPE (cannot build).

    **Operator knowledge lives in exactly one place, the grammar** (`runtime/grammar.py`). This
    used to keep its own small table that knew only 7 operators — and once the operator table grew
    to 14, every operator the small table did not know became "cannot set up / cannot break", i.e.
    **that wall was never verified**, with no error reported.
    """
    v = GRAM.satisfying("ne" if op == "neq" else op, val)
    return _NOPE if v is GRAM.NOPE else v


def _falsifying(op, val):
    """Build a value that makes `col <op> val` false. → value | _NOPE."""
    v = GRAM.falsifying("ne" if op == "neq" else op, val)
    return _NOPE if v is GRAM.NOPE else v


def _v_back(v):
    """IR Value → source-syntax Value. Used by `_as_state`."""
    if not isinstance(v, dict):
        return {"lit": v}
    if "col" in v:
        return {"col": v["col"]}
    if v.get("now") is True:
        return {"sym": "$now"}
    for k, pre in (("arg", "$arg."), ("actor", "$actor."), ("session", "$session.")):
        if k in v:
            return {"ref": pre + str(v[k])}
    return v


def _as_state(x):
    """IR Count tree → source syntax `{entity, scope[], card}`. **The probe's world-setup logic is
    written against the source syntax**, while det now emits IR; the 340 cached specs are still in
    source syntax. Both must be readable.

    Only the one shape det produces is reconstructed (count(select(entity, flat and), op, n)).
    A tree that really contains `or` / `not` **returns None when it cannot be reconstructed** —
    cannot set up beats setting up wrong; the caller records it as "this branch cannot be broken".
    """
    if not isinstance(x, dict) or "node" not in x:
        return x                                     # source syntax, as is
    if x.get("node") != "count":
        return None
    sel = x.get("select")
    if not isinstance(sel, dict) or sel.get("node") != "select":
        return None
    w = sel.get("where")
    if w is None:
        leaves = []
    elif isinstance(w, dict) and w.get("node") == "field":
        leaves = [w]
    elif isinstance(w, dict) and w.get("node") == "and":
        leaves = [a for a in (w.get("args") or [])]
    else:
        return None                                  # or / not: not expressible at this level
    scope = []
    for lf in leaves:
        if not isinstance(lf, dict) or lf.get("node") != "field":
            return None
        cl = {"col": lf.get("col"), "op": lf.get("op", "eq")}
        if "value" in lf:
            cl["value"] = _v_back(lf["value"])
        if lf.get("optional"):
            cl["optional"] = True
        scope.append(cl)
    return {"entity": sel.get("entity"), "scope": scope,
            "card": {"op": x.get("op", "gte"), "n": x.get("n", 1)}}


def _dnf_of(g):
    """`guards.preconditions` → a one-level DNF, **each item already converted to source syntax**.
    Always read preconditions through here rather than each caller doing `g.get("preconditions")`
    — that is exactly why things fell apart whenever the shape changed."""
    out = []
    for grp in ((g or {}).get("preconditions") or []):
        grp = grp if isinstance(grp, list) else [grp]
        out.append([_as_state(x) for x in grp])
    return out


def _card_of(st):
    """card → (op, n). **String aliases are accepted too** — 46 live places write exists /
    not_exists, and this used to do `(st.get("card") or {}).get("op")` directly, raising
    AttributeError on strings (observed on the register tool of answer.spec.json)."""
    c = st.get("card") or "exists"
    if isinstance(c, str):
        return {"exists": ("gte", 1), "not_exists": ("eq", 0)}.get(c)
    if isinstance(c, dict):
        try:
            return c.get("op", "gte"), int(c.get("n", 1))
        except (TypeError, ValueError):
            return None
    return None


def _satisfy(env, spec, tool, args):
    """Set up the world so this tool's guards pass. → (ok, why)

    Only the **first disjunct** is set up (satisfying any one branch lets the call through);
    every State in the branch must be settable, and if one is not, give up entirely — a
    half-set-up world only makes the failure reason harder to read.
    """
    dnf = _dnf_of(tool.get("guards"))
    if not dnf:
        return False, "no preconditions; not blocked by a precondition"
    grp = [x for x in dnf[0] if x is not None]
    if not grp:
        return False, "this branch is an irreducible tree (or/not); cannot set up"
    colmap = {}
    for e in (spec.get("entities") or []):
        colmap[(e.get("name") or e.get("entity"))] = e
    for st in grp:
        if not isinstance(st, dict):
            return False, "State has the wrong shape"
        ent = st.get("entity")
        eo = colmap.get(ent)
        if eo is None:
            return False, "entity %r referenced by the guard is not in the spec" % ent
        card = _card(st.get("card"))
        if card is None:
            return False, "unknown card %r" % st.get("card")
        op, n = card.get("op"), int(card.get("n", 1))
        rows = env.state.setdefault(ent, [])
        if op == "eq" and n == 0:
            # not_exists: just remove the matching rows; this branch can always be set up
            keep = []
            for r in rows:
                try:
                    hit = all(_match_row(r, cl, env, args) for cl in (st.get("scope") or []))
                except Exception:
                    hit = False
                if not hit:
                    keep.append(r)
            env.state[ent] = keep
            continue
        if op not in ("gte", "lte"):
            return False, "card.op %r cannot be set up" % op
        if op == "lte":
            continue                                  # at most: an empty table satisfies it trivially
        # gte n: top up to n matching rows
        row = {}
        for cl in (st.get("scope") or []):
            if not isinstance(cl, dict):
                return False, "scope clause has the wrong shape"
            cop = cl.get("op", "eq")
            _cv = cl.get("value")
            if isinstance(_cv, dict) and "expr" in _cv:
                # Arithmetic: first evaluate the expression on **the current row**, then use it as
                # the right operand to build the left value. If it cannot be solved, give up on the
                # whole State and say why — a half-set-up world only makes the failure reason harder to read.
                _val, _why = _solve_expr(_cv["expr"], row,
                                         lambda x: (_setup_value(x, env, args) + (None,))[1]
                                         if _setup_value(x, env, args)[0] else None)
                if _val is _NOPE:
                    return False, "%s.%s involves arithmetic, cannot set up: %s" % (ent, cl.get("col"), _why)
                ok, val = True, _val
            else:
                ok, val = _setup_value(_cv, env, args)
            if not ok:
                # Almost always the guard references $arg.x while x is not a parameter of this
                # tool at all. **That is a spec defect, not something the probe should paper over**
                # — papering over it lets the tool through for a false reason, and L2 then reports
                # a wrote that does not hold. Give up honestly and report it to the agent.
                return False, "cannot set up a value for %s.%s (does the guard reference something not in the inputs?)" % (ent, cl.get("col"))
            v = _satisfying(cop, val)
            if v is _NOPE:
                return False, "scope contains %r; cannot construct a definite row" % cop
            row[cl["col"]] = v
        need = n - sum(1 for r in rows
                       if all(r.get(k) == v for k, v in row.items()))
        for i in range(max(0, need)):
            full = dict(row)
            for c in (eo.get("columns") or []):
                if not isinstance(c, dict) or c["name"] in full:
                    continue
                if c.get("pk") or c["name"] == "id":
                    full[c["name"]] = len(rows) + i + 1000
                    continue
                fk = c.get("fk_to")
                if isinstance(fk, str) and "." in fk:
                    te, _, tc = fk.partition(".")
                    pv = _parent_val(env, colmap, te, tc)
                    if pv is None and c.get("nullable") is False:
                        # If the parent row cannot be built, do not build the child — a dangling FK
                        # makes the next call report "FK points at a nonexistent row", which looks
                        # exactly like "the spec is wrong".
                        return False, "%s.%s: cannot build its parent row in %s" % (ent, c["name"], te)
                    full[c["name"]] = pv
                    continue
                if c.get("nullable") is False or c.get("enum"):
                    full[c["name"]] = BS._val(c, len(rows) + i, ent, None)
            rows.append(full)
    return True, ""


def _parent_val(env, colmap, te, tc, depth=0):
    """A tc value that really exists in the parent table; if none, build a row on the spot.
    → value | None (cannot build). Only drills down one level — any deeper becomes "lay out half
    the world to test one tool", which is not the probe's job."""
    rows = env.state.get(te) or []
    for r in rows:
        if r.get(tc) is not None:
            return r[tc]
    if depth >= 1:
        return None
    eo = colmap.get(te)
    if eo is None:
        return None
    new = {}
    for c in (eo.get("columns") or []):
        if not isinstance(c, dict):
            continue
        n = c["name"]
        if c.get("pk") or n == "id":
            new[n] = 900 + len(rows)
            continue
        fk = c.get("fk_to")
        if isinstance(fk, str) and "." in fk:
            pe, _, pc = fk.partition(".")
            if pe == te:                              # self-reference: leave empty or point at itself
                new[n] = None if c.get("nullable") is not False else new.get("id")
                continue
            v = _parent_val(env, colmap, pe, pc, depth + 1)
            if v is None and c.get("nullable") is False:
                return None
            new[n] = v
            continue
        if c.get("nullable") is False or c.get("enum"):
            new[n] = BS._val(c, len(rows), te, None)
    if new.get(tc) is None:
        new[tc] = 900 + len(rows)
    env.state.setdefault(te, []).append(new)
    return new[tc]


def _break_group(env, spec, grp, args):
    """Break one conjunctive branch (make at least one of its States false). → (success, concrete reason when it cannot be broken)

    The inverse of `_satisfy`: that one makes "every branch true", this one makes "every branch
    false". How to break depends on the card's lower/upper bound:
      · at least / more than / exactly n (n>0) rows  → **empty that table**; always works, no side effects
      · exactly 0 rows                               → conversely, insert a row matching the scope
      · at most / fewer than n rows (upper bound)    → cannot be broken today; **recorded explicitly**
    Every "cannot break" = that wall was **not verified** this round, so the reason must be
    specific enough to act on; never just return False.
    """
    ents = {(e.get("name") or e.get("entity")) for e in (spec.get("entities") or [])}
    whys = []
    for st in grp:                                   # (1) empty: breaks every lower-bound kind
        if not isinstance(st, dict):
            continue
        c = _card_of(st)
        if c is None:
            whys.append("unrecognized card: %r" % (st.get("card"),))
            continue
        op, n = c
        if st.get("entity") not in ents:
            whys.append("entity not in spec: %r" % (st.get("entity"),))
            continue
        if op in ("gte", "gt") or (op == "eq" and n > 0) or (op == "ne" and n == 0):
            env.state[st["entity"]] = []
            return True, ""
    for st in grp:                                   # (2) insert a row: breaks not_exists
        if not isinstance(st, dict):
            continue
        if _card_of(st) != ("eq", 0):
            continue
        ok, w = _satisfy(env, spec, {"guards": {"preconditions": [[
            dict(st, card={"op": "gte", "n": 1})]]}}, args)
        if ok:
            return True, ""
        whys.append("need to insert a row to break not_exists (%s) but cannot set it up: %s" % (st.get("entity"), w))
    for st in grp:                                   # (3) upper-bound kind: cannot break, record it clearly
        c = _card_of(st) if isinstance(st, dict) else None
        if c and c[0] in ("lte", "lt"):
            whys.append("upper-bound card (%s %d): breaking it requires inserting past the limit; not supported yet" % c)
    return False, ("; ".join(whys[:3]) or "no State in this branch is breakable")


def _match_row(r, cl, env, args):
    ok, val = _setup_value(cl.get("value"), env, args)
    return ok and r.get(cl.get("col")) == val


def _digest(env):
    return {k: (len(v), tuple(sorted(json.dumps(r, sort_keys=True, default=str) for r in v)))
            for k, v in env.state.items() if isinstance(v, list)}


# ── L2: real driving ──────────────────────────────────────────────────────────
def l2(spec):
    """Log in → call each tool once → classify by the before/after world diff. → (labels, notes)

    Labels (one per tool):
      write tools  wrote / no_op / wrong_entity / error / guarded
      read tools   returned / empty / error
    `no_op` is the most toxic: the call succeeds, the world does not change, static checks can
    never catch it, and downstream it shows up as a postcondition that is always false.
    """
    import runtime
    labels, notes = {}, []
    setup = {"attempted": 0, "unblocked": 0}
    ok, why, env = l1(spec)
    if env is None:
        return labels, ["L1 does not build, L2 cannot run: %s" % why], setup, {"ok": None, "why": why}
    lt, largs = BS.login_args(spec)
    logged = False
    # Whether login succeeded is the **premise** for reading this whole section, not a side note
    # to bury in notes: when login fails, every auth-gated tool below is labelled guarded, and
    # guarded normally means "the wall is working" — so a report of "the auth block is wrong"
    # reads like a report of "everything is fine", and the agent gets only this one round. Hence
    # it is structured separately and rendered at the very top.
    login = {"ok": None, "tool": lt, "why": None}
    if lt:
        r = env.call(lt, largs)
        logged = isinstance(r, dict) and r.get("ok") is not False
        login["ok"] = bool(logged)
        if not logged:
            login["why"] = str((r or {}).get("error"))[:120]
            notes.append("login failed (%s): %s — every auth-gated tool below is `guarded` "
                         "because of this, not because a wall worked"
                         % (lt, login["why"]))
    else:
        login["why"] = "no guard.auth tool in the spec"
        notes.append("no `guard.auth` tool — the probe drove everything **not logged in**")
    def _relogin():
        """Log back in if the session dropped. logout must be driven (it is a real tool), but the
        session must be restored afterwards — otherwise the dozens of tools after it all hit the
        auth wall, which the probe caused itself. Observed: this alone once dropped wrote from 12 to 1."""
        if lt and logged and not env.session.get("authed"):
            env.call(lt, largs)

    # Drive logout last. It always kills the session, and the tool order is collection order,
    # not a meaningful one — leaving it second would randomly disable every auth-gated tool after it.
    order = [t for t in (spec.get("tools") or []) if t.get("family") != "guard.logout"] + \
            [t for t in (spec.get("tools") or []) if t.get("family") == "guard.logout"]
    for t in order:
        tn, fam = t.get("tool"), t.get("family")
        if tn == lt:
            labels[tn] = "wrote" if logged else "error"
            continue
        _relogin()
        try:
            args = _mkargs(spec, env, t)
        except Exception as ex:
            # Two cases: the probe's own limitation vs **the runtime cannot read this exec_spec
            # either**. AttributeError/TypeError raised while traversing exec_spec is almost always
            # the latter (observed: target written as a string → 'str' has no attribute 'get', and
            # the runtime raises the same). The message must say which — calling it "argument
            # synthesis failed" means the probe blames itself, and the agent treats it as a probe
            # limitation and does not fix it.
            labels[tn] = "bad_exec_spec" if isinstance(ex, (AttributeError, TypeError)) \
                else "unverifiable"
            notes.append("the runtime cannot read the exec_spec of %s: %s: %s (the probe hit it while synthesizing args; "
                         "loading it into the runtime raises the same exception)" % (tn, type(ex).__name__, str(ex)[:80])
                         if labels[tn] == "bad_exec_spec"
                         else "%s argument synthesis failed (probe limitation, not a failure verdict): %s" % (tn, type(ex).__name__))
            continue
        before = _digest(env)
        try:
            res = env.call(tn, args)
        except Exception as ex:
            labels[tn] = "error"
            notes.append("%s raised: %s: %s" % (tn, type(ex).__name__, str(ex)[:70]))
            continue
        after = _digest(env)
        failed = isinstance(res, dict) and res.get("ok") is False
        err = str((res or {}).get("error") or "")
        if failed and res.get("refused_by") == "guard" and (t.get("guards") or {}).get("preconditions"):
            # The wall blocked it → set up the world per the guard's State so it passes, and drive
            # again. Without setup the tool stays at guarded: an effective wall is good, but **what
            # it actually does when it runs** stays unknown, and these are exactly the most valuable
            # part of tasks (operations that need multi-step preparation).
            setup["attempted"] += 1
            # **The whole experiment is isolated**: full snapshot → setup → retry → unconditional
            # restore. The rows laid down only answer "what does this tool do once past the wall",
            # and must not stay in the world to affect later tools.
            keep_state = copy.deepcopy(env.state)
            keep_sess = dict(env.session)
            try:
                sok, swhy = _satisfy(env, spec, t, args)
                if sok:
                    before = _digest(env)
                    try:
                        res2 = env.call(tn, args)
                    except Exception:
                        res2 = {"ok": False, "error": "raised after setup"}
                    after = _digest(env)
                    if isinstance(res2, dict) and res2.get("ok") is not False:
                        setup["unblocked"] += 1
                        res, failed = res2, False
                        # the before/after used for classification come from this isolated experiment
                        if _is_read(fam):
                            rr = (res2 or {}).get("result")
                            labels[tn] = "returned" if rr not in (None, [], {}) else "empty"
                        else:
                            changed = [k for k in set(before) | set(after)
                                       if before.get(k) != after.get(k)]
                            labels[tn] = _label_write(t, changed, ent_of(t))
                        notes.append("%s drivable after setup → %s" % (tn, labels[tn]))
                        continue
                    notes.append("%s still refused after setup: %s"
                                 % (tn, str((res2 or {}).get("error"))[:60]))
                else:
                    notes.append("%s cannot set up a world satisfying the preconditions: %s" % (tn, swhy))
            finally:
                env.state.clear(); env.state.update(keep_state)
                env.session.clear(); env.session.update(keep_sess)
        if failed:
            # "Blocked by a wall" is not an error — it shows the wall works. Classify by the
            # structured marker the runtime returns, **not by matching message text**: the text is
            # written by the agent in the app's own words, and matching it would force a particular
            # wording on it.
            labels[tn] = "guarded" if res.get("refused_by") else "error"
            continue
        if _is_read(fam):
            r = (res or {}).get("result")
            labels[tn] = "returned" if r not in (None, [], {}) else "empty"
            continue
        changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
        labels[tn] = _label_write(t, changed, ent_of(t))
        if labels[tn] == "wrong_entity":
            notes.append("%s declares it touches %r, but actually touched %s" % (tn, ent_of(t), changed[:3]))
    return labels, notes, setup, login


def ent_of(t):
    return (t.get("exec_spec") or {}).get("entity") or t.get("entity")


def _label_write(t, changed, ent):
    """Classification criterion for write tools. Shared by the setup path and the main path — two
    separate criteria would drift apart sooner or later."""
    es = t.get("exec_spec") or {}
    touched = set(es.get("_expect_entities") or [])
    touched.add(ent)
    for sp in (es.get("spawn") or []):
        touched.add(sp.get("entity"))
    rec = (es.get("record") or {}).get("table")
    if rec:
        touched.add(rec)
    elif t.get("family") == "action.emit":
        # ex_emit falls back to f"{entity or 'Dispatch'}Log" — compare against **the table the
        # executor will actually use**, otherwise "lands on the derived table by convention" is
        # misreported as wrong_entity (observed: 100+ false reports in one run).
        touched.add("%sLog" % (ent or "Dispatch"))
    if not changed:
        return "no_op"
    return "wrote" if any(c in touched for c in changed) else "wrong_entity"


# ── L3: wall hits ────────────────────────────────────────────────────────────
def l3(spec):
    """For every **declared** wall, deliberately call once in violation. → (results, notes)
    Three states: wall_hit (hit it) / wall_missing (declared but not hit = fake wall, the worst) /
          unverifiable (the probe cannot construct a violation — honest degradation, not a failure verdict).
    """
    import runtime
    res, notes = [], []

    def fresh():
        ok, why, env = l1(spec)
        return env

    def _login(env):
        lt, la = BS.login_args(spec)
        if lt:
            r = env.call(lt, la)
            return isinstance(r, dict) and r.get("ok") is not False
        return False

    for t in (spec.get("tools") or []):
        try:
            tn = t.get("tool")
            g = t.get("guards") or {}
            es = t.get("exec_spec") or {}

            # (1) requires login: call **without logging in** → expect refusal
            if g.get("requires_auth"):
                env = fresh()
                if env is None:
                    continue
                try:
                    r = env.call(tn, _mkargs(spec, env, t))
                    hit = isinstance(r, dict) and r.get("ok") is False
                    res.append((tn, "requires_auth", "wall_hit" if hit else "wall_missing",
                                str((r or {}).get("error"))[:70]))
                except Exception as ex:
                    res.append((tn, "requires_auth", "unverifiable", type(ex).__name__))

            # (2) business preconditions: preconditions is a **one-level DNF** (any branch lets the
            #    call through), so violating it requires **breaking every branch**. Breaking only the
            #    first leaves another one satisfied, and the call of course passes — observed: this
            #    one mistake produced 8/8 fake wall_missing.
            dnf = _dnf_of(g)
            if dnf:
                env = fresh()
                if env is None:
                    continue
                _login(env)
                args = _mkargs(spec, env, t)
                why = None
                for grp in dnf:
                    grp = grp if isinstance(grp, list) else [grp]
                    broke, w = _break_group(env, spec, grp, args)
                    if not broke:
                        why = "a branch cannot be broken: %s" % (w or "unknown reason")
                        break
                if why:
                    res.append((tn, "precondition", "unverifiable", why))
                else:
                    try:
                        r = env.call(tn, args)
                        hit = isinstance(r, dict) and r.get("ok") is False
                        res.append((tn, "precondition", "wall_hit" if hit else "wall_missing",
                                    str((r or {}).get("error"))[:70]))
                    except Exception as ex:
                        res.append((tn, "precondition", "unverifiable", type(ex).__name__))

            # (3) unique conflict: insert with a unique value that **already exists** in the seed
            uo = es.get("unique_on")
            if uo and t.get("family") == "crud.insert":
                env = fresh()
                if env is None:
                    continue
                _login(env)
                ent = es.get("entity")
                rows = env.state.get(ent) or []
                if not rows:
                    res.append((tn, "unique", "unverifiable", "no row in the seed to copy"))
                else:
                    a = _mkargs(spec, env, t)
                    for c in uo:
                        if c in (t.get("input_schema") or {}):
                            a[c] = rows[0].get(c)
                    try:
                        r = env.call(tn, a)
                        hit = isinstance(r, dict) and r.get("ok") is False
                        res.append((tn, "unique", "wall_hit" if hit else "wall_missing",
                                    str((r or {}).get("error"))[:70]))
                    except Exception as ex:
                        res.append((tn, "unique", "unverifiable", type(ex).__name__))

            # (4) illegal state transition: set the target row's status to a value **not in from**
            frm = es.get("from")
            if frm and t.get("family") == "update.status_transition":
                env = fresh()
                if env is None:
                    continue
                _login(env)
                ent, col = es.get("entity"), es.get("status_col")
                rows = env.state.get(ent) or []
                allowed = frm if isinstance(frm, list) else [frm]
                states = next((e.get("_lifecycle", {}).get("states") or []
                               for e in (spec.get("entities") or [])
                               if (e.get("name") or e.get("entity")) == ent), [])
                bad = next((s for s in states if s not in allowed), None)
                if not rows or bad is None or not col:
                    res.append((tn, "transition", "unverifiable", "cannot construct a status not in from"))
                else:
                    rows[0][col] = bad
                    try:
                        r = env.call(tn, _mkargs(spec, env, t))
                        hit = isinstance(r, dict) and r.get("ok") is False
                        res.append((tn, "transition", "wall_hit" if hit else "wall_missing",
                                    str((r or {}).get("error"))[:70]))
                    except Exception as ex:
                        res.append((tn, "transition", "unverifiable", type(ex).__name__))

            # (5) missing required parameter. The runtime originally did not implement this wall
            #    (so the probe's first round misreported 430 fake walls); a generic guard has since
            #    been added following "fix the runtime infrastructure rather than patch around it",
            #    and real verification is restored here.
            req = g.get("required")
            if req:
                env = fresh()
                if env is None:
                    continue
                _login(env)
                a = _mkargs(spec, env, t)
                dropped = [c for c in req if c in a]
                if not dropped:
                    res.append((tn, "required", "unverifiable", "required parameter not in the synthesized args"))
                else:
                    a.pop(dropped[0], None)
                    try:
                        r = env.call(tn, a)
                        hit = isinstance(r, dict) and r.get("ok") is False
                        res.append((tn, "required", "wall_hit" if hit else "wall_missing",
                                    str((r or {}).get("error"))[:70]))
                    except Exception as ex:
                        res.append((tn, "required", "unverifiable", type(ex).__name__))
        except Exception as _ex:
            # A malformed exec_spec / guards makes the traversal code raise. This used to crash
            # the **whole repo**: the agent's 40 minutes of output lost, with not a single
            # diagnostic — worse than failing it. Now only this one tool is lost, and **the
            # exception text itself is the diagnostic for the agent**.
            res.append((t.get("tool"), "probe_error", "unverifiable", "%s: %s" % (type(_ex).__name__, str(_ex)[:90])))
    return res, notes


def probe(spec, n=3):
    """One full four-layer probe. → report (**contains no sample rows** — the agent reads it, and
    if data were included it might copy it into its own draft seed: contamination leaking in
    through the report)."""
    rep = {"env_id": spec.get("env_id"), "tools": len(spec.get("tools") or []),
           "entities": len(spec.get("entities") or [])}
    # **No normalization**: the spec goes into the runtime as is, so the probe sees exactly what
    # the runtime sees. Whether a shape is right is the runtime's call (L2 really calls each tool and
    # records exceptions verbatim), not something predicted here.
    rows = l0(spec)
    rep["l0"] = {"err": [(w, x) for s, w, x in rows if s == "err"][:60],
                 "warn": [(w, x) for s, w, x in rows if s == "warn"][:30],
                 "n_err": sum(1 for s, _, _ in rows if s == "err"),
                 "n_warn": sum(1 for s, _, _ in rows if s == "warn"),
                 # Counted separately: the prompt explicitly says "a wall without evidence must
                 # not be written", so this one is **unrelated to how hard the repo is** — it is
                 # purely whether it was done. Always computed; just never used to drive the loop.
                 "n_no_evidence": sum(1 for sv, _, x in rows
                                      if sv == "warn" and "_evidence.edges" in x)}
    # NOTE: there used to be l1_own here — checking the agent's own smoke seeds. **Removed (in review).**
    # The rows it judged are **wiped wholesale** by `ignite._inject_seeds` at ignition and replaced
    # by the real data: i.e. we were permanently blacklisting whole repos over "a few empty fields
    # in data that never reaches a work order". Observed cost: in a 225-repo batch, 26 died on it,
    # 25 of which **passed every other criterion**.
    # It was not demoted to bookkeeping because **there is no consumer**: using it in the feedback
    # round to make the agent fix seeds that will be discarded burns turns; center is an LLM and
    # judges account problems itself. Bookkeeping with no consumer is dead code.
    ut = under_test(spec, n=n)
    ok, why, env = l1(ut)
    rep["l1"] = {"ok": ok, "why": why}
    if env is None:
        rep["_note"] = "L1 does not build, L2/L3 skipped (**a skip is recorded too**, it is not a pass)"
        return rep
    labels, notes, setup, login = l2(ut)
    cnt = {}
    for v in labels.values():
        cnt[v] = cnt.get(v, 0) + 1
    # Denominator: number of writable tools. The **absolute** count of wrote is not comparable
    # (the agent may delete tools), so look at the ratio; the ratio is meaningful against the
    # **candidate-pool baseline** — hard repos have a low baseline anyway, so this normalizes automatically.
    rep["writable"] = sum(1 for t in (spec.get("tools") or [])
                          if not _is_read(t.get("family") or ""))
    rep["l2"] = {"counts": cnt, "setup": setup, "login": login, "notes": notes[:20],
                 "bad_exec_spec": [k for k, v in labels.items() if v == "bad_exec_spec"],
                 "no_op": sorted(k for k, v in labels.items() if v == "no_op")[:40],
                 "wrong_entity": sorted(k for k, v in labels.items() if v == "wrong_entity")[:20]}
    walls, wnotes = l3(ut)
    wc = {}
    for _, kind, verdict, _ in walls:
        wc["%s/%s" % (kind, verdict)] = wc.get("%s/%s" % (kind, verdict), 0) + 1
    # The fourth element of `walls` is the **reason** (why it was not hit / why no violation could
    # be constructed). This used to keep only the first two elements of wall_missing and drop the
    # reason column entirely — so the concrete "cannot set up" causes were squashed into one
    # `unverifiable` count in the report; the agent could see "N were not verified" but not "not
    # verified because the seed has no row to copy". **When it cannot be judged, say which kind of
    # cannot.**
    _unv = {}
    for _a, _k, _v, _why in walls:
        if _v == "unverifiable" and _k != "probe_error":
            _unv.setdefault(_k, []).append("%s — %s" % (_a, _why))
    rep["l3"] = {"counts": wc,
                 "wall_missing": [(a, b) for a, b, v, _ in walls if v == "wall_missing"][:40],
                 "n_wall_missing": sum(1 for _, _, v, _ in walls if v == "wall_missing"),
                 # probe_error is **not** unverifiable: it means the probe blew up while walking
                 # this tool, the same origin as bad_exec_spec — a spec defect, not a probe
                 # limitation. Reporting them together would teach the agent to treat a class of
                 # real defects as "ignore".
                 "probe_error": [(a, w) for a, k, v, w in walls if k == "probe_error"][:20],
                 "n_probe_error": sum(1 for _, k, _, _ in walls if k == "probe_error"),
                 "unverifiable_why": {k: v[:8] for k, v in _unv.items()},
                 "n_unverifiable": sum(len(v) for v in _unv.values())}
    return rep


if __name__ == "__main__":
    import glob, collections
    C = collections.Counter
    if len(sys.argv) < 2:
        sys.exit("usage: build_probe.py <dir of *.json specs> [limit]")
    src = sys.argv[1]
    files = sorted(glob.glob(src + "/*.json"))
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else len(files)
    e0, w0, l1f, l2c, l3c = C(), C(), C(), C(), C()
    nr = ok1 = 0
    import re
    for f in files[:lim]:
        try:
            spec = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        nr += 1
        try:
            rep = probe(spec)
        except Exception as ex:
            l1f["probe itself crashed: %s" % type(ex).__name__] += 1
            continue
        for _, x in rep["l0"]["err"]:
            e0[re.sub(r"'[^']*'|\"[^\"]*\"|\[[^\]]*\]|\b\d+\b", "·", x)[:78]] += 1
        for _, x in rep["l0"]["warn"]:
            w0[re.sub(r"'[^']*'|\"[^\"]*\"|\[[^\]]*\]|\b\d+\b", "·", x)[:78]] += 1
        if rep["l1"]["ok"]:
            ok1 += 1
        else:
            l1f[re.sub(r"'[^']*'|\b\d+\b", "·", rep["l1"]["why"])[:88]] += 1
        for k, v in (rep.get("l2") or {}).get("counts", {}).items():
            l2c[k] += v
        for k, v in (rep.get("l3") or {}).get("counts", {}).items():
            l3c[k] += v
    print("=== %d repos ===" % nr)
    print("\n--- L0 structure ---")
    for k, v in e0.most_common(12):
        print("   err  %6d  %s" % (v, k))
    for k, v in w0.most_common(5):
        print("   warn %6d  %s" % (v, k))
    print("\n--- L1 seed self-consistency --- passed %d / %d" % (ok1, nr))
    for k, v in l1f.most_common(8):
        print("   %5d  %s" % (v, k))
    print("\n--- L2 real driving ---")
    tot = sum(l2c.values())
    for k, v in l2c.most_common():
        print("   %-14s %6d  %.1f%%" % (k, v, 100.0 * v / tot if tot else 0))
    print("\n--- L3 wall hits ---")
    for k, v in l3c.most_common(14):
        print("   %-34s %6d" % (k, v))
