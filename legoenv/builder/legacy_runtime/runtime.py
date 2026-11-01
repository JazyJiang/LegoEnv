#!/usr/bin/env python3.12
"""LegoEnv deterministic runtime + verifier predicate engine (v2: behaviour-family executors).

Division of labour (decided): an env is declarative JSON (env-spec); this file is the single shared interpreter (approach A, not per-env codegen).
Each tool declares which **behaviour family** it belongs to plus an **exec_spec** (parameters); the runtime runs the matching
**deterministic parameterised executor** for that family. The executor vocabulary = ~29 dense families grown bottom-up from the library (reference/behavior_families.json).

- Env       — executes the env-spec as a relational state machine. tool.call → guards → dispatch executor by family → mutate state / return result.
- Verifier  — programmatic predicates judge the final state; never calls an LLM.
- Old-format fallback — when a tool has no family, fall back to simplified behaviour by op (create/read/search/update/delete/login) so old env-specs still run.

Families that need external resources (semantic retrieval needs embeddings, actions that really send/probe) → deterministic stubs or precomputed vectors; see each executor.
"""
import json
import grammar as GRAM, copy, sys, hashlib, glob, os, csv, re
from collections import defaultdict
# (the sampler lives in sampler_v1.py; the runtime only executes)

_UNRESOLVED = object()


def _read_rows(raw_path, n):
    """Read the first n rows of real data from a datapool raw directory; return list[dict]. Supports parquet/csv/jsonl."""
    if not raw_path or not os.path.isdir(raw_path):
        return []
    files = (sorted(glob.glob(f"{raw_path}/**/*.parquet", recursive=True))
             or sorted(glob.glob(f"{raw_path}/**/*.csv", recursive=True))
             or sorted(glob.glob(f"{raw_path}/**/*.jsonl", recursive=True)))
    rows = []
    for fp in files:
        if len(rows) >= n:
            break
        try:
            if fp.endswith(".parquet"):
                import pyarrow.parquet as pq
                tbl = pq.read_table(fp)
                for batch in tbl.to_batches(max_chunksize=min(n, 2000)):
                    rows.extend(batch.to_pylist())
                    if len(rows) >= n:
                        break
            elif fp.endswith(".csv"):
                with open(fp, newline="") as f:
                    for r in csv.DictReader(f):
                        rows.append(r)
                        if len(rows) >= n:
                            break
            else:
                with open(fp) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rows.append(json.loads(line))
                        if len(rows) >= n:
                            break
        except Exception:
            continue
    return rows[:n]
AUDIT_DEFAULT = {"created_at", "updated_at", "createdAt", "updatedAt"}


# ---------------------------------------------------------------------------
# $ref / $arg resolution + where matching + nested filter evaluation
# ---------------------------------------------------------------------------
# Current session snapshot, used by resolve() to resolve {"$session":"<key>"} (Env.call refreshes it before dispatch).
# Execution is single-process and serial with no concurrency, so module level is fine; resolve returns _UNRESOLVED when missing.
_SESSION = {}


def resolve(val, state, args=None):
    if isinstance(val, dict) and "$ref" in val:
        r = val["$ref"]
        where = {k: resolve(v, state, args) for k, v in r.get("where", {}).items()}
        rows = query(state, r["entity"], where)
        return rows[0].get(r["col"], _UNRESOLVED) if rows else _UNRESOLVED
    if isinstance(val, dict) and "$session" in val:
        return _SESSION.get(val["$session"], _UNRESOLVED)
    if isinstance(val, dict) and "$arg" in val:
        return (args or {}).get(val["$arg"], _UNRESOLVED)
    if isinstance(val, dict) and "$const" in val:
        return val["$const"]
    return val


def _resolve_expr(val, env, args, fields):
    """Resolve a declarative field expression in exec_spec (used by set_on_create / set_on_spawn / cascade /
    filling fields after a spawn.from_cart copy). Supports:
      scalar / {$const:v} / {$arg:col} / {$session:key} / {$ref:...} —— reuses resolve semantics
      {$resolve:"Entity.col via fk_col"} —— cross-entity column: look up the row in Entity by this row's fields[fk_col], take col
      {$compute:"price*qty"}            —— arithmetic: identifiers such as price/qty come from fields (resolved values)
      {$auto:"10000+max(order_id)+1"}   —— auto-increment: max(<pk>) is the entity's current max pk, +1
    Returns _UNRESOLVED on failure (the caller skips or errors as appropriate)."""
    if not isinstance(val, dict):
        return val
    if "$const" in val:
        return val["$const"]
    if "$arg" in val:
        return (args or {}).get(val["$arg"], _UNRESOLVED)
    if "$session" in val:
        return env.session.get(val["$session"], _UNRESOLVED)
    if "$ref" in val:
        return resolve(val, env.state, args)
    if "$resolve" in val:
        spec_str = val["$resolve"]            # "Entity.col via fk_col"
        try:
            left, fk = spec_str.split(" via ")
            ent, col = left.split(".")
        except Exception:
            return _UNRESOLVED
        fkv = fields.get(fk)
        if fkv is None or fkv is _UNRESOLVED:
            return _UNRESOLVED
        rows = query(env.state, ent, {fk: fkv})
        return rows[0].get(col, _UNRESOLVED) if rows else _UNRESOLVED
    if "$compute" in val:
        expr = val["$compute"]                # "price*qty"
        try:
            import re
            ns = {}
            for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr):
                v = fields.get(t)
                if v is None or v is _UNRESOLVED:
                    # Fallback: if the token is not a column name, find a column in fields containing the token (e.g. "price"->product_price)
                    cand = [fv for fk, fv in fields.items() if t in fk and isinstance(fv, (int, float))]
                    v = cand[0] if cand else None
                if v is None or v is _UNRESOLVED:
                    return _UNRESOLVED
                ns[t] = float(v)
            safe = re.sub(r"[A-Za-z_][A-Za-z0-9_]*", lambda m: str(ns[m.group(0)]), expr)
            if re.search(r"[^0-9.+\-*/() ]", safe):
                return _UNRESOLVED
            return float(eval(safe, {"__builtins__": {}}, {}))
        except Exception:
            return _UNRESOLVED
    if "$auto" in val:
        spec_str = val["$auto"]               # "10000+max(order_id)+1"
        try:
            import re
            mx = re.search(r"max\((\w+)\)", spec_str)
            base = 0
            if mx:
                pk = mx.group(1)
                vals = [r.get(pk) for r in env.state.get(args.get("_spawn_entity", ""), [])]
                vals = [v for v in vals if isinstance(v, (int, float))]
                base = max(vals) if vals else 0
            # Of the form "10000+max(...)+1": take the constants before and after max
            m = re.match(r"(\d+)\s*\+?\s*max\([^)]*\)\s*\+\s*(\d+)", spec_str)
            if m:
                return int(m.group(1)) + base + int(m.group(2))
            return base + 1
        except Exception:
            return _UNRESOLVED
    return val


def query(state, entity, where=None):
    rows = state.get(entity, [])
    if not where:
        return list(rows)
    out = []
    for r in rows:
        if all(v is not _UNRESOLVED and r.get(k) == v for k, v in where.items()):
            out.append(r)
    return out


# ─────────── Unified predicate evaluator (shape = the collector-side State; strict resolution on the guard side) ───────────

_CARD_ALIAS = {"exists": {"op": "gte", "n": 1}, "not_exists": {"op": "eq", "n": 0}}

# The **single source of truth for the operator table is grammar.FIELD_OPS**. Only two
# adaptations are made here; no separate table is maintained:
#   · `neq` is the old name, equivalent to `ne` —— live specs use both, accept both.
#   · grammar comparisons are three-valued; a scope clause is a **row filter**, so under WHERE semantics UNKNOWN → the row
#     does not match. Strictness lives in the outer card assertion and in operand resolution (unresolvable still raises),
#     not in the per-row comparison —— this is how the "strictness belongs to the site" correction is realised.
_OP_ALIAS = {"neq": "ne"}
_STATE_OPS = {**{k: v for k, v in GRAM.FIELD_OPS.items()}, "neq": GRAM.FIELD_OPS["ne"]}
_UNARY_OPS = {k for k, (ar, _f) in GRAM.FIELD_OPS.items() if ar == 1}


class StateError(Exception):
    """State evaluation failure: an operand cannot be resolved, or the spec is wrong. The guard side never swallows it; always explicit —— silently
    letting it pass amounts to a wall that randomly disappears."""



def _expr_value(e, env, args, session, row, ent, resolve1):
    """Arithmetic: `{"col": c, "op": "+", "by": V}` → value | UNKNOWN. **Forward evaluation only, never inverted.**

    Inversion ("build a row so that price*qty <= balance holds") is the probe's job, in build_probe,
    and when it cannot solve it must **loudly** report that it cannot seed —— grammar completeness must not be clipped by solver capability.
    """
    if not isinstance(e, dict):
        return GRAM.UNKNOWN
    a = (row or {}).get(e.get("col"), GRAM.UNKNOWN)
    b = resolve1(e.get("by"))
    if a is GRAM.UNKNOWN or b is GRAM.UNKNOWN or a is None or b is None:
        return GRAM.UNKNOWN
    try:
        op = e.get("op")
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/": return GRAM.UNKNOWN if not b else a / b
    except TypeError:
        return GRAM.UNKNOWN                 # Type mismatch: undecidable, not false
    return GRAM.UNKNOWN


def _was_value(env, ent, row, col):
    """The value of this row's column **before the current operation**. → value | GRAM.UNKNOWN

    If there is no "previous world" (not a write call, or nothing has run yet), or this row is newly created (did not exist before),
    return UNKNOWN —— **not None**. None is a legal column value; using it to mean "absent" would conflate
    "this column used to be empty" with "this row did not exist before".
    """
    before = getattr(env, "_before", None)
    if not before or not ent:
        return GRAM.UNKNOWN
    rid = (row or {}).get("id")
    prev = (before.get(ent) or {}).get(rid)
    if prev is None:
        return GRAM.UNKNOWN                          # Newly created row: did not exist before
    return prev.get(col, GRAM.UNKNOWN)


def state_value(v, env, args, session, row=None, ent=None):
    """{lit} / {ref} / {col} / {sym} / {was} → actual value. Raises StateError if unresolvable."""
    if not isinstance(v, dict):
        return v                                    # A bare scalar is a literal
    if "lit" in v:
        return v["lit"]
    if "was" in v:
        if row is None:
            raise StateError("value.was is only allowed in row-level comparisons: %r" % v)
        return _was_value(env, ent, row, v["was"])
    if "expr" in v:
        if row is None:
            raise StateError("value.expr is only allowed at row level: %r" % v)
        return _expr_value(v["expr"], env, args, session, row, ent,
                           lambda x: state_value(x, env, args, session, row, ent))
    if "col" in v:                                  # Another column of the same row
        if row is None:
            raise StateError("value.col is only allowed in row-level comparisons: %r" % v)
        return row.get(v["col"])
    if "sym" in v:
        if v["sym"] == "$now":
            return env._now
        raise StateError("unknown symbolic constant %r" % v["sym"])
    if "_legacy" in v:
        # $ref / $subquery from old-style where. **Must go through _resolve_filter_val** —— resolve() does not understand
        # $subquery and returns the whole dict unchanged; comparing it with a column value is always False, which shows up as a guard
        # that always refuses, while the error message says "precondition not met", so nobody would suspect the evaluator.
        lv = v["_legacy"]
        r = _resolve_filter_val(lv, env.state, args, session)
        if r is _UNRESOLVED:
            raise StateError("legacy reference could not be resolved: %r" % lv)
        if isinstance(r, dict):
            raise StateError("legacy reference not recognized (returned as-is): %r" % lv)
        return r
    if "ref" in v:
        r = str(v["ref"])
        if r.startswith("$arg."):
            k = r[5:]
            if not args or k not in args:
                raise StateError("argument %s not provided" % k)
            return args[k]
        if r.startswith("$actor."):
            # The protocol gives $actor only .id. The old code checked only the prefix and dropped everything after the dot, so $actor.role
            # (the most common form for permission guards) silently resolved to account_id → always False → the guard always refused.
            if r != "$actor.id":
                raise StateError("$actor only supports .id, got %r; use a scope clause to read other columns" % r)
            a = (session or {}).get("account_id")
            if a is None:
                raise StateError("not logged in, cannot resolve %s" % r)
            return a
        if r.startswith("$session."):
            k = r[9:]
            if not session or k not in session:
                raise StateError("session has no %s" % k)
            return session[k]
        if r.startswith("$subject."):
            # The subject row's identifier. Guards run **before** the executor locates the target row, so it can only come from the args
            # —— nearly all subject identifiers are explicit args anyway (id/slug). Fail strictly if it is missing.
            k = r[9:]
            if args and k in args:
                return args[k]
            raise StateError("cannot resolve %s (subject identifier not in arguments)" % r)
        raise StateError("unknown reference %r" % r)
    raise StateError("unrecognized value shape: %r" % v)


def _num(x):
    """Try numeric coercion. Every column seeded from CSV (csv.DictReader) is a string,
    while spec literals are ints —— without trying, "5" > 0 blows up with a TypeError."""
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


def apply_op(op, a, b):
    """Per-row comparison. → bool

    Three-valued collapse rules (consistent with the grammar's site boundaries):
      · either side is NULL          → UNKNOWN → **False** (WHERE semantics: the row does not match)
      · both non-NULL but incomparable → **raise**. That is not data sparsity but a type error in the spec;
                                 silently treating it as False is yet another wall that can disappear.
    """
    meta = _STATE_OPS.get(op)
    if meta is None:
        raise StateError("unknown scope.op %r (valid: %s)" % (op, " ".join(sorted(_STATE_OPS))))
    arity, f = meta
    # **The operand itself is unresolvable** ≠ a type error. Take the same path as NULL (the row does not match).
    # Origin: `{"was": col}` has no "before" on a newly created row —— asking a row that did not yet exist
    # "did it go up?" is undecidable, not "1 and UNKNOWN are type-incomparable".
    # Raising that error would disguise a true statement (unresolvable) as a false one (the spec has a type error),
    # and would point debugging in entirely the wrong direction.
    # The direction is also conservative: when provides has no "before", it will not claim the state is established.
    if a is GRAM.UNKNOWN or b is GRAM.UNKNOWN:
        return False
    r = f(a) if arity == 1 else f(a, b)
    if r is GRAM.UNKNOWN:
        if a is None or b is None:
            return False
        raise StateError("incomparable types: %r %s %r" % (a, op, b))
    return bool(r)


def match_state_clause(row, cl, env, args, session):
    """A single clause (constraint side; the guard side uses eval_state's pre-resolution path)."""
    if not isinstance(cl, dict):
        raise StateError("scope clause must be an object: %r" % cl)
    return apply_op(cl.get("op", "eq"), row.get(cl.get("col")),
                    state_value(cl.get("value"), env, args, session, row))


def _resolver(env, args, session, ent=None):
    """Operand-resolution callback for the grammar evaluator. Returns UNKNOWN when unresolvable (**never raises, never returns None**
    —— None is a legal column value; using it for "unresolvable" would conflate an empty column with a missing argument)."""
    def r(v, row=None):
        if isinstance(v, dict) and v.get("node") == "select":
            return _select_rows(v, env, args, session)
        if not isinstance(v, dict):
            return v
        if "const" in v and len(v) == 1:
            # Non-scalar literals (JSON objects / arrays). In the IR a bare dict is a node, so literals and nodes
            # collide in shape —— the grammar wraps them explicitly as {"const": …}, unwrapped here. Observed source:
            # cloudserver sets `tags` to `{}` (clearing a JSON column).
            return v["const"]
        if "col" in v:
            return (row or {}).get(v["col"])
        if "was" in v:
            return _was_value(env, ent, row, v["was"])
        if "expr" in v:
            return _expr_value(v["expr"], env, args, session, row, ent, lambda x: r(x, row))
        if "now" in v:
            return env._now
        if "arg" in v:
            return (args or {}).get(v["arg"], GRAM.UNKNOWN) if args and v["arg"] in args else GRAM.UNKNOWN
        if "session" in v:
            return (session or {}).get(v["session"], GRAM.UNKNOWN) if session and v["session"] in session else GRAM.UNKNOWN
        if "actor" in v:
            a = (session or {}).get("account_id")
            return GRAM.UNKNOWN if a is None else a
        return GRAM.UNKNOWN
    return r


def _prescan(node, res):
    """Resolve the **row-independent** operands once before the row loop. → all resolvable?

    This discipline was already argued in the old eval_state docstring and the new path must follow it: $arg/$actor/$session
    are row-independent; resolving them inside the row loop makes strictness **data-dependent** —— if the table is empty, or earlier clauses
    filtered out every row, later unresolvable operands never get evaluated and the guard silently disappears.
    (optional clauses do not count: they are allowed to "not filter when the argument is absent".)
    """
    if not isinstance(node, dict):
        return True
    k = node.get("node")
    if k in ("and", "or", "not"):
        return all(_prescan(a, res) for a in (node.get("args") or []))
    if k == "field":
        v = node.get("value")
        if isinstance(v, dict) and v.get("node") == "select":
            return _prescan(v.get("where"), res)
        if isinstance(v, dict) and "col" not in v and not node.get("optional"):
            return res(v) is not GRAM.UNKNOWN
        return True
    if k == "count":
        return _prescan((node.get("select") or {}).get("where"), res)
    if k == "select":
        return _prescan(node.get("where"), res)
    return True


def _select_rows(sel, env, args, session):
    """Select → list of matching rows (projected to a list of values if get.col is given).

    Two levels of semantics; do not mix them:
      · **operand unresolvable** → the whole Select is UNKNOWN, propagated up for the site to handle (a guard raises).
      · **column value is NULL**  → only this row does not match (WHERE semantics).
    """
    res = _resolver(env, args, session, sel.get("entity"))
    w = sel.get("where")
    if w is not None and not _prescan(w, res):
        return GRAM.UNKNOWN
    rows = env.state.get(sel.get("entity"), []) or []
    hit = [r for r in rows if (GRAM.settle(GRAM._eval(w, r, res), "filter") if w is not None else True)]
    g = sel.get("get") or {}
    if "agg" in g:
        return _agg1(g["agg"], hit, g.get("col"))
    if "col" in g:
        return [r.get(g["col"]) for r in hit]
    return hit


def eval_node(node, env, args, session, site="precondition"):
    """Evaluate a grammar tree (Pred / Count). → bool. UNKNOWN collapses according to the site's acceptance boundary."""
    return GRAM.eval_pred(node, None, _resolver(env, args, session), site=site)


def eval_state(st, env, args, session):
    """"The rows of the entity table that satisfy scope must have a count satisfying card". → bool

    ⚠ **Both shapes are accepted** (transition period of grammar batches 1/3): anything with a `node` key is the new grammar
    (Pred / Count tree) and goes straight to the grammar evaluator; otherwise it takes the old State path below. Both paths share
    the same semantics —— the old path's scope is a flat and, and card is the outer Count.
    Coexistence during the transition is deliberate: after the prompt switches to the new grammar, the 340 specs already on disk need not be regenerated.

    ⚠ Operands **must be resolved before the row loop**. $arg/$actor/$session are row-independent; resolving them in the loop makes
    strictness data-dependent: if the table is empty, or earlier clauses filtered out every row, later unresolvable operands
    never get evaluated —— and the guard silently disappears. That is exactly the failure mode this design claims to eliminate, and the first version
    rebuilt it. As a bonus this also reduces repeated resolution from O(rows×clauses) to O(clauses).
    """
    if not isinstance(st, dict):
        raise StateError("State must be an object: %r" % st)
    if "node" in st:                                  # New grammar: hand the whole tree to grammar
        try:
            return eval_node(st, env, args, session, site="precondition")
        except GRAM.GrammarError as ex:
            raise StateError(str(ex))
    rows = env.state.get(st.get("entity"), []) or []
    scope = st.get("scope") or []
    prepared = []                       # (col, op, value or placeholder, resolve per row?)
    for cl in scope:
        if not isinstance(cl, dict):
            raise StateError("scope clause must be an object: %r" % cl)
        op = cl.get("op", "eq")
        if op not in _STATE_OPS:
            raise StateError("unknown scope.op %r" % op)
        if op in _UNARY_OPS:                              # is_null / is_not_null: no right operand
            prepared.append((cl.get("col"), op, None, False))
            continue
        v = cl.get("value")
        # Row-level Values come in two kinds: {col} (another column of the same row) and {was} (the same row before).
        # Missing was would resolve it only once outside the loop —— comparing every row against the first row's old value.
        per_row = isinstance(v, dict) and ("col" in v or "was" in v or "expr" in v)
        prepared.append((cl.get("col"), op,
                         v if per_row else state_value(v, env, args, session), per_row))
    card = st.get("card") or "exists"
    _c = _CARD_ALIAS.get(card) if isinstance(card, str) else card
    if not isinstance(_c, dict):
        raise StateError("unknown card %r" % card)
    _op, _n = _c.get("op", "gte"), int(_c.get("n", 1))
    n_hit = 0
    for r in rows:
        hit = True
        for col, op, v, per_row in prepared:
            rv = state_value(v, env, args, session, r, st.get("entity")) if per_row else v
            if not apply_op(op, r.get(col), rv):
                hit = False
                break
        if hit:
            n_hit += 1
            if _op == "gte" and n_hit >= _n:
                return True             # Early exit: a hit is enough for exists / gte
    card = st.get("card") or "exists"
    if isinstance(card, str):
        card = _CARD_ALIAS.get(card)
        if card is None:
            raise StateError("unknown card alias %r" % st.get("card"))
    op, n = card.get("op", "gte"), int(card.get("n", 1))
    if op == "gte":
        return n_hit >= n
    if op == "lte":
        return n_hit <= n
    if op == "eq":
        return n_hit == n
    raise StateError("unknown card.op %r" % op)


def _hashable(v):
    """Turn a column value into a hashable equivalent. When a dict / list lands in a unique key, the old direct tuple()
    raised a TypeError that broke the whole write path —— and this does occur in real repos (unique keys containing json columns).
    Use a stable serialisation instead; equality semantics are unchanged."""
    if isinstance(v, (dict, list)):
        try:
            return json.dumps(v, sort_keys=True, ensure_ascii=False, default=str)
        except Exception:
            return repr(v)
    return v


def _skip(env, entity, why):
    """Bookkeeping for skipped constraints, deduplicated —— previously every call appended, growing unboundedly on long trajectories, and duplicates drowned
    the diagnostic value."""
    k = (entity, why)
    if k not in env._constraint_skips:
        env._constraint_skips.append(k)


def _constraint_rows(env, entity):
    return env.state.get(entity, []) or []


def check_constraints(env, entity):
    """→ (ok, why). Check each table-level constraint declared on the entity. Constraints that cannot be structured are skipped and recorded."""
    cons = (env._constraints or {}).get(entity) or []
    if not cons:
        return True, ""
    rows = _constraint_rows(env, entity)
    for c in cons:
        kind = c.get("kind")
        if kind == "unique":
            cols = c.get("cols") or ([c["col"]] if c.get("col") else [])
            if not cols:
                continue
            seen = set()
            for r in rows:
                key = tuple(_hashable(r.get(k)) for k in cols)
                if any(v is None for v in key):     # SQL semantics: NULL does not participate in uniqueness conflicts
                    continue
                if key in seen:
                    return False, "unique constraint %s(%s) violated: %s" % (entity, ",".join(cols), key)
                seen.add(key)
        elif kind == "check":
            cl = {"col": (c.get("left") or {}).get("col"), "op": c.get("op"),
                  "value": c.get("right")}
            if not cl["col"] or not cl["op"]:
                _skip(env, entity, "check is unstructured")
                continue
            for r in rows:
                # SQL semantics: a CHECK expression that is UNKNOWN (operands contain NULL) counts as **satisfied**.
                # The unique branch in this function already implements "NULL does not conflict"; check must be consistent,
                # otherwise with a check on a nullable column, every legal agent write that leaves that column empty would be refused.
                if r.get(cl["col"]) is None:
                    continue
                try:
                    if not match_state_clause(r, cl, env, None, None):
                        return False, "check constraint violated: %s.%s %s %s" % (
                            entity, cl["col"], cl["op"], cl["value"])
                except StateError:
                    _skip(env, entity, "check evaluation failed")
                    break
        elif kind == "conditional":
            ifs, thens = c.get("if") or [], c.get("then") or []
            if not ifs or not thens:
                _skip(env, entity, "conditional is missing if/then")
                continue
            for r in rows:
                try:
                    if all(match_state_clause(r, x, env, None, None) for x in ifs):
                        if not all(match_state_clause(r, x, env, None, None) for x in thens):
                            return False, "conditional constraint violated: %s satisfies if but not then" % entity
                except StateError:
                    _skip(env, entity, "conditional evaluation failed")
                    break
        else:
            _skip(env, entity, "unknown kind %r" % kind)
    return True, ""


def _legacy_clause(col, v):
    """One old-style where item `{col: v}` → new scope clause `{col, op, value}`.

    Why we cannot always use `op="eq"` (observed 2026-09-10): the value position of an old where **may carry an operator** ——
    `{"fn": {"endswith": ".wiki"}}` means "fn ends with .wiki". This used to hard-code op as
    `eq` and stuff the whole `{"endswith": ".wiki"}` into value, so:
      · `_resolve_filter_val` did not recognise it (no `$` prefix, falls through to the final `return val`)
      · `state_value` got a dict → raised "old-style reference not recognised (returned unchanged)"
    The consequence was not an error exit, but **the whole distractor group being judged broken** and **the vacuous check silently skipping it** ——
    the emitter can write it, the middle layer does not accept it, and it gets lost there. This project has hit the same shape five times.

    The operator table used is **`_STATE_OPS`** —— i.e. **the table `eval_state` actually looks up**
    (grammar.FIELD_OPS + the old name `neq`). Do not set up a separate one here: a separate table sooner or later becomes narrower than the receiver,
    and the narrower side does not error, it just quietly accepts fewer forms.
    Unary operators (is_null / is_not_null) take no operand; value is None.
    """
    if isinstance(v, dict) and len(v) == 1:
        k = next(iter(v))
        if isinstance(k, str) and k in _STATE_OPS:
            return ({"col": col, "op": k, "value": None} if k in _UNARY_OPS
                    else {"col": col, "op": k, "value": _legacy_val(v[k])})
    return {"col": col, "op": "eq", "value": _legacy_val(v)}


def _legacy_val(v):
    """Old-style where value form → new Value."""
    if not isinstance(v, dict):
        return {"lit": v}
    if "$arg" in v:
        return {"ref": "$arg." + str(v["$arg"])}
    if "$const" in v:
        return {"lit": v["$const"]}
    if "$session" in v:
        # Only account_id is equivalent to $actor.id. The old runtime's session has no "id" key,
        # so it is unresolvable → the query matches nothing → **block**; mapping it to actor.id too would turn "block" into "allow",
        # which is not compatibility but a one-way loosening of the guard.
        k = str(v["$session"])
        return {"ref": "$actor.id"} if k == "account_id" else {"ref": "$session." + k}
    return {"_legacy": v}                           # $ref / $subquery etc. are passed unchanged to the old resolve


def norm_preconditions(pcs):
    """→ one-level DNF [[State, ...], ...]. All three input forms are accepted:
       new shape [[S,...],[S,...]] / bare State list (treated as a single conjunction) / old [{entity, where}] (same)."""
    if not pcs:
        return []
    if isinstance(pcs, list) and pcs and isinstance(pcs[0], list):
        # Sniffing only the first element would pass half-migrated shapes like [[S1], S2] through unchanged; downstream would use a dict's keys as States
        # → AttributeError escapes except GuardError and breaks the service; the other branch would silently drop a group of
        # the DNF (= a wall disappears). Any inconsistent shape raises explicitly.
        for grp in pcs:
            if not isinstance(grp, list):
                raise StateError("preconditions are malformed: every DNF item must be a list of States, "
                                 "got %r" % (grp,))
        return pcs
    grp = []
    for pc in (pcs or []):
        if not isinstance(pc, dict):
            continue
        if "scope" in pc or "card" in pc:
            grp.append(pc)
        else:                                       # Old {entity, where}: equality conjunction + at least one row
            grp.append({"entity": pc.get("entity"), "card": "exists",
                        "_msg": pc.get("message"),
                        "scope": [_legacy_clause(k, v)
                                  for k, v in (pc.get("where") or {}).items()]})
    return [grp] if grp else []


def _resolve_filter_val(val, state, args, session):
    """A filter clause's val may be: scalar / {$arg:name} / {$ref:...} / {$session.account_id} /
    {$subquery:{entity,where,select}}. Resolve to the actual value (subquery returns a list of ids)."""
    if isinstance(val, dict):
        if "$arg" in val:
            return (args or {}).get(val["$arg"], _UNRESOLVED)
        if "$ref" in val:
            return resolve(val, state, args)
        if "$session" in val:        # {"$session":"customer_id"} -> take that session field
            return (session or {}).get(val["$session"], _UNRESOLVED)
        if val.get("$session.account_id") is not None or "$session.account_id" in val:
            return session.get("account_id") if session else None
        if "$const" in val:
            return val["$const"]
        if "$subquery" in val:
            sq = val["$subquery"]
            sq_where = {}
            any_unresolved = False
            for k, v in (sq.get("where") or {}).items():
                if isinstance(v, dict) and "mode" in v:
                    # {col: {$arg:x, mode:substring}} —— take the argument value, then filter by mode
                    av = _resolve_filter_val({k2: v2 for k2, v2 in v.items() if k2 != "mode"}, state, args, session)
                    if av is _UNRESOLVED:
                        any_unresolved = True
                    sq_where[k] = (av, v.get("mode"))
                else:
                    av = _resolve_filter_val(v, state, args, session)
                    if av is _UNRESOLVED:
                        any_unresolved = True
                    sq_where[k] = av
            if any_unresolved:
                return _UNRESOLVED  # An argument the subquery depends on is missing → let the optional clause pass
            sel = sq.get("select", "id")
            out = []
            for r in state.get(sq["entity"], []):
                ok = True
                for k, spec in sq_where.items():
                    if isinstance(spec, tuple):
                        av, mode = spec
                        if mode == "substring":
                            ok = ok and av is not None and r.get(k) is not None and str(av).lower() in str(r.get(k)).lower()
                        else:
                            ok = ok and r.get(k) == av
                    else:
                        ok = ok and r.get(k) == spec
                    if not ok:
                        break
                if ok:
                    out.append(r.get(sel))
            return out
        if any(isinstance(k, str) and k.startswith("$") for k in val):
            # **Unknown placeholders always raise; they are no longer returned unchanged.** The final line used to be `return val`: an unrecognised
            # placeholder would hand back the whole dict, which was then compared with column values → always False, with no error anywhere.
            # Specs had grown 15 kinds of placeholders while only 12 were recognised here; the difference was silently blind.
            raise StateError("unknown placeholder %r -- recognized: $arg/$ref/$session/$const/$subquery"
                             % (sorted(k for k in val if isinstance(k, str)),))
    return val


def _is_blank(v):
    return v is None or v == "" or v is _UNRESOLVED or (isinstance(v, (list, dict)) and len(v) == 0)


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _iso_date_prefix(s):
    """Whether s starts with YYYY-MM-DD (ISO date/datetime). The range scalar branch uses it for date-prefix equality."""
    return isinstance(s, str) and bool(_ISO_DATE_RE.match(s))


# The read-side filter mode **is a third operator vocabulary** (the other two are the grammar's 14 operators and eval_state's
# _STATE_OPS), and it has no ordering comparisons —— those go through range {min,max}. Not unifying the three is debt owed to "grammar
# batch 3: full switch"; for now this plugs the hole where **a misspelling silently excludes every row**.
# Measured on live specs: of 360 clauses, **6 use mode="eq"** (bracket), and they currently exclude every row.
_FILTER_MODE_ALIAS = {"eq": "exact", "equals": "exact", "is": "exact", "==": "exact",
                      "contains": "substring", "icontains": "substring", "like": "substring"}
_FILTER_MODES = ("exact", "in", "range", "substring", "ilike", "geo_contains")


def _match_clause(row, c, state=None, args=None, session=None):
    col, mode = c.get("col"), c.get("mode", "exact")
    mode = _FILTER_MODE_ALIAS.get(mode, mode)
    val = _resolve_filter_val(c.get("val"), state, args, session)
    # optional clause: if the argument is absent (val unresolved/empty/empty list), let it pass and do not filter
    if c.get("optional") and _is_blank(val):
        return True
    rv = row.get(col)
    if mode == "exact":      return rv == val
    if mode == "in":         return rv in (val or [])
    if mode == "range":
        # val is expected to be a {min,max} dict, but specs often write a range clause's val directly as {$arg:cdate}
        # —— a scalar (a single date/number rather than an interval); it resolves to str/int and calling .get blows up
        # ('str' object has no attribute 'get') —— any matching row breaks the whole read.
        # Defend against three val forms; the dict path stays as before:
        #   - {$arg} not passed (val=_UNRESOLVED): this filter dimension does not participate (like optional), so "list all of mine" works;
        #   - scalar (single date/value): degrades to "exactly equal to that value";
        #   - {min,max} dict: the original interval semantics.
        if val is _UNRESOLVED:
            return True
        if not isinstance(val, dict):
            if rv is None or val is None: return False
            if rv == val:
                return True
            # Date tolerance: when the stored value is "2025-01-10T00:00:00" and the query is "2025-01-10" (or vice versa),
            # treat as equality on the YYYY-MM-DD prefix —— "single-day" filters like cdate often have this inconsistency.
            if isinstance(rv, str) and isinstance(val, str):
                if _iso_date_prefix(rv) and _iso_date_prefix(val) and rv[:10] == val[:10]:
                    return True
            return False
        lo, hi = val.get("min"), val.get("max")
        # Interval endpoints may themselves be {$arg}/{$session} references (observed in gladys calendarevent_getevents from/to);
        # unresolvable (argument not passed) = that end is open, rather than comparing a dict by magnitude.
        lo = _resolve_filter_val(lo, state, args, session) if isinstance(lo, dict) else lo
        hi = _resolve_filter_val(hi, state, args, session) if isinstance(hi, dict) else hi
        if lo is _UNRESOLVED or _is_blank(lo): lo = None
        if hi is _UNRESOLVED or _is_blank(hi): hi = None
        if lo is None and hi is None: return True
        if rv is None: return False
        def _tz(x):   # ISO datetime strings: drop 'Z' / '+HH:MM' so bounds and stored values compare on the same 19 chars
            if isinstance(x, str) and _iso_date_prefix(x):
                x = x.rstrip("Z"); m = re.match(r"^(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?)", x)
                return m.group(1).replace(" ", "T") if m else x
            return x
        rv, lo, hi = _tz(rv), _tz(lo), _tz(hi)
        try:
            return (lo is None or rv >= lo) and (hi is None or rv <= hi)
        except TypeError:
            return False
    if mode in ("substring", "ilike"):
        return rv is not None and val is not None and val is not _UNRESOLVED and str(val).lower() in str(rv).lower()
    if mode == "geo_contains":   # best-effort: no real polygon handling, degrades to existence
        return rv is not None
    # **No longer silently return False.** A misspelled mode would make this clause exclude every row, while the tool result
    # is still ok + empty list —— the same disease as crud.fetch treating not-found as success, or misaligned lookup_by argument names.
    raise StateError("read-side filter does not recognize mode=%r (col=%r); accepts only %s"
                     % (c.get("mode"), col, ", ".join(_FILTER_MODES)))


def eval_filter(row, f, state=None, args=None, session=None):
    """Nested filter: {op:and|or|not, clauses:[...]} or a leaf {col,mode,val}.
    A leaf val may contain {$arg}/{$ref}/{$session.account_id}/{$subquery}; optional clauses pass when the argument is empty."""
    if not f:
        return True
    if "op" in f and f["op"] in ("and", "or", "not"):
        cls = f.get("clauses", [])
        if f["op"] == "and": return all(eval_filter(row, c, state, args, session) for c in cls)
        if f["op"] == "or":  return any(eval_filter(row, c, state, args, session) for c in cls)
        if f["op"] == "not": return not eval_filter(row, cls[0] if cls else {}, state, args, session)
    return _match_clause(row, f, state, args, session)


def _tokens(s):
    return [t for t in ''.join(ch.lower() if ch.isalnum() else ' ' for ch in str(s)).split() if t]


# ---------------------------------------------------------------------------
# column_map expression evaluation (column_map values of seed_sources/joint_sources):
#   "dataset_col"            -> row.get("dataset_col")
#   {"$const": v}            -> v
#   {"$concat": [parts...]}  -> concatenation (parts may be str=column name / dict=sub-expression / scalar)
#   {"$basename": "col"}     -> os.path.basename(row["col"])
#   {"$date_from":"col","fmt":"%Y%m%d"} -> parse the column as a date, output ISO datetime
# env-specs use these to compose real data columns into an entity's url/uuid/published_at; the runtime must interpret them or env loading crashes.
# ---------------------------------------------------------------------------
def _map_val(dc, r):
    import os
    from datetime import datetime as _dt
    if isinstance(dc, dict):
        if "$const" in dc:
            return dc["$const"]
        if "$concat" in dc:
            parts = []
            for p in dc["$concat"]:
                parts.append(_map_val(p, r) if isinstance(p, dict)
                             else (r.get(p) if isinstance(p, str) else p))
            return "".join("" if x is None else str(x) for x in parts)
        if "$basename" in dc:
            col = dc["$basename"]
            v = r.get(col) if isinstance(col, str) else None
            return os.path.basename(v) if v else ""
        if "$date_from" in dc:
            col, fmt = dc["$date_from"], dc.get("fmt", "%Y-%m-%d")
            try:
                return _dt.strptime(str(r.get(col)), fmt).strftime("%Y-%m-%dT00:00:00Z")
            except Exception:
                return None
        return None
    return r.get(dc)


class GuardError(Exception):
    pass


def id_col(env, entity):
    """Which column this entity uses as row identity.

    The runtime long assumed "every table has an integer id". Real projects are not like that: OctoPrint's User uses
    username as primary key (users.py:919), dokuwiki likewise, dspace uses uuid, bugzilla uses userid.
    Of 220 repos in the library, 63 have account entities without an id column —— those worlds are not broken; the runtime's
    assumption was too narrow.

    Rows we create ourselves (_insert/_load_*) always carry an id, so the write side is unaffected; **only the read side**
    (seed rows, existing rows found by queries) may lack an id. A single rule here: use id if present,
    otherwise the entity's declared primary key.
    """
    return "id" if any(c["name"] == "id" for c in env._cols(entity)) \
        else next((c["name"] for c in env._cols(entity) if c.get("pk")), "id")


def default_key(env, entity, args, fallback=None):
    """Which where to use to locate the target row when the spec gives no row_key/lookup_by.

    This used to be hard-coded as {"id": args["id"]} —— for an entity without id, args naturally has no "id",
    so it degraded to an empty where. An empty where does not error, it **matches the first row**: updating the wrong row, deleting the wrong row,
    all with ok. Far more dangerous than a KeyError, because there is no signal at all.
    Now we use the entity's identity column; if the args do not have it either → return fallback (default None means "cannot be determined").
    """
    c = id_col(env, entity)
    if c in args:
        return {c: args[c]}
    if "id" in args:
        return {"id": args["id"]}
    return fallback


def row_id(env, entity, row, strict=True):
    """Get a row's identity value. With strict, raise GuardError when missing instead of letting a KeyError escape ——
    upstream, KeyError('id') can only be diagnosed by reading the source, while a one-line error points straight at the spec."""
    c = id_col(env, entity)
    if c in row:
        return row[c]
    if "id" in row:
        return row["id"]
    if strict:
        raise GuardError("rows of %s have no usable identity column (neither id nor %s exists) -- spec declares no primary key" % (entity, c))
    return None


# ---------------------------------------------------------------------------
# Env
# ---------------------------------------------------------------------------
class Env:
    def __init__(self, spec, embed_fn=None):
        self.spec = spec
        self.entities = {e["name"]: e for e in spec["entities"]}
        self.tools = {t["tool"]: t for t in spec["tools"]}
        self.auth_cfg = spec.get("auth", {})
        self.embed_fn = embed_fn            # Optional: for semantic retrieval, signature f(list[str])->list[vec]
        self.reset()

    def reset(self):
        self.state = defaultdict(list)
        self._id = defaultdict(int)
        for ent, rows in self.spec.get("seed_state", {}).items():
            for row in rows:
                self.state[ent].append(dict(row))
                if isinstance(row.get("id"), int):
                    self._id[ent] = max(self._id[ent], row["id"])
        # Referenced large seed: pull N rows of real data from the datapool raw (③), map into the entity via column_map
        for ent, src in self.spec.get("seed_sources", {}).items():
            self._load_seed_source(ent, src)
        # Relational load from a joint dataset: group by join_key, parent row + its child rows (FKs wired up), keeping content consistent
        for grp, src in self.spec.get("joint_sources", {}).items():
            self._load_joint_source(src)
        self.session = {"authed": False, "account_id": None, "role": None}
        self._events = []
        # Anchor for $now. **Must be deterministic**: a random clock would make the same spec produce a non-replayable world.
        # Use the spec's value if given, otherwise a fixed default.
        self._now = (self.spec or {}).get("now") or "2026-01-01T00:00:00"
        # Index table-level constraints by entity. Only entities that declare constraints are included, and only these are checked after writes —— bounded cost.
        self._constraints = {}
        self._constraint_skips = []
        for e in (self.spec or {}).get("entities", []) or []:
            cons = e.get("constraints") or []
            if cons:
                # Keys must match those of self.entities / state —— the whole file uses e["name"].
                # Writing it the other way, when an entity carries an entity field the index hangs off a key that does not exist in state:
                # _constraint_rows returns [], the constraint is always true, snapshots always empty —— **completely silent failure**.
                self._constraints[e.get("name") or e.get("entity")] = cons

    def _load_seed_source(self, entity, src):
        """src = {raw_path, n, column_map:{entity_col:dataset_col}, dedup_on?, fk_const?:{col:val}}。
        When the runtime is instantiated it reads real rows from raw; task-gen decides n = how many to load. dedup_on = deduplicate by a dataset column."""
        n = int(src.get("n", 200))
        dedup = src.get("dedup_on")
        rows = _read_rows(src.get("raw_path", ""), n * 8 if dedup else n)
        if dedup:
            seen, ded = set(), []
            for r in rows:
                k = r.get(dedup)
                if k in seen:
                    continue
                seen.add(k); ded.append(r)
                if len(ded) >= n:
                    break
            rows = ded
        else:
            rows = rows[:n]
        cmap = src.get("column_map", {})
        const = src.get("fk_const", {})
        # owner_spread: rotate the owner column across several accounts to create a needle-in-haystack ——
        # lots of real data belonging to many people, with the persona owning only a small slice, so owner-scoped retrieval really means "find mine".
        # {col, account_ids:[...]} (persona accounts included); if absent, degrade to fk_const / no owner.
        spread = src.get("owner_spread") or {}
        sp_col, sp_ids = spread.get("col"), spread.get("account_ids") or []
        for i, r in enumerate(rows):
            row = {"id": self._new_id(entity)}
            for ecol, dcol in cmap.items():
                row[ecol] = _map_val(dcol, r)
            row.update(const)
            if sp_col and sp_ids:
                row[sp_col] = sp_ids[i % len(sp_ids)]
            self.state[entity].append(row)

    # ---- column utilities ----
    def _cols(self, e):    return self.entities.get(e, {}).get("columns", [])
    def _fk_cols(self, e): return [c for c in self._cols(e) if c.get("fk_to")]
    def _writable(self, e):
        return [c for c in self._cols(e) if c["type"] != "id" and not c.get("audit")]
    def _new_id(self, e):
        self._id[e] += 1
        return self._id[e]

    def _find(self, entity, where, args=None):
        where = {k: resolve(v, self.state, args) for k, v in (where or {}).items()}
        rows = query(self.state, entity, where)
        # An empty where = no locating condition at all. When the table has one row it is equivalent to "that single row"
        # (singleton config tables use it this way); **with multiple rows it is always a bug** —— the old implementation returned rows[0],
        # so it updated or deleted the wrong row and still returned ok. The worst kind of failure: no signal at all.
        # Measured: 13 tools take this path; the ugliest is pufferpanel's daemon_server*:
        # the argument is named serverId while Server's identity column is identifier; the names do not match,
        # so no matter which server is named, it is always the first one that changes. Better to refuse loudly.
        if not where and len(rows) > 1:
            raise GuardError("%s cannot pin down the target row: the call gave no identity column (%s) and the table has %d rows"
                             % (entity, id_col(self, entity), len(rows)))
        return rows[0] if rows else None

    def _check_fks(self, entity, values, tool=None):
        """The parent row an FK points to must actually exist.

        `tool` is for the **message**: agents hit this wall a lot (giving a non-existent parent id when creating a child row),
        and it used to be a hard-coded Chinese string —— while the agent's prompt is English. A wall's message is the training signal
        itself, so `guards.messages.fk` can override it here too."""
        for c in self._fk_cols(entity):
            n = c["name"]
            if n in values and values[n] is not None:
                te, tc = c["fk_to"].split(".")
                if te != entity and not query(self.state, te, {tc: values[n]}):
                    raise GuardError(_msg(tool, "fk") if tool is not None and _msg(tool, "fk")
                                     else f"FK {entity}.{n}={values[n]} points to a nonexistent {te}.{tc}")

    def _insert(self, entity, fields):
        row = {"id": self._new_id(entity)}
        cols = self._cols(entity)
        if cols:
            # Declared entity: only write writable or known columns (prevents writing id/audit/internal FKs)
            writ = {c["name"] for c in self._writable(entity)}
            known = {c["name"] for c in cols}
            for k, v in fields.items():
                if k in writ or k in known:
                    row[k] = v
            # Business PK (a pk:true column like <entity>_id that is != "id") is aligned with the internal id:
            # evershop keeps the bundle's cart_id/product_id/order_id PK convention while the runtime uniformly uses id,
            # so the PK column is set to the same value here; later FK lookups (cart_id etc.) can then find the new row.
            for c in cols:
                if c.get("pk") and c["name"] != "id" and c.get("type") == "id":
                    if row.get(c["name"]) is None:
                        row[c["name"]] = row["id"]
        else:
            # Undeclared association tables (e.g. a video_tag m2m through table): accept everything
            for k, v in fields.items():
                row[k] = v
        self.state[entity].append(row)
        return row

    def _load_joint_source(self, src):
        """Relational load from a joint dataset: group one dataset by join_key, each group → one parent row + several child rows (FK to the parent),
        where the child content is really about the parent (reviews really about that product/movie). Fixes cross-source content inconsistency.
        src = {raw_path, join_key, n_parents, max_children_per_parent,
               parent:{entity, column_map}, child:{entity, column_map, fk_col}}"""
        nP = int(src.get("n_parents", 50))
        maxc = int(src.get("max_children_per_parent", 5))
        rows = _read_rows(src.get("raw_path", ""), nP * (maxc + 2) * 4)
        jk = src["join_key"]
        pent, pmap = src["parent"]["entity"], src["parent"].get("column_map", {})
        cent, cmap, fk = src["child"]["entity"], src["child"].get("column_map", {}), src["child"].get("fk_col")
        # owner_spread: rotate the owner column across several accounts (persona included) to create a needle-in-haystack.
        # It may be on either child or parent; child rotation follows global child-row order so the same persona gets several scattered rows.
        cspread = (src.get("child") or {}).get("owner_spread") or {}
        pspread = (src.get("parent") or {}).get("owner_spread") or {}
        c_spcol, c_spids = cspread.get("col"), cspread.get("account_ids") or []
        p_spcol, p_spids = pspread.get("col"), pspread.get("account_ids") or []
        p_i = 0
        c_i = 0
        groups = {}
        for r in rows:
            k = r.get(jk)
            if k in (None, ""):
                continue
            if k not in groups and len(groups) >= nP:
                continue
            groups.setdefault(k, []).append(r)
        for k, grp in groups.items():
            prow = {"id": self._new_id(pent)}
            for ec, dc in pmap.items():
                prow[ec] = k if dc == jk else _map_val(dc, grp[0])
            if p_spcol and p_spids:
                prow[p_spcol] = p_spids[p_i % len(p_spids)]
                p_i += 1
            self.state[pent].append(prow)
            for r in grp[:maxc]:
                crow = {"id": self._new_id(cent)}
                if fk:
                    crow[fk] = prow["id"]
                for ec, dc in cmap.items():
                    crow[ec] = _map_val(dc, r)
                if c_spcol and c_spids:
                    crow[c_spcol] = c_spids[c_i % len(c_spids)]
                    c_i += 1
                self.state[cent].append(crow)

    # ---- call entry: parse args → guards → dispatch to family executor ----
    def call(self, tool_name, args=None):
        if tool_name not in self.tools:
            return {"ok": False, "error": f"no such tool: {tool_name}"}
        tool = self.tools[tool_name]
        _SESSION.clear(); _SESSION.update(self.session)   # For resolve() to resolve {"$session":...}
        resolved = {}
        for k, v in (args or {}).items():
            rv = resolve(v, self.state)
            if rv is _UNRESOLVED:
                return {"ok": False, "error": f"the $ref of argument {k} matches no row"}
            resolved[k] = rv
        args = resolved
        fam = tool.get("family") or _op_to_family(tool.get("op", ""))
        snap = None
        try:
            # Guards also run inside the transaction: ex_trigger-style tools "update the target row first, then spawn"; if spawn raises,
            # the earlier changes must be rolled back with it.
            snap = self._snapshot(tool) if not _family_base(fam) in ("search", "read") else None
            _multi = _spec(tool).get("multi")
            _multi = _multi if isinstance(_multi, dict) and _multi.get("arg") else None
            if not _multi:
                self._guards(tool, args)     # With multi, guards run **per item**; see _run_multi
            fn = EXECUTORS.get(fam) or EXECUTORS.get(_family_base(fam))
            if not fn:
                return {"ok": False, "error": f"unimplemented family: {fam}"}
            # ── transaction boundary ──
            # Read-only families never enter this path (otherwise a pure search would pay for snapshot + validation).
            # Write families: snapshot **every table this call may touch** (not just those with constraints) ——
            # a single call writes side_inserts / spawn / cascade / snapshot tables / summary rows;
            # rolling back only some of them leaves orphan rows and dangling FKs while the caller sees ok:False
            # and assumes nothing happened. That is worse than no rollback, because it is a silent inconsistency.
            writes = snap is not None
            cons_ents = [e for e in (snap or {}).get("_ents", ()) if e in self._constraints]
            # Prior baseline: seeds that already violate constraints must not be blamed on this call (same discipline as distractor guard ④)
            pre_bad = {e for e in cons_ents if not check_constraints(self, e)[0]}
            res = _run_multi(self, tool, fn, args, _multi) if _multi else fn(self, tool, args)
            if writes:
                if isinstance(res, dict) and res.get("ok") is False:
                    self._restore(snap)                 # If the executor itself reports failure, roll back too
                    return res
                for e in cons_ents:
                    ok_c, why = check_constraints(self, e)
                    if not ok_c and e not in pre_bad:
                        self._restore(snap)
                        return {"ok": False, "refused_by": "constraint", "error":
                                (tool.get("guards", {}).get("messages") or {}).get("constraint") or why}
            if writes:
                # **Keep the "previous world" even on success.** The snapshot used to be taken only for rollback and discarded on success ——
                # leaving delta assertions (`{"was": col}`) with no raw material. Keep one indexed by id;
                # the next write call overwrites it: the semantics of `was` are "relative to before the last write".
                self._before = {e: {r.get("id"): r for r in (snap.get(e) or [])}
                                for e in snap.get("_ents", ())}
            return res
        except GuardError as e:
            if snap is not None:
                self._restore(snap)                     # Executors write first and raise later, so the guard path must roll back as well
            # refused_by lets downstream **structurally** distinguish "a wall blocked it" from "the call errored",
            # instead of matching error text —— the text can be overridden by guards.messages, and matching it
            # would require the app to speak Chinese.
            return {"ok": False, "error": str(e), "refused_by": "guard"}
        except StateError as e:
            if snap is not None:
                self._restore(snap)
            return {"ok": False, "error": str(e)}

    def _snapshot(self, tool):
        """Tables this call may touch → shallow row-level copies. Includes the session and id counters —— two residues were observed:
        "login failed but session already authed" and "ids skip after rollback"."""
        ents = self._touched(tool)
        snap = {e: [dict(r) for r in (self.state.get(e) or [])] for e in ents}
        snap["_ents"] = ents
        snap["_session"] = dict(self.session)
        snap["_id"] = dict(getattr(self, "_id", {}) or {})
        return snap

    def _restore(self, snap):
        for e in snap.get("_ents", ()):
            self.state[e] = snap[e]
        self.session.clear(); self.session.update(snap["_session"])
        _SESSION.clear(); _SESSION.update(self.session)
        if hasattr(self, "_id"):
            self._id.clear(); self._id.update(snap["_id"])

    def _touched(self, tool):
        """Which tables this call may write. exec_spec has too many key positions holding table names (entity / table /
        child_entity / through_table / spawn[].entity / record.table / …); rather than enumerate them,
        **recursively collect every string value that matches a known entity name** —— missing one table means a silent
        partial rollback, so better to snapshot a few extra."""
        found = set()
        if tool.get("entity") in self.entities:
            found.add(tool["entity"])

        def walk(x):
            if isinstance(x, dict):
                for v in x.values():
                    walk(v)
            elif isinstance(x, (list, tuple)):
                for v in x:
                    walk(v)
            elif isinstance(x, str) and x in self.entities:
                found.add(x)
        walk(tool.get("exec_spec") or {})
        # Summary/log tables may appear in exec_spec only as table-name strings, already covered above;
        # entities that declare constraints are always included (they are what gets validated and must be restorable).
        found.update(self._constraints)
        # Deletion propagates via on_child to child tables (cascade deletes rows / detach updates columns), and child table names **do not appear in
        # exec_spec** —— the recursive scan above cannot find them. Without this step we get exactly the silent partial rollback this function's
        # comment warns about: the parent table is restored, the cascaded child rows are not. Take the transitive closure over FKs.
        if str(tool.get("family") or "").startswith("crud.delete"):
            frontier = list(found)
            while frontier:
                e = frontier.pop()
                for ce in self.entities:
                    if ce in found:
                        continue
                    if any(str(c.get("fk_to") or "").split(".")[0] == e
                           for c in self._fk_cols(ce)):
                        found.add(ce)
                        frontier.append(ce)
        return tuple(found)

    def _guards(self, tool, args):
        g = tool.get("guards", {})
        msgs = g.get("messages") or {}
        if g.get("requires_auth") and not self.session["authed"]:
            raise GuardError(msgs.get("auth") or f"not logged in; {tool['tool']} requires authentication")
        # auth_realm: dual-principal envs (e.g. evershop customer/admin) are isolated by realm —— the logged-in realm must match
        need_realm = g.get("auth_realm") or tool.get("auth_realm")
        if g.get("requires_auth") and need_realm:
            # This used to read only guards.auth_realm while ex_login writes it at the tool top level —— when the key positions differ,
            # session.realm is always None, and `if realm and ...` short-circuits on None and skips the whole check:
            # the permission isolation of dual-principal envs silently fails entirely. Read both, and None no longer passes.
            if self.session.get("realm") != need_realm:
                raise GuardError(msgs.get("realm") or
                                 f"permission denied: {tool['tool']} requires the {need_realm} realm, "
                                 f"current is {self.session.get('realm')}")
        # Missing required argument. The only one of the eight wall types that was never implemented —— probes found that tools declaring required
        # let calls with missing arguments through. It is worth having: when an agent omits an argument, getting "missing X" teaches far more than
        # a vague downstream error, and that is exactly the value of the failure→recovery turns.
        #
        # **Strict; do not borrow the retrieval side's optional semantics**: on the retrieval side "pass if the argument is absent" is right (one fewer
        # filter = broader results); copying it to guards gives a wall that randomly disappears. Empty string / None count as absent;
        # empty list and 0 / False count as given (they are legal values).
        req = g.get("required")
        if isinstance(req, (list, tuple)):
            miss = [k for k in req if isinstance(k, str)
                    and (k not in (args or {}) or (args or {}).get(k) in (None, ""))]
            if miss:
                raise GuardError(msgs.get("required") or
                                 f"missing required arguments: {tool['tool']} requires {', '.join(miss)}")
        # Preconditions: one-level DNF —— satisfying any group suffices. Permission guards in real code are very often
        # isAdmin || isMod || (isOwner && !locked); flattening that into AND produces a wall nobody can satisfy.
        dnf = norm_preconditions(g.get("preconditions"))
        if dnf:
            passed, errs, first_msg = False, [], None
            for grp in dnf:
                try:
                    if all(eval_state(st, self, args, self.session) for st in grp):
                        passed = True
                        break
                except StateError as ex:
                    errs.append(str(ex))            # Strict: unresolvable does not count as passing
                for st in grp:
                    first_msg = first_msg or st.get("_msg")
            if not passed:
                why = ("precondition evaluation failed: " + errs[0]) if errs and len(errs) == len(dnf) else \
                      ("precondition not met: " + "; or ".join(
                          "".join(_brief_state(st) for st in grp) for grp in dnf))
                raise GuardError(msgs.get("precondition") or first_msg or why)


def _brief_state(st):
    """One precondition → human-readable text. **Both shapes must be describable.**

    The evaluation side `eval_state` has long accepted both, but this message used to be built only from the source grammar
    (`st.get("entity")` + `st["scope"]`). After det switched to emitting IR, the wall itself stayed correct,
    but the message degraded to the equivalent of `precondition not met: None; or None` —— **no test would go red**, while the wall message
    is the training signal itself; a wall with zero information only makes the agent guess blindly or give up.
    """
    if not isinstance(st, dict):
        return "?"
    if "node" in st:                                  # IR:count(select(entity, where))
        sel = st.get("select") or {}
        w = sel.get("where")
        if w is None:
            leaves = []
        elif isinstance(w, dict) and w.get("node") == "field":
            leaves = [w]
        elif isinstance(w, dict) and w.get("node") == "and":
            leaves = [x for x in (w.get("args") or []) if isinstance(x, dict)]
        else:
            leaves = []                               # or / not: only name the table, do not make things up
        cl = [{"col": x.get("col"), "op": x.get("op", "eq"),
               "value": x.get("value")} for x in leaves if x.get("node") == "field"]
        return "%s%s" % (sel.get("entity"), _brief_scope(cl))
    return "%s%s" % (st.get("entity"), _brief_scope(st.get("scope") or []))


def _brief_scope(cl):
    """Describe scope in human terms when erroring: this is the sentence the agent reads when it hits the wall."""
    if not cl:
        return ""
    out = []
    for c in cl:
        if not isinstance(c, dict):
            continue
        v = c.get("value")
        if isinstance(v, dict):
            # Print the actually resolved values. Rendering "…" gives the agent an error it cannot use to correct itself ——
            # and the wall message is the training signal itself; a wall with zero information only makes it guess blindly or give up.
            # Both Value surfaces must render human-readable: source grammar {lit}/{ref}/{col}/{sym},
            # and IR {arg}/{actor}/{session}/{col}/{now} plus bare scalars.
            if "lit" in v:
                shown = v["lit"]
            elif "ref" in v:
                shown = v["ref"]
            elif "col" in v:
                shown = v["col"]
            elif "sym" in v:
                shown = v["sym"]
            elif "arg" in v:
                shown = "$arg." + str(v["arg"])
            elif "actor" in v:
                shown = "$actor." + str(v["actor"])
            elif "session" in v:
                shown = "$session." + str(v["session"])
            elif "const" in v:
                shown = json.dumps(v["const"], ensure_ascii=False)[:40]
            elif v.get("now"):
                shown = "$now"
            else:
                shown = "?"
        else:
            shown = v
        out.append("%s %s %s" % (c.get("col"), c.get("op", "eq"), shown))
    return " where " + ", ".join(out)


def _family_base(fam):       # "search.keyword_weighted" -> "search"
    return fam.split(".")[0] if fam else ""

def _op_to_family(op):       # Fallback mapping for old op format
    return {"create": "crud.insert", "read": "search.filtered_list", "search": "search.filtered_list",
            "update": "update.field_set", "delete": "crud.delete",
            "login": "guard.auth", "logout": "guard.logout"}.get(op, op)


# ---------------------------------------------------------------------------
# Executors: one deterministic parameterised block per family, reading tool["exec_spec"] + args + env.state
# spec.get always uses safe defaults; when exec_spec is missing, infer from args where possible (old-format compatibility)
# ---------------------------------------------------------------------------
def _spec(tool):  return tool.get("exec_spec", {}) or {}
def _ent(tool, spec, args):
    return spec.get("entity") or tool.get("entity") or args.get("entity")


def _account_entity(env):
    """This env's account entity name. **Read from auth, not hard-coded** —— the old code insisted on "Account",
    a leftover from the era of hand-built envs: in real repos the account table is called User (153/193), Member, Customer...
    Measured: 191/193 repos do not call it Account, so owner injection **never fired**, and all creates of the 1008 entities
    with a non-null owner FK hit "missing required FK"."""
    ae = ((getattr(env, "spec", None) or {}).get("auth") or {}).get("account_entity")
    return ae if ae in getattr(env, "entities", {}) else "Account"


def _owner_fk_cols(env, entity):
    """FK column names on this entity that point to the account entity (possibly several: created_by / updated_by / owner_id)."""
    ae = _account_entity(env)
    return [c for c in env._fk_cols(entity) if c["fk_to"].split(".")[0] == ae]


def _owner_fk_col(env, entity):
    """The first FK column name pointing to the account entity (if any). Used for session owner injection:
    create_channel's account_id / create_video's owner_account_id, etc."""
    cols = _owner_fk_cols(env, entity)
    return cols[0]["name"] if cols else None


def _resolve_fields(spec, args, env, entity):
    """Merge exec_spec.fields + args into {col: val}.
    fields has two valid forms:
        - list[str]  : column names that may be written (new v2 contract); values come from args, missing ones are not written
        - dict{col: val|{$arg:col}} : old v1 contract; val is a constant or a {$arg:param_name} reference to this call's input
    Then merge the constant fields from set_on_create (type/name/privacy of create_watch_later_playlist).
    """
    fmap = spec.get("fields")
    merged = {}
    if isinstance(fmap, list):
        for col in fmap:
            if col in args:
                merged[col] = args[col]
    elif isinstance(fmap, dict):
        for col, v in fmap.items():
            if isinstance(v, dict):
                if "$arg" in v:
                    if v["$arg"] in args:
                        merged[col] = args[v["$arg"]]
                elif "$session" in v:
                    rv = env.session.get(v["$session"], _UNRESOLVED)
                    if rv is not _UNRESOLVED:
                        merged[col] = rv
                elif "$ref" in v:
                    rv = resolve(v, env.state, args)
                    if rv is not _UNRESOLVED:
                        merged[col] = rv
                else:
                    merged[col] = v
            else:
                merged[col] = v
    # Also merge any other args whose name matches a column of this entity (input_schema params map straight to columns)
    cols = {c["name"] for c in env._cols(entity)}
    for k, v in args.items():
        if k in cols and k not in merged:
            merged[k] = v
    # set_on_create: resolve each declarative expression ($const/$arg/$session/$ref/$resolve/$compute/$auto).
    # $compute may depend on columns produced by $resolve in the same batch, so iterate to a fixed point (two rounds usually suffice).
    # Inject _spawn_entity=this entity so that $auto's max(<pk>) looks at this entity's rows (not the spawn context).
    soc_args = dict(args, _spawn_entity=entity) if entity else args
    soc = spec.get("set_on_create") or {}
    for _ in range(3):
        progressed = False
        for col, v in soc.items():
            if col in merged and not isinstance(merged[col], dict):
                continue
            rv = _resolve_expr(v, env, soc_args, merged)
            if rv is not _UNRESOLVED and not isinstance(rv, dict):
                merged[col] = rv
                progressed = True
        if not progressed:
            break
    return merged


def _maybe_inject_owner(env, entity, fields, declared=()):
    """FKs pointing at the account entity are injected from session.account_id when not given. The answer to "who did it"
    can only come from the session; the caller should not and cannot pass it (if it could, it could forge ownership).

    Inject **all** such missing columns, not just the first: in real repos one table often has created_by /
    updated_by / owner_id all pointing at the account; filling only the first still hits a wall if the other two are NOT NULL.

    **But never touch columns the tool has declared as caller-writable** (`declared` = exec_spec.fields/insert_fields).
    About a third of the columns that point at the account table are not "who did it" but business references: Message.recipient_id,
    Transfer.to_user_id, Review.reviewed_user_id. Injecting the current account there means messaging
    yourself or transferring to yourself. If the tool contract says the caller supplies the column, then not supplying it means
    it was not supplied; runtime must not fill it in.

    This is a **fallback, not the proper fix**. The proper fix is for the build spec agent to write
    `{"$session":"account_id"}` explicitly in exec_spec.set: det provides the evidence, the agent declares, runtime does not guess semantics.
    """
    if not (env.session.get("authed") and env.session.get("account_id") is not None):
        return fields
    me = env.session["account_id"]
    for c in _owner_fk_cols(env, entity):
        n = c["name"]
        if n in declared:                       # The caller's territory; runtime stays out
            continue
        if n not in fields or fields.get(n) is None:
            fields[n] = me
            env._events.append({"owner_injected": {"entity": entity, "col": n}})
    return fields


def _maybe_autogen(env, entity, fields):
    """For non-null business identifiers such as uuid, generate a deterministic value from the content when missing, avoiding unique_on conflicts and NOT NULL violations."""
    for c in env._cols(entity):
        if c["name"] == "uuid" and not c.get("nullable") and not fields.get("uuid"):
            seed = f"{entity}-{fields.get('name') or fields.get('channel_id') or fields.get('id') or ''}"
            fields["uuid"] = "auto-" + hashlib.sha256(seed.encode()).hexdigest()[:16]
    return fields

def _recalc_cart(env, cart_id):
    """Recompute the summary columns of a Cart (triggered by add/remove/update cart_item).
    total_qty=Σqty, sub_total=Σsub_total, tax_amount=Σtax_amount,
    discount_amount=Σdiscount_amount, grand_total=sub_total+tax_amount+shipping_fee_incl_tax-discount_amount。
    Amounts are rounded to 2 decimals. Skip if the Cart does not exist."""
    carts = query(env.state, "Cart", {"cart_id": cart_id})
    if not carts:
        return
    cart = carts[0]
    items = query(env.state, "CartItem", {"cart_id": cart_id})
    def s(col):
        return round(sum(i.get(col) or 0 for i in items), 2)
    qty = sum(int(i.get("qty") or 0) for i in items)
    sub = s("sub_total")
    tax = s("tax_amount")
    disc = s("discount_amount")
    ship = cart.get("shipping_fee_incl_tax") or 0
    grand = round(sub + tax + ship - disc, 2)
    cart["total_qty"] = qty
    cart["sub_total"] = sub
    cart["sub_total_incl_tax"] = round(sub + tax, 2)
    cart["sub_total_with_discount"] = round(sub - disc, 2)
    cart["sub_total_with_discount_incl_tax"] = round(sub - disc + tax, 2)
    cart["tax_amount"] = tax
    cart["discount_amount"] = disc
    cart["grand_total"] = grand
    cart["total_weight"] = round(sum(i.get("product_weight") or 0 for i in items), 2)


# ── Error messages and child-row handling (2026-08-25) ──────────────────────────────
def _msg(tool, key):
    """Agent-written error messages take precedence. The message on a wall is itself the training signal; a wall with zero information only makes the agent
    guess blindly or give up. guards.messages is the primary location (10283 entries in current specs), exec_spec.messages is the legacy one."""
    g = ((tool.get("guards") or {}).get("messages") or {}).get(key)
    return g or ((tool.get("exec_spec") or {}).get("messages") or {}).get(key)


# schema on_delete -> three real behaviours. Values measured over the whole corpus: cascade family 5080, set_null family 1062,
# restrict family 1000, undeclared 8454. Case variants and framework dialects (Rails destroy / Django protect /
# Ecto nilify_all) all map onto these three.
_ON_DELETE = {
    "cascade": "cascade", "destroy": "cascade", "delete_all": "cascade", "delete": "cascade",
    "set_null": "detach", "set null": "detach", "setnull": "detach", "nullify": "detach",
    "nilify_all": "detach", "set_default": "detach", "nullify_all": "detach",
    "restrict": "block", "no_action": "block", "no action": "block", "protect": "block",
    "do_nothing": "block", "restrict_with_exception": "block", "restrict_with_error": "block",
}


def _on_delete(col):
    """-> cascade | detach | block. **Undeclared follows the SQL default (NO ACTION) = block**;
    this is also the AIP-135 default: "if child resources exist, return FAILED_PRECONDITION"."""
    v = str(col.get("on_delete") or "").strip().lower().replace("-", "_")
    return _ON_DELETE.get(v, "block")


def _child_refs(env, entity, parent):
    """-> [(child entity, fk column, policy, [child rows...])]: all child rows whose foreign key points at **this row** of parent.

    Child rows store the value of the column **named by** fk_to, not necessarily the parent's identity column; this is the same issue as the comment
    in ex_delete_cascade (artalk's Page.site_name -> Site.name; comparing against id matches nothing).
    """
    out = []
    for ce in env.entities:
        for c in env._fk_cols(ce):
            tgt = str(c.get("fk_to") or "")
            if tgt.split(".")[0] != entity:
                continue
            pcol = tgt.split(".")[1] if "." in tgt else None
            pval = parent.get(pcol) if pcol else None
            if pval is None:
                pval = row_id(env, entity, parent, strict=False)
            if pval is None:
                continue
            hits = [r for r in env.state.get(ce, []) if r.get(c["name"]) == pval]
            if hits:
                out.append((ce, c["name"], _on_delete(c), hits))
    return out


def _apply_on_child(env, tool, entity, parents, override, depth=0):
    """Handle the child rows of parents **before** deleting them. The policy is derived per FK from schema on_delete;
    `exec_spec.on_child` overrides it for the whole tool.

    Previously ex_delete always deleted directly without looking at child rows, and check_constraints only validates the entity's own declared
    unique / check, so **deleting a referenced parent silently left dangling FKs, with no error and no rollback**.
    Defaulting to block is not just aligning with AIP-135; it closes this hole.
    """
    if depth > 8:
        raise StateError("cascade depth exceeds 8 levels, likely a self-referencing cycle: %s" % entity)
    for parent in parents:
        for ce, fkcol, pol, kids in _child_refs(env, entity, parent):
            pol = override or pol
            if pol == "block":
                raise GuardError(_msg(tool, "on_child")
                                 or "%s is still referenced by %d rows of %s.%s, cannot delete"
                                    % (entity, len(kids), ce, fkcol))
            if pol == "detach":
                for r in kids:
                    r[fkcol] = None
                continue
            _apply_on_child(env, tool, ce, kids, override, depth + 1)   # Handle grandchildren first
            _drop = {id(r) for r in kids}
            env.state[ce] = [r for r in env.state.get(ce, []) if id(r) not in _drop]


def ex_insert(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    # The tail of `_resolve_fields` also merges "args whose name matches a column of this entity", so insert and
    # field_set have **exactly the same hole**, and insert is the largest family (3595 tools).
    # Passing an extra status="published" to `article_create(title)` directly creates a published article,
    # bypassing the state-transition tool that is supposed to govern publishing.
    _assert_on_panel(tool, args, {c["name"] for c in env._cols(entity)},
                     set(spec.get("fields") or ()) | set(spec.get("insert_fields") or ())
                     | set(spec.get("set_on_create") or ()) | set(spec.get("set") or ()))
    fields = _resolve_fields(spec, args, env, entity)
    # `fields` has two valid shapes, list and dict (dict = {column: {"$arg": param_name}}, used by tools
    # where **column name != param name**). If only list were recognised, `_decl` for dict-shaped tools would be empty,
    # so `_maybe_inject_owner` would inject the current account into columns "the tool declares as caller-written",
    # exactly what its docstring says must never be touched.
    _fv = spec.get("fields")
    _decl = set(_fv) if isinstance(_fv, (list, dict)) else set()
    _decl |= set(spec.get("insert_fields") or [])
    fields = _maybe_inject_owner(env, entity, fields, _decl)
    fields = _maybe_autogen(env, entity, fields)
    # unique_on: composite unique key (e.g. account_id+name); when all key columns have values, check duplicates jointly rather than per column
    uo = spec.get("unique_on") or []
    if uo and all(fields.get(col) is not None for col in uo):
        dup_where = {col: fields[col] for col in uo}
        if query(env.state, entity, dup_where):
            return {"ok": False, "error": (spec.get("messages") or {}).get("unique")
                    or f"uniqueness conflict {entity} {dup_where}"}
    # Required FK check
    for c in env._fk_cols(entity):
        if not c.get("nullable") and (c["name"] not in fields or fields[c["name"]] is None):
            raise GuardError(_msg(tool, "fk_missing")
                             or f"create {entity} is missing required FK {c['name']}")
    env._check_fks(entity, fields, tool)
    row = env._insert(entity, fields)
    for si in spec.get("side_inserts", []):
        sf = {}
        for k, v in (si.get("fields") or {}).items():
            sf[k] = resolve(v, env.state, args) if isinstance(v, dict) else v
        # link_col: attach the id of the just-created parent row to an FK column of the child (register -> Account.user_id;
        # create_channel→Actor.video_channel_id; create_video→Thumbnail.video_id)
        if si.get("link_col"):
            sf[si["link_col"]] = row["id"]
        # owner_account_from: copy the child's owner FK from a column of the parent (create_channel's Actor takes the channel's account_id)
        if si.get("owner_account_from"):
            oc = _owner_fk_col(env, si["entity"])
            if oc:
                sf[oc] = row.get(si["owner_account_from"])
        # owner=true: wire the child's owner FK directly to the current session account (register's Account has no owner FK, skip)
        env._insert(si["entity"], sf)
    # evershop: recompute cart totals after add_cart_item (skipped for envs without a CartItem entity)
    if entity == "CartItem" and "cart_id" in row:
        _recalc_cart(env, row["cart_id"])
    return {"ok": True, "result": {"id": row["id"]}, "entity": entity}

def ex_fetch(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    _assert_declared(tool, args, "where")
    if spec.get("lookup_by"):
        where = spec["lookup_by"]
    elif "where" in args:
        where = args["where"]            # The line above already guarantees it is on the panel
    else:
        # Fallback: use the inputs directly as query conditions. **Validate only on this path**: when lookup_by is present, extra inputs
        # are never consumed, so rejecting them would be over-blocking. The executor **must not consume parameters outside the panel**, that is all.
        _assert_on_panel(tool, args, {c["name"] for c in env._cols(entity)})
        where = {k: v for k, v in args.items() if k != "entity"}
    _w = {k: resolve(v, env.state, args) for k, v in where.items()}
    rows = query(env.state, entity, _w)
    if not rows:
        # **Failing to fetch one row = failure, not success.** search returning an empty list is success (it may legitimately find nothing),
        # but get naming a specific row and not finding it means something is wrong. Zapier / Workato / Make all pin these
        # two semantics as opposites. The old behaviour was always {"ok": True, "result": None}, which is exactly how those 373
        # tools with mismatched lookup_by param names could fail silently: the caller believed "this row does not exist".
        raise GuardError(_msg(tool, "not_found") or "%s not found: %s" % (entity, _w))
    row = dict(rows[0])
    eg = spec.get("eager")
    if eg is True:          # In the contract eager:true means "fetch one row" with no relation preloading; only a list is a relation description
        eg = []
    for eg in (eg or []):
        if isinstance(eg, str):      # eager:["category_id",...] only declares the column names to include, no relation preloading
            continue
        rel_e = eg.get("entity")
        if rel_e:
            row[eg.get("rel", rel_e)] = _eager_rows(env, entity, row, rel_e, eg)
    if spec.get("field_mask"):
        row = {k: row[k] for k in spec["field_mask"] if k in row}
    return {"ok": True, "result": row}

def _apply_scope(env, spec, rows, args=None):
    """Read-side visibility scope: narrow "everything" down to "what the current session can see". Derived from the impl's behaviour signature:
    in real code an owner-bound search is `current_user.x`, not a global table scan. This is the root of task-scope realism:
    "search my bookmarks" != "search all bookmarks". Grammar (written in the search tool's exec_spec.scope):
        owner_col=C                         -> only row[C]==session.account_id (not logged in -> empty)
        visibility_col=V + public=[...]     -> only rows with row[V] in the public set
        owner_col + visibility_col          -> own ∪ public (needle-in-haystack: private rows mixed into the public pool)
        where={col:val|$session.account_id} -> static scope, ANDed in (multi-tenant / fixed channel, etc.)
    No scope = old behaviour (see everything), for backward compatibility."""
    sc = spec.get("scope")
    if not sc:
        return rows
    me = env.session.get("account_id")
    owner_col = sc.get("owner_col")
    vis_col = sc.get("visibility_col")
    pub = sc.get("public") or sc.get("public_values") or []
    where = sc.get("where")
    out = rows
    if where:
        w = {}
        for k, v in where.items():
            # {$arg:x}/{$ref:...} resolve against this call's inputs; "$session.<key>" reads a session field (e.g. multi-tenant tenant_id)
            if isinstance(v, str) and v.startswith("$session."):
                w[k] = env.session.get(v[len("$session."):])
            else:
                w[k] = me if v == "$session.account_id" else resolve(v, env.state, args)
        out = [r for r in out if all(r.get(k) == v for k, v in w.items())]
    if owner_col or vis_col:
        if owner_col and not vis_col and me is None:
            return []                       # Private scope and not logged in -> sees nothing
        def visible(r):
            own = bool(owner_col) and r.get(owner_col) == me
            isp = bool(vis_col) and r.get(vis_col) in pub
            return (own or isp) if (owner_col and vis_col) else (own if owner_col else isp)
        out = [r for r in out if visible(r)]
    return out


def ex_filtered_list(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    _assert_declared(tool, args, "filter", "where")
    rows = _apply_scope(env, spec, list(env.state.get(entity, [])), args)
    f = args.get("filter") if "filter" in args else spec.get("filter")
    if "where" in args and not f:          # Old format
        w = {k: resolve(v, env.state, args) for k, v in args["where"].items()}
        rows = [r for r in rows if all(r.get(k) == v for k, v in w.items())]
    elif f:
        rows = [r for r in rows if eval_filter(r, f, env.state, args, env.session)]
    sort = spec.get("sort")
    if isinstance(sort, dict) and sort.get("col"):
        sc = sort["col"] if not isinstance(sort["col"], dict) else resolve(sort["col"], env.state, args)
        if sc:
            rows.sort(key=lambda r: (r.get(sc) is None, r.get(sc)), reverse=(sort.get("dir") == "desc"))
    elif isinstance(sort, list):
        for s in reversed(sort):
            rows.sort(key=lambda r: (r.get(s["col"]) is None, r.get(s["col"])),
                      reverse=(s.get("dir") == "desc"))
    pag = spec.get("pagination") or {}
    def _pag_val(v):
        if isinstance(v, dict):
            rv = resolve(v, env.state, args)
            return None if rv is _UNRESOLVED else rv
        return v
    start = _pag_val(pag.get("start"))
    count = _pag_val(pag.get("count"))
    # limit may be written as {"$arg":"top_k"} (resolved via _pag_val); args.top_k / args.limit / default are also accepted
    limit = (args.get("limit") or count or _pag_val(pag.get("limit"))
             or pag.get("default_limit") or pag.get("default") or args.get("top_k"))
    if limit:
        s = int(start) if start not in (None, _UNRESOLVED) else 0
        rows = rows[s:s + int(limit)]
    return {"ok": True, "result": rows}

def ex_keyword(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    _m, rc = _rank_of(tool, spec)
    q = _tokens(args.get("q") or args.get("query") or "")
    fields = (_rank_get(spec, rc, "fields", "search_fields", "fields")
              or [c["name"] for c in env._cols(entity) if c["type"] == "text"])
    if isinstance(fields, dict):
        fields = list(fields.keys())
    weight = _rank_get(spec, rc, "weight", "weight") or {}
    rows = _apply_scope(env, spec, list(env.state.get(entity, [])), args)
    pre = spec.get("filter")
    if pre:
        rows = [r for r in rows if eval_filter(r, pre, env.state, args, env.session)]
    def score(r):
        s = 0.0
        for fcol in fields:
            toks = _tokens(r.get(fcol, ""))
            hit = sum(1 for t in q if t in toks)
            s += hit * float(weight.get(fcol, 1.0))
        return s
    scored = sorted(((score(r), i, r) for i, r in enumerate(rows)), key=lambda x: (-x[0], x[1]))
    top_k = int(args.get("top_k") or _rank_get(spec, rc, "top_k", "top_k") or 10)
    out = [r for sc, i, r in scored if sc > 0][:top_k]
    if spec.get("rerank") and spec.get("rerank_by"):
        out.sort(key=lambda r: (r.get(spec["rerank_by"]) is None, r.get(spec["rerank_by"])), reverse=True)
    return {"ok": True, "result": out}

def ex_semantic(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    _m, rc = _rank_of(tool, spec)
    rows = _apply_scope(env, spec, list(env.state.get(entity, [])), args)
    vfields = [v["col"] if isinstance(v, dict) else v
               for v in (_rank_get(spec, rc, "fields", "vector_fields", "search_fields", "fields") or [])]
    top_k = int(args.get("top_k") or _rank_get(spec, rc, "top_k", "top_k") or 10)
    q = args.get("q") or args.get("query") or ""
    if not env.embed_fn:                   # No embedding -> fall back to keyword
        return ex_keyword(env, {"exec_spec": {"entity": entity, "search_fields": vfields, "top_k": top_k}},
                          {"q": q})
    def text(r): return " ".join(str(r.get(c, "")) for c in vfields)
    vecs = {id(r): (r.get("_vec") or env.embed_fn([text(r)])[0]) for r in rows}
    qv = env.embed_fn([q])[0]
    import math
    def cos(a, b):
        d = math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(y*y for y in b))
        return sum(x*y for x, y in zip(a, b)) / d if d else 0.0
    scored = sorted(((cos(qv, vecs[id(r)]), i, r) for i, r in enumerate(rows)), key=lambda x: (-x[0], x[1]))
    return {"ok": True, "result": [r for s, i, r in scored][:top_k]}

def _rank_of(tool, spec):
    """-> (ranking method, config).

    **`rank.method` records the source code's matching/ranking method, with 5 values (as the miner classifies them):**
        exact / substring   -- match predicates, not ranking. runtime treats them as pure filters; actual matching relies on `filter`
        keyword / hybrid    -- term-frequency scoring
        semantic            -- vector similarity

    Old specs (family hard-coded as search.keyword_weighted / search.semantic) fall back on the family.
    """
    r = spec.get("rank")
    m = r.get("method") if isinstance(r, dict) else None
    if not isinstance(m, str):
        fam = str(tool.get("family") or "")
        m = ("keyword" if fam == "search.keyword_weighted" else
             "semantic" if fam == "search.semantic" else None)
        r = None
    return (m if m in ("keyword", "hybrid", "semantic") else None), (r if isinstance(r, dict) else {})


def _rank_get(spec, rc, new_key, *old_keys):
    """rank.<new_key> takes precedence, falling back to the old top-level exec_spec key (backward compatible with the 338 current specs)."""
    v = rc.get(new_key)
    if v not in (None, {}, []):
        return v
    for k in old_keys:
        v = spec.get(k)
        if v not in (None, {}, []):
            return v
    return None


def ex_search(env, tool, args):
    """The single entry point of the search family. **The ranking method is a parameter, not a family.**

    No API standard, schema->API generator or integration platform splits operation types by "ranking algorithm":
    OData has a single `$search`, AIP a single `filter` field, Zapier/Make/Workato each have a single
    search class. We used to have three families, compressing the miner's 5 methods into 3,
    and the difference between exact (2802) and substring (372) was lost in that compression. Making it a parameter is lossless.
    """
    method, _rc = _rank_of(tool, _spec(tool))
    if method in ("keyword", "hybrid"):
        return ex_keyword(env, tool, args)
    if method == "semantic":
        return ex_semantic(env, tool, args)
    return ex_filtered_list(env, tool, args)   # No rank / exact / substring -> pure filtering


def _eager_rows(env, entity, row, rel_e, eg):
    """Relation expansion: when fetching this row, also bring along its related rows.

    The original implementation was `query(env.state, rel_e, {})[:10]`: **empty condition = first 10 rows of the whole table, with no
    join at all**. "Fetch the line items of order 7" would return the 10 earliest line items in the system, with ok:true.
    Of the 14977 tools in the library, 0 declared `eager`, so it never ran; it was a landmine.

    `via` = the foreign key column in the child table that points back to this row, **directly derivable from schema `fk_to`**,
    so build_spec need not invent anything. Without `via`, find the FK pointing at this entity automatically.
    Child rows store the value of the column **named by** `fk_to`, not necessarily the parent's identity column.
    """
    via = eg.get("via")
    fks = env._fk_cols(rel_e)
    fk = (next((c for c in fks if c["name"] == via), None) if via else
          next((c for c in fks if str(c.get("fk_to") or "").split(".")[0] == entity), None))
    if not fk:
        raise StateError("eager preload %s found no foreign key back to %s -- provide via" % (rel_e, entity))
    tgt = str(fk.get("fk_to") or "")
    pcol = tgt.split(".")[1] if "." in tgt else None
    pval = row.get(pcol) if pcol else None
    if pval is None:
        pval = row_id(env, entity, row, strict=False)
    if pval is None:
        return []
    lim = int(eg.get("limit") or 20)
    return [r for r in env.state.get(rel_e, []) if r.get(fk["name"]) == pval][:lim]


# Closed vocabulary of aggregate functions: the intersection across 11 systems.
_AGG_FNS = ("count", "count_distinct", "sum", "avg", "min", "max")


def _agg1(fnm, rows, col):
    """SQL semantics: **aggregates ignore NULL**; count of an empty set is 0, every other aggregate of an empty set is NULL."""
    if fnm == "count" and not col:
        return len(rows)
    vals = [r.get(col) for r in rows if r.get(col) is not None]
    if fnm == "count":
        return len(vals)
    if fnm == "count_distinct":
        return len({_hashable(v) for v in vals})
    if not vals:
        return None
    if fnm == "sum":
        return sum(vals)
    if fnm == "avg":
        return sum(vals) / len(vals)
    return (min if fnm == "min" else max)(vals)


def ex_aggregate(env, tool, args):
    """Aggregate statistics. **A separate family, not attached to rank.**

    Why not a parameter of search: (1) the return shape differs (groups and numbers, not a list of rows),
    and we just acknowledged at crud.fetch that the return shape is load-bearing; (2) the verifier semantics differ (asserting
    "a row satisfying X exists" vs asserting "the count equals 12"); (3) Hasura makes `select` and `select_aggregate`
    **two separate root fields**, and it has the most complete aggregate support among these systems.

    Ranking and aggregation conflict: ranking produces an ordered top-k, aggregation produces grouped statistics;
    "keyword-search the top 10 and then sum them" is something nobody does in the real world, since top-k truncation makes the statistics meaningless.

    `filter` and `having` both use **the read-side filter language** (`{col, mode, val}` + and/or/not),
    consistent with `filter` in the same family; **not the grammar's Pred tree**. The read-side filter is still not wired to
    the grammar, which is debt owed by "batch 3: replace the whole grammar"; this family should not open a second language next to it.
    Magnitude comparisons use `range {min, max}` (the read-side modes have no gt/lt).
    """
    spec = _spec(tool); entity = _ent(tool, spec, args)
    _assert_declared(tool, args, "filter")
    rows = _apply_scope(env, spec, list(env.state.get(entity, [])), args)
    f = args.get("filter") if "filter" in args else spec.get("filter")
    if f:
        rows = [r for r in rows if eval_filter(r, f, env.state, args, env.session)]
    gb = [c for c in (spec.get("group_by") or []) if isinstance(c, str)]
    aggs = [a for a in (spec.get("aggregate") or []) if isinstance(a, dict)] or \
           [{"fn": "count", "as": "count"}]
    groups = {}
    if gb:
        for r in rows:
            groups.setdefault(tuple(_hashable(r.get(c)) for c in gb), []).append(r)
    else:
        groups[()] = rows            # No grouping = the whole table is one group; an empty table still returns one row with count=0
    out = []
    for key, grp in groups.items():
        one = {c: key[i] for i, c in enumerate(gb)}
        for a in aggs:
            fnm = str(a.get("fn") or "count").lower()
            if fnm not in _AGG_FNS:
                raise StateError("unknown aggregate function %r (accepts only %s)" % (a.get("fn"), ", ".join(_AGG_FNS)))
            col = a.get("col")
            one[a.get("as") or (fnm if not col else "%s_%s" % (fnm, col))] = _agg1(fnm, grp, col)
        out.append(one)
    h = spec.get("having")
    if h:
        out = [r for r in out if eval_filter(r, h, env.state, args, env.session)]
    srt = spec.get("sort")
    if isinstance(srt, dict) and srt.get("col"):
        out.sort(key=lambda r: (r.get(srt["col"]) is None, r.get(srt["col"])),
                 reverse=(srt.get("dir") == "desc"))
    lim = args.get("limit") or (spec.get("pagination") or {}).get("default_limit")
    return {"ok": True, "result": out[:int(lim)] if lim else out}


def _run_multi(env, tool, fn, args, m):
    """`multi`: bind each element of an **array** input to one parameter and run the same tool N times.

    **No new family; the loop lives in call()**, so none of the 19 executors needs a single line changed.
    It is also faithful to the source: real repos expose `alias_bulk_delete({ids:[...]})`, not a generic
    batch_apply (measured over the corpus: 357 bulk endpoints, 1.46%).

    Two fixed semantics:

    · **Guards run per item.** Running guards only once would be a **public bypass channel**: an agent that cannot pass delete
        would learn to go through the bulk route instead. The guard layer is the training signal itself; a hole in the guards is a hole in the environment.
        (K8s deletecollection runs admission per object, Hasura folds each row's check with bool_and,
          Postgres RLS "for any of the records inserted": every system where per-row logic belongs to **authorization**
          skips none. What ORMs skip are **user callbacks**, and their only reason is saving database
          round trips, which does not apply to an in-memory dict.)
    · **All or nothing.** call() returns `{ok: bool}`, and one bool cannot express "7 items succeeded, 3 failed"
        (in AIP-233's words). The first failure rolls back everything; the failing position is reported by index in `failed_requests`.
        Because it is atomic, this map only ever has one entry, but the shape is kept.

    Constraint checks **run only once at the end** (guaranteed by the existing flow of call()): intermediate states may be temporarily invalid.
    When reordering in bulk, the unique key conflicts right after A is changed and only becomes valid after B. Per-item checks would reject valid batches.
    """
    an = m.get("arg")
    bind = m.get("bind") or an
    vals = args.get(an)
    if not isinstance(vals, (list, tuple)):
        raise GuardError(_msg(tool, "multi")
                         or "%s requires array argument %s" % (tool.get("tool"), an))
    cap = int(m.get("max") or 100)
    if len(vals) > cap:
        raise GuardError("at most %d items per call, got %d" % (cap, len(vals)))
    out = []
    for idx, v in enumerate(vals):
        item = {k: x for k, x in args.items() if k != an}
        item[bind] = v
        try:
            env._guards(tool, item)          # Per item: a hole in the guards is a hole in the environment
            r = fn(env, tool, item)
        except (GuardError, StateError) as ex:
            return {"ok": False, "refused_by": "guard",
                    "error": "batch failed at item %d" % idx,
                    "failed_requests": {str(idx): str(ex)}}
        if isinstance(r, dict) and r.get("ok") is False:
            return {"ok": False, "error": "batch failed at item %d" % idx,
                    "failed_requests": {str(idx): str(r.get("error"))}}
        out.append(r.get("result") if isinstance(r, dict) else r)
    return {"ok": True, "result": out, "n": len(out)}


def _assert_declared(tool, args, *keys):
    """When the caller passes `filter` / `where`, **it must have been declared on the panel**.

    `ex_filtered_list` has always been `args.get("filter") if "filter" in args else spec.get("filter")`,
    yet the `input_schema` of the 2496 search tools has **no filter at all** (only 8 do).
    So an agent that merely guesses to pass `filter={...}` gets arbitrary query capability the real application
    **does not provide**, with no layer telling it not to. `args["where"]` in `ex_fetch` is the same.

    This is not as harmless as "an extra parameter gets ignored". The condition language is **the rules of the world**, not a query tool for the agent:

        · Faithfulness: the real `bug_search` panel is quicksearch / bug_status / product,
            not `filter={and:[...]}`. Leaving it open invents an interface that does not exist in the source.
        · Difficulty: "find the order whose total exceeds X and belongs to customer Y" is normally a multi-hop search -> read ->
            search again; a generic condition language makes it one call, and the discoverability graph collapses.
        · The verifier's condition and the "find the target" condition **are often the same**: leave it open and the "find" step disappears.

    Tools that really have `filter` on the panel (8 of them) pass as usual; that is what the source genuinely exposes.
    """
    ins = tool.get("input_schema") or {}
    for k in keys:
        if k in (args or {}) and k not in ins:
            raise GuardError(_msg(tool, k) or
                             "%s is not on the panel of %s -- the real app does not accept arbitrary query expressions"
                             % (k, tool.get("tool")))


def _assert_on_panel(tool, args, targets, allowed=()):
    """Inputs to write families **must be on the panel**.

    `ex_field_set` does `setmap = {**spec_set, **args}` and then filters by `_writable`; it only asks
    "is this name a writable column", **not "is it on the panel"**. So filling one extra parameter bypasses the state machine.

    Measured: of 3284 field_set tools, **169** can quietly change "a column guarded by some update.status_transition
    tool": anonaddy's `alias_update(id, description)` has only description on its panel,
    but `active` is a writable column of Alias, so passing `active=false` deactivates the alias, while active is governed by
    another tool with guards (login / precondition / from-to).

    **The verifier cannot tell**: it asserts state, and if the state is right it is right; it cannot see which door was used.
    "Can it be done" and "should this tool be the one doing it" come apart here.

    `ex_upsert` is worse: `row[k] = v` has no `_writable` filtering at all, so any column can be written.

    The read side uses it too: without `lookup_by`, `ex_fetch` treats **all inputs as query conditions**, so
    `user_get(slug="x", password="y")` gains a search dimension the panel should not offer;
    this is the same thing as the `filter` backdoor (last time only the explicit `args["where"]` was closed, the fallback path leaked).

    Misspelled parameter names are **harmless** (they are not columns and were ignored anyway); the only thing blocked is "passing a column name that is
    not on the panel", which has **zero effect on legitimate calls**, since callers can only fill parameters on the panel.
    Evidence: across the 334 witness steps emitted, write families relied on it to pass **not a single time**.
    """
    ins = tool.get("input_schema") or {}
    bad = sorted(k for k in (args or {})
                 if k not in ("id", "entity") and k not in ins
                 and k not in (allowed or ()) and k in (targets or ()))
    if bad:
        raise GuardError(_msg(tool, "off_panel") or
                         "%s is not on the panel of %s -- this tool must not write it"
                         % (", ".join(bad), tool.get("tool")))


def ex_field_set(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    rk = spec.get("row_key") or default_key(env, entity, args, fallback={})
    row = env._find(entity, rk, args)
    if not row:
        raise GuardError(_msg(tool, "not_found")
                         or f"update {entity}: target row does not exist {rk}")
    spec_set = {k: resolve(v, env.state, args) for k, v in (spec.get("set") or {}).items()}
    setmap = {**spec_set, **{k: v for k, v in args.items() if k not in ("id", "entity")}}
    if spec.get("snapshot"):
        env._insert(spec.get("snapshot_target") or f"{entity}History", dict(row))
    writ = {c["name"] for c in env._writable(entity)}
    _assert_on_panel(tool, args, writ, spec_set)
    for k, v in setmap.items():
        if v is _UNRESOLVED:
            continue
        if k in writ and not (spec.get("skip_blank") and v in (None, "")):
            row[k] = v
    # evershop: after update_cart_item_qty changes qty, recompute the line amount (price*qty) and then the cart
    if entity == "CartItem" and "qty" in setmap and row.get("qty") is not None:
        price = row.get("product_price") or row.get("final_price") or 0
        qty = int(row["qty"])
        line = round(price * qty, 2)
        for c in ("sub_total", "line_total_with_discount", "total", "line_total_with_discount_incl_tax"):
            if c in row:
                row[c] = line
        if row.get("cart_id") is not None:
            _recalc_cart(env, row["cart_id"])
    for se in spec.get("side_effect", []) or []:
        env._events.append({"side_effect": se, "entity": entity})
    return {"ok": True, "result": {"id": row.get("id")}}

def ex_status_transition(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    rk = spec.get("row_key") or default_key(env, entity, args, fallback={})
    row = env._find(entity, rk, args)
    if not row:
        raise GuardError(_msg(tool, "not_found")
                         or f"status_transition {entity}: target row does not exist {rk}")
    col = spec.get("status_col", "status")
    # spec.to/from may be {$arg}/{$ref} expressions (v2 contract) or literals; resolve them,
    # falling back to args[col]/args["to"] when the spec leaves the target to the caller.
    to_raw = spec.get("to")
    to = resolve(to_raw, env.state, args) if to_raw is not None else (args.get(col) or args.get("to"))
    frm_raw = spec.get("from")
    frm = resolve(frm_raw, env.state, args) if frm_raw is not None else None
    if frm is _UNRESOLVED:
        frm = None
    if to is _UNRESOLVED:
        to = args.get(col) or args.get("to")
    # frm can be a single value or a list of "states allowed to transition from" (e.g. cancel_order from:[pending,processing])
    allowed_from = frm if isinstance(frm, list) else ([frm] if frm not in (None, "toggle") else None)
    if allowed_from is not None and row.get(col) not in allowed_from:
        raise GuardError((spec.get("messages") or {}).get("transition")
                         or f"illegal status transition: {entity}.{col} is currently {row.get(col)}, not in from {allowed_from}")
    if frm == "toggle":
        enum = spec.get("enum") or []
        to = enum[(enum.index(row.get(col)) + 1) % len(enum)] if row.get(col) in enum and enum else to
    row[col] = to
    if spec.get("timestamp_col"):
        row[spec["timestamp_col"]] = "2026-01-01T00:00:00Z"
    # cascade: with mode=insert actually insert child rows (e.g. cancel_order inserts OrderActivity,
    # update_order_payment_status inserts PaymentTransaction). The child's FK -> parent is matched by the parent PK name.
    parent_pk = next((c["name"] for c in env._cols(entity) if c.get("pk")), "id")
    for cs in spec.get("cascade", []) or []:
        env._events.append({"cascade": cs, "entity": entity})
        if cs.get("mode") == "insert":
            ce = cs.get("child_entity") or cs.get("entity")
            if not ce:
                continue
            cf = {}
            # Child FK points to parent: guess the same-named column (parent_pk); if e.g. order_activity_order_id does not match, find the FK column pointing at this entity
            fkcol = None
            for c in env._fk_cols(ce):
                te = c["fk_to"].split(".")[0]
                if te == entity:
                    fkcol = c["name"]; break
            if fkcol:
                cf[fkcol] = row.get(parent_pk)
            for k, v in cs.items():
                if k in ("child_entity", "entity", "mode"):
                    continue
                rv = _resolve_expr(v, env, args, row)
                if rv is not _UNRESOLVED and not isinstance(rv, dict):
                    cf[k] = rv
                elif not isinstance(v, dict):
                    cf[k] = v
            cf = _maybe_autogen(env, ce, cf)
            env._insert(ce, cf)
    return {"ok": True, "result": {"id": row.get("id"), col: to}}

def ex_relation_link(env, tool, args):
    spec = _spec(tool)
    rtype = spec.get("relation_type", "m2m")
    mode = spec.get("mode", "add")

    def _keyval(v):
        # {$arg:name}, or a bare string that happens to be a param name (set_video_tags object_key {"tag_id":"tags"}),
        # both resolve to this call's input value; otherwise treated as a literal
        if isinstance(v, dict) and "$arg" in v:
            return args.get(v["$arg"], _UNRESOLVED)
        if isinstance(v, str) and v in args:
            return args[v]
        return v

    subj = {k: _keyval(v) for k, v in (spec.get("subject_key") or {}).items()}
    obj = {k: _keyval(v) for k, v in (spec.get("object_key") or {}).items()}
    subj = {**subj, **{k: v for k, v in args.items() if k != "entity"}}
    if rtype == "m2m":
        tbl = spec.get("through_table")
        if mode == "set":
            # First clear the subject's existing link rows, then insert one per item of the object list (set_video_tags: tags is a list of names)
            env.state[tbl] = [r for r in env.state.get(tbl, []) if not all(r.get(k) == v for k, v in subj.items())]
            for ok, ov in obj.items():
                vals = ov if isinstance(ov, list) else [ov]
                for v in vals:
                    env._insert(tbl, {**subj, ok: v})
        elif mode == "add":
            env._insert(tbl, {**subj, **obj})
        elif mode in ("remove",):
            env.state[tbl] = [r for r in env.state.get(tbl, []) if not all(r.get(k) == v for k, v in {**subj, **obj}.items())]
        return {"ok": True, "result": {"relation": mode}}
    # fk / tree: set the fk column on the linked row
    fk = spec.get("fk_col")
    row = env._find(spec.get("entity") or tool.get("entity"), subj, args)
    if row and fk:
        row[fk] = (obj or {}).get("id") if mode != "remove" else None
    return {"ok": True, "result": {"relation": mode}}

def ex_delete(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    # `{}` and "not given" are different: `{}` = this operation does not target a single row (bulk delete) and should match the whole table;
    # only "not given" falls back to default_key guessing. The old code used `or`, so a falsy `{}` was treated as not given, and
    # a declared bulk delete would guess by id: passing an id deleted one row, not passing one deleted nothing.
    lb = spec.get("lookup_by")
    if lb is None:
        lb = default_key(env, entity, args, fallback=args)
    lb = {k: resolve(v, env.state, args) for k, v in lb.items() if k != "entity"}
    before = len(env.state.get(entity, []))
    removed = [r for r in env.state.get(entity, []) if all(r.get(k) == v for k, v in lb.items())]
    # guard_last: forbid deleting the last one (previously only in ex_delete_cascade;
    # now that crud.delete_cascade is merged in, it must be honoured here too)
    gl = spec.get("guard_last")
    if removed and gl and len(query(env.state, entity, gl)) <= 1:
        raise GuardError(_msg(tool, "guard_last")
                         or (spec.get("messages") or {}).get("guard_last")
                         or "cannot delete the last %s (%s)" % (entity, gl))
    if removed:
        _apply_on_child(env, tool, entity, removed, spec.get("on_child"))
    # Capture carts that need recomputing (after remove_cart_item the row is gone)
    recalc_carts = {r.get("cart_id") for r in removed if entity == "CartItem" and r.get("cart_id")}
    env.state[entity] = [r for r in env.state.get(entity, []) if r not in removed]
    if len(env.state[entity]) == before:
        raise GuardError(_msg(tool, "not_found") or f"delete {entity}: no matching row {lb}")
    for cid in recalc_carts:
        _recalc_cart(env, cid)
    ses = spec.get("side_effects")
    if isinstance(ses, list):
        # List form: update fields on related-table rows (e.g. clearing User.auto_follow_back_aspect_id when an aspect is deleted)
        for se in ses:
            te = se.get("entity")
            w = {k: resolve(v, env.state, args) for k, v in (se.get("where") or {}).items()}
            sset = {k: (resolve(v, env.state, args) if isinstance(v, dict) else v)
                    for k, v in (se.get("set") or {}).items()}
            for r in env.state.get(te, []):
                if all(r.get(k) == v for k, v in w.items()):
                    for k, v in sset.items():
                        r[k] = v
    elif isinstance(ses, dict):
        for ev in ses.get("dispatch_events", []):
            env._events.append({"event": ev})
    return {"ok": True, "result": {"deleted": len(removed)}}

def ex_soft_delete(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    pc = spec.get("pre_confirm")
    if isinstance(pc, dict):       # {confirm_field: expected_val} form: compare inputs field by field
        for k, v in pc.items():
            if args.get(k) != resolve(v, env.state, args):
                raise GuardError(_msg(tool, "confirm") or f"soft_delete confirmation failed: {k}")
    # pc=True (bool): only declares "needs user confirmation"; the deterministic runtime has no interaction, so treat it as confirmed and allow.
    lb = spec.get("lookup_by") or default_key(env, entity, args, fallback={})
    row = env._find(entity, lb, args)
    if not row:
        raise GuardError(_msg(tool, "not_found") or f"soft_delete {entity}: no matching row")
    setmap = spec.get("set") or {"deleted_at": "2026-01-01T00:00:00Z"}
    for k, v in setmap.items():
        row[k] = ("2026-01-01T00:00:00Z" if v in ("now()", "$now") else v)
    # List-form side_effects: update fields on related-table rows (located by lookup_by/where)
    # (e.g. setting the matching Person.closed_account to true on close_account)
    for se in (spec.get("side_effects") or []):
        te = se.get("entity")
        wsrc = se.get("lookup_by") or se.get("where") or {}
        w = {k: resolve(v, env.state, args) for k, v in wsrc.items()}
        sset = {k: (resolve(v, env.state, args) if isinstance(v, dict) else v)
                for k, v in (se.get("set") or {}).items()}
        for r in env.state.get(te, []):
            if all(r.get(k) == val for k, val in w.items()):
                for k, val in sset.items():
                    r[k] = val
    return {"ok": True, "result": {"soft_deleted": row.get("id")}}

def _cascade_items(spec):
    """Accept all three forms of `cascade` -> [{"child_entity", "fk_col"?}].

    The original implementation only accepted list-of-dict, but current specs really have a **dict form** (`{child_entity: fk_col}`, opencart's
    customer_delete / order_delete, stringer's feed_delete). With that, `for cas in dict`
    yields **key strings**, and `cas["child_entity"]` raises TypeError on the spot; 3 tools crashed outright.
    (mcp_env catches exceptions per call, so during work orders it shows up as one broken tool rather than a disaster, which is exactly why nobody noticed.)
    """
    cas = spec.get("cascade")
    if isinstance(cas, dict):
        return [{"child_entity": k, "fk_col": v if isinstance(v, str) else None}
                for k, v in cas.items() if isinstance(k, str)]
    out = []
    for c in (cas or []):
        if isinstance(c, dict) and isinstance(c.get("child_entity"), str):
            out.append(c)
        elif isinstance(c, str):
            out.append({"child_entity": c})
    return out


def ex_delete_cascade(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    lb = spec.get("lookup_by") or default_key(env, entity, args, fallback={})
    parent = env._find(entity, lb, args)
    if not parent:
        raise GuardError(_msg(tool, "not_found") or f"delete_cascade {entity}: no matching row")
    gl = spec.get("guard_last")
    if gl and len(query(env.state, entity, gl)) <= 1:
        raise GuardError(_msg(tool, "guard_last")
                         or f"cannot delete the last {entity} ({gl})")
    pid = row_id(env, entity, parent, strict=False)
    for cas in _cascade_items(spec):
        ce = cas["child_entity"]
        _named = cas.get("fk_col")
        fk = (next((c for c in env._fk_cols(ce) if c["name"] == _named), None) if _named else None)
        fk = fk or next((c for c in env._fk_cols(ce) if c["fk_to"].split(".")[0] == entity), None)
        if not fk: continue
        fkcol = fk["name"]
        # Child rows store the value of the column **named by** fk_to, not necessarily the parent's identity column:
        # artalk's Page.site_name -> Site.name, while Site also has an id column. Comparing against pid (=id)
        # matches no child row at all; the cascade silently does nothing while the parent is deleted, leaving orphans.
        # Fall back to pid only when the column cannot be read from the parent row (keeps the old behaviour).
        pval = parent.get(fk["fk_to"].split(".")[1], pid)
        if cas.get("mode") == "reassign":
            for r in env.state.get(ce, []):
                if r.get(fkcol) == pval: r[fkcol] = None
        else:
            env.state[ce] = [r for r in env.state.get(ce, []) if r.get(fkcol) != pval]
    _ic = id_col(env, entity)
    env.state[entity] = [r for r in env.state.get(entity, []) if r.get(_ic) != pid]
    return {"ok": True, "result": {"deleted": pid, "cascaded": True}}

def _resolve_upsert_templates(tmpl, env, args):
    """Resolve upsert's set_on_exists / insert_fields template dict into {col: val}.
    Template values may be: scalar constant / {$arg:col} / {$session:key} / {$ref:...} / {$const:v}.
    Key point: when the input referenced by {$arg} is absent (resolves to _UNRESOLVED), drop the column; the literal
    {"$arg":"stand_time"} must not be written into the row (otherwise later reads return it as a value and pollute read-back verification)."""
    if isinstance(tmpl, (list, tuple)):
        # **Pre-existing crash**: when `insert_fields` is a list of column names, this raised AttributeError right here,
        # blowing up the whole insert path of `crud.upsert` (684/692 tools in candidate specs were affected; of the 460
        # already cached, agents hand-fixed 423 by converting to dict, **37 remain broken**).
        # The list semantics match `_resolve_fields`: column name = param name, value taken from the inputs.
        tmpl = {c: {"$arg": c} for c in tmpl if isinstance(c, str)}
    out = {}
    for col, v in (tmpl or {}).items():
        if col == "entity":
            continue
        if not isinstance(v, dict):
            out[col] = v
            continue
        if "$arg" in v:
            if v["$arg"] in (args or {}):
                out[col] = args[v["$arg"]]
            # Input not given -> do not write the column (keep the old row value / leave empty on insert)
            continue
        if "$session" in v:
            rv = env.session.get(v["$session"], _UNRESOLVED)
            if rv is not _UNRESOLVED:
                out[col] = rv
            continue
        if "$ref" in v or "$const" in v:
            rv = resolve(v, env.state, args)
            if rv is not _UNRESOLVED:
                out[col] = rv
            continue
        out[col] = v
    return out


def ex_upsert(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args)
    key = {k: resolve(v, env.state, args) for k, v in (spec.get("key") or {}).items()}
    key = {**key, **{k: v for k, v in args.items() if k in key or not key}}
    # upsert does not even filter by _writable (below is a bare row[k] = v), so treat **all columns** as targets
    _assert_on_panel(tool, args, {c["name"] for c in env._cols(entity)},
                        set(key) | set(spec.get("set_on_exists") or {})
                        | set(spec.get("insert_fields") or {}))
    row = env._find(entity, key, args) if key else None
    if row:
        soe = spec.get("set_on_exists")
        upd = (_resolve_upsert_templates(soe, env, args) if soe
               else {k: v for k, v in args.items() if k != "entity"})
        for k, v in upd.items():
            row[k] = v
        return {"ok": True, "result": {"id": row.get("id"), "upsert": "update"}}
    fields = {**key, **_resolve_upsert_templates(
                  spec.get("insert_fields") or spec.get("set_on_exists"), env, args),
              **{k: v for k, v in args.items() if k != "entity"}}
    row = env._insert(entity, fields)
    return {"ok": True, "result": {"id": row["id"], "upsert": "insert"}}

def _auth_cols(env, spec):
    """-> (username_col, password_col). **Per-tool first, global fallback.**

    In a merged world each of the k repos has its own account table and column names (measured over 242 repos with account candidates,
    (username_col, password_col) has 64 combinations; honouring only the global pair would leave 55% of repos unable to log in
    in the merged world). The old approach was inject_persona stuffing two "merged columns" email/password into account rows
    to fit the global config; that was a backdoor for **synthetic** accounts, real accounts lack those columns. So the column names follow the tool:
    merge_world writes each login/register tool's own repo column names into its verify."""
    v = spec.get("verify") or {}
    a = env.auth_cfg
    return (v.get("username_col") or a.get("username_col", "username"),
            v.get("password_col") or a.get("password_col", "password"))


def ex_register(env, tool, args):
    spec = _spec(tool); entity = _ent(tool, spec, args) or env.auth_cfg.get("account_entity", "User")
    uname_col = _auth_cols(env, spec)[0]
    _uc, _pc = _auth_cols(env, spec)
    _assert_on_panel(tool, args, {c["name"] for c in env._cols(entity)},
                     set(spec.get("fields") or ()) | set(spec.get("set_on_create") or ())
                     | {_uc, _pc})
    # prechecks: the new contract is [{entity,where,negate?}] (v2 register checks username/email uniqueness);
    # the old contract is a list of strings like ["dup_name"]. Both are supported.
    # Switch-style preconditions such as {kind:"registrations_open_or_valid_invite"} (pod has open registration / valid invite)
    # are treated as passing (with no invite parameter, allow as "open registration").
    for pc in (spec.get("prechecks") or []):
        if isinstance(pc, dict):
            if "entity" in pc and "where" in pc:
                where = {k: resolve(v, env.state, args) for k, v in pc.get("where", {}).items()}
                hit = bool(query(env.state, pc["entity"], where))
                if hit == bool(pc.get("negate", False)):  # negate=True requires "does not exist" (hit must be False); otherwise requires existence (hit must be True)
                    return {"ok": False, "error": pc.get("message")
                            or f"registration precondition not met: {pc.get('entity')} {where}"}
            elif pc.get("kind") == "registrations_open_or_valid_invite":
                continue
            elif pc.get("kind") == "dup_name" and query(env.state, entity, {uname_col: args.get(uname_col)}):
                return {"ok": False, "error": "username already exists"}
        elif pc == "dup_name" and query(env.state, entity, {uname_col: args.get(uname_col)}):
            return {"ok": False, "error": "username already exists"}
    fields = _resolve_fields(spec, args, env, entity)
    # hash_password: in envs without salt/hash function, degrade to storing plaintext (consistent with plaintext seeds; login also compares plaintext)
    row = env._insert(entity, fields)
    # side_inserts: register also creates an Account (link_col=user_id, owner=true)
    for si in spec.get("side_inserts", []):
        sf = {}
        for k, v in (si.get("fields") or {}).items():
            sf[k] = resolve(v, env.state, args) if isinstance(v, dict) else v
        if si.get("link_col"):
            sf[si["link_col"]] = row["id"]
        env._insert(si["entity"], sf)
    # Registering counts as logged in (account_link resolves Account.id for later owner-scoped tools)
    link_ent = env.auth_cfg.get("account_link_entity")
    link_col = env.auth_cfg.get("account_link_col")
    acct_id = None
    if link_ent and link_col:
        accts = query(env.state, link_ent, {link_col: row["id"]})
        if accts:
            acct_id = accts[0]["id"]
    env.session = {"authed": True, "account_id": acct_id, "role": row.get("role"), "user_id": row["id"]}
    return {"ok": True, "result": {"id": row["id"], "account_id": acct_id}}

def ex_login(env, tool, args):
    spec = _spec(tool)
    acct = (spec.get("verify", {}) or {}).get("entity") or env.auth_cfg.get("account_entity", "Account")
    uc, pc = _auth_cols(env, spec)
    rows = query(env.state, acct, {uc: args.get("username") or args.get(uc),
                                   pc: args.get("password") or args.get(pc)})
    if not rows:
        return {"ok": False, "error": "login failed: wrong account or password"}
    # session_account_ref points at the id of the "account entity"; if auth keeps credentials on User and Account links via user_id,
    # the session account_id must resolve to Account.id (that is what owner-scoped tools compare owner_col against)
    link_ent = env.auth_cfg.get("account_link_entity")
    link_col = env.auth_cfg.get("account_link_col")
    sess_ref = env.auth_cfg.get("session_account_ref", "account_id")
    # The account entity does not necessarily have an id column: repos like octoprint use username as the primary key (real OctoPrint
    # users.py:919 does this, and the spec translates it faithfully). Unconditionally reading rows[0]["id"] used to raise KeyError('id');
    # 63 of the 220 repos in the library have an auth entity without an id column, so login was permanently unusable.
    # Still prefer id (behaviour for 154 repos is byte-for-byte unchanged), otherwise fall back to the entity's declared primary key.
    # Falling back to the pk rather than synthesising an integer id is because FKs pointing at this entity store the primary key value
    # (AppKey.user_id -> User.username); a synthetic id would make owner-scope silently find nothing.
    raw_id = row_id(env, acct, rows[0])
    acct_id = raw_id
    if link_ent and link_col and acct != link_ent:
        accts = query(env.state, link_ent, {link_col: raw_id})
        if accts:
            acct_id = row_id(env, link_ent, accts[0])
    env.session = {"authed": True, sess_ref: acct_id, "account_id": acct_id,
                   "role": rows[0].get("role"), "user_id": raw_id,
                   "realm": tool.get("auth_realm")}
    # If a Person entity exists with owner_id -> <account entity>, also bring the "federated identity of the logged-in account" Person.id
    # into the session (so $session.person_id can inject the author into Post/Comment/Photo.author_id). For local accounts user_id==person_id.
    if "Person" in env.entities:
        oc = next((c["name"] for c in env._fk_cols("Person")
                   if c["fk_to"].split(".")[0] == acct), None)
        if oc:
            pers = query(env.state, "Person", {oc: raw_id})
            if pers:
                env.session["person_id"] = row_id(env, "Person", pers[0])
    # session_fields: copy columns from the auth row (e.g. tenant_id/roles/admin/builder) into the session, for $session.<key> scopes.
    # Multi-tenant owner-scoped search relies on this to carry the "current tenant" into scope.where.
    for skey, scol in env.auth_cfg.get("session_fields", {}).items():
        if skey not in env.session and scol in rows[0]:
            env.session[skey] = rows[0][scol]
    return {"ok": True, "result": f"logged in as {acct}#{raw_id} (account {acct_id})"}

def ex_logout(env, tool, args):
    env.session = {"authed": False, "account_id": None, "role": None}
    return {"ok": True, "result": "logged out"}

def ex_permission(env, tool, args):
    spec = _spec(tool)
    if not env.session["authed"]:
        return {"ok": False, "error": "not authenticated"}
    req = spec.get("required") or {}
    need_role = req.get("role") if isinstance(req, dict) else None
    if need_role and env.session.get("role") != need_role:
        return {"ok": False, "error": f"requires role {need_role}"}
    rel = spec.get("relation")
    on = spec.get("on")
    if rel in ("owner", "creator") and on:
        row = env._find(on["resource"], on.get("lookup_by", {}), args)
        if row and row.get("owner_id") not in (None, env.session["account_id"]) and row.get("user_id") not in (None, env.session["account_id"]):
            return {"ok": False, "error": "not the resource owner"}
    return {"ok": True, "result": "allow"}

# Keys in action.trigger's exec_spec that runtime actually reads. **Declared but read by nobody = silently does nothing**,
# which is one source of its 20.9% no_op rate (an order of magnitude higher): the beets batch of tools wrote
# `select_by` / `fields`, which the executor does not recognise, so the receipt says ok and the world does not move.
_TRIGGER_KEYS = ("target", "set", "spawn", "set_on_spawn", "dispatch_events",
                 "output", "entity", "from_parent", "from_cart", "set_on_create", "messages")


def ex_trigger(env, tool, args):
    """Business actions with structural side effects; this family is the **escape hatch**.

    Each of the 11 systems has exactly one generic escape hatch, all with the same shape: **name + typed input +
    typed output + handler**(Hasura Action / PostgREST /rpc / Rails member route /
    DRF @action / Prisma TypedSQL ...). Our problem was never a wrong concept but being **too thin**:
    only three keys target/spawn/set, with neither typed output nor declared side effects.

    So what is added here is "declare and deliver":
        · Declaring no side effect at all -> **error**. 20 of the 91 trigger tools in current specs (22%) are like this,
            matching the measured 20.9% no_op rate. For an action that changes nothing, the caller cannot tell whether it took effect.
        · Declared but nothing happened -> **error**. Previously, when target was not found, set was silently skipped and the receipt was still ok.
        · Keys in exec_spec that the executor does not recognise -> **error**, no longer silently ignored.
    """
    spec = _spec(tool)
    tgt = spec.get("target")
    if isinstance(tgt, str):        # 7 in current specs have this shape (pufferpanel); it used to raise AttributeError on the spot
        tgt = {"entity": tgt}
    tgt = tgt if isinstance(tgt, dict) else {}
    entity = tgt.get("entity") or _ent(tool, spec, args)

    # The executor only reads these two keys in target. The beets batch wrote select_by / fields;
    # "select a batch of rows by query and change fields" is a **real need**, but the executor did not recognise it, so it silently did nothing.
    _unknown = [k for k in spec if k not in _TRIGGER_KEYS and not k.startswith("_")]
    _unknown += ["target.%s" % k for k in tgt
                 if k not in ("entity", "lookup_by") and not str(k).startswith("_")]
    if _unknown:
        raise StateError("action.trigger does not recognize %s in exec_spec -- a key nobody reads silently does nothing"
                         % ", ".join(sorted(_unknown)))
    if not [k for k in ("set", "spawn", "dispatch_events") if spec.get(k)]:
        raise StateError("action.trigger declares no side effects (set / spawn / dispatch_events) -- "
                         "an action that changes nothing gives the caller no way to tell whether it took effect")

    row = env._find(entity, tgt.get("lookup_by") or default_key(env, entity, args, fallback={}), args) \
        if entity else None
    if row is None and spec.get("set"):
        raise GuardError(_msg(tool, "not_found")
                         or "action.trigger target row does not exist: %s %s" % (entity, tgt.get("lookup_by")))
    _n_changed = 0
    # set: write inputs/expressions onto the target row (e.g. checkout writes shipping_address_id/payment_method)
    for k, v in (spec.get("set") or {}).items():
        rv = _resolve_expr(v, env, args, row or {})
        if row and rv is not _UNRESOLVED and not isinstance(rv, dict):
            row[k] = rv
            _n_changed += 1
    spawned = []
    for sp in spec.get("spawn", []):
        ce, n = sp["entity"], int(sp.get("n", 1))
        link = sp.get("link_col")
        for i in range(n):
            f = dict(sp.get("fields", {}))           # Old contract: spawn[].fields gives the fields directly
            # from_cart: {child_col: parent_col}, copy columns from the parent row (cart) to the child row (order) (evershop checkout)
            for sub_col, par_col in (sp.get("from_cart") or sp.get("from_parent") or {}).items():
                if row and par_col in row:
                    f[sub_col] = row[par_col]
            if link and row:
                f[link] = row.get("id")
            # set_on_spawn: resolve declarative expressions ($const/$arg/$session/$ref/$resolve/$compute/$auto)
            args_spawn = dict(args, _spawn_entity=ce)
            for _ in range(3):
                prog = False
                for col, v in (sp.get("set_on_spawn") or {}).items():
                    if col in f and not isinstance(f[col], dict):
                        continue
                    rv = _resolve_expr(v, env, args_spawn, f)
                    if rv is not _UNRESOLVED and not isinstance(rv, dict):
                        f[col] = rv
                        prog = True
                if not prog:
                    break
            # Fallback for non-null business columns such as uuid
            f = _maybe_autogen(env, ce, f)
            env._check_fks(ce, f)
            spawned.append(env._insert(ce, f)["id"])
            _n_changed += 1
    # dispatch_events: actually applied (not just queued). Supported:
    #   {create_order_activity:{comment, customer_notified}} -- insert an activity for the just-spawned order
    #   {disable_cart:{set:{status:..}}}                    -- set fields on the target cart row
    for ev in spec.get("dispatch_events", []):
        env._events.append({"event": ev})
        _n_changed += 1
        if "create_order_activity" in ev and spawned:
            oa = ev["create_order_activity"]
            env._insert("OrderActivity", {
                "order_activity_order_id": spawned[0],
                "comment": oa.get("comment", ""),
                "customer_notified": oa.get("customer_notified", False),
            })
        elif "disable_cart" in ev and row:
            ds = ev["disable_cart"].get("set") or {}
            for k, v in ds.items():
                row[k] = v
    if not _n_changed:
        # **Side effects were declared but none happened.** Previously this path returned ok while the world did not move;
        # the same disease as crud.fetch treating not-found as success: failing while reporting success.
        raise StateError("action.trigger declared side effects, but none happened -- "
                         "most likely no set value resolved, or the spawned child entity is not in this world")
    res = {"triggered": True, "spawned": spawned}
    # typed output: project the caller-visible fields from the target row. The escape hatch needs a **declared return contract**,
    # otherwise downstream (verifier / witness) only gets an always-true triggered:true.
    out = spec.get("output")
    if isinstance(out, dict) and isinstance(out.get("fields"), list) and row:
        res["result"] = {c: row.get(c) for c in out["fields"] if isinstance(c, str)}
    return {"ok": True, "result": res}

def ex_emit(env, tool, args):
    spec = _spec(tool)
    rec = spec.get("record") or {}
    table = rec.get("table") or f"{_ent(tool, spec, args) or 'Dispatch'}Log"
    fields = {"status": "sent", **(rec.get("set") or {}), **{k: v for k, v in args.items() if k != "entity"}}
    row = env._insert(table, fields)
    env._events.append({"emit": spec.get("channel", "event")})
    return {"ok": True, "result": {"dispatched": row["id"], "channel": spec.get("channel")}}

def ex_probe(env, tool, args):
    spec = _spec(tool)
    target = args.get("target") or args.get("url") or args.get("host") or json.dumps(spec.get("target_key"))
    h = int(hashlib.sha256(str(target).encode()).hexdigest(), 16)
    result = "online" if h % 2 == 0 else "offline"      # Deterministic stub: hash by target
    wb = spec.get("write_back")
    if wb and wb.get("col"):
        ent = _ent(tool, spec, args)
        row = env._find(ent, {k: v for k, v in args.items() if k != "entity"}, args)
        if row: row[wb["status_col"] if wb.get("status_col") else wb["col"]] = result
    return {"ok": True, "result": {"probe": result}}


EXECUTORS = {
    "crud.insert": ex_insert, "crud.fetch": ex_fetch, "crud.delete": ex_delete,
    "crud.soft_delete": ex_soft_delete, "crud.delete_cascade": ex_delete_cascade, "crud.upsert": ex_upsert,
    "update.field_set": ex_field_set, "update.status_transition": ex_status_transition,
    "update.relation_link": ex_relation_link,
    # Search: **one family, ranking method goes through exec_spec.rank**. The three old names below are kept as aliases;
    # the 338 current specs still use them, and removing them would make them "unimplemented families".
    "search": ex_search, "search.aggregate": ex_aggregate,
    "search.filtered_list": ex_filtered_list, "search.keyword_weighted": ex_keyword, "search.semantic": ex_semantic,
    "guard.permission": ex_permission, "guard.auth": ex_login, "guard.logout": ex_logout,
    "auth.register": ex_register,
    "action.trigger": ex_trigger, "action.emit": ex_emit, "action.probe": ex_probe,
    # base fallback (when family only gives the first level)
    "crud": ex_insert, "update": ex_field_set,
    "guard": ex_login, "action": ex_trigger,
}


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------
class _StateView:
    """Minimal env view for the Verifier; eval_state only needs .state and ._now.
    There is no Env instance at verification time (it judges a final-state snapshot), but the evaluator should not fork a second implementation for that."""

    def __init__(self, state, now=None):
        self.state = state
        self._now = now or "2026-01-01T00:00:00"


def _pred_to_state(pred):
    """The four old ops -> State. **Translate, do not coexist**: coexisting would be yet another language,
    and the whole point of this change is to avoid a third one."""
    ent = pred.get("entity")
    scope = [_legacy_clause(k, v)
             for k, v in (pred.get("where") or {}).items()]
    op = pred["op"]
    if op == "exists":
        return {"entity": ent, "scope": scope, "card": {"op": "gte", "n": 1}}
    if op == "not_exists":
        return {"entity": ent, "scope": scope, "card": {"op": "eq", "n": 0}}
    if op == "count_gte":
        return {"entity": ent, "scope": scope, "card": {"op": "gte", "n": int(pred.get("n", 1))}}
    if op == "field_eq":
        # The original was rows[0].get(col) == value: with multiple matching rows it **depends on insertion order**,
        # and the distractor's job is precisely to insert rows: a poisoned row placed first can flip the verdict.
        # Changed to "some row satisfies both where and col==value", independent of order.
        return {"entity": ent, "card": {"op": "gte", "n": 1},
                "scope": scope + [_legacy_clause(pred["col"], pred.get("value"))]}
    raise ValueError("unknown predicate op: %s" % op)


class Verifier:
    """Judge the final state. **Shares eval_state with the guards**; otherwise world properties expressible by guards could not be judged by the verifier.

    There is no call context at verification time, so Value only accepts lit / col / sym / old-style $ref (cross-table lookup, still meaningful
    on the final state). $arg / $actor raise StateError: that means the postcondition is wrong
    (build_contract should already have resolved $anchor into a literal), and **it must not silently become "no match"
    as in the old implementation**: the old query() treated _UNRESOLVED as a non-matching row, so a not_exists whose reference
    resolved to nothing would silently evaluate True and the task would be "completed" out of thin air.
    """

    def eval(self, pred, state, now=None):
        if isinstance(pred, dict) and "node" in pred:
            # grammar IR (Count tree) goes straight to eval_node; placeholder postconditions (UNKNOWN -> raise, never silently true)
            return bool(eval_node(pred, _StateView(state, now), None, None, site="postcondition"))
        op = pred.get("op")
        if op == "and":
            return all(self.eval(c, state, now) for c in pred["clauses"])
        if op == "or":
            return any(self.eval(c, state, now) for c in pred["clauses"])
        if op == "not":
            return not self.eval(pred["clause"], state, now)
        st = pred if op == "state" else _pred_to_state(pred)
        return eval_state(st, _StateView(state, now), None, None)


def run_task(spec, task, verbose=True, embed_fn=None):
    env = Env(spec, embed_fn=embed_fn)
    if verbose:
        print(f"=== env: {spec['env_id']}  entities {len(env.entities)} tools {len(env.tools)} ===")
        print(f"goal: {task['goal_nl']}\n")
    for i, step in enumerate(task["witness"], 1):
        res = env.call(step["tool"], step.get("args", {}))
        if verbose:
            flag = "ok" if res["ok"] else "ERR"
            print(f"  [{i}] {step['tool']} -> {flag} {res.get('result', res.get('error'))}")
        if not res["ok"]:
            print(f"  !! witness step {i} failed")
            return False
    v = Verifier()
    ok = v.eval(task["verifier"], env.state)
    if verbose:
        print(f"\nverifier final state: {ok} | initial seed state (should be False): {v.eval(task['verifier'], Env(spec).state)}")
    return ok


def project_surface(spec):
    """Deterministic projection: strip the env-spec down to a "user-facing surface" fed to user_sim. user_sim must be fully blind to internal structure
    (like a real user who sees the UI, not the DB), so **only what a user can perceive is kept**: what the app is, which entities and their user-facing columns,
    and for each tool its verb / target entity / read-write nature / whether login is required / whether scope is private or public.
    **Stripped**: fk_to, guards.preconditions, exec_spec internals, seed_sources/raw_path, verifier, snapshot, etc.
    This projection is physical isolation: it does not rely on a prompt asking user_sim not to look, it simply never shows it."""
    SENSITIVE = ("password", "passwd", "token", "secret", "hash", "salt", "api_key", "apikey")
    def user_cols(e):                       # Columns the user "can see": drop id / audit columns / FK internals / sensitive credentials
        out = []
        for c in e.get("columns", []):
            n = c["name"]
            if c.get("type") == "id" or c.get("audit") or n == "id" or c.get("fk_to"):
                continue
            if any(s in n.lower() for s in SENSITIVE):
                continue
            out.append(n)
        return out
    ents = [{"name": e["name"], "fields": user_cols(e)} for e in spec.get("entities", [])]
    VERB = {"search": "search/lookup", "crud": "create/update/delete", "update": "update",
            "guard": "login/permissions", "auth": "register", "action": "trigger action",
            # Old-format op-level fallback
            "create": "create", "read": "search/lookup", "delete": "delete",
            "login": "login", "logout": "logout"}
    tools = []
    for t in spec.get("tools", []):
        fam = t.get("family") or t.get("op", "")
        base = fam.split(".")[0]
        sc = (t.get("exec_spec") or {}).get("scope")
        if sc and sc.get("owner_col") and sc.get("visibility_col"):
            scope_kind = "public pool + my private items"
        elif sc and sc.get("owner_col"):
            scope_kind = "only mine (my own)"
        elif sc:
            scope_kind = "restricted"
        else:
            scope_kind = "public/global"
        tools.append({"tool": t["tool"], "does": VERB.get(base, base),
                      "on": (t.get("exec_spec") or {}).get("entity") or t.get("entity"),
                      "needs_login": bool((t.get("guards") or {}).get("requires_auth")),
                      "scope": scope_kind})
    return {"env_id": spec.get("env_id"),
            "about": spec.get("about") or spec.get("description") or spec.get("env_id"),
            "entities": ents, "tools": tools}


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "surface":     # Projection: env-spec -> user-facing surface (fed to user_sim)
        print(json.dumps(project_surface(json.load(open(sys.argv[2]))), ensure_ascii=False, indent=2))
    else:
        spec = json.load(open(sys.argv[1]))
        task = json.load(open(sys.argv[2]))
        run_task(spec, task)
