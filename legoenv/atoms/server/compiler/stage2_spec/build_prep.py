#!/usr/bin/env python3
"""Deterministic pre-translation layer of Build Spec: collect/<repo>.json -> spec.raw.json + prep_report.json.

**Why this layer exists.** The old spec_builder did two jobs in one LLM call: mechanically transcribe
tens of thousands of entities and operations into an EnvSpec, and decide what to keep, how to name it and what description to write. Measured retention was 48% of entities /
23% of impls / 7.7% of guards -- the model's budget burned on transcription and the judgment never happened.

Once the runtime was unified onto the collector-side State shape, transcription became **mechanical**. So we split it:
**det translates everything and drops nothing (anything dropped must be accounted for); the agent only judges.**

The product spec.raw.json is the **full candidate set**, not the final spec -- selection is the agent's job, and what it cuts is
"tasks that can never be done on this repo", so it must state that explicitly and record it in _dropped, rather than the old code's
silent truncation like impls[:120].

-- The collect v3 contract changes four things relative to v2; this file targets v3 and stays v2-compatible --
  (1) `required_columns` -> `params`: parameters and columns are different things. params only holds **what the caller passes**;
     `binds:"Entity.col"|null` points back to the column it lands in. Session injection / system values are now expressed via effects.sets.
  (2) `effects[].sets`: {col: Value}, adds "what value it becomes" -- v2's fields only said which columns changed.
  (3) effects is the **sole authority** on the touched surface: read / search also emit effects (`row_read` / `row_search`),
     `search_spec` moves into `row_search`, and `impls[].entity` is retired.
  (4) `scope` is a property of the **read**, not of the search; `row_read` and `row_search` share it;
     how the app responds when a row is not visible is demoted to the repo-level `conventions.read_denied`.
"""
import json
import os
import re
import sys

# **The single source of truth for the operator vocabulary is `runtime/grammar.py`.** This layer is the compiler's middle end, and what it translates is that
# language -- keep a second copy of the vocabulary and the two drift apart (this happened three times already: the $ symbol table, session_fields,
# and the operator table itself, each time "the middle layer is narrower than both ends and does not report it"). build_probe uses the same path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rt  # noqa: E402,F401  (puts the runtime directory on sys.path)
import grammar as _GRAM          # noqa: E402

# -- Closed type vocabulary ------------------------------------------------
_TYPES = ("text", "int", "float", "bool", "datetime", "id", "json")
_TYPE_ALIAS = {
    "varchar": "text", "char": "text", "string": "text", "str": "text", "uuid": "text",
    "clob": "text", "lob": "text", "enum": "text", "citext": "text", "inet": "text",
    "integer": "int", "bigint": "int", "smallint": "int", "tinyint": "int", "serial": "int",
    "bigserial": "int", "int64": "int", "int32": "int", "long": "int", "number": "int",
    "numeric": "float", "decimal": "float", "double": "float", "real": "float",
    "money": "float", "boolean": "bool",
    "timestamp": "datetime", "timestamptz": "datetime", "date": "datetime",
    "time": "datetime", "localdatetime": "datetime", "arrowtype": "datetime",
    "instant": "datetime", "zoneddatetime": "datetime", "offsetdatetime": "datetime",
    "jsonb": "json", "array": "json", "map": "json", "object": "json", "list": "json",
    "dict": "json", "binary": "text", "bytea": "text", "blob": "text", "varbinary": "text",
    "foreignkey": "id", "objectid": "id", "reference": "id", "file": "text",
    # -- Frappe / ERPNext DocType field types (a system of their own; the whole hrms family uses them) --
    "link": "id", "dynamic link": "id", "data": "text", "check": "bool",
    "select": "text", "currency": "float", "percent": "float", "table": "json",
    "table multiselect": "json", "small text": "text", "long text": "text",
    "text editor": "text", "code": "text", "markdown editor": "text",
    "attach": "text", "attach image": "text", "read only": "text", "password": "text",
    "duration": "int", "rating": "float", "color": "text", "barcode": "text",
    "geolocation": "json", "signature": "text", "html editor": "text",
    # -- Django / DRF Field class names --
    "charfield": "text", "textfield": "text", "slugfield": "text", "emailfield": "text",
    "urlfield": "text", "filefield": "text", "imagefield": "text", "integerfield": "int",
    "positiveintegerfield": "int", "positivesmallintegerfield": "int", "bigintegerfield": "int",
    "smallintegerfield": "int", "floatfield": "float", "decimalfield": "float",
    "booleanfield": "bool", "nullbooleanfield": "bool", "datetimefield": "datetime",
    "datefield": "datetime", "timefield": "datetime", "durationfield": "int",
    "jsonfield": "json", "uuidfield": "text", "autofield": "id", "bigautofield": "id",
    "onetoonefield": "id", "manytomanyfield": "json", "arrayfield": "json",
    # -- Other dialects --
    "mediumtext": "text", "longtext": "text", "tinytext": "text", "nvarchar": "text",
    "nchar": "text", "guid": "text", "uniqueidentifier": "text", "pk": "id", "rowid": "id",
    "literal": "text", "bit": "bool", "year": "int", "double precision": "float",
    "email": "text", "url": "text", "slug": "text", "any": "text",
    "string": "text", "str": "text", "num": "float", "bool": "bool",
}


_TYPE_FLAT = {}          # see norm_type: synonym lookup table with spaces/underscores removed (filled at module load)

_ARRAYISH = re.compile(r"^\[.+\]$|\[\s*\]$|^(list|array|set|seq)\s*[<(\[]")


_TYPE_FLAT.update({re.sub(r"[^a-z0-9]", "", k): v for k, v in _TYPE_ALIAS.items()})
_TYPE_FLAT.update({re.sub(r"[^a-z0-9]", "", k): k for k in _TYPES})


def norm_type(t):
    """Native DB / language type -> closed vocabulary. Returns None when undecidable, and the caller records it -- never guess text to slip through."""
    if not isinstance(t, str):
        return None
    s = t.strip().lower()
    if s in _TYPES:
        return s
    if _ARRAYISH.search(s):
        return "json"                              # int[] / [id] / list<x> -- a sequence of things
    # For ambiguous `a/b` forms (timestamptz/datetime), take the first part that normalizes
    for part in re.split(r"\s*[/|]\s*", s):
        if not part:
            continue
        if part in _TYPES:
            return part
        base = re.split(r"[\s(\[<]", part, 1)[0]   # varchar(255) / int(10) unsigned
        # **Check base against the closed vocabulary itself first.** It used to check only the alias table, so the base of `int(11)` is `int` --
        # which is in _TYPES but not in _TYPE_ALIAS, so it was undecidable and fell back to text. Measured: 271 cases.
        if base in _TYPES:
            return base
        if base in _TYPE_ALIAS:
            return _TYPE_ALIAS[base]
        # Strip spaces/underscores/hyphens and look up again: `SmallText`->`small text`, `TextEditor`->
        # `text editor`, `Table MultiSelect`->`table multiselect`. Same vocabulary, just different spellings.
        flat = re.sub(r"[^a-z0-9]", "", part)
        if flat in _TYPE_FLAT:
            return _TYPE_FLAT[flat]
    return None


# -- Columns ---------------------------------------------------------------
_COL_KEEP = ("name", "type", "pk", "nullable", "fk_to", "enum", "audit", "immutable",
             "default", "on_delete", "max", "min", "unique")
_COL_ALIAS = {
    "is_pk": "pk", "primary_key": "pk", "pk_part": "pk",
    "not_null": "_notnull", "notnull": "_notnull",
    "fk": "fk_to", "fk_constraint": "fk_to", "self_ref_to": "fk_to", "FK": "fk_to",
    "ondelete": "on_delete", "fk_on_delete": "on_delete",
    "enum_values": "enum", "choices": "enum", "values": "enum",
    "max_length": "max", "maxlength": "max", "length": "max",
    "auto_now_add": "audit", "auto_now": "audit",
    "db_column": "name", "column": "name", "col": "name", "columnName": "name", "colName": "name", "colName": "name",
    # `null: true` means `nullable: true` (the opposite of `not_null`; do not mix them up). Measured: 372 cases.
    "null": "nullable", "is_nullable": "nullable", "optional": "nullable",
    "reqd": "_notnull", "required": "_notnull",       # Frappe's reqd:1 = required
}
_AUDIT_RE = re.compile(r"(?i)^(created|updated|modified|changed|inserted)_?(at|on|time|date)$"
                       r"|^(date_)?(created|updated|modified)$|^(ctime|mtime)$")
_SOFT_RE = re.compile(r"(?i)^(is_)?(deleted|archived|trashed|removed|disabled)(_at)?$")


def norm_col(c, drop, mend=None):
    """One column -> a runtime-contract column. Unknown keys are dropped and recorded; **normalizing on upstream's behalf is recorded too** (mend)."""
    if isinstance(c, str):
        return {"name": c, "type": "text"}, ["column has only a name, type missing (fell back to text)"]
    if not isinstance(c, dict):
        drop.append(("column", "neither object nor string: %r" % (c,)))
        return None, []
    out, notes, src = {}, [], {}
    for k, v in c.items():
        a = _COL_ALIAS.get(str(k))
        if a is not None and mend is not None:
            # The contract fixes the vocabulary of column keys; hitting the alias table means the miner copied the source framework's spelling
            # (Django's max_length/choices, DDL's not_null). The conversion is correct, but it **must leave a trace**
            # -- a silent rename means we can never see whether this ratio goes up or down. Measured: 1208/112734 = 1.07%.
            mend.append(("column", "key %r is not in the contract vocabulary, mapped by alias to %r" % (str(k), a)))
        src[a if a is not None else str(k)] = v
    if "_notnull" in src and "nullable" not in src:
        src["nullable"] = not bool(src.pop("_notnull"))
    src.pop("_notnull", None)
    name = src.get("name")
    if not isinstance(name, str) or not name:
        drop.append(("column", "no column name: %s" % json.dumps(c, ensure_ascii=False, default=str)[:80]))
        return None, []
    out["name"] = name
    t = norm_type(src.get("type"))
    if t is None:
        notes.append("type %r does not normalize -> text" % (src.get("type"),))
        if mend is not None:
            mend.append(("column", "%s: type %r does not normalize, fell back to text" % (name, src.get("type"))))
        t = "text"
    out["type"] = t
    for k in ("pk", "nullable", "audit", "immutable", "unique"):
        if k in src and isinstance(src[k], bool):
            out[k] = src[k]
    if isinstance(src.get("fk_to"), str) and "." in src["fk_to"]:
        out["fk_to"] = src["fk_to"]
    elif isinstance(src.get("fk_to"), str) and src["fk_to"]:
        out["_fk_bare"] = src["fk_to"]              # only the entity name was given; filling in the pk must wait until the index is built
    if isinstance(src.get("enum"), list) and src["enum"]:
        out["enum"] = [x for x in src["enum"] if isinstance(x, (str, int, float, bool))]
    for k in ("default", "on_delete", "max", "min"):
        if k in src and not isinstance(src[k], (dict, list)):
            out[k] = src[k]
    return out, notes


# -- Table-level constraints -----------------------------------------------
_CONS_KEEP = ("unique", "check", "conditional")
_CONS_ALIAS = {"uk": "unique", "unique_index": "unique", "unique_lookup": "unique",
               "unique_caseinsensitive": "unique", "conditional_unique": "conditional",
               "conditional_required": "conditional", "conditional_optional": "conditional",
               "regex": "check", "format": "check", "min_length": "check",
               "id_format": "check", "id_pattern": "check", "max_count": "check"}
_CONS_DROP_SILENT = ("index", "index_gin", "pk", "primary", "PRIMARY", "composite_pk",
                     "fk", "foreign", "not_null", "required", "INDEX", "relation")


def norm_constraint(cn, cols, drop):
    """One table-level constraint -> runtime shape. cols is used to verify the columns really exist -- a constraint on a ghost column makes every write
    get rejected, with an error message pointing at a nonexistent column, which the agent has no way to fix."""
    if not isinstance(cn, dict):
        drop.append(("constraint", "not an object: %r" % (cn,)))
        return None
    kind = cn.get("kind")
    kind = _CONS_ALIAS.get(kind, kind)
    if kind in _CONS_DROP_SILENT:
        drop.append(("constraint", "kind=%s is not an integrity constraint (index has no semantics / pk lives on the column / fk is guarded by the runtime)" % kind))
        return None
    if kind not in _CONS_KEEP:
        drop.append(("constraint", "unknown kind %r" % (cn.get("kind"),)))
        return None
    if kind == "unique":
        c = cn.get("cols") or cn.get("columns") or cn.get("col")
        c = [c] if isinstance(c, str) else c
        if not isinstance(c, list) or not c or not all(isinstance(x, str) for x in c):
            drop.append(("constraint", "unique cols has the wrong shape: %r" % (c,)))
            return None
        miss = [x for x in c if x not in cols]
        if miss:
            drop.append(("constraint", "unique references nonexistent columns %s" % miss))
            return None
        return {"kind": "unique", "cols": c}
    if kind == "check":
        # The collector writes exactly the runtime shape {left:{col}, op, right}.
        # What remains is {cols} / {expr} free text -- the runtime cannot structure those, so drop them explicitly.
        left = cn.get("left")
        cl = norm_clause({"col": left.get("col") if isinstance(left, dict) else left,
                          "op": cn.get("op"), "value": cn.get("right")}, drop, cols, "check")
        if not cl:
            return None
        out = {"kind": "check", "left": {"col": cl["col"]}, "op": cl["op"]}
        # Unary operators (is_null / is_not_null) **have no right operand** -- norm_clause explicitly
        # returns only {col, op} for arity=1 ops. This used to read cl["value"] unconditionally, so one `is_not_null`
        # check constraint made **the whole build crash with KeyError in the prep stage, losing the entire repo in 0 seconds**
        # (seven repos on an earlier run, e.g. libredesk/wger/bencher/dspace/lemmy/tracim).
        # The runtime's check_constraints does `cl = {..., "value": c.get("right")}`; for unary operators
        # that value never takes part in evaluation, so **omitting the key** is the correct shape, not stuffing in a None.
        # Once again "the middle layer is narrower than both ends": the prompt taught it, grammar supports it, the runtime reads it, and it got stuck here.
        if "value" in cl:
            out["right"] = cl["value"]
        return out
    # conditional: if / then are both **clause arrays** (conjunctions) -- the runtime's check_constraints
    # reads them exactly that way with `all(match_state_clause(r, x) for x in ifs)`.
    out = {}
    for fld in ("if", "then"):
        v = cn.get(fld)
        v = [v] if isinstance(v, dict) else v
        if not isinstance(v, list) or not v:
            drop.append(("constraint", "conditional %s has the wrong shape (%s)" % (fld, type(cn.get(fld)).__name__)))
            return None
        conj = []
        for x in v:
            n = norm_clause(x, drop, cols, "conditional.%s" % fld)
            if n is None:
                return None                          # dropping one conjunct = a looser condition, so discard the whole thing
            conj.append(n)
        out[fld] = conj
    return {"kind": "conditional", "if": out["if"], "then": out["then"]}


def norm_clause(cl, drop, cols, where):
    """Normalize a single {col, op, value} clause -- shared by check / conditional / State.scope."""
    if not isinstance(cl, dict):
        drop.append(("clause", "%s not an object: %r" % (where, cl)))
        return None
    col = cl.get("col") or cl.get("column") or cl.get("left")
    if isinstance(col, dict):
        col = col.get("col")
    if not isinstance(col, str):
        drop.append(("clause", "%s has no col: %s" % (where, json.dumps(cl, ensure_ascii=False, default=str)[:80])))
        return None
    if cols is not None and col not in cols:
        drop.append(("clause", "%s references nonexistent column %r" % (where, col)))
        return None
    op = norm_op(cl.get("op"))
    if op is None:
        drop.append(("clause", "%s op %r is not in the runtime vocabulary" % (where, cl.get("op"))))
        return None
    if op in _UNARY_OPS:
        # Unary operators carry no value (arity=1 in `grammar.FIELD_OPS`). If one is written it is ignored -- but we **must not**
        # drop the whole clause for "having no value", that would take the whole State down with it.
        return {"col": col, "op": op}
    _raw = cl.get("value", cl.get("right"))
    if isinstance(_raw, dict) and "from" in _raw:
        # State goes through `state_value`, which accepts `{"_legacy": ...}` and hands it to `_resolve_filter_val`
        # (the comment at runtime.py:251 says exactly "the $ref / $subquery from the old where").
        fv, fwhy = from_ref(_raw, legacy=True, op=op)
        if fv is None:
            drop.append(("clause", "%s from-subquery cannot be translated: %s" % (where, fwhy)))
            return None
        return {"col": col, "op": op, "value": fv}
    v = norm_value(_raw)
    if v is None:
        drop.append(("clause", "%s value shape not recognized: %r" % (where, cl.get("value"))))
        return None
    return {"col": col, "op": op, "value": v}


# -- State (the shared machinery of guards / constraints / verifier) -------
# **This table must equal the runtime's `grammar.FIELD_OPS`.** It once had only 7 entries, while the prompt and
# grammar both had 14 -- so the miner wrote `icontains` per the prompt, det judged it None here,
# `norm_clause` dropped that clause, and `norm_state`'s discipline is "drop one clause = the wall widens, discard the whole
# State". **The prompt taught it plainly, the runtime supported it plainly, and the middle layer threw away the whole wall.**
# The existing corpus had 0 cases (it predates that prompt change), so it was latent and blew up the day we re-mined.
# This was the third time this round we hit the same shape: the middle layer is narrower than both ends, and does not report it.
_OPS = tuple(sorted(_GRAM.FIELD_OPS))            # exactly grammar's table, no separate copy
_UNARY_OPS = tuple(k for k, (ar, _f) in _GRAM.FIELD_OPS.items() if ar == 1)
# Only **spelling aliases** go here (symbols, underscore variants, old spellings). `neq` is the old State spelling; the IR's canonical form is `ne`
# -- this follows the IR; the runtime accepts both (runtime.py:176).
_OP_ALIAS = {"==": "eq", "=": "eq", "is": "eq", "neq": "ne", "!=": "ne", "<>": "ne",
             ">": "gt", ">=": "gte", "=>": "gte", "<": "lt", "<=": "lte", "=<": "lte",
             "not_in": "nin", "notin": "nin", "like": "contains", "ilike": "icontains",
             "isnull": "is_null", "notnull": "is_not_null", "isnotnull": "is_not_null",
             "starts_with": "startswith", "ends_with": "endswith", "band": None}


def norm_op(op):
    if op is None:
        return "eq"
    if not isinstance(op, str):
        return None
    s = op.strip().lower()
    return s if s in _OPS else _OP_ALIAS.get(s)


_FROM_KEYS = {"entity", "where", "get"}
# The outer operators that take a **list**: the subquery must return **all** values of a column, which is the runtime's
# `$subquery` (_resolve_filter_val scans the whole table collecting select), not `$ref` (which takes only one column of the first
# matching row). **This was added later** -- the previous version always translated to `$ref`, so
# `feed_id in (all feeds in this category)` was quietly translated into `feed_id in <id of the first feed>`;
# a set test collapsed into a scalar test, without any report. Measured: 4 places (sentry / v2 x2 / wagtail).
_LIST_OPS = {"in", "nin"}


def from_ref(v, legacy=False, op=None):
    """collect's `{"from": ...}` subquery -> the runtime's `{"$ref": ...}`. -> (value, None) or (None, reason).

    **This is the fourth time the middle layer was narrower than both ends.** The collector prompt teaches `{"from": ...}` as one of the seven
    Value forms ("Legal wherever a Value is"), contract_check's `_from_bad` validates it,
    and the runtime accepts it on both paths (`resolve()`'s `$ref` takes one column / `_resolve_filter_val`'s `$subquery`
    takes the list of a column, with State routed there via `{"_legacy": ...}`) -- only `norm_value` returned None,
    so every occurrence was dropped as "value shape not recognized". Measured on the 188 already-built repos: 772 places lost
    (sets 636 / clause 136), across 158 repos. The previous three were `icontains`, `$session.k`,
    `$actor.<non-id>`, the same shape.

    **Translate what can be translated; for what cannot, state the reason clearly** (passed upward to be recorded and reported by the checker); never degrade silently:
      - aggregation `{"agg": "sum"}` -- `$ref` takes only one column of the first matching row, `$subquery` only takes a list;
        neither can compute an aggregate. Forcing it turns "how much was spent" into "how much the first payment was".
      - empty `where` -- the subquery would pick the first row of that table, and `_find` only refuses loudly when there are multiple rows.
        That is exactly the "silently modifies the wrong row" category.
      - non-equality `where` -- the runtime's `$ref.where` goes through `query()`, which only does equality.
      - `from` nested in `from` -- the prompt says plainly: one level only.
    """
    sq = v.get("from") if isinstance(v, dict) else None
    if not isinstance(sq, dict):
        return None, u"from is not an object"
    _extra = sorted(set(sq) - _FROM_KEYS)
    if _extra:
        # Keys like `{"join": ..., "on": ...}` that the prompt never taught and the checker never defined: translating along entity/where/get
        # would drop the join condition entirely -- the result looks legal but queries a different table.
        return None, u"from has keys outside the protocol %s (only entity / where / get are accepted)" % (_extra,)
    ent = sq.get("entity")
    if not isinstance(ent, str) or not ent.strip():
        return None, u"from has no entity (say which table is being read)"
    g = sq.get("get")
    if isinstance(g, dict) and "agg" in g:
        return None, (u"aggregating subquery (agg=%r): the runtime can only take one column of the first matching row, "
                      u"it cannot compute aggregates" % (g.get("agg"),))
    col = g if isinstance(g, str) else (g.get("col") if isinstance(g, dict) else None)
    if not isinstance(col, str) or not col.strip():
        return None, u"from.get does not say which column to take"
    w = sq.get("where")
    if isinstance(w, dict):
        w = [w]
    if not isinstance(w, list) or not w:
        return None, u"from has no where -- a subquery with an empty condition would pick the first row of the table"
    out = {}
    for cl in w:
        if not isinstance(cl, dict):
            return None, u"where contains a non-object clause: %r" % (cl,)
        c = cl.get("col")
        if isinstance(c, dict):
            c = c.get("col")
        if not isinstance(c, str):
            return None, u"where clause has no col"
        # NOTE: this variable must not be named op -- that is the **outer clause's** operator, which decides whether this subquery returns a scalar or
        #    a list. Naming it op would overwrite it with the inner "eq" inside the loop, so `in` would never reach
        #    the `$subquery` branch. Caught on the spot by a unit test.
        _cop = norm_op(cl.get("op"))
        if _cop != "eq":
            return None, u"where only supports equality, got op=%r" % (cl.get("op"),)
        val = cl.get("value", cl.get("right"))
        if isinstance(val, dict) and "from" in val:
            return None, u"from nested inside from (only one level allowed)"
        nv = norm_value(val)
        if nv is None:
            return None, u"where value shape not recognized: %r" % (val,)
        if "lit" in nv:
            out[c] = nv["lit"]
        elif "sym" in nv:
            out[c] = "2026-01-01T00:00:00"
        elif "ref" in nv:
            rv, why = _sym_ref(nv["ref"])
            if rv is None:
                return None, u"where reference does not resolve: %s" % why
            out[c] = rv
        else:
            return None, u"where value is {col: ...} (in-row comparison), cannot be resolved inside a subquery"
    if op in _LIST_OPS:
        ref = {"$subquery": {"entity": ent, "where": out, "select": col}}
    else:
        ref = {"$ref": {"entity": ent, "where": out, "col": col}}
    return ({"_legacy": ref} if legacy else ref), None


def norm_value(v):
    """The four forms {lit}/{ref}/{col}/{sym}. Bare scalars are accepted as literals. Returns None if it cannot be resolved.

    NOTE: `{"from": ...}` is **not translated here** -- its product is a runtime execution-time reference, not a State
    Value, and the two consumers need different wrappers (State wants `{"_legacy": ...}`, sets wants a bare
    `{"$ref": ...}`). Each call site calls `from_ref()` itself first; see the comments there.
    """
    if v is None:
        return {"lit": None}
    if not isinstance(v, dict):
        return {"lit": v}
    for k in ("lit", "col"):
        if k in v:
            return {k: v[k]}
    if "ref" in v:
        r = v["ref"]
        return {"ref": r} if isinstance(r, str) and r.startswith("$") else None
    if "sym" in v:
        s = v["sym"]
        if s == "$now":
            return {"sym": "$now"}
        return {"ref": s} if isinstance(s, str) and s.startswith("$") else None
    if "value" in v:
        return norm_value(v["value"])
    return None


# -- $ symbols -> runtime execution-time references ------------------------
def _sym_ref(r):
    """`"$arg.x"` / `"$actor.id"` / `"$session.k"` -> a reference the runtime accepts.
    -> (value, None) if recognized; (None, reason) if not.

    **This table must be a superset of the widest of the three: what the prompt teaches, what the runtime accepts, and what det translates**,
    otherwise this middle layer becomes a funnel that does not report errors. It has leaked twice already:

    - `$session.k` -- the second example in prompt section 2.2 (`{"tenant_id":"$session.org_id"}`)
      is exactly this, and the runtime accepts `{"$session": k}` (runtime.py:227), yet `_row_key` did not translate it,
      so it fell into the "bare string taken as literal" branch and became a query for `tenant_id == '$session.org_id'`.
    - `$actor.<non-id>` -- the old code only looked at the `$actor` prefix and dropped everything after the dot, so `$actor.company_id`
      was treated as `$actor.id` and written as account_id. Measured: **232 places, 52 repos**; the wrongly written columns are mostly
      **tenant-boundary columns** like group_id / tenant_id / company_id -- rows landed in the wrong tenant,
      with no signal at all. The runtime itself refuses (runtime.py:221 raises directly); only this layer was guessing on its behalf.
    """
    if not isinstance(r, str) or not r.startswith("$"):
        return None, "not a $ symbol: %r" % (r,)
    head, _, tail = r.partition(".")
    if head == "$arg":
        return ({"$arg": tail}, None) if tail else (None, "$arg has no parameter name after it")
    if head == "$actor":
        if tail and tail != "id":
            # **"The tenant/company/group the current user belongs to" is a real need** (measured: 52 repos write it), while the session
            # only holds account_id. The runtime already left an opening: `auth.session_fields`
            # ({session key: column on the account row}) copies those columns into the session at login (runtime.py:2264),
            # and its comment says exactly "e.g. tenant_id/roles/admin/builder". Nobody ever wired it up from
            # the miner's evidence -- 305 repos have an auth block, only 16 configure session_fields.
            # So we translate to $session.<col> here, and seal() fills in the config after the agent picks the account entity.
            # If it cannot be configured (the column is not on the account row), the runtime cannot resolve it -> the column is skipped,
            # which is equivalent to "not writing it"; **nothing is lost**.
            return {"$session": tail}, None
        return {"$session": "account_id"}, None
    if head == "$session":
        return ({"$session": tail}, None) if tail else (None, "$session has no key name after it")
    if head == "$subject":
        return None, u"$subject is an edge-level concept with no counterpart while executing a single tool"
    return None, u"unrecognized symbol %s" % r


_CARD_ALIAS = {"exists": {"op": "gte", "n": 1}, "not_exists": {"op": "eq", "n": 0},
               "one": {"op": "gte", "n": 1}, "1": {"op": "gte", "n": 1},
               "many": {"op": "gte", "n": 2}, "some": {"op": "gte", "n": 1},
               "none": {"op": "eq", "n": 0}, "absent": {"op": "eq", "n": 0},
               "zero": {"op": "eq", "n": 0}, "0": {"op": "eq", "n": 0},
               "0..1": {"op": "lte", "n": 1}, "at_most_one": {"op": "lte", "n": 1}}
# Same as above, derived from `grammar.CARD_OPS`; extra keys in the dict are only spelling aliases.
_CARD_OP = dict({k: k for k in _GRAM.CARD_OPS},
                **{"neq": "ne", ">=": "gte", "==": "eq", "=": "eq", "<=": "lte",
                   ">": "gt", "<": "lt", "!=": "ne", "<>": "ne"})


def norm_card(c):
    """`card` -> `{op, n}`. **Operators follow `grammar.CARD_OPS`; all six are accepted, no more rewriting.**

    This used to say "the runtime's card has only gte / eq / lte" and translated `gt n` into `gte n+1`.
    That statement is now false: grammar's count node evaluates directly via `FIELD_OPS` (grammar.py:359),
    and build_probe's world seeding has long had gt / lt / ne branches (build_probe.py:633, 648) --
    **this was the only narrow layer of the three**. Now it is a pure translation: det does not rewrite upstream's meaning.
    (The existing corpus has 0 card entries with gt / lt / ne, so this change makes no difference to existing products.)
    """
    if isinstance(c, str):
        return _CARD_ALIAS.get(c.strip().lower())
    if isinstance(c, bool):
        return None
    if isinstance(c, int):
        return {"op": "gte", "n": c} if c > 0 else {"op": "eq", "n": 0}
    if isinstance(c, dict):
        op, n = c.get("op"), c.get("n")
        if not isinstance(n, int) or isinstance(n, bool):
            return None
        op = _CARD_OP.get(op)
        return {"op": op, "n": n} if op else None
    return None


# $ref namespaces on the guard side: the runtime's state_value only accepts these four.
# v3 output also produced $generated / $request / $return / $output / $result / $params /
# $computed / $context (about 500 in total, 3.7%) -- they point either at call return values or at HTTP-layer
# things, **none of which exist yet when guards are evaluated**, so they cannot be accepted.
_REF_NS = ("$arg", "$actor", "$session", "$subject")


def scan_actor_cols(d):
    """All `$actor.<col>` (col != id) appearing anywhere in the collect -> ordered list of column names.

    **A separate independent pass, not collected along the translation path** -- it must cover `sets` / `row_key` /
    `needs` / `provides` / `constraints`, every position (measured: 408 in needs, 232 in sets),
    and the normalizers for those paths are spread across four places; threading it through would dirty the signatures and still miss one or two.

    This **only says "which columns this repo mentioned"**; it does not judge whether they are on the account row -- that has to wait
    until the agent picks the account entity, and seal() decides.
    """
    out, seen = [], set()

    def walk(o):
        if isinstance(o, dict):
            r = o.get("ref")
            if isinstance(r, str) and r.startswith("$actor.") and r != "$actor.id":
                c = r.split(".", 1)[1]
                if "." not in c and c not in seen:   # two hops ($actor.a.b) cannot be expressed here
                    seen.add(c)
                    out.append(c)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(d)
    return out


def norm_state(st, ents, drop, where):
    """Normalize one State + grounding check. **The entity and columns must really exist** -- a guard on a ghost entity
    queries an empty table at runtime: not_exists is always true, exists always false, a wall in a random direction."""
    if not isinstance(st, dict):
        drop.append(("state", "%s not an object" % where))
        return None
    ent = st.get("entity")
    if not isinstance(ent, str) or ent not in ents:
        drop.append(("state", "%s entity %r is not in the schema" % (where, ent)))
        return None
    card = norm_card(st.get("card"))
    if card is None:
        drop.append(("state", "%s card %r does not normalize" % (where, st.get("card"))))
        return None
    cols = ents[ent]
    scope = []
    for cl in (st.get("scope") if isinstance(st.get("scope"), list) else []):
        n = norm_clause(cl, drop, cols, "%s.scope" % where)
        if n is None:
            return None                              # drop one clause = the wall widens; discard the whole State
        if "value" not in n:                         # unary operator: no right operand, skip the value checks below
            scope.append(n)
            continue
        v = n["value"]
        # `$actor.<non-id>` in guards is likewise rerouted to $session -- eval_state raises on it directly
        # (runtime.py:221); this layer used to check only the namespace head and ignore what follows the dot, so it passed through unchanged
        # and the whole guard blew up at runtime. After rerouting it uses the session_fields configured by seal().
        if "ref" in v and isinstance(v["ref"], str) and v["ref"].startswith("$actor.") \
                and v["ref"] != "$actor.id":
            v = n["value"] = {"ref": "$session." + v["ref"].split(".", 1)[1]}
        if "ref" in v and v["ref"].split(".")[0] not in _REF_NS:
            drop.append(("state", "%s references %s, which does not exist when guards are evaluated" % (where, v["ref"])))
            return None
        scope.append(n)
    # **This emits source syntax; compilation is deferred to `seal()`.** `{entity, scope[], card}` is source syntax,
    # grammar's Pred/Count tree is the IR. Compilation must happen, of course, but **after the agent** --
    # the build spec agent is the **author** (it decides which walls are real, which to promote, which to drop),
    # and authors work on source syntax; the IR only appears where it is consumed. Same reason as "don't make the miner hand-write trees".
    return {"entity": ent, "scope": scope, "card": card}


def norm_needs(needs, ents, drop, where):
    """edges[].needs -> one-level DNF preconditions for the runtime.
    **Dropping any conjunct from a disjunct widens the wall**, so that whole disjunct is discarded; the remaining disjuncts stay usable
    (losing one "or" branch only makes the wall stricter, never a false pass). Returns None if all are dropped."""
    if not isinstance(needs, list) or not needs:
        return None
    groups = needs if isinstance(needs[0], list) else [needs]
    out = []
    for gi, grp in enumerate(groups):
        if not isinstance(grp, list):
            drop.append(("needs", "%s disjunct %d is not an array" % (where, gi)))
            continue
        conj, bad = [], False
        for st in grp:
            n = norm_state(st, ents, drop, "%s[%d]" % (where, gi))
            if n is None:
                bad = True
                break
            conj.append(n)
        if not bad and conj:
            out.append(conj)
    return out or None


# ── effect.kind → family ────────────────────────────────────────────────
_EFF_ALIAS = {
    "insert": "row_insert", "create": "row_insert", "row_create": "row_insert",
    "row_insert_many": "row_insert", "audit_log": "row_insert",
    "update": "row_update", "row_update_many": "row_update", "row_update_bulk": "row_update",
    "increment": "row_update", "row_recalc": "row_update", "row_rename": "row_update",
    "row_replace": "row_update", "compute": "row_update", "lifecycle_transition": "row_update",
    "delete": "row_delete", "row_destroy": "row_delete", "row_delete_many": "row_delete",
    "row_delete_bulk": "row_delete", "row_delete_conditional": "row_delete",
    "row_truncate": "row_delete", "cascade": "cascade_delete", "cascade_delete": "cascade_delete",
    "soft_delete": "row_soft_delete",
    "upsert": "row_upsert", "row_insert_or_update": "row_upsert",
    "row_update_or_insert": "row_upsert", "create_or_update": "row_upsert",
    "row_read_or_create": "row_upsert",
    "read": "row_read", "row_select": "row_read", "select": "row_read", "read_check": "row_read",
    "search": "row_search", "row_list": "row_search", "list": "row_search", "query": "row_search",
    "m2m_add": "link", "m2m_remove": "unlink", "link_or_unlink": "link",
    "dispatch_webhook": "dispatch", "dispatch_email": "dispatch", "pubsub": "dispatch",
    "event": "dispatch", "signal": "dispatch", "enqueue": "dispatch", "webhook": "dispatch",
    "email_provider": "external", "call": "external", "method_call": "external",
    "delegate": "external", "side_effect": "external",
    # A catch-all escape hatch that appeared in v3: 4338 `action` entries, 80% without even an entity, all free-text
    # description -- i.e. "something happened but I can't classify it". Mapped to external (real side effect, no row written),
    # and recorded so the feedback round can see this ratio.
    "action": "external", "sorted_set": "external", "cache_set": "cache",
    "cache_flush": "cache", "invalidate": "cache",
    "auth_session": "auth", "auth_cookie": "auth", "auth_signout": "auth",
}
# Priority of structural effects (ones that really change rows in the world): when deciding family, take the one ranked first
_EFF_RANK = ("spawn", "row_upsert", "row_insert", "row_soft_delete", "cascade_delete",
             "row_delete", "link", "unlink", "row_update", "row_search", "row_read",
             "dispatch", "external", "schedule", "probe", "cache", "auth")
_WRITE_KINDS = ("row_insert", "row_update", "row_upsert", "row_soft_delete", "row_delete",
                "cascade_delete", "link", "unlink", "spawn")
_FAM_BY_EFF = {
    "row_insert": "crud.insert", "row_upsert": "crud.upsert", "row_read": "crud.fetch",
    "row_search": "search",
    # Cascade is not an operation, it is an option of delete -- 0 of 11 schema->API generators treat it as a separate operation,
    # every standard treats it as a schema property (ON DELETE CASCADE / Prisma referentialActions / TypeORM onDelete).
    "row_delete": "crud.delete", "cascade_delete": "crud.delete",
    "row_soft_delete": "crud.soft_delete", "row_update": "update.field_set",
    "link": "update.relation_link", "unlink": "update.relation_link",
    "spawn": "action.trigger", "dispatch": "action.emit", "external": "action.emit",
    "schedule": "action.emit", "probe": "action.probe",
}
# op fallback table. **`action` maps to emit, not trigger** -- probes measured that 90% of `action.trigger`
# is no_op (123/136): `ex_trigger` does nothing without set / spawn; the Env builds, the call returns
# ok, and the world does not move at all. `ex_emit` at least writes a delivery record, so the effect is **assertable**.
# trigger is kept only for those with real spawn / row_update structural effects (that path goes through _EFF_RANK).
_FAM_BY_OP = {"create": "crud.insert", "read": "crud.fetch", "update": "update.field_set",
              "delete": "crud.delete", "search": "search",
              # The "guard" fallback was removed: op=guard without write effects already returns None above;
              # those with write effects are picked up by _EFF_RANK. Measured on the whole corpus: 0 hits -- keeping it is just a rotting dead entry.
              "action": "action.emit"}
# **Only the seven ops in the contract are accepted.** This table used to also accept link / unlink / probe / soft_delete /
# schedule / external -- those six are **effect.kind names**, not ops. The contract (choose one of seven) does not accept them,
# `contract_check` flags them as violations, yet this place quietly assigned them a family: **the collector side errors, the consumer side accepts anyway**,
# so that violation never hurts, and the escape hatch becomes a shortcut. Measured on the whole corpus: these six had 0 hits; removed together with
# the dead op=guard entry above.
# entry.kind -> whether a tool is generated. **Only the first three generate tools** -- cli / job are real entry points but users cannot call them,
# internal is internal implementation. A **missing `entry` does not mean internal**: the 433 existing collect files do not have this field yet;
# when missing, keep the original behavior, otherwise one change would wipe out the entire existing corpus.
_ENTRY_EXPOSED = ("http", "rpc", "graphql")
_ENTRY_KINDS = _ENTRY_EXPOSED + ("cli", "job", "internal")

# _FAM_BY_METHOD is retired: method no longer decides family, it lands unchanged in exec_spec.rank.
# The runtime's _rank_of only scores keyword/hybrid/semantic; exact/substring are pure filters.
_RANK_METHODS = ("exact", "substring", "keyword", "hybrid", "semantic")


def _kind(ef):
    k = ef.get("kind") if isinstance(ef, dict) else None
    return _EFF_ALIAS.get(k, k)


def eff_kinds(impl):
    """Normalized list of effect kinds (order-preserving, deduplicated)."""
    out = []
    for ef in (impl.get("effects") if isinstance(impl.get("effects"), list) else []):
        k = _kind(ef)
        if isinstance(k, str) and k not in out:
            out.append(k)
    return out


def _first_eff(impl, kinds):
    for ef in (impl.get("effects") if isinstance(impl.get("effects"), list) else []):
        if isinstance(ef, dict) and _kind(ef) in kinds:
            return ef
    return {}


def pick_family(impl, lifecycle_via, mend=None):
    """-> (family, why). **Effects decide the family, op is the fallback** -- family decides how the runtime changes the world,
    while op is only a coarse label given at collection time. Listen to whichever is closer to the truth."""
    op = impl.get("op")
    idl = impl.get("id_local")
    ks = eff_kinds(impl)
    # **Once authentication has an explicit signal, look it up in a table instead of guessing from names.** The effects vocabulary used to have nothing that could say "this is authentication"
    # (login's effects are external+row_read+row_update, which by _EFF_RANK would land on update.field_set),
    # so we could only rely on function names -- and the regex already judged WebAuthnCredential.saveLogin (saving a credential) as a login.
    # The `auth` effect carries a mode, settled with one table lookup; it also gives the account table and the two credential columns (see the candidates in prep).
    _au = _first_eff(impl, ("auth",))
    if _au:
        _m = _au.get("mode")
        _f = {"verify": "guard.auth", "signout": "guard.logout",
              "register": "auth.register"}.get(_m if isinstance(_m, str) else None)
        if _f:
            return _f, "auth effect mode=%s" % _m
        # mode missing or invalid: **don't guess**. Fall through; it ends up in the auth hole of _EFF_RANK and gets recorded.
    if isinstance(idl, str):
        # NOTE: **transitional fallback; delete it after re-mining, rather than waiting for it to stop triggering on its own.**
        # Name matching has no causal relation to "is this authentication": WebAuthnCredential.saveLogin **saves a
        # credential**; after re-mining it still has no auth effect and will still hit these three. So the exit condition is
        # explicit: **once guard.auth tools in the corpus are basically all decided by the auth effect, delete this block**
        # (not before that -- the existing 433 corpus files have no auth effect at all; deleting it would lose every login tool).
        if re.search(r"(?i)login|signin|authenticate", idl) and "row_search" not in ks:
            return "guard.auth", "id_local looks like login"
        if re.search(r"(?i)logout|signout", idl):
            return "guard.logout", "id_local looks like logout"
        if re.search(r"(?i)register|signup", idl) and "row_insert" in ks:
            return "auth.register", "id_local looks like register and has row_insert"
    if "row_search" in ks:
        # **The ordering method is a parameter, not a family.** _FAM_BY_METHOD used to compress the miner's 5 methods
        # into 3 families, and the difference between exact(2802)/substring(372) was lost in the compression. Now method lands
        # unchanged in exec_spec.rank; the runtime only scores keyword/hybrid/semantic, the other two degrade to pure filters.
        m = (_first_eff(impl, ("row_search",)) or {}).get("method")
        return "search", "row_search.method=%r (goes into rank, no longer splits families)" % (m if isinstance(m, str) else None,)
    if op == "guard" and not [k for k in ks if k in _WRITE_KINDS]:
        # **No tool is generated.** op=guard without changing the world = middleware / policy method; in the real app
        # the client **cannot call it**; making it a tool means shipping a tool that does not exist in the real world. Of 365
        # candidates in the whole corpus, 195 have no effects at all, with names like policy_show / authorize / *_guard /
        # auth_check_token (Rails Pundit, Django view mixins).
        # And the **rule it expresses is not lost** -- the checker appears as the object of a `requires` edge on every real operation
        # that calls it, and via edges[].needs becomes guards.preconditions of those tools.
        # The cost is also small: a tool that returns allow/deny without changing the world provides no information the real operation cannot,
        # and hitting the real wall yields a more informative message.
        return None, "op=guard with no structural effect: middleware/policy, not an endpoint"
    for k in _EFF_RANK:
        if k in ks:
            f = _FAM_BY_EFF.get(k)
            if not f and mend is not None:
                # Kinds ranked in `_EFF_RANK` but missing from `_FAM_BY_EFF` (cache / auth) would
                # **silently slip through** and end at the op fallback -- so an operation "with a structural effect" would be treated as
                # "without a structural effect". Neither kind appeared once in the v3 corpus, so today
                # nothing is broken; but precisely because nothing is broken it should be recorded: the day re-mining produces them, we need to know on the spot.
                mend.append(("family", "%r in effects is ranked in _EFF_RANK but has no family mapping; slipped through" % k))
            if f:
                if k == "row_update" and lifecycle_via:
                    return "update.status_transition", "row_update and matches lifecycle.via"
                return f, "effects contain %s" % k
    f = _FAM_BY_OP.get(op)
    if f:
        return f, "effects have no structural entry, fallback by op=%s" % op
    return None, "op=%r and effects have no usable entry" % (op,)


# **How** `entity` was decided. This reason string goes into `_evidence.entity_why` (read by the agent)
# and also serves as a discriminator (is it the "primary effect" tier), so it must be a constant rather than scattered literals --
# the discriminator does startswith on the literal's prefix, so changing the wording changes control flow.
EW_PRIMARY   = "primary effect %s lands on this table"
EW_ID_PREFIX = "fell back to the entity prefix of id_local"
EW_FROM_BINDS = "neither effects nor id_local said; inferred %s from params.binds"
EW_NONE      = "cannot determine the entity"

def eff_entity(impl, ents, mend=None):
    """**The touched surface comes from effects, not impls[].entity**.

    In v2, `impls[].entity` was a scalar while effects was an array carrying entities; the contract contradicted itself: measured 18.7%
    of operations span >=2 tables, and 4.7% of declared entities are not even in the entity set of their own effects
    (`Label.delete` reports Board) -- that field carries the **ownership axis**, not the touched surface. v3 retired it;
    the fallback here only exists to absorb the remaining 4%.
    """
    for k in _EFF_RANK:
        for ef in (impl.get("effects") if isinstance(impl.get("effects"), list) else []):
            if isinstance(ef, dict) and _kind(ef) == k and ef.get("entity") in ents:
                return ef["entity"], EW_PRIMARY % (k,)
    if impl.get("entity") is not None and mend is not None:
        # v2's `impls[].entity` carries the **ownership axis** ("this operation hangs under the Board aggregate"),
        # not the touched surface -- measured: 4.7% of declared entities are not even in the entity set of their own effects.
        # v3 retired it (0/24409 across the whole corpus), so this fallback is removed with it. One record is kept: if v2 output is fed in again
        # we can see it, instead of quietly resolving along the wrong axis.
        mend.append(("entity", "impls[].entity is retired (it is the ownership axis, not the touched surface); no longer used as fallback"))
    if isinstance(impl.get("id_local"), str) and impl["id_local"].split(".")[0] in ents:
        return impl["id_local"].split(".")[0], EW_ID_PREFIX
    # Last resort: **parameter binding**. `binds:"Order.note"` is saying this operation acts on Order --
    # the effect omitted the entity, but the parameter binding did not. Take the most frequent table (for multi-table operations it is the main table);
    # ties are broken by name for determinism -- set/dict iteration order must not enter the det layer.
    cnt = {}
    for pp in (impl.get("params") or []):
        b = pp.get("binds") if isinstance(pp, dict) else None
        if isinstance(b, str) and "." in b:
            te = b.split(".", 1)[0]
            if te in ents:
                cnt[te] = cnt.get(te, 0) + 1
    if cnt:
        best = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        return best, EW_FROM_BINDS % (best,)
    return None, EW_NONE


# ── params → input_schema ───────────────────────────────────────────────
def norm_params(impl, ent, ents, drop, tid, mend=None):
    """`params` -> (input_schema, binds).

    **Parameters and columns are different things**: params only holds **what the caller passes**, and `binds` points back to the column it lands in
    (null if there is no matching column -- a search q or a plaintext password are of this kind). Session injection and system values
    are not here; they are in effects.sets, spelled out as Values.

    binds is kept for the probe: **11.8% of parameters are FK columns**; to really call the tool once, the probe must supply "an id
    that really exists in the seed", and binds is how it knows which table to fetch it from.
    """
    ins, binds = {}, {}
    ps = impl.get("params")
    if not isinstance(ps, list):
        # v2 compatibility: 96.8% of required_columns elements are {name,type,source} rather than bare strings,
        # and those with source=session **must never enter the panel** -- if they did, the agent could pass org_id/user_id itself,
        # and the ownership check would be void on the spot.
        for c in (impl.get("required_columns") or []):
            if isinstance(c, str):
                ins[c] = "text"
            elif isinstance(c, dict) and isinstance(c.get("name"), str):
                if c.get("source") in ("session", "derived", "db", "system"):
                    continue
                ins[c["name"]] = norm_type(c.get("type")) or "text"
        return ins, binds
    for p in ps:
        if isinstance(p, str):                        # 1770 entries (4.3%) gave only a name
            ins[p] = "text"
            continue
        if not isinstance(p, dict) or not isinstance(p.get("name"), str):
            drop.append(("param", "param shape of %s not recognized: %s"
                         % (tid, json.dumps(p, ensure_ascii=False, default=str)[:60])))
            continue
        n = p["name"]
        t = norm_type(p.get("type"))
        if t is None:
            # A fallback, not a drop -- the parameter still goes into the panel. But **the fallback must be loud**: a parameter that is really int/datetime
            # treated as text means the probe fills it with a string, and a whole batch of tools is falsely reported as error.
            # (That is the shape of the time `build_probe` lost all the types from a rich-format input_schema.)
            if mend is not None and p.get("type") is not None:
                mend.append(("param", "%s's %s: type %r does not normalize, fell back to text"
                                      % (tid, n, p.get("type"))))
            t = "text"
        ins[n] = t
        b = p.get("binds")
        if isinstance(b, str) and b:
            if "." not in b:
                # The contract states "`binds` must carry the entity prefix" -- when an operation spans tables, a bare column name cannot tell
                # which table it is. This used to be patched with the tool's primary entity, yet across all 28892 binds in v3
                # **not one lacks the prefix**: that was a v2-era patch. Removed, replaced with a hard record --
                # smoothing things over for upstream would make the "compliance rate" number permanently invisible.
                drop.append(("param", "%s.%s: binds %r lacks the entity prefix (required by the contract)" % (tid, n, b)))
                continue
            te, _, tc = b.partition(".")
            if te in ents and tc in ents[te]:
                binds[n] = b
            else:
                drop.append(("param", "%s.%s: binds %s points outside the schema" % (tid, n, b)))
    return ins, binds


# -- sets: {col: Value} ----------------------------------------------------
def norm_sets(ef, cols, drop, tid):
    """`effects[].sets` -> the runtime's `set`.

    v2's `fields` only said "which columns changed", not "to what" -- measured: 99.5% of write effects carry no value.
    Consequence: after calling `cancel_order` the status is unchanged; "cancel" never happened in the world; the verifier
    also does not know what target value to check. v3 adds `sets`, with values in the State Value vocabulary, so the verifier's
    postconditions and the spec's sets **are the same language and the same evaluator**, with no translation in between.
    """
    out = {}
    st = ef.get("sets")
    if not isinstance(st, dict):
        return out
    for col, v in st.items():
        if not isinstance(col, str):
            continue
        if cols is not None and col not in cols:
            drop.append(("sets", "sets of %s writes ghost column %r" % (tid, col)))
            continue
        if isinstance(v, dict) and "from" in v:
            # sets go into exec_spec's `set`, evaluated by `_resolve_expr`, which accepts `{"$ref": ...}` directly
            # (runtime.py:100). We **must not** wrap it in `_legacy` here -- that is the State-side routing.
            fv, fwhy = from_ref(v)
            if fv is None:
                drop.append(("sets", "%s.%s from-subquery cannot be translated: %s" % (tid, col, fwhy)))
                continue
            out[col] = fv
            continue
        nv = norm_value(v)
        if nv is None:
            drop.append(("sets", "%s.%s value shape not recognized: %r" % (tid, col, v)))
            continue
        # the runtime's _resolve_expr / resolve accept the old {$arg:x}/{$session:k} spelling
        if "lit" in nv:
            out[col] = nv["lit"]
        elif "sym" in nv:
            out[col] = "2026-01-01T00:00:00"          # $now: the runtime's deterministic clock
        elif "ref" in nv:
            rv, why = _sym_ref(nv["ref"])
            if rv is None:
                # **If sets does not resolve, drop it** -- the opposite of row_key's policy: writing one column fewer = that column stays
                # unchanged, a visible omission; whereas losing one locator component = a wider address, silently modifying the wrong row.
                drop.append(("sets", "%s.%s:%s" % (tid, col, why)))
                continue
            out[col] = rv
    return out


# ── exec_spec ───────────────────────────────────────────────────────────
def _param_for(impl, ent, col, need_required=True):
    """Column -> parameter name. -> (param name, basis) or (None, reason it cannot be decided).

    **The collector mined this edge long ago** -- `params[].binds` records "parameter -> Entity.col", and the locator key
    needs exactly the reverse direction. det never did this reverse lookup, so `row_key: ["usr_uuid"]` was translated directly into
    `{"$arg": "usr_uuid"}` -- **inventing out of thin air a parameter that does not exist in the real repo**. That is issue #12:
    admidio's `user_update` has a real parameter named `user_uuid`, and `binds` literally says `User.usr_uuid`;
    the correct answer was one reverse dict lookup away.

    Measured: 67% of the `$arg`s referenced by locator keys are not real parameters of the operation, and 2252 of those binds
    can be fixed right now. The reverse lookup itself is safe -- **column-side uniqueness 28323/28629 = 98.9%**; when not unique, we don't guess.
    """
    ps = [p for p in (impl or {}).get("params") or []
          if isinstance(p, dict) and isinstance(p.get("name"), str)]
    if ent:
        tgt = "%s.%s" % (ent, col)
        # NOTE: **`binds` says "which column this parameter's value lands in", not "which row this parameter identifies".**
        # A parameter can be **payload** rather than **address**: in actual's `Category.delete(category, transferId)`,
        # `transferId` binds to `Category.id`, but it means "move the mappings to this category", not
        # "delete this category"; the real locator parameter is `category`, whose `binds` is null (its value is an object).
        # A direct reverse lookup would soft-delete **the transfer target row** -- degrading from "fails loudly" to "silently deletes the wrong row",
        # the wrong direction.
        #
        # So we add a **necessary condition** (not a heuristic): **the locator parameter must be required**. A parameter the caller can
        # omit gives the executor no way to locate the row. Cases this cannot block still fall back to the column name and get flagged.
        # `need_required` only holds for **locator keys** (see above). **Write columns are the opposite** -- an optional parameter
        # writing a value to some column is perfectly normal (`note` may or may not be passed); there the semantics of binds is exactly what we want,
        # "this parameter's value lands in this column", and no extra condition should be added.
        hit = [p["name"] for p in ps
               if p.get("binds") == tgt and (p.get("required") is True or not need_required)]
        if len(hit) == 1:
            return hit[0], "binds"
        if len(hit) > 1:
            # Several parameters bind to the same column. The one with the same name is most likely it; otherwise **don't guess** -- the costs of
            # guessing wrong and not guessing are asymmetric: guessing wrong makes the tool locate the wrong row, while not guessing just falls back to the status quo and leaves a trace.
            same = [n for n in hit if n == col]
            if len(same) == 1:
                return same[0], "binds (multiple bound, took the same-named one)"
            return None, "%d parameters all bind to %s, cannot tell which one" % (len(hit), tgt)
    if any(p["name"] == col for p in ps):
        # The column name itself is a **really declared** parameter -- this is not a guess, it is confirmed by the panel.
        return col, "same-named parameter"
    if not ps:
        return None, "not a single parameter was collected for this impl"
    if need_required and ent and any(p.get("binds") == "%s.%s" % (ent, col) for p in ps):
        return None, "only optional parameters bind to %s.%s -- the locator parameter must be required, not safe to use" % (ent, col)
    return None, "no required parameter binds to %s.%s, and no same-named parameter" % (ent or "?", col)


_WRITE_EFF = ("row_insert", "row_update", "row_upsert", "row_soft_delete", "spawn")


def _written_cols(impl, ent):
    """Columns this impl declares as "written by the caller" (only **write** effects count).

    NOTE: counting only writes is required: the `fields` of `row_read` / `row_search` are **returned columns**, with entirely different semantics.
    Counting reads too would misjudge 187 normal locator fixes as payload -- I made this mistake once in an audit script.
    """
    out = set()
    for ef in (impl or {}).get("effects") or []:
        if (isinstance(ef, dict) and ef.get("entity") == ent
                and _kind(ef) in _WRITE_EFF and isinstance(ef.get("fields"), list)):
            out |= {x for x in ef["fields"] if isinstance(x, str)}
    return out


def _argref(col, impl, ent, mark, mend, who):
    """One locator-key column -> `{"$arg": param name}`.

    Prefer the real parameter name found by reverse lookup on binds; **only when that fails use the column name as the parameter name, and that step must be flagged** --
    because its consequence is silent: the panel gains a column-name parameter, the real parameter becomes dead, and the agent has no way to know
    which one it must pass."""
    p, why = _param_for(impl, ent, col)
    if p is not None:
        if p != col and mend is not None:
            mend.append(("row_key", "%s: locator column %s reverse-looked-up via binds to parameter %s (different name)" % (who, col, p)))
        if p != col and col in _written_cols(impl, ent):
            # This column is **both a locator key and a caller-writable column**, so the parameter bound to it may be a "new value"
            # rather than an "address": auto-mcs's `server_rename` is row_key=["name"] +
            # fields=["name"], with the parameter named `new_name`. Measured: of 2308 fixes only 17 fall in
            # this cell, and most of them (dokuwiki's `user to modify`, gonic's `specid`) are correctly reverse-looked-up
            # -- **so fix them, but flag them**: trading 15 correct fixes to block 2 suspicious ones
            # is not worth it; and the cost of a miss (silently pointing at the wrong row) must be visible to the agent.
            mark.append(D_ROW_KEY_WRITABLE)
            if mend is not None:
                mend.append(("row_key", "%s's %s is both a locator key and a writable column; the chosen parameter %s may be a new value"
                             % (who, col, p)))
        return {"$arg": p}
    if mend is not None:
        mend.append(("row_key", "%s's locator column %s: %s; can only use the column name as the parameter name" % (who, col, why)))
    mark.append(D_ROW_KEY_COLNAME)
    return {"$arg": col}


# ---------------------------------------------------------------------------
# Closed vocabulary of `_defaulted`. **This is the basis the agent re-checks every round**, so:
#   - the text is English (reports from this chain to the agent are uniformly English);
#   - names are lifted into constants; tests reference the constants instead of hand-copied literals;
#   - the table in the prompt must match this one **item by item** -- omit one and the agent will never re-check it.
#     This actually happened: `entity(...)` was never in the prompt, while `wrong_entity` drives the feedback-round loop.
# ---------------------------------------------------------------------------
D_ROW_KEY            = "row_key"
D_ROW_KEY_WRITABLE   = "row_key (the locator column is also writable — the bound arg may be a new value, not an address)"
D_ROW_KEY_COLNAME    = "row_key (no parameter found; the column name is standing in as one)"
D_ROW_KEY_UNRESOLVED = "row_key (the value does not resolve; kept as-is so the failure is loud)"
D_FIELDS             = "fields"
D_FIELDS_BINDS       = "fields (mapped to the real parameter names via binds)"
D_DROP_GHOST         = "dropped ghost columns %s"
D_DROP_UNWRITABLE    = "dropped unwritable columns %s"
D_ARG_FROM_COL       = "argument invented from the write column"
D_ENTITY             = "entity (not taken from the primary effect: %s)"
D_FAMILY_REGEX       = "family (matched by an id_local regex, not by the effects)"
D_FAMILY_OP          = "family (no structural effect entry; fell back to op)"

#: For the prompt sync test: this is the complete set; the prompt's table may have neither more nor fewer.
DEFAULTED_VOCAB = (D_ROW_KEY, D_ROW_KEY_WRITABLE, D_ROW_KEY_COLNAME, D_ROW_KEY_UNRESOLVED,
                   D_FIELDS, D_FIELDS_BINDS, D_DROP_GHOST, D_DROP_UNWRITABLE,
                   D_ARG_FROM_COL, D_ENTITY, D_FAMILY_REGEX, D_FAMILY_OP)


_BADVAL = object()


def _keyval(v):
    """Value of one key in the object form of `row_key` -> the runtime's where value. -> (value, None) or (_BADVAL, reason).

    **There is only one way to write values across the whole repo**: the State Value vocabulary (`{lit}` / `{ref}` / `{sym}`),
    used by `sets` / `needs` / `provides` / `constraints`. This place used to accept only bare strings
    `"$actor.id"`, while the neighboring `sets` accepts `{"ref":"$actor.id"}` -- the same statement "this value comes from the session"
    was required to be written two ways in adjacent sections. Measured: across 433 repos the object form was used 181 times, **correctly 0 times**,
    and 136 of those stuffed an entire scope clause in (`{"col":..., "ref":...}`).

    Bare strings are still accepted (the existing corpus is all bare strings): a leading `$` means a symbol, otherwise a literal -- this must **come before
    `norm_value`**, otherwise `"$arg.x"` would be taken as a literal by it.
    """
    if isinstance(v, str) and v.startswith("$"):
        rv, why = _sym_ref(v)
        return (rv, None) if rv is not None else (_BADVAL, why)
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v, None
    if isinstance(v, dict) and "from" in v:
        # `{"from": ...}` is not in norm_value (see the comment on from_ref). lookup_by is an equality locator,
        # it needs a scalar, so op=None (not $subquery); legacy=False -- the value slot of where
        # is consumed directly by the runtime's resolve() as `{"$ref": ...}`, without the State-level `{"_legacy": ...}` wrapper.
        rv, why = from_ref(v)
        return (rv, None) if rv is not None else (_BADVAL, why)
    nv = norm_value(v)
    if nv is None:
        return _BADVAL, u"value shape not recognized: %r" % (v,)
    if "lit" in nv:
        return nv["lit"], None
    if "sym" in nv:
        return "2026-01-01T00:00:00", None            # $now: the runtime's deterministic clock
    if "col" in nv:
        # "Another column of this row" cannot be resolved in where -- the runtime's _find hands where values to
        # resolve(), which accepts $ref/$session/$arg/$const and has no concept of "another column of the same row"
        # (that is an in-row comparison, which is the job of constraints).
        return _BADVAL, u"locator value written as another column %r of this row; cannot be resolved in where" % (nv["col"],)
    rv, why = _sym_ref(nv.get("ref"))
    return (rv, None) if rv is not None else (_BADVAL, why)


def _rk_declared_empty(ef):
    """`row_key` **explicitly written as empty** (`[]` / `{}` / `""`) -- "checked, there is no locator column",
    as distinct from the key not existing at all ("didn't look"). `constraints: []` / `no_edges` in the contract follow the same pattern."""
    if not isinstance(ef, dict) or "row_key" not in ef:
        return False
    rk = ef.get("row_key")
    return isinstance(rk, (list, tuple, dict, str)) and len(rk) == 0


def _row_key(ef, cols, pk, mark, impl=None, ent=None, mend=None):
    """effect.row_key -> exec_spec's lookup_by / row_key. Three forms:
      dict {col: "$arg.x"}  the only form that really carries information
      list ["id"]           only names the key columns; values are taken at runtime from same-named inputs
      str  "id"             same as above
    """
    rk = ef.get("row_key")
    _who = (impl or {}).get("id_local") or "?"
    out = {}
    if isinstance(rk, dict):
        for k, v in rk.items():
            if not isinstance(k, str) or (cols is not None and k not in cols):
                continue
            rv, why = _keyval(v)
            if rv is not _BADVAL:
                out[k] = rv
                continue
            # **Keep it as-is even if it doesn't resolve; never drop it**. The runtime's _find only refuses loudly when where is completely empty
            # (runtime.py:872); a partial match on multiple rows silently takes rows[0] -- dropping
            # one component of a composite key trades a "loud not found" for "silently modifying the wrong row". Keeping
            # an unresolvable value means it can never match, the failure is loud, and it is recorded here.
            out[k] = v if isinstance(v, (str, int, float, bool)) else \
                json.dumps(v, ensure_ascii=False, sort_keys=True)
            mark.append(D_ROW_KEY_UNRESOLVED)
            if mend is not None:
                mend.append(("row_key", "%s's locator column %s: %s; kept as-is (can never match)"
                                        % (_who, k, why)))
    elif isinstance(rk, (list, tuple)):
        # **Only the key columns are given, with no word on where the values come from** (measured: 97.8% are this kind). Column name != parameter name, so here
        # we must reverse-look-up binds; we cannot use the column name directly as the parameter name.
        for k in rk:
            if isinstance(k, str) and (cols is None or k in cols):
                out[k] = _argref(k, impl, ent, mark, mend, _who)
    elif isinstance(rk, str) and (cols is None or rk in cols):
        out[rk] = _argref(rk, impl, ent, mark, mend, _who)
    if not out and pk and not _rk_declared_empty(ef):
        # "Addressing by primary key" is **the definition of addressing**, not a guess: an update/delete must be able to point at some row,
        # and the pk is the only universally available identifier. Still flagged -- real code may look up by slug / composite key.
        #
        # NOTE: **this does not apply to an explicit `row_key: []`**. That statement means "this operation does not locate any
        # single row" (bulk delete / conditional write); falling back to `{pk: {"$arg": pk}}` would invent a parameter the interface does not accept,
        # which cannot be obtained at runtime -> no row matches -> GuardError, and the tool **always fails**.
        # Measured on an earlier run: youtube-dl-server's Job.purge_logs (empty params) was translated exactly like this into
        # `lookup_by: {"id": {"$arg": "id"}}`. Missing and empty must be kept apart, in sync with the checker.
        out[pk] = _argref(pk, impl, ent, mark, mend, _who)
        mark.append(D_ROW_KEY)
    return out


def _fields(ef, impl, cols, settable, mark, mend=None, ent=None):
    """Writable columns = effect.fields intersected with entity columns. When both are empty, fall back to settable (the entity's writable columns).

    This is **a superset, not a guess**: when the runtime's _resolve_fields gets a list it only writes the columns actually present in args,
    so an extra column is never written out of thin air; leaving it empty instead yields a tool where the Env builds and a call does nothing --
    the most toxic no_op in L2. When falling back to the default, mark it, so the agent and the report both know **this is not evidence, it is a fallback**.
    """
    def _m(why):
        if mend is not None:
            mend.append(("fields", why))
    out = []
    fv = ef.get("fields")
    if isinstance(fv, list):
        out = [x for x in fv if isinstance(x, str)]
    elif isinstance(fv, dict):
        out = [k for k in fv if isinstance(k, str)]
    if cols is not None:
        # **Hard contradiction**: the miner says it writes X.foo, and X has no foo column at all -- the same collect
        # contradicts itself; you know it is wrong without reading code. det is right to strip it, but this is **a self-inconsistency on the collector side**
        # and must be traceable back to the source, not just vanish here.
        ghost = [c for c in out if c not in cols]
        out = [c for c in out if c in cols]
        if ghost:
            mark.append(D_DROP_GHOST % (ghost[:4],))
            _m("%s's effect declares writes to nonexistent columns %s (collect contradicts itself)" % (ent, ghost[:4]))
    if settable is not None:
        # **Disputed**: "is this column pk / audit / immutable" may itself be misjudged (the audit tier
        # measured 88 cases conflicting with the miner's own effects). So stripping must be loud, so the agent can re-check.
        bad = [c for c in out if c not in settable]
        out = [c for c in out if c in settable]
        if bad:
            mark.append(D_DROP_UNWRITABLE % (bad[:4],))
            _m("%s's effect says the caller writes %s, but those columns were judged pk/audit/immutable" % (ent, bad[:4]))
    # **Logical necessity**: columns in sets have their values set by the implementation itself and should not also appear on the "caller-writable" panel.
    # This tier needs no one to re-check; just record it.
    dup = [c for c in out if c in (ef.get("sets") or {})]
    out = [c for c in out if c not in (ef.get("sets") or {})]
    if dup:
        _m("%s's %s appear in both fields and sets; treated as sets" % (ent, dup[:4]))
    if not out and settable:
        out = list(settable)
        mark.append(D_FIELDS)
        _m("%s's effect gives no usable fields; fell back to all writable columns of the entity" % ent)
    # **Column name != parameter name.** When the runtime's `_resolve_fields` gets a list it does `if col in args`
    # -- fetching the value from inputs by **column name**. So a write whose value comes from the `note` parameter and lands in the `Order.note` column
    # cannot be expressed in list form: it happens to work when the names match, never writes when they differ, and the closure rule would
    # stuff the column name onto the panel to make do (measured: 62% of panel entries are column names rather than parameter names; that is where they came from).
    # The runtime **has long accepted** the dict form `{col: {"$arg": param name}}`; it was det that kept emitting lists.
    # Switch forms only when **at least one column's parameter name differs from the column name**, to keep the change surface minimal.
    if impl is not None and ent and out:
        m, diff = {}, False
        for c in out:
            p, _w = _param_for(impl, ent, c, need_required=False)
            m[c] = {"$arg": p or c}
            if p and p != c:
                diff = True
                _m("%s's write column %s is supplied by parameter %s (column name != parameter name)" % (ent, c, p))
        if diff:
            mark.append(D_FIELDS_BINDS)
            return m
    return out


_SCOPE_KIND = {"owner": "owner", "owner_or_public": "owner_or_public", "global": "global",
               "tenant": "tenant", "static": "tenant", "public": "global",
               "owner_or_admin": "owner_or_public"}


def _scope(ef, cols, tid):
    """effect.scope -> the grammar of runtime._apply_scope.
    **"Did not state" and "judged to be global" must be distinguishable** -- the former goes back to the agent, the latter is a conclusion."""
    sc = ef.get("scope")
    if isinstance(sc, str):
        sc = {"kind": sc}
    if isinstance(sc, list):
        sc = sc[0] if sc and isinstance(sc[0], dict) else None
    if not isinstance(sc, dict):
        return None, "scope missing or shape not recognized (%s)" % type(ef.get("scope")).__name__
    kind = _SCOPE_KIND.get(sc.get("kind"))
    if kind == "global":
        return None, None                            # explicitly global: in the runtime that means no scope is set
    oc, vc = sc.get("owner_col"), sc.get("visibility_col")
    col = sc.get("col") or sc.get("tenant_col")
    out = {}
    if isinstance(oc, str) and (cols is None or oc in cols):
        out["owner_col"] = oc
    if isinstance(vc, str) and (cols is None or vc in cols):
        out["visibility_col"] = vc
        out["public"] = sc.get("public") if isinstance(sc.get("public"), list) else []
    if not out and isinstance(col, str) and (cols is None or col in cols):
        out["where"] = {col: "$session.account_id"}
    if not out:
        return None, "kind=%r but no usable owner_col/visibility_col/col given" % (sc.get("kind"),)
    return out, None


def build_exec_spec(impl, fam, ent, cols, ents, lif, drop, tid, mark, mend=None):
    """Assemble exec_spec per family. **Only write keys the runtime really reads** -- extra keys don't raise errors, they only make people think they
    have semantics (that batch of tools where "the Env builds but every call blows up" came about exactly this way)."""
    es = {"entity": ent} if ent else {}
    pk, settable, insertable = lif.get("_pk"), lif.get("_settable"), lif.get("_insertable")

    def RK(ef):
        return _row_key(ef, cols, pk, mark, impl, ent, mend)

    def FS(ef, ins=False):
        return _fields(ef, impl, cols, insertable if ins else settable, mark, mend, ent)

    def SET(ef):
        return norm_sets(ef, cols, drop, tid)

    if fam == "crud.insert":
        ef = _first_eff(impl, ("row_insert",))
        es["fields"] = FS(ef, ins=True)
        s = SET(ef)
        if s:
            es["set_on_create"] = s
        uo = [c["cols"] for c in (lif.get("_unique") or [])]
        if uo:
            es["unique_on"] = uo[0]
    elif fam == "crud.upsert":
        ef = _first_eff(impl, ("row_upsert",))
        es["key"] = RK(ef)                        # ex_upsert reads .items(); it needs a dict, not a list
        # ex_upsert resolves a template mapping with `.items()`.  crud.insert accepts a list,
        # but copying that shape here creates a tool which Probe can describe yet Runtime can
        # never execute.  Values stay explicit `$arg` expressions so interface closure can
        # expose every required input on the MCP surface.
        es["insert_fields"] = {c: {"$arg": c} for c in FS(ef, ins=True)}
        es["set_on_exists"] = SET(ef)
    elif fam == "crud.fetch":
        ef = _first_eff(impl, ("row_read",))
        es["lookup_by"] = RK(ef)
        sc, why = _scope(ef, cols, tid)
        if sc:
            es["scope"] = sc                          # visibility of the read (new in v3)
        elif why:
            es["_scope_undecided"] = why
    elif fam in ("crud.delete", "crud.delete_cascade"):
        ef = _first_eff(impl, ("row_delete", "cascade_delete"))
        es["lookup_by"] = RK(ef)
        # The source really cascades -> on_child overrides. **Without this override the runtime reads each FK's on_delete from the schema**
        # (cascade 5080 / set_null 1062 / restrict 1000 / undeclared 8454->block),
        # so a plain delete needs nothing filled in.
        if "cascade_delete" in eff_kinds(impl):
            es["on_child"] = "cascade"
    elif fam == "crud.soft_delete":
        ef = _first_eff(impl, ("row_soft_delete",))
        es["lookup_by"] = RK(ef)
        es["set"] = SET(ef) or ({lif["_soft_col"]: True} if lif.get("_soft_col") else {})
    elif fam == "update.field_set":
        ef = _first_eff(impl, ("row_update",))
        es["row_key"] = RK(ef)
        es["fields"] = FS(ef)
        s = SET(ef)
        if s:
            es["set"] = s
    elif fam == "update.status_transition":
        ef = _first_eff(impl, ("row_update",))
        es["row_key"] = RK(ef)
        lv = lif.get("_via") or {}
        es["status_col"] = lv.get("col")
        if lv.get("from"):
            es["from"] = lv["from"]
        s = SET(ef)
        to = s.get(lv.get("col")) if lv.get("col") else None
        if to is not None:
            es["to"] = to                             # sets gives the target state directly, no guessing
        elif lv.get("to") is not None:
            es["to"] = lv["to"]
    elif fam == "update.relation_link":
        ef = _first_eff(impl, ("link", "unlink"))
        tt = ef.get("through_table") or ef.get("through") or ef.get("table")
        es["mode"] = "remove" if _kind(ef) == "unlink" else "add"
        if isinstance(tt, str):
            es["relation_type"] = "m2m"
            es["through_table"] = tt
            lc = ef.get("link_col") or ef.get("fk_col")
            oc = ef.get("other_fk") or ef.get("other_fk_col") or ef.get("through_col")
            _w = impl.get("id_local") or "?"
            es["subject_key"] = ({lc: _argref(lc, impl, tt, mark, mend, _w)}
                                 if isinstance(lc, str) else {})
            es["object_key"] = ({oc: _argref(oc, impl, tt, mark, mend, _w)}
                                if isinstance(oc, str) else {})
        else:
            es["relation_type"] = "fk"
            fk = ef.get("fk_col") or ef.get("link_col")
            if isinstance(fk, str):
                es["fk_col"] = fk
            es["subject_key"] = RK(ef)
            es["object_key"] = {}
    elif fam == "search" or fam.startswith("search."):
        ef = _first_eff(impl, ("row_search",))
        sc, why = _scope(ef, cols, tid)
        if sc:
            es["scope"] = sc
        elif why:
            es["_scope_undecided"] = why
        f = ef.get("fields")
        ff = None
        if isinstance(f, list):
            ff = [x for x in f if isinstance(x, str) and (cols is None or x in cols)]
            if ff:
                es["search_fields"] = ff
        # rank: record the source's matching/ordering method as-is. exact/substring are recorded too -- they are **matching predicates**,
        # treated as pure filters by the runtime, but the fact must stay in the spec for the agent (so it knows whether to write
        # eq or icontains in the filter).
        m = ef.get("method")
        if isinstance(m, str) and m in _RANK_METHODS:
            rank = {"method": m}
            if ff:
                rank["fields"] = ff
            es["rank"] = rank
        if ef.get("paginated"):
            es["pagination"] = {"default_limit": 20}
    elif fam == "action.trigger":
        ef = _first_eff(impl, ("row_update", "spawn"))
        tgt = {"entity": ent}
        rk = RK(ef)
        if rk:
            tgt["lookup_by"] = rk
        es = {"target": tgt}
        s = SET(_first_eff(impl, ("row_update",)))
        if s:
            es["set"] = s
        sp = []
        for e2 in (impl.get("effects") or []):
            if not isinstance(e2, dict) or _kind(e2) not in ("spawn", "row_insert"):
                continue
            ce = e2.get("entity")
            if ce in ents and ce != ent:
                one = {"entity": ce, "n": 1}
                if isinstance(e2.get("link_col"), str):
                    one["link_col"] = e2["link_col"]
                sp.append(one)
        if sp:
            es["spawn"] = sp
    elif fam == "action.emit":
        ef = _first_eff(impl, ("dispatch", "external", "schedule"))
        ch = ef.get("channel") or ef.get("type")
        es = {"channel": ch if isinstance(ch, str) else "event"}
        rec = ef.get("record")
        tbl = rec.get("table") if isinstance(rec, dict) else ef.get("table")
        if not isinstance(tbl, str):
            # The collector's discipline is "if the code writes a delivery/log record row, put that table in entity" --
            # if filled, use it, so the effect lands on a **declared entity** that the verifier can see.
            tbl = ef.get("entity") if ef.get("entity") in ents else None
        if isinstance(tbl, str):
            es["record"] = {"table": tbl}
        elif ent:
            # Second best: derive an <Entity>Log table. It is **not in entities**, so the verifier
            # cannot assert on it -- L0 reports this as a modeling gap and lets the agent decide whether to add a table
            # or accept that "tasks based on this effect are unverifiable".
            es["record"] = {"table": "%sLog" % ent}
            es["_record_undeclared"] = True
        else:
            es["record"] = {"table": "DispatchLog"}
            es["_record_undeclared"] = True
    elif fam == "action.probe":
        es = {"target_key": {"entity": ent}}
    elif fam == "guard.auth":
        es = {"verify": {"entity": ent}} if ent else {}
        acc = lif.get("_account")
        if acc:
            # verify.entity tells the runtime which table to verify against; these two columns are for input_schema --
            # a login tool's panel must really have the email/password parameters, otherwise the agent cannot even get in the door.
            es["verify"]["username_col"] = acc["username_col"]
            es["verify"]["password_col"] = acc["password_col"]
    elif fam == "auth.register":
        es["fields"] = FS(_first_eff(impl, ("row_insert",)), ins=True)
        es["prechecks"] = []
    return es


# -- Main flow -------------------------------------------------------------
def _lifecycle_index(schemas):
    """entity → {col, initial, states, via: {impl_id: {col, from, to}}}"""
    out = {}
    for e in schemas:
        if not isinstance(e, dict):
            continue
        name = e.get("entity") or e.get("name")
        lc = e.get("lifecycle")
        if not isinstance(lc, dict) or not isinstance(lc.get("col"), str):
            continue
        via = {}
        for t in (lc.get("transitions") or []):
            if not isinstance(t, dict):
                continue
            for vv in (t.get("via") if isinstance(t.get("via"), list) else [t.get("via")]):
                if not isinstance(vv, str):
                    continue
                slot = via.setdefault(vv, {"col": lc["col"], "from": [], "to": None})
                if t.get("from") is not None and t["from"] not in slot["from"]:
                    slot["from"].append(t["from"])
                if t.get("to") is not None:
                    slot["to"] = t["to"] if slot["to"] in (None, t["to"]) else None
        out[name] = {"col": lc["col"], "initial": lc.get("initial"),
                     "states": lc.get("states") or [], "via": via}
    return out


# Executors of these families must first locate a table; they cannot run without an entity. Other families (emit/probe/
# logout/permission) don't need one and should not be dropped for lacking an entity.
_NEED_ENTITY = ("crud.insert", "crud.upsert", "crud.fetch", "crud.delete",
                "crud.delete_cascade", "crud.soft_delete", "update.field_set",
                "update.status_transition", "search.filtered_list",
                "search.keyword_weighted", "search.semantic", "guard.auth", "auth.register")

# Account detection. **Exact first, then substring** -- exact matching keeps common cases deterministic, substring catches real repos' spellings:
# usr_login_name / UserName / PasswordHash / cryptpassword / MasterPassword / pwdEnc.
# Measured: exact matching alone misses 68 repos (which clearly have username + password in the same table).
_UCOLS = ("email", "username", "user_name", "login", "user_email", "mail")
_URE = re.compile(r"(?i)(e?mail|user_?name|login_?name|^login$|handle|nickname)")
# Password: accept pass / pwd / crypt, **not bare hash / secret** -- info_hash, barcode_hash,
# file_hash, token_hash, key_hash are not passwords; accepting them would misjudge a pile of non-account tables as account tables.
_PWRE = re.compile(r"(?i)^(password|passwd|password_hash|password_digest|"
                   r"encrypted_password|hashed_password|pass)$")
_PWRE2 = re.compile(r"(?i)(passw|passwd|pwd|crypt)")


_RK1 = re.compile(r"'[^']*'|\"[^\"]*\"|\[[^\]]*\]|\{[^}]*\}")
_RK2 = re.compile(r"[A-Za-z_][A-Za-z0-9_]*[.:][A-Za-z0-9_.:]*")
_RK3 = re.compile(r"\b\d+\b")


def _reason_key(why):
    """Normalize a drop reason down to "the reason" itself: strip quoted contents / bracketed contents / identifiers with dots or colons /
    numbers. Without normalization every drop forms its own bucket, the distribution is a pile of count=1, and the real big hitters are invisible."""
    k = _RK1.sub("·", why)
    k = _RK2.sub("·", k)
    k = _RK3.sub("·", k)
    k = re.sub(r"^\S+(?=\s|\()", "·", k)
    return re.sub(r"·+", "·", k)[:110]



# -- det derivation of provides ---------------------------------------------
# The contract (Code Miner section 3.4) ruled long ago: "**effects is primary**; the provides of the three classes row_insert/row_update/row_delete
# can be **mechanically derived** from effects; only the action class needs extra code reading. This is a **controlled derivation
# relation**, not two paths for the model to flip a coin between." -- but nobody ever derived it, so the miner was asked to say the same thing twice,
# the measured fill rate was only 27%, and 249 of those written had the wrong shape (output_schema stuffed into provides).
#
# Why this is det's job: State has only three slots, each uniquely determined by the effect, and none requires reading code --
#   card   <- kind          closed vocabulary to closed vocabulary, zero degrees of freedom
#   entity <- effect.entity copied directly
#   scope  <- row_key/sets  **moved as-is**: the contract states values use the State Value vocabulary, "do not invent a fifth one",
#                          so row_key / sets / scope.value are the same thing at the **source-syntax level**.
#
# NOTE: we tripped here once: the first version used `_keyval()` -- that is a **row_key-specific converter** that translates source syntax into
#   runtime notation (`{"ref":"$arg.id"}` -> `{"$arg":"id"}`, `{"lit":"paid"}` -> `"paid"`).
#   But State's scope.value needs **source syntax**. **What I need is a validator, not a converter** --
#   using the wrong one produces a batch of provides whose scope.value falls outside the Value vocabulary, without any error.
_VALUE_KEYS = ("lit", "ref", "col", "sym")
# `sym` is a **closed vocabulary**; grammar has only `$now`. Yet the corpus measured 8+ self-invented ones:
# $uuid 28 · $gen 25 · uuid_v4 14 · random 13 · $newGUID 12 · $generate 10 · $generated 9.
# They all express the same thing the contract does not have: "this value is system-generated".
# **When deriving, such clauses must be dropped and recorded** -- asserting equality against a value unknown at mining time
# produces a State that is always false, without any error.
_SYM_OK = ("$now",)
# The `ref` namespace is closed too: $arg / $actor / $session / $subject, four of them. The corpus was measured to contain
# `$user.id` (should be $actor.id), `$recovery_code`, even prose like `env default_ingest_threshold`.
# The checker has this rule (`ref uses an unknown namespace`, 51 cases / 7 repos),
# **but copying it verbatim during derivation would launder something the checker already flagged into "det-produced provides".**
# The column-name part is **required**, not optional. grammar directly rejects a bare `$actor` / `$arg` as
# "unknown reference" -- this check used to be wider than the receiving end, so 35 bare-namespace values slipped past validation
# and only blew up in `from_state` (measured: $arg 27 · $session 3 · $actor 3 · $subject 2).
# The check must sit on the path the receiving end really reads, not on a shape that "looks right".
_REF_OK = re.compile(r"^\$(arg|actor|session|subject)\.[A-Za-z_][A-Za-z0-9_]*$")


def _value_ok(v):
    """Whether this is a legal source-syntax Value. **Validate only, don't convert.**

    Validate down to the value level, not just the keys: `sym` has only $now, `ref` has only four namespaces.
    Checking only keys lets `{"sym":"$uuid"}` / `{"ref":"$user.id"}` slip all the way downstream --
    producing a State that is always false or does not compile at all, without any error.
    """
    if not (isinstance(v, dict) and len(v) == 1):
        return False
    k = next(iter(v))
    if k not in _VALUE_KEYS:
        return False
    if k == "sym":
        return v[k] in _SYM_OK
    if k == "ref":
        return isinstance(v[k], str) and bool(_REF_OK.match(v[k]))
    if k == "col":
        return isinstance(v[k], str) and bool(v[k])
    # `lit` is no longer limited to scalars -- grammar now covers this tier (non-scalars are wrapped in {"const": ...},
    # because in the IR a bare dict is a node, so literals and nodes collide in shape). Source: cloudserver sets `tags`
    # to `{}` to clear a JSON column. **That is a real, decidable write; being unable to express it is a gap in grammar,
    # not a miner error** -- so we fix the syntax rather than drop it at the consumer.
    return True
_PROV_CARD = {"row_insert": ("gte", 1), "row_upsert": ("gte", 1), "row_update": ("gte", 1),
              "row_soft_delete": ("gte", 1), "row_delete": ("eq", 0)}


def derive_provides(impl, mend=None):
    """effects of one impl -> [State, ...]. -> (states, notes)

    notes are **the reasons something could not be derived**, one per effect -- that is what should be fed back to the miner:
    have it fill in the raw material for effects (row_key / entity), rather than copying provides again.
    """
    out, notes = [], []
    for ef in (impl.get("effects") or []):
        if not isinstance(ef, dict):
            continue
        k = _kind(ef)
        if k not in _PROV_CARD:
            continue                                  # action / external / dispatch: structurally underivable
        ent = ef.get("entity")
        if not isinstance(ent, str) or not ent:
            notes.append((k, "effect has no entity; we don't even know which table it is"))
            continue
        op, n = _PROV_CARD[k]
        scope, unresolved = [], []
        # Locate that row: update/delete/upsert/soft_delete rely on row_key, insert relies on the values written
        src = ef.get("row_key") if k != "row_insert" else (ef.get("sets") or {})
        if isinstance(src, str):
            src = [src]                               # `row_key: "id"` is a degenerate spelling of the list form
        if k == "row_insert" or isinstance(src, dict):
            for col, v in (src or {}).items():
                if not _value_ok(v):
                    unresolved.append("%s=%r" % (col, v)); continue
                scope.append({"col": col, "op": "eq", "value": v})
            if k != "row_insert":
                # update/upsert additionally establish the values they hard-set
                for col, v in (ef.get("sets") or {}).items():
                    if _value_ok(v):
                        scope.append({"col": col, "op": "eq", "value": v})
        if isinstance(src, list):
            # **The list form is the norm (measured 97.8%), and it does not mean "no values".** The collection contract splits
            # "which column locates this row" and "which parameter supplies this column's value" into two places: the former in `row_key`,
            # the latter in `params[].binds`. This is not an omission, it is **deliberate** -- writing the same fact twice makes it
            # drift; of the 181 object-form uses in the prompt, 136 copied exactly the work binds should do into row_key,
            # and the number correct was **0**. So what to do here is a **reverse lookup**, not recording "underivable".
            #
            # Don't write a second copy of the criterion: use the same `_param_for` that `_row_key()` uses -- inheriting
            # even the default of `need_required`. The locator parameter must be required, and that holds on the provides
            # side too: scope says exactly "which row", and a parameter the caller may omit cannot point at a row.
            #
            # NOTE: **the notation differs; don't casually reuse `_argref`.** That function emits runtime notation
            # `{"$arg": name}`, while State.scope's value needs **source syntax**
            # `{"ref": "$arg.name"}`. Using a converter as a validator was the first pitfall already hit when writing `provides_of`;
            # don't hit it a second time here.
            #
            # A/B measurement (an earlier collect release, 27098 derivable impls, "before" being the real old code at
            # git HEAD): provides with at least one scoped entry 52.8% -> 93.0%, States with empty scope
            # 47.8% -> 9.5%.
            for col in src:
                if not isinstance(col, str):
                    continue
                p, why = _param_for(impl, ent, col)
                if p is None:
                    # Failing the reverse lookup is still **recorded**, not silent: weak assertions make the closure judge too loosely.
                    unresolved.append("%s(%s)" % (col, why))
                    continue
                scope.append({"col": col, "op": "eq", "value": {"ref": "$arg.%s" % p}})
            # update/upsert additionally establish the values they hard-set (same rule as the dict form)
            for col, v in (ef.get("sets") or {}).items():
                if _value_ok(v):
                    scope.append({"col": col, "op": "eq", "value": v})
        if not scope:
            # **A weaker assertion can be derived, but say where it is weak.** "There are rows in this table" beats nothing,
            # but the closure would judge too loosely with it -- so it must be recorded, not quietly treated as normal output.
            notes.append((k, "missing %s; can only assert \"table %s has rows\", cannot locate which row"
                          % ("sets/fields" if k == "row_insert" else "row_key", ent)))
        if unresolved:
            notes.append((k, "values of these columns cannot be resolved, skipped: %s" % ", ".join(unresolved[:4])))
        out.append({"entity": ent, "scope": scope, "card": {"op": op, "n": n}})
    if mend is not None and out:
        mend.append(("provides", "%s: derived %d provides from effects"
                     % (impl.get("id_local"), len(out))))
    return out, notes


def _state_ok(st):
    """Whether this State can really compile into the IR. **Looking the right shape doesn't count.**

    `$actor.<col>` must first be translated by det into `{"$session": col}` before entering grammar (see `_sym_ref`),
    so strip it before validating -- otherwise the tenant-boundary spelling added this round would be judged illegal.
    """
    if not isinstance(st, dict) or "entity" not in st:
        return False
    try:
        clean = dict(st, scope=[c for c in (st.get("scope") or [])
                                if not (isinstance(c, dict) and isinstance(c.get("value"), dict)
                                        and str(c["value"].get("ref", "")).startswith("$actor.")
                                        and c["value"]["ref"] != "$actor.id")])
        _GRAM.validate(_GRAM.from_state(clean), "precondition")
        return True
    except Exception:
        return False


def provides_of(impl, mend=None):
    """What this impl establishes. **Compilable hand-written ones take priority, det derivation is the fallback.**

    NOTE: "hand-written first" **cannot be unconditional**. The first version passed anything that "is a dict with an entity", and measured 87
    uncompilable ones slipped out anyway: self-invented operators `changed` / `increased`, `card.op = "n"`,
    and `$output.id` (which the prompt **explicitly forbids**: "Nothing can name it -- it does not
    exist when conditions are evaluated"; grammar's ref namespaces are also only four).
    **Looking the right shape does not mean usable.** If not a single one compiles, fall back entirely to det.
    """
    hand = impl.get("provides")
    if hand and isinstance(hand, list):
        good = [p for p in hand if _state_ok(p)]
        if good:
            if mend is not None and len(good) < len(hand):
                mend.append(("provides", "%s: of %d hand-written, %d do not compile, dropped"
                             % (impl.get("id_local"), len(hand), len(hand) - len(good))))
            return good, []
        if mend is not None:
            mend.append(("provides", "%s: of %d hand-written, **none compile**; fell back to det derivation"
                         % (impl.get("id_local"), len(hand))))
    return derive_provides(impl, mend)


def prep(d):
    """collect dict -> (raw_spec, report)."""
    if isinstance(d, list):
        # Some outputs have an impls array directly at the top level (incremental re-collection files). Wrap it into the normal shape,
        # rather than scrapping the whole repo -- the impls inside are fine.
        d = {"impls": d, "schemas": [], "edges": []}
    if not isinstance(d, dict):
        raise ValueError("collect top level is not an object, it is %s" % type(d).__name__)
    repo = d.get("repo") or "unknown"
    if not isinstance(repo, str):
        repo = "unknown"
    if "/" in repo:                                  # the collector sometimes writes the absolute path of the clone
        repo = repo.rstrip("/").rsplit("/", 1)[-1]
    # Raw material for A3: columns the collector **itself** declares as "value given by the caller". Only **write** effects count --
    # the `fields` of `row_read` / `row_search` are **returned columns**, with entirely different semantics (counting reads too would
    # misjudge 187 normal cases as conflicts; I made this mistake once in an audit script).
    _caller_written = {}
    for _i in (d.get("impls") or []) if isinstance(d, dict) else []:
        if not isinstance(_i, dict):
            continue
        for _ef in (_i.get("effects") or []):
            if (isinstance(_ef, dict) and _kind(_ef) in _WRITE_EFF
                    and isinstance(_ef.get("entity"), str)
                    and isinstance(_ef.get("fields"), list)):
                _caller_written.setdefault(_ef["entity"], set()).update(
                    x for x in _ef["fields"] if isinstance(x, str))
    drop, mend = [], []
    # drop = what was discarded; mend = **what det filled in / rewrote / stripped on upstream's behalf**. They must be recorded separately:
    # the former is "this one is gone", the latter is "this one is still here, but not as the miner said". Mixing them makes it impossible to tell
    # "not broken" from "broken and swallowed" -- and the latter is exactly this layer's biggest risk (stating != not looking).
    rep = {"repo": repo, "collect_version": d.get("collect_version"),
           "in": {}, "out": {}, "dropped": [], "mended": [], "notes": []}

    # -- Entities --
    schemas = [x for x in (d.get("schemas") or []) if isinstance(x, dict)]
    life = _lifecycle_index(schemas)
    ents, entities = {}, []
    for e in schemas:
        name = e.get("entity") or e.get("name")
        if not isinstance(name, str) or not name:
            drop.append(("entity", "no entity name"))
            continue
        cols, notes = [], []
        _cl = e.get("columns")
        if not isinstance(_cl, (list, tuple)):
            drop.append(("entity", "columns of %s is not an array (%s)" % (name, type(_cl).__name__)))
            _cl = []
        for c in _cl:
            try:
                nc, nn = norm_col(c, drop, mend)
            except Exception as ex:
                drop.append(("column", "failed to parse a column of %s: %s" % (name, type(ex).__name__)))
                continue
            if nc:
                cols.append(nc)
                notes += ["%s.%s: %s" % (name, nc["name"], x) for x in nn]
        if not cols:
            drop.append(("entity", "%s has no usable columns" % name))
            continue
        rep["notes"] += notes[:20]
        _cw = _caller_written.get(name) or set()
        _disputed = []
        for c in cols:
            if c.get("audit") is None and _AUDIT_RE.match(c["name"]):
                if c["name"] in _cw:
                    # **Self-contradiction**: the regex says this is an audit column, while the collector's own write effect says
                    # "the caller writes it". Only one can be right, and **the miner is the one who read the code** --
                    # paperless-ngx's `Document.created` is a user-editable document date,
                    # not the row insertion time. Marking it audit would mean **no tool in the entire world can write it**.
                    # So det does not take matters into its own hands: don't mark it, hand the disagreement over as-is (measured: 88 cases).
                    _disputed.append(c["name"])
                    mend.append(("column", "%s.%s looks like an audit column by name, but the collector declares the caller writes it"
                                 " -- not marked audit, handed back for judgment" % (name, c["name"])))
                    continue
                # The miner did not mark it; det fills it in by name. Measured: 1127 cases, and marking audit means this column
                # can never again be written by any tool in the whole world, so this fallback must be countable.
                c["audit"] = True
                mend.append(("column", "%s.%s looks like an audit column by name and the miner did not mark it; det adds audit"
                             % (name, c["name"])))
        colset = {c["name"] for c in cols}
        if not any(c.get("pk") for c in cols):
            pk = e.get("pk") or e.get("pk_column")
            pk = pk if isinstance(pk, str) else ("id" if "id" in colset else None)
            if pk in colset:
                for c in cols:
                    if c["name"] == pk:
                        c["pk"] = True
                drop.append(("entity", "%s has no column-level pk, fell back to %s" % (name, pk)))
            else:
                drop.append(("entity", "%s has no pk and no id column -- delete_cascade will find the wrong rows" % name))
        cons = []
        for cn in (e.get("constraints") if isinstance(e.get("constraints"), list) else []):
            n = norm_constraint(cn, colset, drop)
            if n:
                cons.append(n)
        for c in cols:                                # column-level unique promoted to table level (an entity's truth lives on the entity)
            if c.get("unique") and not any(x["kind"] == "unique" and x["cols"] == [c["name"]]
                                           for x in cons):
                cons.append({"kind": "unique", "cols": [c["name"]]})
            c.pop("unique", None)
        ent = {"name": name, "columns": cols}
        if cons:
            ent["constraints"] = cons
        if _disputed:
            # For the agent: these columns look like audit columns by name, but code writes to them. You decide -- mark them audit
            # and nobody can write them; leave them unmarked and you must confirm they really are business fields.
            ent["_audit_disputed"] = sorted(set(_disputed))
        if name in life:
            ent["_lifecycle"] = life[name]
        entities.append(ent)
        ents[name] = colset

    # Backfill bare fk_to + drop dangling fk_to. Must wait until all entities are built -- otherwise forward references are missed.
    _pkmap = {e["name"]: next((c["name"] for c in e["columns"] if c.get("pk")), None)
              for e in entities}
    for e in entities:
        for c in e["columns"]:
            bare = c.pop("_fk_bare", None)
            if bare is not None:
                if _pkmap.get(bare):
                    c["fk_to"] = "%s.%s" % (bare, _pkmap[bare])
                else:
                    drop.append(("column", "%s.%s: fk_to %r is not a known entity" % (e["name"], c["name"], bare)))
            fk = c.get("fk_to")
            if isinstance(fk, str) and "." in fk:
                te, _, tc = fk.partition(".")
                if te not in ents or tc not in ents[te]:
                    c.pop("fk_to", None)
                    drop.append(("column", "%s.%s: fk_to %s points outside the schema, dropped"
                                 " (keeping it would reject every insert)" % (e["name"], c["name"], fk)))

    # -- account detection (needed to build panels for login/register tools; must be computed before building tools) --
    # Scan columns in **declaration order**, not via sets -- set iteration order depends on hashing, so the same input run twice would give different
    # account_entity, breaking both caching and resume. email first (downstream ignite uses it to weld the persona).
    cand = []
    for e in entities:
        names = [c["name"] for c in e["columns"]]
        low = {n.lower(): n for n in names}
        # Exact first, substring as fallback -- both tiers take in **declaration order**, not via sets (set iteration order depends on hashing,
        # so the same input run twice would give different account_entity, breaking both caching and resume).
        u = next((low[k] for k in _UCOLS if k in low), None) or \
            next((n for n in names if _URE.search(n)), None)
        pw = next((n for n in names if _PWRE.match(n)), None) or \
             next((n for n in names if _PWRE2.search(n)), None)
        if u and pw:
            cand.append({"entity": e["name"], "username_col": u, "password_col": pw,
                         "_why": "columns %s + %s" % (u, pw)})
    # **What is read from code takes priority over guesses.** The auth effect states "which table this operation verifies against and which two columns it compares";
    # that is a fact from reading the source; the "has a username-like column + password-like column" approach below is a heuristic (191 repos have only one candidate,
    # in 110 repos det's own two pieces of evidence conflict, in 13 repos the agent ultimately chose an entity outside the candidates).
    _authev, _seen_a = [], set()
    for _i2 in (d.get("impls") or []):
        if not isinstance(_i2, dict):
            continue
        for _ef2 in (_i2.get("effects") or []):
            if not (isinstance(_ef2, dict) and _kind(_ef2) == "auth"):
                continue
            _en2 = _ef2.get("entity")
            _u2, _p2 = _ef2.get("username_col"), _ef2.get("password_col")
            if (_en2 in ents and isinstance(_u2, str) and isinstance(_p2, str)
                    and _u2 in ents[_en2] and _p2 in ents[_en2] and _en2 not in _seen_a):
                _seen_a.add(_en2)
                _authev.append({"entity": _en2, "username_col": _u2, "password_col": _p2,
                                "_why": "auth effect in code (%s)" % _i2.get("id_local")})
    if _authev:
        cand = _authev + [c for c in cand if c["entity"] not in _seen_a]
    _acc = {c["entity"]: c for c in cand}
    if cand:
        # **This is a heuristic, not a conclusion.** Measured over 359 repos: 191 repos have only 1 candidate (the agent has nothing to choose from),
        # in 110 repos det's own two pieces of evidence conflict (_auth_gravity_mismatch), and **in 13 repos the agent ultimately
        # chose an entity outside the candidate list** -- the last one directly proves the candidate set is incomplete.
        mend.append(("auth", "account entity: %d candidates picked by the heuristic \"has a username-like column + password-like column\""
                     % len(cand)))

    # -- Edges -> grouped by subject --
    hard, soft, orphan = {}, {}, []
    n_hard = n_soft = 0
    _ids = {i.get("id_local") for i in (d.get("impls") or []) if isinstance(i, dict)}
    for g in (d.get("edges") or []):
        if not isinstance(g, dict):
            continue
        subj = g.get("subject")
        if isinstance(subj, dict):
            subj = subj.get("ref") or subj.get("id")
        if not isinstance(subj, str):
            continue
        nd = norm_needs(g.get("needs"), ents, drop, "edge %s" % subj)
        if not nd:
            continue
        rel = g.get("relation")
        if subj not in _ids:
            # Ownerless walls: the subject is not any impl. v3 pushed this ratio from 27% down to 9%; the rest
            # are mostly permission checkers / controller names. **Two-hop propagation was disproven** (only +2%, and
            # aggregate nodes like `--guards--> User` would dump hundreds of needs onto one tool = fake walls),
            # so hand them back to the agent as-is -- it has ref_code and can judge which tools this wall belongs on.
            head = subj.split(".")[0] if "." in subj else subj
            why = ("subject does not have the <Entity>.<op> shape" if "." not in subj else
                   "head %r is not a known entity (most likely a controller / permission checker)" % head
                   if head not in ents else
                   "the same entity has other impls, but op %r was not collected" % subj
                   if any(x.startswith(head + ".") for x in _ids if isinstance(x, str)) else
                   "entity %r is in the schema but has no impl at all" % head)
            orphan.append({"subject": subj, "relation": rel, "needs": nd, "why_unattached": why,
                           "condition": g.get("condition"), "evidence": g.get("evidence")})
            continue
        bucket = hard if rel in ("guards", "requires") else soft
        rec = bucket.setdefault(subj, {"dnf": [], "ev": []})
        rec["dnf"] += nd
        if g.get("evidence"):
            rec["ev"].append(str(g["evidence"])[:200])
        if rel in ("guards", "requires"):
            n_hard += 1
        else:
            n_soft += 1

    # -- impl -> candidate tools --
    tools, seen = [], {}
    n_impl = _no_entry = 0
    for i in (d.get("impls") or []):
        if not isinstance(i, dict):
            continue
        n_impl += 1
        idl = i.get("id_local")
        # entry: can the client reach it? If not, no tool is generated -- for a tool that does not exist in the real world,
        # the agent would learn to call it, and the environment would be lying. The criterion is "where the line that registers it is", given by the miner.
        _e = i.get("entry")
        _ek = _e.get("kind") if isinstance(_e, dict) else None
        if _ek is None:
            # **No entry means no tool; there is no lenient tier.** This used to pass (to avoid wiping out the existing corpus),
            # but the cost of that opening: an impl that omits entry **silently** becomes a tool, while it may
            # not be callable in the real app at all -- the agent learns to call it, and the environment lies.
            # The direction of the cost is fixed: mislabeling as external = shipping a nonexistent tool; mislabeling as internal = one tool fewer.
            _no_entry += 1
            drop.append(("impl", "%s yields no tool: no entry -- cannot tell whether the client can reach it" % idl))
            continue
        if _ek in ("internal", "cli", "job"):
            drop.append(("impl", "%s yields no tool: entry=%s, not reachable by the client" % (idl, _ek)))
            continue
        if _ek not in _ENTRY_KINDS:
            drop.append(("impl", "%s yields no tool: entry.kind=%r is not in the closed vocabulary" % (idl, _ek)))
            continue
        ent, ent_why = eff_entity(i, ents, mend)
        lc = life.get(ent) or {}
        via = (lc.get("via") or {}).get(idl)
        fam, why = pick_family(i, via, mend)
        if not fam:
            # "Yields no tool" rather than "cannot determine family" -- both cases end up here: the family really cannot be determined,
            # and **deliberately not generated** (middleware/policy). The latter is not a failure, and the record wording should not call it one.
            drop.append(("impl", "%s yields no tool: %s" % (idl, why)))
            continue
        # **Decide the family first, then see whether that family needs an entity.** The reverse order would wrongly kill a batch: `action.emit`
        # only needs a channel, `guard.logout` needs nothing; having no entity is normal for them.
        if ent is None and fam in _NEED_ENTITY:
            drop.append(("impl", "%s (%s) cannot determine entity: %s" % (idl, fam, ent_why)))
            continue
        name = re.sub(r"[^A-Za-z0-9_]", "_", str(idl or "%s_%s" % (i.get("op"), ent))).strip("_").lower()
        if not name:
            name = "op_%d" % len(tools)
        if name in seen:
            seen[name] += 1
            name = "%s_%d" % (name, seen[name])
        else:
            seen[name] = 0
        eo = next((x for x in entities if x["name"] == ent), None) if ent else None
        lif = {
            "_pk": next((c["name"] for c in eo["columns"] if c.get("pk")), None) if eo else None,
            # Columns that can be given at row creation: exclude pk (auto-generated) and audit columns. **immutable is not excluded** --
            # it means "cannot change after creation", not "cannot be given at creation".
            "_insertable": ([c["name"] for c in eo["columns"]
                             if not c.get("pk") and not c.get("audit")] if eo else None),
            "_settable": ([c["name"] for c in eo["columns"]
                           if not c.get("pk") and not c.get("audit") and not c.get("immutable")]
                          if eo else None),
            "_soft_col": next((c["name"] for c in (eo["columns"] if eo else [])
                               if _SOFT_RE.match(c["name"])), None),
            "_unique": [c for c in ((eo.get("constraints") or []) if eo else [])
                        if isinstance(c, dict) and c.get("kind") == "unique"],
            "_account": _acc.get(ent), "_via": via,
        }
        mark = []
        # The touched surface was not decided by the primary effect -> goes into the review list. Measured: 90% comes from the primary effect (that is grounded),
        # the remaining 4.3% relies on the entity prefix of id_local, 0.5% on params.binds frequency -- **the latter two are guesses**,
        # and a wrong entity is silent: the Env builds, the call returns ok, and the verifier checks a different table.
        if ent and not ent_why.startswith(EW_PRIMARY.split("%s")[0]):
            mark.append(D_ENTITY % (ent_why,))
            mend.append(("entity", "touched surface of %s decided by fallback as %s: %s" % (idl, ent, ent_why)))
        # What decided family must be re-checkable. The 93.6% from the effects lookup needs no attention; **regex and op fallback
        # must go into _defaulted**: no kind in the effects vocabulary can say "this is authentication" (login's effects
        # are external+row_read+row_update, which by _EFF_RANK land on update.field_set), so
        # we can only rely on names -- and a counterexample was already caught: WebAuthnCredential.saveLogin -> guard.auth
        # (it saves a credential, it is not a login). Until the contract adds an authentication signal, these 544 must be re-checkable.
        if why.startswith("id_local looks like"):
            mark.append(D_FAMILY_REGEX)
            mend.append(("family", "family of %s decided by id_local regex as %s" % (idl, fam)))
        elif "by op=" in why:
            mark.append(D_FAMILY_OP)
            mend.append(("family", "effects of %s have no structural entry; family fell back by op to %s"
                         % (idl, fam)))
        es = build_exec_spec(i, fam, ent, ents.get(ent), ents, lif, drop, name, mark, mend)
        ins, binds = norm_params(i, ent, ents, drop, name, mend)
        # {"$arg": x} in row_key / lookup_by must be on the panel, otherwise the runtime cannot resolve it,
        # the executor cannot locate the row, and it shows up as "target row does not exist".
        # After A1a this is **basically an idle safety net**: what _argref reverse-looks-up is the real parameter name, and real parameters
        # were already put on the panel by norm_params, so setdefault does nothing. Only those that failed the reverse lookup and used the column name as a stand-in
        # actually add a column name to the panel -- and those are already flagged with `row_key (column name standing in as the parameter name)`.
        ty = {c["name"]: c.get("type", "text") for c in (eo["columns"] if eo else [])}
        for k in ("row_key", "lookup_by", "subject_key", "object_key"):
            for col, v in (es.get(k) or {}).items():
                if isinstance(v, dict) and isinstance(v.get("$arg"), str):
                    ins.setdefault(v["$arg"], ty.get(col, "text"))
        for k in ("key",):
            for col in (es.get(k) or []):
                if isinstance(col, str):
                    ins.setdefault(col, ty.get(col, "text"))
        v = es.get("verify") or {}
        for k in ("username_col", "password_col"):
            if isinstance(v.get(k), str):
                ins.setdefault(v[k], "text")
        # Write columns - columns covered by sets must be a subset of inputs. The runtime's _writable also excludes type=="id" and
        # audit columns (they are maintained by the system), so filter the same way here, to avoid adding a parameter that can never be written.
        _set_cols = set()
        for k in ("set", "set_on_create", "set_on_exists"):
            _set_cols |= set((es.get(k) or {}).keys())
        for k in ("fields", "insert_fields"):
            if isinstance(es.get(k), dict):
                # The dict form already names the parameters, and parameters were already put on the panel by norm_params --
                # nothing needs to be added here. Adding would stuff column names onto the panel, back to what A1 was meant to fix.
                continue
            for c in (es.get(k) or []):
                if not isinstance(c, str) or c in _set_cols or c in ins:
                    continue
                cd = next((x for x in (eo["columns"] if eo else []) if x["name"] == c), None)
                if cd and cd.get("type") != "id" and not cd.get("audit"):
                    ins[c] = cd.get("type", "text")
                    mark.append(D_ARG_FROM_COL)

        t = {"tool": name, "op": i.get("op"), "family": fam, "exec_spec": es,
             "input_schema": ins,
             "_evidence": {"locator": i.get("locator"), "id_local": idl,
                           **({"entry": _e} if isinstance(_e, dict) else {}),
                           "family_why": why, "entity_why": ent_why}}
        if ent:
            t["entity"] = ent
        if binds:
            t["_binds"] = binds                       # parameter -> Entity.col, used by the probe to synthesize inputs
        if i.get("output_schema") is not None:
            t["_output_schema"] = i["output_schema"]  # used by the agent to write the description
        if isinstance(i.get("ref_code"), str):
            t["_evidence"]["ref_code"] = i["ref_code"][:600]
        g = {}
        hrec = hard.get(idl)
        if hrec and hrec["dnf"]:
            g["preconditions"] = hrec["dnf"]
            t["_evidence"]["edges"] = hrec["ev"][:6]
        srec = soft.get(idl)
        if srec and srec["dnf"]:
            # needs with relation=triggers are a **soft order** ("who gets called first"), not a hard wall.
            # Hard-coding them as guards would create walls that do not exist in the real code -- leave them to the agent to judge one by one.
            t["_candidate_preconditions"] = srec["dnf"]
        # $actor in a guard = evaluation requires a session, otherwise the runtime raises StateError.
        # This is not a heuristic, it is a necessary condition.
        # NOTE: once the shape switched to IR, `$actor.id` in the tree is `{"actor": "id"}` -- the old
        # string scan `"$actor" in ...` would **find none at all**, and requires_auth would silently stop working.
        # Accept both skins (old specs in the cache are still source syntax).
        if any(('"actor"' in json.dumps(c, ensure_ascii=False, default=str)
                or "$actor" in json.dumps(c, ensure_ascii=False, default=str))
               for grp in g.get("preconditions", []) for c in grp):
            g["requires_auth"] = True
        req = [p["name"] for p in (i.get("params") or [])
               if isinstance(p, dict) and p.get("required") and isinstance(p.get("name"), str)]
        if req:
            g["required"] = req
        if g:
            t["guards"] = g
        if mark:
            # "These fields were filled in by det as fallback, not read from the code" -- stating != not looking.
            t["_defaulted"] = sorted(set(mark))
        tools.append(t)

    raw = {"env_id": repo, "_prep_version": 3, "entities": entities, "tools": tools,
           "seed_state": {}, "summary": d.get("summary"), "_auth_candidates": cand}
    _sfc = scan_actor_cols(d)
    if _sfc:
        raw["_session_fields"] = _sfc
    if n_impl and _no_entry >= n_impl:
        # An empty spec is **the hardest kind of failure to diagnose**: downstream only says "no write tool changed the world",
        # while the real cause is three stations upstream. So say it plainly here, and say that this layer cannot fix it.
        raw["_entry_missing"] = (
            "%d operations in this repo, **none has an entry**, so not a single tool was generated. "
            "`entry` answers \"can the client reach it\" -- if that cannot be decided, no tool can be generated. **This needs re-mining; "
            "it is not something the build layer can fix.**" % n_impl)
    if cand:
        raw["_auth_method"] = (("The auth effect in code directly gives the account table and the two credential columns (listed first); the remaining "
                                if _authev else "") +
                               "candidates = entities that have both a \"username-like column\" and a \"password-like column\", scanned in declaration order. "
                               "**This is a heuristic, not a conclusion** -- confirm by reading code; "
                               "if this repo's account table is not among the candidates, choose an entity outside the candidates directly.")
    if not cand:
        # No candidate at all = this env **cannot log in**, and owner-scoped search and persona welding
        # all presuppose being able to log in. **We must say which kind it is**; we must not quietly produce a spec that cannot be logged into --
        # "failing is allowed; failing without saying so is not".
        has_u = any(_URE.search(c["name"]) for e in entities for c in e["columns"])
        has_p = any(_PWRE2.search(c["name"]) for e in entities for c in e["columns"])
        raw["_auth_missing"] = (
            "the spec has no entities at all" if not entities else
            "username and password columns are in two different tables (separate credential table) -- you need to judge which is the account table" if has_u and has_p else
            "only username-like columns, no password column -- possibly external auth / OAuth" if has_u else
            "only password-like columns, no username-like column" if has_p else
            "no sign of accounts at all; this repo may simply have no user system")
    # **Circumstantial evidence** for the account entity: the table most foreign keys point to. It agrees with candidates[0] only 52% of the time -- disagreement does not mean
    # wrong (in some repos foreign keys all point to Project / Workspace anyway), but it is a divergence worth the agent's look.
    grav = {}
    for e in entities:
        for c in e["columns"]:
            fk = c.get("fk_to")
            if isinstance(fk, str) and "." in fk:
                t = fk.split(".", 1)[0]
                grav[t] = grav.get(t, 0) + 1
    if grav:
        top = sorted(grav.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        raw["_fk_gravity"] = {"entity": top[0], "fk_count": top[1]}
        if cand and top[0] != cand[0]["entity"]:
            raw["_auth_gravity_mismatch"] = (
                "most foreign keys point to %s (%d of them), while the account candidate is %s -- confirm the ownership anchor"
                % (top[0], top[1], cand[0]["entity"]))
    conv = d.get("conventions")
    if isinstance(conv, dict) and conv.get("read_denied") in ("not_found", "forbidden"):
        # How the world responds when a row is not visible is this app's own personality, written in the real code. **A repo-level convention**,
        # not a per-op fact (a shared authorize()/policy layer, one style used throughout).
        raw["_read_denied"] = conv["read_denied"]
    if orphan:
        raw["_unattached_walls"] = orphan[:200]
    if isinstance(d.get("no_edges"), list) and d["no_edges"]:
        raw["_no_edges"] = d["no_edges"][:200]        # "judged that there really are no edges", not a collection miss

    rep["in"] = {"entities": len(schemas), "impls": n_impl, "edges": len(d.get("edges") or []),
                 "edges_hard_with_needs": n_hard, "edges_soft_with_needs": n_soft}
    rep["out"] = {
        "entities": len(entities),
        "columns": sum(len(e["columns"]) for e in entities),
        "constraints": sum(len(e.get("constraints") or []) for e in entities),
        "lifecycle": sum(1 for e in entities if e.get("_lifecycle")),
        "tools": len(tools),
        "tools_with_preconditions": sum(1 for t in tools if (t.get("guards") or {}).get("preconditions")),
        "tools_with_candidate_pre": sum(1 for t in tools if t.get("_candidate_preconditions")),
        "precondition_groups": sum(len((t.get("guards") or {}).get("preconditions") or []) for t in tools),
        "tools_with_binds": sum(1 for t in tools if t.get("_binds")),
        "tools_with_output": sum(1 for t in tools if t.get("_output_schema")),
        "tools_with_set": sum(1 for t in tools if any(
            k in (t["exec_spec"] or {}) for k in ("set", "set_on_create", "set_on_exists"))),
        "read_tools": sum(1 for t in tools if t["family"] == "crud.fetch"),
        "read_scoped": sum(1 for t in tools if t["family"] == "crud.fetch"
                           and (t["exec_spec"] or {}).get("scope")),
        "search_tools": sum(1 for t in tools if t["family"].startswith("search.")),
        "search_scoped": sum(1 for t in tools if t["family"].startswith("search.")
                             and (t["exec_spec"] or {}).get("scope")),
        # The three states must be recorded separately: has scope / judged global / did not state.
        # "Indistinguishable coverage is no coverage."
        "read_search_global": sum(1 for t in tools
                                  if (t["family"].startswith("search.") or t["family"] == "crud.fetch")
                                  and not (t["exec_spec"] or {}).get("scope")
                                  and not (t["exec_spec"] or {}).get("_scope_undecided")),
        "scope_undecided": sum(1 for t in tools if (t["exec_spec"] or {}).get("_scope_undecided")),
        "status_transition": sum(1 for t in tools if t["family"] == "update.status_transition"),
        "auth_candidates": len(cand),
        "unattached_walls": len(orphan),
    }
    agg = {}
    for layer, why in drop:
        key = _reason_key(why)
        agg.setdefault(layer, {}).setdefault(key, 0)
        agg[layer][key] += 1
    # Display keeps only the top 12 (otherwise the report is unreadable), but dropped_total is the **full count** -- quietly under-reporting equals
    # lying about coverage.
    rep["dropped"] = {k: sorted(v.items(), key=lambda x: -x[1])[:12] for k, v in agg.items()}
    rep["dropped_total"] = {k: sum(v.values()) for k, v in agg.items()}
    rep["dropped_kinds"] = {k: len(v) for k, v in agg.items()}
    magg = {}
    for layer, why in mend:
        key = _reason_key(why)
        magg.setdefault(layer, {}).setdefault(key, 0)
        magg[layer][key] += 1
    rep["mended"] = {k: sorted(v.items(), key=lambda x: -x[1])[:12] for k, v in magg.items()}
    rep["mended_total"] = {k: sum(v.values()) for k, v in magg.items()}
    return raw, rep


if __name__ == "__main__":
    import sys
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    raw, rep = prep(d)
    print(json.dumps(rep, ensure_ascii=False, indent=1))


def _compile_guards(spec):
    """Source syntax of `guards.preconditions` -> grammar's IR. -> list of records.

    **Compilation happens after the agent and before the probe.** The source syntax `{entity, scope[], card}` is written for **authors**
    (the collector-side miner and the build spec agent here are both authors); the IR is for **machines** to evaluate.
    `grammar.from_state` is the parser between the two -- det, as the compiler middle end, calls it once, so downstream does not have to
    traverse scope arrays separately at every station.

    It lives here rather than in `norm_state` because the agent has to **judge** which walls are real, which to promote, and
    which to drop (the `_candidate_preconditions` item in `build_spec.md`). Making it face a tree its prompt
    never described amounts to forcing it to edit something it cannot understand. Measured: 299 repos, 4600 tools with preconditions;
    this path is heavily used, and it must not be allowed to misstep.

    Entries already in IR pass through unchanged (idempotent); those that cannot be compiled **keep the source syntax** -- the runtime accepts both, keeping beats dropping.
    """
    notes, n_ok, n_bad = [], 0, 0
    for t in (spec.get("tools") or []):
        if not isinstance(t, dict):
            continue
        g = t.get("guards")
        if not isinstance(g, dict) or not g.get("preconditions"):
            continue
        out = []
        for grp in g["preconditions"]:
            grp = grp if isinstance(grp, list) else [grp]
            conj = []
            for st in grp:
                if not isinstance(st, dict) or "node" in st:
                    conj.append(st)                  # already IR / shape not recognized: as-is
                    continue
                try:
                    conj.append(_GRAM.from_state(st))
                    n_ok += 1
                except _GRAM.GrammarError as ex:
                    conj.append(st)
                    n_bad += 1
                    if n_bad <= 3:
                        notes.append(("guards", "a precondition of %s cannot be compiled into IR: %s (kept as source syntax, "
                                                "the runtime accepts both)" % (t.get("tool"), ex)))
            out.append(conj)
        g["preconditions"] = out
    if n_ok:
        notes.append(("guards", "compiled %d preconditions from source syntax into IR" % n_ok))
    return notes


# -- det normalization after the agent hands back its draft ------------------
def seal(spec, raw):
    """Normalize the agent-written spec in place. -> list of records `[(kind, description)]`.

    **This is an opening that rewrites the agent's product, so its boundary must be drawn hard:**
      (1) only things "mechanically derivable by det, where asking the agent to copy them only leads to omissions", **no judgment at all**;
      (2) **add only, never change** -- keys the agent explicitly wrote are never overwritten;
      (3) every change is recorded (same philosophy as `mend`), otherwise this becomes a place to hide errors.

    Placement: inside the `build_node` feedback-round loop, before `probe(spec)`. All four are hard constraints --
      - must be after the agent: the `session_fields` columns must sit on the account entity **the agent picked**,
        and the candidate spec has no auth block at all;
      - must be before the probe: otherwise the probe world cannot resolve `$session.<col>`, inserts still fail,
        **reporting a pile of fake write failures**, and the agent gets sent to fix a problem that is not its own;
      - must be inside the loop: the agent rewrites the draft on every feedback round (idempotent; rerunning has no side effects);
      - must be before promote: `repo_specs/` is ignite's only spec source.
    """
    notes = []
    notes += _compile_guards(spec)
    want = raw.get("_session_fields") or []
    if not want:
        return notes
    auth = spec.get("auth")
    if not isinstance(auth, dict) or not auth.get("account_entity"):
        notes.append(("session_fields",
                      "spec has no auth.account_entity; %d $actor.<col> have nowhere to go: %s"
                      % (len(want), ", ".join(want[:6]))))
        return notes
    ae = auth["account_entity"]
    acols = set()
    for e in (spec.get("entities") or []):
        if isinstance(e, dict) and e.get("name") == ae:
            acols = {c.get("name") for c in (e.get("columns") or []) if isinstance(c, dict)}
            break
    sf = auth.get("session_fields")
    sf = dict(sf) if isinstance(sf, dict) else {}
    added, off, kept = [], [], []
    for c in want:
        if c not in acols:
            off.append(c)
        elif c in sf:
            kept.append(c)                 # the agent wrote it itself; don't overwrite
        else:
            sf[c] = c
            added.append(c)
    if added:
        auth["session_fields"] = sf
        spec["auth"] = auth
        notes.append(("session_fields", "configured %d columns (copied into the session from the %s row at login): %s"
                                        % (len(added), ae, ", ".join(added))))
    if kept:
        notes.append(("session_fields", "%d columns already configured by the agent, kept as-is: %s"
                                        % (len(kept), ", ".join(kept))))
    if off:
        # **This batch is exactly the collector-side evidence**: the miner wrote `$actor.company_id`, but the account table has no such column
        # -- the source most likely fetches it across a relation (user -> owning company -> id), and the miner did not read it accurately. This layer cannot configure it,
        # and should not patch it here either (see the station boundary: whatever can be judged from the collect alone belongs to the collector side).
        notes.append(("session_fields_off",
                      "%d columns do not exist on account table %s, cannot configure: %s. "
                      "Most likely the source fetches them across a relation; **this must be fixed on the collector side, build cannot patch it**"
                      % (len(off), ae, ", ".join(off[:8]))))
    return notes
