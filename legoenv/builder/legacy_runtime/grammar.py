#!/usr/bin/env python3.12
"""The **condition language** shared across all of LegoEnv: syntax / normalization / negation / site declarations.

The shape follows OPA's UCAST (a discriminated union with `node` as the tag; one flat operator table), operator names and error
algebra follow CEL, and `Count` fills the document-level slot that UCAST defines but never implemented.

This module **is only about syntax**: it does not touch the env or the session and does not read from disk. External information needed
for evaluation is passed in by the caller as a `resolve(value_node, row) -> actual value` callback (see `eval_pred`). This way the runtime,
build_probe and the miner-side static checks share the same semantics without depending on one another.

━━ Three-valued logic is the backbone of the language ━━
If either side of a comparison cannot be resolved (NULL, missing argument, unresolvable reference), the result is **UNKNOWN**, not False.
"Cannot decide != not satisfied": silently treating UNKNOWN as False amounts to a wall that randomly disappears.
How UNKNOWN is handled **belongs to the site, not to the operator table**:

    exec_spec.filter    UNKNOWN → False    the row is not returned (SQL WHERE semantics)
    constraints         UNKNOWN → True     treated as satisfied (SQL CHECK semantics)
    preconditions       UNKNOWN → raise    a guard must never silently disappear
    postconditions      UNKNOWN → raise    a verifier predicate must never silently be true
    DAG `at`            not applicable     it is a Select, not a predicate

Previously `contains` was kept out of the predicate side to make that side "strict"; that put strictness in the operator table,
and lost on both ends: tasks the read side can express could not be verified, while the places that should be strict (unresolvable) still passed silently.
"""

import json
import re


class GrammarError(Exception):
    """Grammar error: invalid shape, unknown operator, or a site that does not allow it. **Always explicit, never a silent downgrade.**"""


class Unknown:
    """The third value of three-valued logic. A singleton; test with `is UNKNOWN`."""
    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __bool__(self):
        raise GrammarError("UNKNOWN cannot be used directly as a truth value; the site's acceptance boundary must handle it")

    def __repr__(self):
        return "UNKNOWN"


UNKNOWN = Unknown()


# ───────────────────────── FieldOp: one flat operator table (closed) ─────────────────────────
# Merges the old `op` axis (eq/in/range/...) and the `mode` axis (exact/substring/ilike/...).
# Each operator has three parts: arity (2 = needs a right operand, 1 = unary), evaluation, negation.

def _cmp(f):
    """Wrapper for numeric/string comparison: either side None → UNKNOWN (NULL does not take part in ordering).
    If the types are not comparable, try numeric coercion first (CSV-seeded columns are all strings); if that still fails → UNKNOWN."""
    def g(a, b):
        if a is None or b is None:
            return UNKNOWN
        try:
            return bool(f(a, b))
        except TypeError:
            na, nb = _num(a), _num(b)
            if na is None or nb is None:
                return UNKNOWN
            return bool(f(na, nb))
    return g


def _num(x):
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return x
    if isinstance(x, str):
        try:
            return float(x)
        except ValueError:
            return None
    return None


def _sub(a, b, fold=False):
    """Substring. Either side None → UNKNOWN (not False)."""
    if a is None or b is None:
        return UNKNOWN
    sa, sb = str(a), str(b)
    if fold:
        sa, sb = sa.lower(), sb.lower()
    return sb in sa


def _member(a, b):
    if b is None:
        return UNKNOWN
    if not isinstance(b, (list, tuple, set)):
        raise GrammarError("the right operand of in / nin must be a list, got %r" % (b,))
    return a in b


FIELD_OPS = {
    #  op            arity  eval
    "eq":           (2, lambda a, b: UNKNOWN if (a is None) != (b is None) else a == b),
    "ne":           (2, lambda a, b: UNKNOWN if (a is None) != (b is None) else a != b),
    "lt":           (2, _cmp(lambda a, b: a < b)),
    "lte":          (2, _cmp(lambda a, b: a <= b)),
    "gt":           (2, _cmp(lambda a, b: a > b)),
    "gte":          (2, _cmp(lambda a, b: a >= b)),
    "in":           (2, _member),
    "nin":          (2, lambda a, b: UNKNOWN if _member(a, b) is UNKNOWN else not _member(a, b)),
    "contains":     (2, lambda a, b: _sub(a, b)),
    "icontains":    (2, lambda a, b: _sub(a, b, fold=True)),
    "startswith":   (2, lambda a, b: UNKNOWN if a is None or b is None else str(a).startswith(str(b))),
    "endswith":     (2, lambda a, b: UNKNOWN if a is None or b is None else str(a).endswith(str(b))),
    "is_null":      (1, lambda a, _b=None: a is None),
    "is_not_null":  (1, lambda a, _b=None: a is not None),
}

#: Operators with a direct dual. The negator prefers these; they help build_probe construct counterexamples better than wrapping in `not`.
OP_DUAL = {
    "eq": "ne", "ne": "eq",
    "lt": "gte", "gte": "lt",
    "gt": "lte", "lte": "gt",
    "in": "nin", "nin": "in",
    "is_null": "is_not_null", "is_not_null": "is_null",
}
# contains / icontains / startswith / endswith have no single-operator dual; negation wraps them in not.

CARD_OPS = {"eq", "ne", "lt", "lte", "gt", "gte"}

#: Closed vocabulary for `select.get.agg`. **It is the same set as the runtime's `_agg1`**: the runtime has long implemented
#: count / count_distinct / sum / avg / min / max, while this list used to artificially allow only count,
#: so a condition like "order total exceeds X" could not be expressed at the grammar level. The vocabulary lives here, the implementation there,
#: and test_agg_vocab pins the two together.
AGGS = {"count", "count_distinct", "sum", "avg", "min", "max"}


# ───────────────────────── The five sites: top-level type · Γ · acceptance boundary ─────────────────────────
# Γ = which Value kinds may appear at this site. `row` means another column of the same row ({"col":...}).

FALSE_ON_UNKNOWN = "false"     # SQL WHERE
TRUE_ON_UNKNOWN = "true"       # SQL CHECK
RAISE_ON_UNKNOWN = "raise"     # guards / verifier predicates

SITES = {
    "filter": {
        "top": ("field", "and", "or", "not", "count"),
        "gamma": {"row", "arg", "session", "actor", "now", "db"},
        "unknown": FALSE_ON_UNKNOWN,
        "why": "read-side filter: one condition fewer = a wider result, so an undecidable row is not returned",
    },
    "constraint": {
        "top": ("field", "and", "or", "not", "count"),
        "gamma": {"row", "now", "db"},                       # no arg: constraints are independent of the call
        "unknown": TRUE_ON_UNKNOWN,
        "why": "entity constraint: SQL CHECK semantics, undecidable counts as satisfied (otherwise a NULL column would fail the whole table)",
    },
    "precondition": {
        "top": ("count",),
        # Γ is almost the full set. Measured on 338 specs: 3316 guards use $arg (ownership guards such as "you can only delete your own board"
        # need the argument to locate the row anyway), and 1 uses a same-row column reference. **What separates guards from the read side is not Γ
        # but the acceptance boundary** (raise vs false). This is the full form of the rule "strictness belongs to the site, not to the operator table":
        # Γ should not be used as a stand-in for strictness either.
        "gamma": {"row", "arg", "session", "actor", "now", "db"},
        "unknown": RAISE_ON_UNKNOWN,
        "why": "tool guard: undecidable != unsatisfied. Silently letting it pass = a wall that randomly disappears",
    },
    "postcondition": {
        "top": ("count",),
        "gamma": {"now", "db"},
        "unknown": RAISE_ON_UNKNOWN,
        "why": "task verdict: undecidable must not silently become true, or it yields an unverified sample",
    },
    # Site for `provides` / delta assertions: evaluated **after the operation has run with its arguments**, so arguments, session
    # and actor are still in Γ (unlike postconditions, which only have {db, now}),
    # plus `was` (the previous world). This is the only site that allows delta: guards run before the operation,
    # so "before" means nothing to them; the same holds for read-side filters and entity constraints.
    "provides": {"top": ("count",),
                 "gamma": {"row", "arg", "session", "actor", "now", "db", "was"},
                 "unknown": "raise",
                 "why": "what an operation establishes: undecidable must not silently become true, or the closure would think someone can pass this wall"},
    "at": {
        "top": ("select",),
        "gamma": {"db"},
        "unknown": None,                                      # Select is not a predicate and has no boundary
        "why": "DAG node locator: it selects a row, it does not answer true/false",
    },
}

#: Value kind tag → discriminating key
# `was` = **the value of this column of this row before the current operation**. It is the only ingredient of delta assertions:
#     increased ≡ {"op":"gt",  "value":{"was":"view_count"}}
#     decreased ≡ {"op":"lt",  "value":{"was":"..."}}
#     changed   ≡ {"op":"ne",  "value":{"was":"..."}}
#     not less  ≡ {"op":"gte", "value":{"was":"balance"}}   ← adding operators cannot express this; this can
# **Deliberately no new operators**: the operator table stays at 14, and delta lives in the "where does this value come from" slot, which is
# Value's job anyway. It composes with every comparison operator for free, and legal sites are governed by Γ with no extra rules.
# Corpus evidence: the miner invented `changed` / `increased` / `increment` (view_count / answer_count / invite_user_id
# in the answer repo), showing this is a real need that simply could not be expressed.
# `expr` = **arithmetic**: `{"expr": {"col": c, "op": "+", "by": <Value>}}`.
# It always references a column of the same row, so its kind is row: it is legal wherever {col} is legal,
# **decided uniformly by Γ, with no special exceptions for "whichever side is easier to implement"**.
#   write side      sets: {"answer_count": {"expr": {"col":"answer_count","op":"+","by":{"lit":1}}}}
#   condition side  {"col":"balance","op":"gte","value":{"expr":{"col":"price","op":"*","by":{"col":"qty"}}}}
# Corpus evidence: 235 tautologies of the form `{col: {"col": same column}}`, all trying to say "this column changes relative to itself"
# but unable to, so they wrote a no-op and lost "by how much" along the way.
VALUE_KINDS = {"col": "row", "expr": "row", "was": "was", "arg": "arg", "session": "session",
               "actor": "actor", "now": "now"}

_EXPR_OPS = ("+", "-", "*", "/")
MAX_SELECT_DEPTH = 2          # Subqueries do not get unlimited depth. **What is counted is the number of nested selects**:
                              #  a top-level count(select) is level 1, another select inside its condition
                              #  is level 2, and anything deeper is rejected.
MAX_JSON_PATH_HOPS = 2        # `custom_attributes.subject`; the first segment must be a real column


# ───────────────────────── Validation ─────────────────────────

def value_kind(v):
    """Value → kind tag ('scalar' / 'row' / 'arg' / 'session' / 'actor' / 'now' / 'db')."""
    if not isinstance(v, dict):
        return "scalar"
    if v.get("node") == "select":
        return "db"
    if "const" in v and len(v) == 1:
        return "scalar"          # Non-scalar literal (JSON object/array); semantically just a constant
    for k, kind in VALUE_KINDS.items():
        if k in v:
            return kind
    raise GrammarError("unrecognized Value shape: %r" % (v,))


def validate(node, site, _depth=0):
    """Validate a tree against a site. Anything invalid raises GrammarError (no bool return: silent validation is no validation)."""
    s = SITES.get(site)
    if s is None:
        raise GrammarError("unknown site %r (valid: %s)" % (site, sorted(SITES)))
    _walk(node, s, site, _depth, top=True)
    return True


def _walk(n, s, site, depth, top=False):
    if not isinstance(n, dict):
        raise GrammarError("[%s] node must be an object, got %r" % (site, n))
    kind = n.get("node")
    if kind is None:
        raise GrammarError("[%s] node is missing the `node` tag: %r" % (site, n))
    if top and kind not in s["top"]:
        raise GrammarError("[%s] top level must be %s, got %r" % (site, "/".join(s["top"]), kind))

    if kind in ("and", "or"):
        args = n.get("args")
        if not isinstance(args, list) or not args:
            raise GrammarError("[%s] args of %s must be a non-empty list" % (site, kind))
        for a in args:
            _walk(a, s, site, depth)
    elif kind == "not":
        args = n.get("args")
        if not isinstance(args, list) or len(args) != 1:
            raise GrammarError("[%s] args of not must have exactly one item" % site)
        _walk(args[0], s, site, depth)
    elif kind == "field":
        col = n.get("col")
        if not isinstance(col, str) or not col:
            raise GrammarError("[%s] field is missing col: %r" % (site, n))
        if col.count(".") > MAX_JSON_PATH_HOPS - 1:
            raise GrammarError("[%s] in-column JSON path allows at most two hops: %r" % (site, col))
        op = n.get("op")
        meta = FIELD_OPS.get(op)
        if meta is None:
            raise GrammarError("[%s] unknown operator %r (valid: %s)" % (site, op, " ".join(sorted(FIELD_OPS))))
        arity = meta[0]
        if arity == 1:
            if "value" in n and n["value"] is not None:
                raise GrammarError("[%s] %s is a unary operator and must not carry a value" % (site, op))
        else:
            if "value" not in n:
                raise GrammarError("[%s] %s is missing value" % (site, op))
            _check_value(n["value"], s, site, depth)
        if n.get("optional") and s["unknown"] != FALSE_ON_UNKNOWN:
            # optional is read-side sugar. The assertion-side Γ has no arg at all, so this sugar cannot even trigger there;
            # writing it anyway would move "one fewer condition = broader" onto the guard side = a wall that can disappear.
            raise GrammarError("[%s] optional is only valid on the read side" % site)
    elif kind == "count":
        sel = n.get("select")
        if not isinstance(sel, dict):
            raise GrammarError("[%s] count is missing select" % site)
        _walk(sel, s, site, depth)
        if n.get("op") not in CARD_OPS:
            raise GrammarError("[%s] count.op must be one of %s, got %r" % (site, "/".join(sorted(CARD_OPS)), n.get("op")))
        if not isinstance(n.get("n"), int) or isinstance(n.get("n"), bool):
            raise GrammarError("[%s] count.n must be an integer: %r" % (site, n.get("n")))
    elif kind == "select":
        if depth >= MAX_SELECT_DEPTH:
            raise GrammarError("[%s] subquery nesting exceeds %d levels" % (site, MAX_SELECT_DEPTH))
        if not isinstance(n.get("entity"), str) or not n["entity"]:
            raise GrammarError("[%s] select is missing entity" % site)
        w = n.get("where")
        if w is not None:
            _walk(w, s, site, depth + 1)
        g = n.get("get")
        if g is not None:
            if not isinstance(g, dict) or not (("col" in g) or ("agg" in g)):
                raise GrammarError("[%s] get must give either {col} (take this column) or {agg} (aggregate): %r"
                                   % (site, g))
            if "agg" in g:
                if g["agg"] not in AGGS:
                    raise GrammarError("[%s] get.agg must be one of %s, got %r"
                                       % (site, "/".join(sorted(AGGS)), g["agg"]))
                if g["agg"] != "count" and not g.get("col"):
                    raise GrammarError("[%s] %s must name the column to aggregate (only count may omit col)"
                                       % (site, g["agg"]))
    else:
        raise GrammarError("[%s] unknown node %r" % (site, kind))


def _check_value(v, s, site, depth):
    kind = value_kind(v)
    if kind == "scalar":
        return
    if kind not in s["gamma"]:
        raise GrammarError("[%s] %s is not allowed here (Γ = %s) -- %s"
                           % (site, kind, " · ".join(sorted(s["gamma"])), s["why"]))
    if kind == "db":
        _walk(v, s, site, depth)
    if "expr" in v:
        e = v["expr"] if isinstance(v["expr"], dict) else {}
        if e.get("op") not in _EXPR_OPS:
            raise GrammarError("[%s] unknown arithmetic operator %r" % (site, e.get("op")))
        if not e.get("col"):
            raise GrammarError("[%s] expr must name the column it is based on" % site)
        # **The ban on time arithmetic must be enforced here, not only in prompt prose.**
        # `by` validates its value recursively, so {"sym": "$now"} would compile, and then in the runtime
        # `_expr_value` would do arithmetic on a time string, the types would not match, it would **silently** return UNKNOWN,
        # and the caller would collapse UNKNOWN into False. An assertion meant to express "how long until it expires"
        # would become one that never holds, with zero errors along the way.
        # Rule: if it can be expressed and downstream can use it → extend the grammar; if it can be expressed but we do not support it → **reject loudly**.
        # Time arithmetic is the latter ("$now is the only symbolic constant, and time arithmetic is forbidden").
        if value_kind(e.get("by")) == "now":
            raise GrammarError("[%s] expr.by must not be $now -- time arithmetic is forbidden, "
                               "and at runtime it would silently become UNKNOWN" % site)
        _check_value(e.get("by"), s, site, depth)      # by itself must also be valid
    if kind == "actor" and v.get("actor") != "id":
        raise GrammarError("[%s] $actor only has .id; use a select clause to read other columns" % site)


# ───────────────────────── Evaluation (three-valued) ─────────────────────────

def eval_pred(n, row, resolve, site=None):
    """→ True / False / UNKNOWN。

    `resolve(value_node, row)` is supplied by the caller: it resolves a non-scalar Value to an actual value; if it cannot, it should return
    UNKNOWN (do not raise, and do not return None, since None is a legal column value).
    If `site` is given, UNKNOWN is collapsed to a bool or raised according to that site's acceptance boundary.
    """
    r = _eval(n, row, resolve)
    if site is None:
        return r
    return settle(r, site)


def settle(r, site):
    """Handle UNKNOWN according to the site's acceptance boundary."""
    if r is not UNKNOWN:
        return bool(r)
    policy = SITES[site]["unknown"]
    if policy == FALSE_ON_UNKNOWN:
        return False
    if policy == TRUE_ON_UNKNOWN:
        return True
    raise GrammarError("[%s] condition is undecidable (operand could not be resolved) -- %s" % (site, SITES[site]["why"]))


def _eval(n, row, resolve):
    kind = n.get("node")
    if kind == "and":
        seen_unknown = False
        for a in n["args"]:
            r = _eval(a, row, resolve)
            if r is False:
                return False            # one branch definitely false → whole thing false, even if other branches are UNKNOWN
            if r is UNKNOWN:
                seen_unknown = True
        return UNKNOWN if seen_unknown else True
    if kind == "or":
        seen_unknown = False
        for a in n["args"]:
            r = _eval(a, row, resolve)
            if r is True:
                return True
            if r is UNKNOWN:
                seen_unknown = True
        return UNKNOWN if seen_unknown else False
    if kind == "not":
        r = _eval(n["args"][0], row, resolve)
        return UNKNOWN if r is UNKNOWN else (not r)
    if kind == "field":
        arity, f = FIELD_OPS[n["op"]]
        lv = _get_col(row, n["col"])
        if arity == 1:
            return f(lv)
        rv = n["value"]
        if isinstance(rv, dict):
            rv = resolve(rv, row)
        if rv is UNKNOWN:
            # optional is read-side sugar: if the argument is not given, the clause is treated as absent
            return True if n.get("optional") else UNKNOWN
        return f(lv, rv)
    if kind == "count":
        rows = resolve(n["select"], row)
        if rows is UNKNOWN:
            return UNKNOWN
        arity, f = FIELD_OPS[n["op"]]
        return f(len(rows), n["n"])
    raise GrammarError("evaluation hit unknown node %r" % kind)


def _get_col(row, col):
    """Get a column value, supporting an in-column JSON path of at most two hops (the first segment must be a real column)."""
    if "." not in col:
        return (row or {}).get(col)
    head, _, tail = col.partition(".")
    v = (row or {}).get(head)
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return None
    return v.get(tail) if isinstance(v, dict) else None


# ───────────────────────── Generic negator (foundation for the counterexample builders) ─────────────────────────

def negate(n):
    """→ A new tree that is the semantic negation. **Negating `and` needs only one branch broken; negating `or` needs every branch broken**,
    so `not and` returns an `or` that the caller (build_probe) enumerates branch by branch, and `not or` returns an `and`
    that the caller must break entirely. This is De Morgan, expressed structurally so downstream need not unpack another DNF layer."""
    kind = n.get("node")
    if kind == "and":
        return {"node": "or", "args": [negate(a) for a in n["args"]]}
    if kind == "or":
        return {"node": "and", "args": [negate(a) for a in n["args"]]}
    if kind == "not":
        return n["args"][0]
    if kind == "field":
        dual = OP_DUAL.get(n["op"])
        if dual:
            m = dict(n)
            m["op"] = dual
            m.pop("optional", None)     # optional is meaningless after negation: what we want is exactly for it not to hold
            return m
        return {"node": "not", "args": [dict(n, **{"optional": False}) if n.get("optional") else n]}
    if kind == "count":
        dual = OP_DUAL.get(n["op"])
        if dual:
            return dict(n, op=dual)
        return {"node": "not", "args": [n]}
    raise GrammarError("negation hit unknown node %r" % kind)


# ═══════════════════════ Normalization: the six legacy surface syntaxes of one language ═══════════════════════
# Measured on 340 repo_specs + 285 fork boards.
# Normalization is **one-way**: old → new. There is no reverse path; keeping a return ticket would allow two shapes to coexist.

_MODE_TO_OP = {                    # the old read-side `mode` axis
    "exact": "eq", "in": "in",
    "substring": "icontains", "ilike": "icontains",
    "geo_contains": "is_not_null",     # best-effort, same as the old implementation: degrade to an existence check
}
_OP_ALIAS = {"neq": "ne"}          # old State uses neq


def _v_state(v):
    """Old State Value ({lit}/{col}/{sym}/{ref}/{_legacy}) → new Value."""
    if not isinstance(v, dict):
        return v
    if "lit" in v:
        # Scalars are returned as-is (literals are bare values in the IR). **Non-scalars must be wrapped explicitly**:
        # a bare dict in the IR is a "node", so literal and node collide in shape and `value_kind({})` can only raise
        # "unrecognized Value form". Measured case: cloudserver's `Object.deleteTagging`
        # sets `tags` to `{}` (clearing a JSON column). That is a real, checkable write;
        # being unable to express it is a gap in the grammar, not a miner mistake.
        lv = v["lit"]
        return lv if (lv is None or isinstance(lv, (str, int, float, bool))) else {"const": lv}
    if "col" in v:
        return {"col": v["col"]}
    if "was" in v:
        return {"was": v["was"]}
    if "expr" in v:
        e = v["expr"] if isinstance(v["expr"], dict) else {}
        if e.get("op") not in _EXPR_OPS:
            raise GrammarError("unknown arithmetic operator %r (valid: %s)" % (e.get("op"), " ".join(_EXPR_OPS)))
        return {"expr": {"col": e.get("col"), "op": e.get("op"), "by": _v_state(e.get("by"))}}
    if "sym" in v:
        if v["sym"] == "$now":
            return {"now": True}
        raise GrammarError("unknown symbolic constant %r" % v["sym"])
    if "from" in v:
        # **Source-syntax subquery / aggregation**: `{"from": {"entity", "where": [clauses], "get"}}`.
        # State Values used to be only {lit}/{ref}/{col}/{sym}, which cannot say "a column of another table"
        # or "the total of those rows". The IR has long had a select node (with get.col / get.agg),
        # and the runtime has long implemented it; only the source-syntax entry point was missing. This translates it directly.
        #   get: "col_name"  or  {"col": ...}  or  {"agg": "sum", "col": "amount"}
        sq = v["from"] if isinstance(v["from"], dict) else {}
        w = [_leaf(c.get("col"), c.get("op", "eq"), _v_state(c.get("value")))
             for c in (sq.get("where") or []) if isinstance(c, dict)]
        g = sq.get("get")
        g = {"col": g} if isinstance(g, str) else (g if isinstance(g, dict) else {"col": "id"})
        return {"node": "select", "entity": sq.get("entity"), "where": _and(w), "get": g}
    if "ref" in v:
        r = str(v["ref"])
        if r.startswith("$arg."):
            return {"arg": r[5:]}
        if r == "$actor.id":
            return {"actor": "id"}
        if r.startswith("$session."):
            return {"session": r[9:]}
        if r.startswith("$subject."):
            # Identifier of the subject row: guards run before the target row is located, so it can only come from the arguments, same as the old implementation.
            return {"arg": r[9:]}
        raise GrammarError("unknown reference %r" % r)
    if "_legacy" in v:
        return _v_filter(v["_legacy"])
    if any(k.startswith("$") for k in v):
        # Read-side forms leaked into State (measured: 10 occurrences of {"$session":"account_id"}). Mixing two surface syntaxes is exactly
        # what this module is meant to eliminate; it is caught here so that only one form remains after normalization.
        return _v_filter(v)
    raise GrammarError("unrecognized State Value: %r" % (v,))


def _v_filter(v):
    """Old read-side val ({$arg}/{$const}/{$session}/{$ref}/{$subquery}) → new Value."""
    if not isinstance(v, dict):
        return v
    if "$arg" in v:
        return {"arg": str(v["$arg"])}
    if "$const" in v:
        return v["$const"]
    if "$session" in v:
        k = str(v["$session"])
        return {"actor": "id"} if k == "account_id" else {"session": k}
    if "$session.account_id" in v:
        return {"actor": "id"}
    if "$subquery" in v:
        sq = v["$subquery"]
        where = [_leaf(k, "eq", _v_filter(vv)) for k, vv in (sq.get("where") or {}).items()]
        return {"node": "select", "entity": sq.get("entity"),
                "where": _and(where),
                "get": {"col": sq.get("select", "id")}}
    if "$ref" in v:
        # Old references like {"$ref": "Entity.col"}: left to the caller to resolve within Γ; syntactically treated as a db reference
        raise GrammarError("$ref has no new-form equivalent; rewrite it as a select according to its actual semantics: %r" % (v,))
    raise GrammarError("unrecognized filter val: %r" % (v,))


def _leaf(col, op, value, optional=False):
    n = {"node": "field", "col": col, "op": _OP_ALIAS.get(op, op)}
    if FIELD_OPS.get(n["op"], (2,))[0] == 2:
        n["value"] = value
    if optional:
        n["optional"] = True
    return n


def _and(args):
    args = [a for a in args if a]
    if not args:
        return None
    return args[0] if len(args) == 1 else {"node": "and", "args": args}


def from_state(st):
    """(1) State `{entity, scope, card}` → `Count`. 5302 nodes / 9088 clauses."""
    if not isinstance(st, dict):
        raise GrammarError("State must be an object: %r" % (st,))
    where = []
    for cl in (st.get("scope") or []):
        if not isinstance(cl, dict):
            raise GrammarError("scope clause must be an object: %r" % (cl,))
        where.append(_leaf(cl.get("col"), cl.get("op", "eq"), _v_state(cl.get("value"))))
    card = st.get("card") or "exists"
    if isinstance(card, str):
        alias = {"exists": ("gte", 1), "not_exists": ("eq", 0)}.get(card)
        if alias is None:
            raise GrammarError("unknown card alias %r" % card)
        op, n = alias
    else:
        op, n = card.get("op", "gte"), int(card.get("n", 1))
    out = {"node": "count",
           "select": {"node": "select", "entity": st.get("entity"), "where": _and(where)},
           "op": _OP_ALIAS.get(op, op), "n": n}
    # **The rejection message must be carried over too.** What is translated here is logic; `_msg` is not logic but what this wall says when hit,
    # so nobody minded it during translation: it was lost on every compile, and neither end reported an error. The agent put it in the right place,
    # promote deleted nothing, the runtime accepts both shapes; only this one translation step dropped a field.
    # Measured on 2026-09-06: corteza's 118 messages (each using the app's own vocabulary)
    # all vanished at seal time; only the IR remained in the cache and the runtime fell back to the generic default message.
    # The runtime's `first_msg = st.get("_msg")` reads it equally from the IR shape, so carrying it over takes effect immediately.
    _m = st.get("_msg") or st.get("message")
    if _m:
        out["_msg"] = _m
    return out


def from_filter(f):
    """(2) Read-side `exec_spec.filter` → `Pred`. 361 clauses.
    `range` is retired: it is split into two clauses, gte + lte."""
    if not f:
        return None
    if isinstance(f, dict) and f.get("op") in ("and", "or", "not"):
        args = [from_filter(c) for c in (f.get("clauses") or [])]
        args = [a for a in args if a]
        if not args:
            return None
        if f["op"] == "not":
            return {"node": "not", "args": args[:1]}
        return args[0] if len(args) == 1 and f["op"] == "and" else {"node": f["op"], "args": args}
    if "col" not in f:
        # Old-style equality where-map {column: value} (measured: 13 occurrences). With no col key and not and/or/not,
        # this is the only possibility; expand it directly into a conjunction of equalities.
        return _and([_leaf(k, "eq", _v_filter(vv)) for k, vv in f.items()])
    col = f.get("col")
    mode = f.get("mode", "exact")
    optional = bool(f.get("optional"))
    raw = f.get("val")
    if mode == "range":
        val = raw if isinstance(raw, dict) and ("min" in raw or "max" in raw) else None
        if val is None:                       # in the old implementation the val of range was often a scalar → degrade to equality
            return _leaf(col, "eq", _v_filter(raw), optional)
        parts = []
        if val.get("min") is not None:
            parts.append(_leaf(col, "gte", _v_filter(val["min"]), optional))
        if val.get("max") is not None:
            parts.append(_leaf(col, "lte", _v_filter(val["max"]), optional))
        return _and(parts)
    op = _MODE_TO_OP.get(mode) or (mode if mode in FIELD_OPS else None)
    if op is None:
        raise GrammarError("unknown filter mode %r" % mode)
    if FIELD_OPS[op][0] == 1:
        return _leaf(col, op, None, optional)
    return _leaf(col, op, _v_filter(raw), optional)


def from_constraint(c):
    """(3)(4) `entities[].constraints` check / conditional → `Pred`. 80 + 36 entries.

    conditional is an **implication**: `if → then` ≡ `or(not(and if), and then)`.
    The clauses are State clauses already, so both share one leaf constructor; this is exactly the evidence that "they are not independent semantics".
    """
    if not isinstance(c, dict):
        raise GrammarError("constraint must be an object: %r" % (c,))
    kind = c.get("kind")
    if kind == "check":
        left = c.get("left") or {}
        col = left.get("col") if isinstance(left, dict) else left
        right = c.get("right")
        return _leaf(col, c.get("op", "eq"),
                     _v_state(right) if isinstance(right, dict) else right)
    if kind == "conditional":
        pre = _and([_leaf(x.get("col"), x.get("op", "eq"), _v_state(x.get("value")))
                    for x in (c.get("if") or [])])
        post = _and([_leaf(x.get("col"), x.get("op", "eq"), _v_state(x.get("value")))
                     for x in (c.get("then") or [])])
        if pre is None:
            return post
        if post is None:
            return {"node": "not", "args": [pre]}
        return {"node": "or", "args": [{"node": "not", "args": [pre]}, post]}
    if kind == "unique":
        raise GrammarError("unique is not a condition, it is index semantics -- not part of this language")
    raise GrammarError("unknown constraint kind %r" % kind)


def from_postcondition(p):
    """(5) The four verifier operators → `Count`. 304 entries.

    `exists / not_exists / field_eq / count_gte` are four special cases of `Count`, retired into syntactic sugar:
        exists     → count(select where …) gte 1
        not_exists → count(…)              eq  0
        field_eq   → count(where … and col=value) gte 1
        count_gte  → count(…)              gte n
    """
    if not isinstance(p, dict):
        raise GrammarError("postcondition pred must be an object: %r" % (p,))
    op = p.get("op")
    where = [_leaf(k, "eq", v) for k, v in (p.get("where") or {}).items()]
    if op == "field_eq":
        if "col" not in p:
            raise GrammarError("field_eq is missing col: %r" % (p,))
        where.append(_leaf(p["col"], "eq", p.get("value")))
        cop, n = "gte", 1
    elif op == "exists":
        cop, n = "gte", 1
    elif op == "not_exists":
        cop, n = "eq", 0
    elif op == "count_gte":
        if not isinstance(p.get("value"), int):
            raise GrammarError("value of count_gte must be an integer: %r" % (p,))
        cop, n = "gte", int(p["value"])
    elif op == "state":
        return from_state(p.get("scope") or p)
    else:
        raise GrammarError("unknown postcondition op %r" % op)
    return {"node": "count",
            "select": {"node": "select", "entity": p.get("entity"), "where": _and(where)},
            "op": cop, "n": n}


_SLOT_RE = re.compile(r"^\s*([A-Za-z_][\w]*(?:__[\w]+)?)\s*\.\s*([\w]+)\s*$")


def from_slot(slot, where=None):
    """(6) DAG `slot` free-form string `"Entity.column"` → `Select`. 1369 nodes, 35% unparseable.

    Unparseable **raises**, with no fallback: a fallback is exactly why those 35% went unnoticed for so long.
    `where` is attached if given (the old slot had no locating information; this is what the new `at` adds over it).
    """
    if not isinstance(slot, str):
        raise GrammarError("slot must be a string: %r" % (slot,))
    m = _SLOT_RE.match(slot)
    if not m:
        raise GrammarError("slot does not parse as Entity.column: %r" % (slot,))
    return {"node": "select", "entity": m.group(1),
            "where": where, "get": {"col": m.group(2)}}


# ═══════════════════════ Counterexample / example builders (inverse solving) ═══════════════════════
# `build_probe` must verify that every guard wall **actually blocks**, by constructing a world where it is false and calling again.
# Operator knowledge exists only here; the probe should not maintain its own table, which would be the "N surface syntaxes" problem again.
# Anything that cannot be constructed returns NOPE and **the caller accounts for it explicitly**: every "cannot construct" = that wall was never verified.

NOPE = object()

_ALPHA = "x"          # padding for string counterexamples: a short string that will not collide with real data


def _other_scalar(v):
    """Construct a value of the same type that is definitely not equal to v."""
    if isinstance(v, bool):
        return not v
    if isinstance(v, (int, float)):
        return v + 1
    if isinstance(v, str):
        return v + "_" + _ALPHA
    if v is None:
        return 0
    return NOPE


def satisfying(op, val):
    """Construct a value that makes `column op val` **true**. → value | NOPE"""
    if op == "eq":
        return val
    if op == "ne":
        return _other_scalar(val)
    if op == "is_null":
        return None
    if op == "is_not_null":
        return _ALPHA
    if op == "in":
        return val[0] if isinstance(val, (list, tuple)) and val else NOPE
    if op == "nin":
        if not isinstance(val, (list, tuple)):
            return NOPE
        base = val[0] if val else _ALPHA
        cand = _other_scalar(base)
        while cand is not NOPE and cand in val:
            cand = _other_scalar(cand)
        return cand
    if op in ("contains", "icontains"):
        return NOPE if val is None else str(val)             # a string contains itself
    if op == "startswith":
        return NOPE if val is None else str(val) + _ALPHA
    if op == "endswith":
        return NOPE if val is None else _ALPHA + str(val)
    if isinstance(val, bool):
        return NOPE                                          # ordering comparisons on bool are meaningless
    if isinstance(val, (int, float)):
        return {"gte": val, "gt": val + 1, "lte": val, "lt": val - 1}.get(op, NOPE)
    if isinstance(val, str) and op in ("gte", "lte"):
        return val                                           # closed-interval boundary: equality satisfies
    return NOPE


def falsifying(op, val):
    """Construct a value that makes `column op val` **false**. → value | NOPE

    Note that "false" is not "UNKNOWN": returning None only truly makes it false for is_not_null;
    elsewhere None gives UNKNOWN, and UNKNOWN at a guard site **raises** rather than passes, so
    the probe would be checking "this wall explodes" rather than "this wall blocks", which are different things.
    """
    if op == "eq":
        return _other_scalar(val)
    if op == "ne":
        return val
    if op == "is_null":
        return _ALPHA
    if op == "is_not_null":
        return None
    if op == "in":
        return satisfying("nin", val)
    if op == "nin":
        return val[0] if isinstance(val, (list, tuple)) and val else NOPE
    if op in ("contains", "icontains"):
        return _ALPHA if val is None else (_ALPHA * (len(str(val)) + 1))[: len(str(val))] \
            if str(val) and set(str(val).lower()) != {_ALPHA} else "zz"
    if op == "startswith":
        return NOPE if val is None else "zz_" + str(val)
    if op == "endswith":
        return NOPE if val is None else str(val) + "_zz"
    if isinstance(val, bool):
        return NOPE
    if isinstance(val, (int, float)):
        return {"gte": val - 1, "gt": val, "lte": val + 1, "lt": val}.get(op, NOPE)
    return NOPE
