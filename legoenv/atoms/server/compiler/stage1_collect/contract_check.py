#!/usr/bin/env python3
"""Contract compliance check — det finds the faults, whoever wrote the output fixes them (invariant I8).

This used to check depth-1 coverage only. The batch of mandatory positions the v3 contract added
(params/binds/sets/row_key/pk/scope.kind/the entity of effects...) had **no det validating any of them** — and the v2 lesson was exactly that
a field nobody det-checks sees its fill rate collapse (pk 0%, description 100% empty, scope 66% missing). Hence this.

Two disciplines that hold throughout:
  - det only finds faults and gives evidence; **judgement and the fix stay with the session that wrote it**;
  - "judged it" and "didn't look" must be distinguishable — so `unknown` / an empty list is compliant; only omission is a violation.

Output work/<repo>.json:
  {repo, session_id, config_dir, coverage, missing:[...], violations:{rule:[...]}, ...}
The feedback round renders its prompt from this; after fixing, rerun this script and compare.
"""
import json, glob, os, re, sys, collections

if __name__ == "__main__" and len(sys.argv) < 3:
    sys.exit("usage: contract_check.py <collect dir> <work-order dir> "
             "(set BASELINE=<previous collect dir> for regression checks)")
COLLECT = sys.argv[1] if len(sys.argv) > 1 else "collect"
OUT = sys.argv[2] if len(sys.argv) > 2 else "topup"
THRESH = float(os.environ.get("TOPUP_THRESH", "1.0"))
MAX_LIST = int(os.environ.get("TOPUP_MAX_LIST", "120"))
MAX_VIOL = int(os.environ.get("TOPUP_MAX_VIOL", "40"))     # max examples listed per rule
SESSMAP = os.environ.get("SESSMAP", "")      # optional {repo: {session_id, config_dir}} fallback
BASELINE = os.environ.get("BASELINE", "")      # previous collect dir, for regression checks
REG_NOEDGE = int(os.environ.get("REG_NOEDGE", "20"))   # how many new no_edges entries count as suspicious

MUT = {"create", "update", "delete", "action"}
READY = {"read", "search"}
WRITE_KINDS = {"row_insert", "row_update", "row_delete", "row_soft_delete", "row_upsert"}
NEED_ROWKEY = {"row_update", "row_delete", "row_soft_delete", "row_upsert", "row_read"}
NEED_FIELDS = {"row_insert", "row_update", "row_upsert"}
READ_KINDS = {"row_read", "row_search"}
ALL_KINDS = WRITE_KINDS | READ_KINDS | {"link", "unlink", "spawn", "dispatch",
                                        "probe", "schedule", "external", "auth"}
AUTH_MODES = {"verify", "signout", "register"}
TYPES = {"text", "int", "float", "bool", "datetime", "id", "json"}
# Keys allowed on a column: the 13 fixed by the contract + three documentation-only fields. Anything else is **a copy of the source repo's framework idiom**
# (Django's max_length/choices, DDL's not_null, ORM auto_increment/precision...).
# det has an alias table to catch them, but that fallback is a **silent rename** — the contract side must say no, or we would never see whether
# this rate is rising or falling. Note `unique` used to be outside too: uniqueness is **table-level** and belongs in constraints[].
# `unique` stays inside: **a single-column unique key carries exactly the same information on the column or on the table**; downstream lifts it to table-level losslessly.
# Forcing 1533 mechanical rewrites would only flood the work orders without buying any information. Composite unique keys still go table-level only.
# ── det's normalisation ability: only report what it cannot absorb ─────────────────────────
# If downstream **absorbs a violation losslessly and records it**, reporting it is noise — and re-mining is not cheap; work orders flooded with noise
# bury the real problems (same reason the `name looks like an audit column but no position taken` rule was deleted). So ask det directly:
# can you normalise this type / this key name? If yes, don't report it.
#
# ⚠ By direction, library should not depend on composition; this is an exception: the alternative is copying the two tables over here,
# and **a copy means they drift apart**. Better this import, with the test_prompt_vocab_sync
# assertion nailing down that "both sides read the same table". build_prep only imports json / re; no side effects.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "stage2_spec"))
import build_prep as _PREP          # noqa: E402


COL_KEYS = {"name", "type", "pk", "nullable", "default", "enum", "min", "max", "pattern",
            "fk_to", "on_delete", "audit", "immutable", "unique",
            "description", "locator", "note"}
AUDIT_RE = re.compile(r"(?i)^(created|updated|modified|changed|inserted)_?(at|on|time|date)$"
                      r"|^(date_)?(created|updated|modified)$|^(ctime|mtime)$")
SYM_HEADS = {"$arg", "$actor", "$session"}


def _sym_hint(v):
    """An unknown $ symbol in row_key → a sentence **one can act on**.

    It used to reply only "unknown symbol $subject.id". That says it is illegal, but not why, and not what to write
    instead — while contract_check set its own rule: "when reporting an error, always give the correct shape; saying only
    'this is illegal' makes the miner guess, and its guess will be the next invented form". This rule broke its own rule.
    Measured: 221 occurrences of `$subject.x`; 14 repos were **this one rule away** from zero violations, and nobody fixed it for three rounds.
    Two causes need separate ways out (measured 22% / 78%):
      - the caller can actually supply this column; the parameter is right there unused → write $arg.<param name>
      - the row is looked up through other columns, but row_key names an internal auto-increment pk the caller never knows
        (airflow: the caller gives dag_id+dag_run_id+task_ids, but row_key says ti_id)
        → row_key should use **that set of columns**, not the internal pk
    """
    if str(v).partition(".")[0] == "$subject":
        return (u"%s — `$subject` only means something on an edge; inside an effect there is "
                u"no such thing as \u201cthe row we are about to find\u201d (that is circular). "
                u"Two ways out: (a) if the caller does supply this column, write "
                u"`$arg.<param>`; (b) if this row is located through *other* columns, put "
                u"**those** columns in `row_key` \u2014 not an internal auto-increment id the "
                u"caller has never seen." % v)
    return u"unknown symbol %s \u2014 legal heads are %s" % (v, " ".join(sorted(SYM_HEADS)))


def _rkval_bad(v, pnames=None):
    """Is one value in the object form of `row_key` legal? → None if legal; otherwise a reason.

    Only three things are legal: a `$` symbol (`$arg.x` / `$actor.id` / `$session.k`, bare or wrapped as
    `{"ref": ...}`), `{"lit": ...}` or a bare scalar, and `{"sym": "$now"}`.

    `{"col": ...}` is illegal — "another column of this row" cannot be resolved in a where clause; that is a row-internal comparison
    and belongs in constraints. `$subject` is illegal too — it is an edge concept with no counterpart while a single tool executes.
    """
    if isinstance(v, str) and v.startswith("$"):
        if v.partition(".")[0] in SYM_HEADS:
            return None
        return _sym_hint(v)
    if isinstance(v, (str, int, float, bool)) or v is None:
        return None
    if not isinstance(v, dict):
        return u"unrecognised value shape: %r" % (v,)
    if "lit" in v:
        return None
    if "sym" in v:
        return None if v["sym"] == "$now" else u"$now is the only symbolic constant, got %r" % (v["sym"],)
    if "from" in v:
        # "The row to locate is pointed at by a value on another table." row_key value slots and sets/needs
        # value slots share one Value vocabulary, and `{"from": ...}` is one of its forms — this used to be rejected here,
        # so write effects where "the reference lives on the other side" (the parent has no column pointing at the child) **could not be expressed in the contract**:
        # neither of the two ways out the message offered (write this table's FK column / add a parameter) applied.
        # Validation fully reuses `_from_bad` — three layers read one language, so the vocabulary can have only one source of truth.
        _fb = _from_bad(v)
        if _fb:
            return _fb
        # ⚠ Opening this door means guarding it too. row_key has the rule "some required parameter must
        # bind to this column" because **a write that cannot locate its row is a failure with no signal**; a subquery bypasses
        # that rule, so if the `$arg.x` it references is an invented parameter, it recreates the same hole somewhere else
        # (how airflow invented ti_id in an earlier round). Other Value slots lack this check;
        # that is an existing gap. This is a newly opened door and must not open with the gap.
        _w = v["from"].get("where")
        if isinstance(_w, dict):
            _w = [_w]
        for _cl in _L(_w):
            _vv = _D(_cl).get("value", _D(_cl).get("right"))
            _r = _vv.get("ref") if isinstance(_vv, dict) else (
                _vv if isinstance(_vv, str) and _vv.startswith("$") else None)
            if not (isinstance(_r, str) and _r.startswith("$arg.")):
                continue
            _pn = _r.split(".", 1)[1]
            if pnames is not None and _k(_pn) not in pnames:
                return (u"the subquery matches on `%s`, but this operation declares no such "
                        u"parameter (it has: %s). The whole point of locating the row through "
                        u"another table is that the caller *does* name something \u2014 use the "
                        u"parameter it really takes, and do not invent one the interface does "
                        u"not have" % (_r, ", ".join(sorted(pnames)) or "none"))
        return None
    if "col" in v:
        return u"this names another column of the same row (%r), which a where clause cannot resolve — a row-internal comparison belongs in constraints" % (v["col"],)
    if "ref" in v:
        r = v["ref"]
        if not isinstance(r, str) or not r.startswith("$"):
            return u"ref is not a $ symbol: %r" % (r,)
        return None if r.partition(".")[0] in SYM_HEADS else _sym_hint(r)
    return u"unrecognised value shape: %r" % (v,)


SCOPE_KINDS = {"owner", "owner_or_public", "tenant", "global"}
METHODS = {"exact", "substring", "keyword", "semantic", "hybrid", "unknown"}
# **Derived from grammar, not hand-copied.** The cost of hand-copying showed up right away this round: grammar gained `expr`/`was`
# and this did not follow, so the checker both suggested "write {"was": ...}" and flagged output written that way as
# "value outside the Value vocabulary" — an agent following it traded one violation for another, same tier, reported again next round.
# This is the Nth case of "the middle layer is narrower than both ends": three layers read one language, so the vocabulary can have only one source of truth.
# Rule names of the two per-repo distribution alerts. They are constants because tests look them up by name — hand-copied literals
# mean a wording change does not turn the test red (an assertion expecting False silently becomes a false green).
RULE_ALL_ENTRY_INTERNAL = "every entry is internal"
RULE_NO_ENTRY_INTERNAL  = "not a single entry is internal"

VALUE_KEYS = set(_PREP._VALUE_KEYS) | {"from", "expr", "was"}
# **Derived from `runtime/grammar.py`; no separate table.** All three layers (prompt / det / checker) now point at
# the same source of truth; a copy costs drift, and drift raises no error. `neq` is also accepted: it is the old State
# spelling, all 609 existing corpus occurrences use it, and flagging it would punish things that are not broken.
# Invented operator → correct form. **When reporting an error, always give the correct shape** — saying only "this operator is illegal"
# makes the miner guess, and its guess will be the next invented operator (measured, there is already a string of
# changed / increased / increment / concat / any).
# grammar now supports the delta case: not by adding an operator but by adding a sixth Value `{"was": col}`,
# so it composes with every comparison operator automatically.
_OP_FIX = {
    "increased":  'op="gt"  + value={"was": "<same column>"}',
    "increment":  'op="gt"  + value={"was": "<same column>"}',
    "incremented":'op="gt"  + value={"was": "<same column>"}',
    "decreased":  'op="lt"  + value={"was": "<same column>"}',
    "decremented":'op="lt"  + value={"was": "<same column>"}',
    "changed":    'op="ne"  + value={"was": "<same column>"}',
    "modified":   'op="ne"  + value={"was": "<same column>"}',
    "updated":    'op="ne"  + value={"was": "<same column>"}',
    "not_null":   'op="is_not_null" (unary — write no value)',
    "any":        'drop the clause — "any value" is simply no constraint',
}

OPS = set(_PREP._GRAM.FIELD_OPS) | {"neq"}
CARD_OPS = set(_PREP._GRAM.CARD_OPS) | {"neq"}
TIMEY = {"datetime", "timestamp", "timestamptz", "date", "time", "datetime2"}
NULLY = {"null", "none", ""}


def _n(v):
    if isinstance(v, dict):
        v = v.get("ref") or v.get("id_local") or v.get("name")
    if v is None or isinstance(v, str):
        return v
    # ref written as an array/object/number — turn it into a hashable short string so it lands as a violation instead of crashing the check
    return repr(v)[:80]


def _k(v):
    """Scalarise: every value that goes into a set or an `in` test passes through here.
    dict/list become a short string — it matches no closed vocabulary, so it lands as a violation instead of crashing the check."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return repr(v)[:80]


def _L(x):
    """Return the list; anything not a list counts as empty — the type error is recorded as a separate violation by the caller, not raised here."""
    return x if isinstance(x, list) else []


def _D(x):
    return x if isinstance(x, dict) else {}


# `expr.by` must be a numeric Value. `{"sym": "$now"}` is **a backdoor for time arithmetic**:
# grammar now rejects it at compile time (it used to compile, then silently become UNKNOWN in runtime — an assertion meant to say
# "how long until it expires" became one that never holds, with zero errors throughout).
# The checker must report it **on the collect side**: if it only blows up at build spec, a whole tool blows up, two stages away from whoever wrote it.
def _expr_by_bad(v):
    """→ explanation | None. Recursively checks `by` in every expr level of the Value."""
    if not isinstance(v, dict):
        return None
    e = v.get("expr")
    if isinstance(e, dict):
        by = e.get("by")
        if isinstance(by, dict) and "sym" in by:
            return "expr.by = %r — time arithmetic is forbidden; `by` must be a number-valued Value ({\"lit\"} / {\"col\"} / {\"ref\": \"$arg.x\"})" % (by,)
        return _expr_by_bad(by)
    return None


# Equality against NULL is **a no-op under three-valued logic**: in SQL `x = NULL` / `x <> NULL` evaluate to
# UNKNOWN rather than true/false, and a row filter collapses UNKNOWN to False — so the clause **never holds**,
# the whole guard / constraint silently stops working, with zero errors throughout. The grammar has unary operators `is_null` / `is_not_null`
# precisely for this.
#
# This is not theoretical: two assertions in runtime/test_constraints were red from the day they were added; the root cause was
# the test writing "not null" as `neq` + `{"lit": null}`; and code_collector's flagship example
# **was written the same way** — that is exactly what the miner copied.
_NULLY_OPS = {"eq": "is_null", "ne": "is_not_null", "neq": "is_not_null"}


def _null_cmp_bad(op, v):
    """→ correct form | None."""
    fix = _NULLY_OPS.get(_k(op))
    if not fix:
        return None
    if isinstance(v, dict) and len(v) == 1 and "lit" in v and v["lit"] is None:
        return fix
    return None


def _arity_of(op):
    """Operator arity; taken from FIELD_OPS in runtime/grammar.py; unknown ones are treated as binary."""
    try:
        meta = _PREP._GRAM.FIELD_OPS.get(_k(op))
        return meta[0] if meta else 2
    except Exception:
        return 2


def _val_ok(v):
    # `{"lit": ..., "verbatim": true}` is **the only two-key Value allowed**: the model uses it to declare
    # "this string is literally what the column stores", specifically to counter false positives of the content heuristic below.
    # ⚠ Without letting it through, the third way out we offer would immediately hit that rule — the emitter being wider than the receiver,
    # the mirror image of the same disease as "the middle layer is narrower than both ends".
    if isinstance(v, dict) and set(v) == {"lit", "verbatim"}:
        return v.get("verbatim") is True
    return isinstance(v, dict) and len(v) == 1 and next(iter(v)) in VALUE_KEYS


# ── a "description" in a value slot instead of a "value" ────────────────────────────────
# **This is the first rule in this checker that looks at string content.** Every other rule is structural, and structurally
# this case is flawless: `{"lit": <any string>}` is legal by definition, and `{"lit": "bcrypt($arg.password)"}`
# looks exactly like `{"lit": "pending"}`. So it sails into the spec, and runtime writes that sentence verbatim
# into the database. Measured harm: opengist's `uuid = "(generated uuid)"` collides with `unique_on: ["uuid"]`,
# **the create tool works only once**, and 6 other tools that locate by uuid can never reach new rows.
#
# Being a heuristic, three things must go together: (1) skip whatever can be ruled out structurally (the value is a declared enum member of that column);
# (2) give the model a **structured** way to object (`verbatim`); its count is this rule's false-positive rate;
# (3) give different ways out per cause; don't just say "this is a description".
_PR_ANGLE = re.compile(r"^<[^>]{1,80}>$")
_PR_PAREN = re.compile(r"\S\s*\([^)]{0,80}\)|^\([^)]{1,80}\)$")
_PR_VERB = re.compile(r"::|derived|copied|inherit(ed)?|generated|parsed|"
                      r"serializ|implementation|auto[- ]?(from|set|assigned)|"
                      r"from (the )?(file|upload|body|context|request|scan|tags)", re.I)
# Normal literals: a single word/enum, number, ISO time, URL, path — never flagged
_PR_SAFE = re.compile(r"^[A-Za-z_][\w.\-]*$|^-?\d+(\.\d+)?$|^\d{4}-\d\d-\d\d|^https?://|^/[\w/.\-]*$")

_PR_CAUSE = [
    ("time", r"now\(\)|current_?timestamp|utcnow|curdate|sysutcdatetime|today",
     u"this is the current time — write `{\"sym\": \"$now\"}`"),
    ("agg", r"sum\s*\(|count\s*\(|avg\s*\(|min\s*\(|max\s*\(",
     u"this is an aggregate. The runtime has no aggregate in a value position. If the "
     u"aggregate is being recomputed **because this operation wrote one row**, say the "
     u"change instead: `{\"expr\": {\"col\": \"<this column>\", \"op\": \"+\", "
     u"\"by\": {\"lit\": 1}}}`. If it is a genuine cross-row total the caller never "
     u"supplies **and the read side computes it from the rows**, the column is "
     u"derived rather than written — only then does it leave `sets`. If the row really "
     u"does carry the total, it is written, and it stays"),
    ("arith", r"[+\-*/]\s*\d|head\s*\+|\+ *1",
     u"this is arithmetic on a column of this row — write "
     u"`{\"expr\": {\"col\": …, \"op\": …, \"by\": …}}`"),
    ("xtable", r"from \w+|of (the )?(parent|related|prior|shared|boosted|created|resolved)|"
               r"inherited|copied|derived from|lookup",
     u"this says the value is read off another row — write "
     u"`{\"from\": {\"entity\": …, \"where\": [{\"col\": …, \"op\": \"eq\", "
     u"\"value\": {\"ref\": \"$arg.<param>\"}}], \"get\": \"<column>\"}}`"),
    ("actor", r"\$actor|session|current_?user|logged[- ]in|req\.uid|userFromSession",
     u"this comes from the request context — write `{\"ref\": \"$actor.<col>\"}` or "
     u"`{\"ref\": \"$session.<key>\"}`"),
    ("arg", r"\$arg|from (the )?(param|argument|input)",
     u"this comes from a parameter — write `{\"ref\": \"$arg.<param>\"}`"),
    ("opaque", r"random|uuid|guid|token|secret|salt|bcrypt|argon|sha\d|md5|nanoid|crypt|"
               r"hash|jti|api[_ ]?key|currval|nextval|sequence",
     u"this value is produced at run time (a random string, a hash, a sequence). **The "
     u"Value vocabulary genuinely has no form for it** — this is the one case where way "
     u"(2) is the right answer"),
    ("extern", r"fetch|http|scrape|download|upload|thumbnail|render|user[- ]agent|ua-parser|geoip",
     u"this value comes from outside the application (an upload, a fetch, the request "
     u"envelope). The vocabulary cannot say it either — way (2)"),
    ("placeholder", r"^<[^>]*>$|impl|internal|computed|assigned|tbd|unknown",
     u"**this is a placeholder, not a value** — it says that something sets the column "
     u"without saying what. Go back to the code and find the value; if it turns out to be "
     u"generated at run time, way (2)"),
]

_PR_TAIL = (u" —— `sets` holds what the column actually contains, byte for byte, and the "
            u"runtime writes this string verbatim; it is not a place to describe how the "
            u"value is computed. Three ways out, pick the true one. **(1)** Say it in one of "
            u"the Value forms: `{\"lit\": …}` a fixed value · `{\"sym\": \"$now\"}` · "
            u"`{\"ref\": \"$arg.x\" | \"$actor.col\" | \"$session.key\"}` · "
            u"`{\"col\": …}` another column of this row · "
            u"`{\"from\": {\"entity\", \"where\", \"get\"}}` a value read off another "
            u"row · `{\"expr\": {\"col\", \"op\", \"by\"}}` arithmetic on this row. "
            u"**(2)** If none of them can say it because the value is generated at run time, "
            u"name the column in this effect's `note` and say what generates it — that does "
            u"**not** clear this violation, it records a gap in the vocabulary so it can be "
            u"counted. **Deleting the entry is not a fourth way out.** A column listed in "
            u"`sets` says *this operation writes it*; removing it says *this operation never "
            u"writes it* — the opposite claim, not a weaker one. Make it only when you "
            u"have read the code and that is true. Two signals that it almost certainly is "
            u"not: the column is `nullable: false` on the schema, or another operation reads "
            u"it. If the implementation does write the column and you simply cannot say the "
            u"value, that is way (2) — the exact opposite of deleting. **(3)** If this "
            u"string really "
            u"is what the column stores, say so "
            u"structurally: `{\"lit\": <the string>, \"verbatim\": true}` — that clears it, "
            u"and it is how you tell us this rule misjudged you.")


def _prose_bad(v, coldef=None):
    u"""The value slot holds a description instead of a value → a reason; otherwise → None."""
    if isinstance(v, dict) and v.get("verbatim") is True:
        return None                       # the model has declared "this is a literal"
    s = v if isinstance(v, str) else (v.get("lit") if isinstance(v, dict) else None)
    if not isinstance(s, str) or len(s) < 4 or _PR_SAFE.match(s):
        return None
    if not (_PR_ANGLE.match(s) or _PR_PAREN.search(s) or _PR_VERB.search(s)):
        return None
    _enum = [str(x) for x in _L(_D(coldef).get("enum"))]
    if _enum and s in _enum:
        return None                       # ruled out structurally: it is one of the column's declared values
    if _enum:
        _m = re.match(r"^\s*([A-Za-z_][\w \-]{0,40}?)\s*\(\s*([^()]{1,30}?)\s*\)\s*$", s)
        if _m:
            for _cand in (_m.group(1).strip(), _m.group(2).strip()):
                if _cand in _enum:
                    return (u"you wrote the name and the code together, but this column "
                            u"declares enum=%s — it stores exactly one of them. Write "
                            u"`{\"lit\": %r}`" % (_enum[:6], _cand)) + _PR_TAIL
    for _name, _pat, _way in _PR_CAUSE:
        if re.search(_pat, s, re.I):
            return _way + _PR_TAIL
    return (u"this reads as a description of the value rather than the value") + _PR_TAIL




# A legal symbolic reference has only this one shape. **Note the key name `ref` has two unrelated uses in the contract** —
# here it is the `{"ref": "$arg.x"}` inside a Value; `edges[].object` is also called `ref` and holds
# `{"ref":"Transaction.create","kind":"op"}`, the object of the SVO, unrelated to this rule.
# (It nearly got checked along with this one, which would have produced 19475 bogus reports.)
_REF_OK = re.compile(r"^\$(arg|actor|session|subject)(\.[A-Za-z_][A-Za-z0-9_]*)?$")


# ── violation priority tiers ────────────────────────────────────────────────────
# **Tiers are set in code; work orders are rendered grouped by tier.** Work orders used to be one flat list (sorted by count), with priority written only in
# the reactivate prompt as prose — leaving the model to map 70-odd rule names onto seven tiers itself.
# This round added a dozen-plus rules to the feedback layer; the prose did not keep up, and none of the new rules got a tier.
#
# Order is priority; the first matching substring decides the tier. **Matching none = hard error** (see
# test_topup_tiers.py): a new rule added without a tier would otherwise quietly sink to the bottom.
TIERS = [
    (1, "the file itself is unreadable", [
        "the file is not valid JSON",
        "the top level is not a CollectOutput object",
        "the checker threw", "schemas is not an array", "impls is not an array",
        "edges is not an array", "contains a non-object item"]),
    (2, "unfixed = this repo yields zero tools", [
        "every entry is internal",
        "not a single entry is internal",
        "has no entry", "entry.kind", "entry is not internal",
        "impl.locator sits in an internal"]),
    (3, "the only source code anyone downstream sees", ["ref_code"]),
    (4, "self-contradictory (visible without reading code)", [
        "names a column the entity does not have", "effect.entity is not a declared",
        "fields and sets overlap", "enum disagrees", "caller writes an audit column",
        "comparing against null with eq/ne",
        "fk_to points at an entity that is not declared",
        "fk_to points at a column that entity does not have",
        "a `sets` entry sets a column to itself",
        "row_key holds a scope clause", "$actor.<col>", "ref uses an unknown namespace",
        "ref does not start with $", "ref crosses two hops", "ref has prose",
        "JSON sub-path", "lifecycle.col points at",
        "credential columns are not on", "impls[].entity is still", "on_miss moved",
        "still using v2", "search_spec was not folded", "edge.subject is not"]),
    (5, "no position taken (unknown / null / [] all count; omitting does not)", [
        "this operation has edges but none of them says what guards it",
        "constraints omitted", "param omits binds", "param has no required",
        "row_search has no why", "row_search.method missing", "scope.kind is missing",
        "output_schema missing", "params missing", "row_key missing", "effects missing",
        "row_key is empty but nothing says why",
        "auth effect mode missing", "auth effect has no credential", "has no owner_col"]),
    (6, "shape and closed vocabularies (mechanical, but downstream has to guess)", [
        "an invented operator",
        "a guards/requires edge has the test only as prose",
        "`sym` is a closed vocabulary",
        "expr.by is $now",
        "a constraint is not an object",
        "a constraint uses an operator outside",
        "from-subquery is malformed", "cannot be normalised", "no alias for",
        "effect.kind outside", "op outside the seven", "State scope.op outside",
        "State scope.value is outside", "card is invalid", "sets is not an object",
        "a sets value is outside", "a sets value describes the value instead of being it",
        "a provides `card` narrates what happened",
        "a row_key value is outside", "provides is not State-shaped",
        "needs is not one level", "has no entity prefix", "lifecycle is not a state machine",
        "the lifecycle column has no enum", "has no id_local", "effect has no entity",
        "effects is not an array", "params is not an array", "fields is not an array",
        "schema.columns is not an array", "an effect is not an object",
        "a params item is not an object",
        "written under a key the contract does not read"]),
    (7, "needs the code re-read (slowest per fix, hence last — not least important)", [
        "a triggers edge points at an operation",
        "a guards/requires edge says a wall exists but never says what it is",
        "has no required parameter bound", "wrapped inside an object parameter",
        "has no parameter that can supply", "empty effects", "has no pk",
        "has no row_read", "fields and sets both missing", "no_edges jumped", "shrank"]),
]
TIER_TITLE = {t: title for t, title, _ in TIERS}


def rule_tier(rule):
    """Rule name → tier. Returns None on no match (a hard error, not a silent fallback)."""
    for t, _title, keys in TIERS:
        for k in keys:
            if k in rule:
                return t
    return None


def _cn(x):
    """Column-name normalisation: only for deciding "is this the same name"; changes no output."""
    return re.sub(r"[^a-z0-9]", "", str(x).lower())


AGGS = {"count", "count_distinct", "sum", "avg", "min", "max"}


FROM_KEYS = {"entity", "where", "get"}


def _from_bad(v, state=False):
    """Is a `{"from": {...}}` subquery legal? → a reason, or None.

    `state=True` means **a State slot on an edge** (guards / needs / scope / constraints), which is read by the
    State evaluator, not fetched at execution time — that layer's `_select_rows` really computes aggregates and really supports
    where=None (whole table) and the full operator set. Applying the three execution-time bans verbatim there makes **the emitter narrower
    than the receiver**: the model writes an aggregate guard runtime runs perfectly well, and it gets flagged "malformed".
    Measured: these three bans have not a single real instance on edges (all 12 from-violations in the corpus are in sets), so
    this is not loosening the check; it fills a pit nobody has stepped in yet — the unit test test_agg_subquery had
    already written this down, and it stayed red for more than one round.

    **This table must match exactly what build_prep.from_ref accepts.** It used to check only entity and get,
    so any where passed — and the prep layer **drops the whole thing** when it cannot translate, with two kinds of consequence:
    `sets` loses a column (a still-visible gap), `clause` loses a clause (**the wall gets lower and the probe stays green**).
    The model cannot see prep's ledger, so whatever can be ruled out here must be ruled out on the spot.

    Measured across 710 `from` occurrences in the corpus: aggregates 35 (sum 19 / count 10 / max 4 / avg 2,
    all in sets), non-equality where 6, no where 1, out-of-protocol keys (join/on) a few.
    """
    if not (isinstance(v, dict) and "from" in v):
        return None
    sq = v["from"]
    if not isinstance(sq, dict) or not isinstance(sq.get("entity"), str) or not sq["entity"]:
        return "from has no entity (say which table it reads)"
    _extra = sorted(set(sq) - FROM_KEYS)
    if _extra:
        return ("from has keys the protocol does not define: %s — only entity / where / get "
                "exist. A join is not one of them: say the join as a `where` clause on the "
                "column that holds the reference" % (_extra,))
    g = sq.get("get")
    if isinstance(g, dict) and "agg" in g:
        if g["agg"] not in AGGS:
            return "get.agg must be one of %s, got %r" % ("/".join(sorted(AGGS)), g["agg"])
        if state:
            # State slot: aggregates are legal (`_select_rows` goes through `_agg1`). Only check self-consistency —
            # count needs no column; the other four have nothing to compute without one.
            if g["agg"] != "count" and not (isinstance(g.get("col"), str) and g["col"]):
                return "get.agg=%r needs a col to aggregate over" % (g["agg"],)
            return None
        return ("get.agg=%r — **the runtime has no aggregate in a value position**: it can "
                "take one column of the first matching row, or that column over all matching "
                "rows, but it never sums or counts them. Two honest rewrites, pick by what "
                "the code does: (a) if this is a counter being recomputed *because this very "
                "operation wrote one row*, say the change, not the total — "
                "`{\"expr\": {\"col\": \"<this column>\", \"op\": \"+\", "
                "\"by\": {\"lit\": 1}}}`; a recomputed aggregate after a single-row write "
                "**is** an increment, and it seeds and verifies. (b) if it is a genuine "
                "cross-row total the caller never supplies, this column is **derived, not "
                "written** — it leaves `sets` only because the read side computes it from "
                                  "the rows, not because its value is hard to say"
                % (g["agg"],))
    if g is not None and not isinstance(g, (str, dict)):
        return "get has an unrecognised shape: %r" % (g,)
    if isinstance(g, dict) and not g.get("col"):
        return "get takes either col (that column) or agg (an aggregate)"
    if g is None:
        return "get is missing (say which column of the matching row this value is)"
    _w = sq.get("where")
    if isinstance(_w, dict):
        _w = [_w]
    if state and not _w:
        return None            # whole-table aggregates are normal in a State slot ("my balance >= the sum of all orders")
    if not isinstance(_w, list) or not _w:
        return ("from has no where — a subquery with no condition matches the whole table and "
                "silently takes its first row. Say which rows it means: "
                "`\"where\": [{\"col\": \"<the column holding the reference>\", "
                "\"op\": \"eq\", \"value\": {\"ref\": \"$arg.<param>\"}}]`")
    for _cl in _w:
        if not isinstance(_cl, dict):
            return "where contains a clause that is not an object: %r" % (_cl,)
        _c = _cl.get("col")
        if isinstance(_c, dict):
            _c = _c.get("col")
        if not isinstance(_c, str) or not _c:
            return "a where clause has no col"
        _o = _cl.get("op")
        if _o is not None and not state and _k(_o) not in ("eq", "=", "=="):
            return ("where uses op=%r — **a subquery's own where is equality-only**: it is "
                    "resolved by a plain lookup, not by the State evaluator. Keep the join key "
                    "here (`op: \"eq\"`) and put the comparison in the **outer** clause, "
                    "which does have the full operator table" % (_o,))
        _v2 = _cl.get("value", _cl.get("right"))
        if isinstance(_v2, dict) and "from" in _v2:
            return "a from inside a from — one level only, as the contract says"
        if isinstance(_v2, dict) and len(_v2) == 1 and "col" in _v2:
            return ("a where clause compares against {\"col\": %r} — inside a subquery there "
                    "is no \"same row\" to take that column from. Use a literal or a "
                    "`$arg` / `$actor` / `$session` reference" % (_v2["col"],))
    return None


def _ref_bad(v, cols=None, ncols=None, state=False):
    """Is the shape of a `ref` in a Value right? → (category, reason) or None.

    If `cols` / `ncols` are given, also checks whether the column name in `$actor.<col>` exists in this repo
    (raw-name set / normalised set). **Do not pass them for a repo with no columns mined** — that would flag the whole repo.

    These four categories **can be ruled out from collect alone**, and downstream **silently discards** them — when normalisation cannot resolve one,
    it throws the whole thing away, with no error and no trace. Measured: 4248 of 23604 refs in Value slots (18%) fall here.
    """
    if isinstance(v, dict) and "from" in v:
        _fb = _from_bad(v, state=state)
        return ("the from-subquery is malformed", _fb) if _fb else None
    # A Value has exactly one key. `edges[].object` is {"ref": ..., "kind": "op|entity"} — two keys,
    # so it never gets here. **The comment above used to be only a comment; the check itself was missing**, and the tests caught it right away.
    if not (isinstance(v, dict) and len(v) == 1 and isinstance(v.get("ref"), str)):
        return None
    r = v["ref"]
    if _REF_OK.match(r):
        return None
    if not r.startswith("$"):
        return ("ref does not start with $ (a bare column or parameter name)",
                "%r — a left operand alone is not a condition; add the $arg. / $actor. prefix or drop the clause" % r)
    head = r.split(".")[0]
    if head in ("$arg", "$actor", "$session", "$subject") and r.count(".") >= 2:
        return ("ref crosses two hops (a field of an object parameter)",
                "%r — arguments are looked up by FLAT name, so a nested field never "
                "resolves; flatten that object parameter into scalar ones" % r)
    for ch in " <>[]{}()?":
        if ch in r:
            return ("ref has prose, a subscript or a question mark glued on",
                    "%r — this must be a symbol, not a sentence" % r)
    return ("ref uses an unknown namespace",
            "%r — only $arg / $actor / $session / $subject exist. One pointing at what "
            "the call RETURNS ($output / $result) does not exist yet when the condition is "
            "evaluated; if you cannot express it, drop the whole entry" % r)


_CODEISH = re.compile(r"[(){};=\[\]<>]|\n|->|=>|::")
_LOCATORISH = re.compile(r"^[\w./@\\-]+\.\w{1,5}(:\d+(-\d+)?)?$")
_ELIDED = re.compile(r"\{\s*(\.\.\.|\u2026)\s*\}|\(\s*\.\.\.\s*\)")


def _refcode_bad(rc):
    """Does `ref_code` really contain code? → (category, reason) or None.

    **It is the only source code downstream ever sees** — the spec-building layer relies on it to write tool descriptions, parameter descriptions and the
    error message of every wall, and that layer cannot open the repo. Measured: only 26% of 24409 give real code; failures come in five kinds,
    and only the four **unambiguous** ones are reported here (the under-40-characters bucket is deliberately not: real code can be a one-liner,
    and an over-broad rule would make the miner change a batch of things that were not broken):

      - missing or empty                       4597
      - written as a file location             2467  — that is `locator`; saying it twice is saying it once
      - not a single code character            6625  — `ModelViewSet.destroy` / `DRF default destroy`
      - signature only, body elided as {...}   1057  — and the body is the only part that carries information
    """
    if not isinstance(rc, str) or not rc.strip():
        return ("ref_code missing or empty",
                "downstream sees no source at all; the tool description and every error string become guesswork")
    r = rc.strip()
    if _LOCATORISH.match(r):
        return ("ref_code holds a file position (that is locator's job)",
                "%r — the position is already in locator; what belongs here is those lines of code themselves" % r[:60])
    if not _CODEISH.search(r):
        return ("ref_code is not source (a framework name or prose)",
                "%r — a framework's name is not this app's behaviour; paste the lines that actually decide it" % r[:60])
    if _ELIDED.search(r) and len(r) < 80:
        return ("ref_code is a signature with the body elided",
                "%r — what was elided is the only part that carried information (pre-checks, writes, the status assignment)" % r[:60])
    return None


def _actor_col_bad(v, cols, ncols):
    """Does the column name in `$actor.<col>` exist in this repo? → (category, reason) or None.

    `$actor.<col>` is "some column on the row of the currently logged-in user", copied from the account row into the session at login
    (`auth.session_fields`). So it **must be a real data column**. Two kinds of mistake were measured;
    **the fixes differ, so they are reported separately**:

      - the name exists nowhere in the repo (34 cases): `$actor.session_id` / `$actor.updated_map` /
        `$actor.org` — treating an HTTP session, in-memory object or framework field as a data column. This is not a
        "which table" problem; it simply is not data.
      - the spelling does not match the real column name (5 cases): writing `$actor.tenantId` when the column is `tenant_id`.
        Downstream takes the session key **verbatim**, so it fails to resolve all the same; use the column's real name.

    Two-hop refs (`$actor.a.b`) are not judged here — `_ref_bad` already reports them separately; reporting again would only
    make the same thing show up twice in the work order.
    """
    if not cols:
        # **The guard lives in the function, not at the call site.** Asking "does this column exist" with an empty set for a repo with no columns mined
        # would flag the whole repo (measured: 57 of 433 repos are like this). At the call site, a bare call to this function from elsewhere
        # would have no protection — the mutation test caught exactly this.
        return None
    if not (isinstance(v, dict) and len(v) == 1 and isinstance(v.get("ref"), str)):
        return None
    r = v["ref"]
    if not r.startswith("$actor.") or r.count(".") != 1:
        return None
    col = r.split(".", 1)[1]
    if col == "id" or col in cols:
        return None
    if _cn(col) in ncols:
        return ("$actor.<col> is spelled differently from the real column",
                "%r — the session key is looked up verbatim, so a different spelling never resolves; use the column's real name" % r)
    return ("$actor.<col> names a column no table in this repo has",
            "%r — `$actor.<col>` means a column ON the logged-in user's row, so it must "
            "be a real data column. An HTTP session, an in-memory object, a framework field "
            "are not. If you cannot express it, drop the whole entry" % r)


# Closed vocabulary of entry.kind. **Only the first three produce tools** — cli / job are real entry points but users cannot call them;
# internal is internal implementation. Three tiers, not two: a cron job and a private helper are different things.
ENTRY_KINDS = ("http", "rpc", "graphql", "cli", "job", "internal")
ENTRY_EXPOSED = ("http", "rpc", "graphql")
# Path patterns that plainly say "internal implementation". **Only for challenging a claim, never for deciding** — measured over the whole corpus it covers only 27.4%,
# and worse on op=guard (80.8% indistinguishable). The decision belongs to whoever wrote it; det only demands evidence.
_INTERNALISH = re.compile(
    r"(?i)(^|/)(internal|private)/|/lib/private/|Middleware|/Acl\.|AccessControl|"
    r"Authorization/|Polic(y|ies)/|Manager\.(php|mjs|js|ts|py|go|java|rb)")


def check_repo(d):
    _n_entry = collections.Counter()
    """→ (violations{rule: [evidence...]}, stats). Every piece of evidence points at a specific id_local / entity."""
    V = collections.defaultdict(list)
    if not isinstance(d.get("schemas"), (list, type(None))):
        V["schemas is not an array"].append(type(d.get("schemas")).__name__)
    if not isinstance(d.get("impls"), (list, type(None))):
        V["impls is not an array"].append(type(d.get("impls")).__name__)
    if not isinstance(d.get("edges"), (list, type(None))):
        V["edges is not an array"].append(type(d.get("edges")).__name__)
    ents = {_k(_D(e).get("entity") or _D(e).get("name")) for e in _L(d.get("schemas"))}
    ents.discard(None)
    # entity → {column name: column definition}. The phantom-column / audit-column-conflict / auth-credential-column rules all need it.
    colmap = {}
    for _e in _L(d.get("schemas")):
        if isinstance(_e, dict):
            colmap[_k(_e.get("entity") or _e.get("name"))] = {
                _k(c.get("name")): c for c in _L(_e.get("columns"))
                if isinstance(c, dict) and c.get("name")}

    # All column names in the repo (raw / normalised). **An empty set means this repo has no columns mined** — such a repo cannot be used
    # to judge "this column does not exist", or the whole repo gets flagged (measured: 57 of 433 repos are like this).
    _allcols = {cn for m in colmap.values() for cn in m}
    _allncols = {_cn(cn) for cn in _allcols}

    # Which entities are modified **by row**. A pk is for "locating a row to change it", so a missing pk only matters when
    # row_update / row_delete / row_soft_delete / row_upsert appear.
    # Tables that are only inserted / read (logs, ledgers) often have no primary key in real databases —
    # measured: 7 of 37 entities "with no pk" were this kind: koha/Statistic,
    # phpbb/LoginAttempt, sympa/Log, sympa/StatCounter, pymedusa/Failed,
    # bytebase/TaskRunLog, all {'row_insert': n} or {'row_read','row_insert'}.
    # The counterexample is just as firm: bugzilla/LoginFailure is {'row_insert':1,'row_delete':1};
    # it has a delete, so it must say what it deletes by — judging by whether the table name looks like a log is guesswork;
    # the criterion can only be **whether this table is modified by row**.
    _ROW_MOD_KINDS = ("row_update", "row_delete", "row_soft_delete", "row_upsert")
    # Record **who** modifies it by row: reporting only "no pk" gets pushed back with "this is an append-only log table, it
    # has no primary key by design", and the evidence refuting that is in the same output.
    _row_mod = {}
    for _i in _L(d.get("impls")):
        if not isinstance(_i, dict):
            continue
        for _e in _L(_i.get("effects")):
            if isinstance(_e, dict) and _k(_e.get("kind")) in _ROW_MOD_KINDS and _e.get("entity"):
                _row_mod.setdefault(_k(_e.get("entity")), []).append(
                    "%s/%s" % (_i.get("id_local"), _k(_e.get("kind"))))

    # ── schema layer ──
    for e in _L(d.get("schemas")):
        if not isinstance(e, dict):
            V["schemas contains a non-object item"].append(type(e).__name__); continue
        en = e.get("entity") or e.get("name")
        if not isinstance(e.get("columns"), (list, type(None))):
            V["schema.columns is not an array"].append("%s(%s)" % (en, type(e.get("columns")).__name__))
        cols = _L(e.get("columns"))
        if _k(en) in _row_mod and not any(c.get("pk") for c in cols if isinstance(c, dict)):
            # Measured: gaseous-server/UserTimeTracking and frigate/Timeline each
            # wrote a note saying "append-only, no primary key by design" and refused to change it — while their
            # own effects contain 3 row_update / 3 row_delete respectively. The rule was not wrong;
            # the evidence did not say why it fired, so the model pushed back with a reason this rule had already excluded.
            _wit = _row_mod[_k(en)]
            V["the entity has no pk"].append(
                "%s —— row-modified by %s%s. An append-only note does not apply here: to "
                "update or delete *this row*, something has to locate it. Either mark the "
                "locating column(s) `pk: true`, or those effects are wrong — a whole-table "
                "or scope-filtered write is not a row_update/row_delete"
                % (en, ", ".join(_wit[:3]),
                   " (+%d more)" % (len(_wit) - 3) if len(_wit) > 3 else ""))
        if "constraints" not in e:
            V["constraints omitted (write [] to mean 'checked, there are none')"].append(en)
        # The **content** of entity constraints was never checked anywhere before — only whether the key exists. So a broken constraint
        # travelled all the way into runtime before failing, and failed **silently** (cannot judge → UNKNOWN → counted as "satisfied" under
        # SQL CHECK semantics). The conditional in the flagship example was broken exactly this way, and nobody reported it.
        for _con in _L(e.get("constraints")):
            if not isinstance(_con, dict):
                V["a constraint is not an object"].append("%s: %r" % (en, _con))
                continue
            _kind = _k(_con.get("kind"))
            if _kind == "check":
                _cls = [{"col": (_D(_con.get("left"))).get("col"), "op": _con.get("op"),
                         "value": _con.get("right")}] if _con.get("op") else []
            elif _kind == "conditional":
                _cls = _L(_con.get("if")) + _L(_con.get("then"))
            else:
                _cls = []
            for _cl in _cls:
                if not isinstance(_cl, dict):
                    continue
                _op = _k(_cl.get("op"))
                if _op and _op not in OPS:
                    _f = _OP_FIX.get(_op)
                    V["a constraint uses an operator outside the closed vocabulary"].append(
                        "%s/%s: op=%r%s" % (en, _kind, _cl.get("op"),
                                            (" — write it as %s" % _f) if _f else ""))
                _nb2 = _null_cmp_bad(_cl.get("op"), _cl.get("value"))
                if _nb2:
                    V["comparing against null with eq/ne — the clause can never be true"].append(
                        "%s/%s: %s %r {\"lit\": null} — write op=%r instead (unary, no value)"
                        % (en, _kind, _cl.get("col"), _cl.get("op"), _nb2))
        for c in cols:
            if not isinstance(c, dict):
                continue
            cn = c.get("name")
            # (1) Closed type vocabulary. Anything that cannot be normalised **silently falls back to text** downstream, so the probe fills
            #    a datetime column with a string and a whole batch of tools gets falsely reported as error.
            # **Only report what det cannot normalise either.** Dialects (varchar/integer) and framework field types
            # (Frappe's Data/Link/Check, Django's CharField) are in det's alias table, absorbed losslessly
            # and recorded as mend — reporting them makes the miner change things where the change makes no difference. Measured: of 5772,
            # det absorbs 5567; only 205 are really lost.
            if _k(c.get("type")) not in TYPES and _PREP.norm_type(c.get("type")) is None:
                V["columns[].type cannot be normalised (downstream falls back to text)"].append(
                    "%s.%s=%r" % (en, cn, c.get("type")))
            # (2) Closed key-name vocabulary.
            # Likewise: hits in det's alias table (`fk`→`fk_to`, `length`→`max`, `null`→`nullable`)
            # are lossless and not reported; only keys **det does not recognise either** are — that key's information really is lost.
            for _kk in c:
                if _kk not in COL_KEYS and _kk not in _PREP._COL_ALIAS:
                    V["a column key downstream has no alias for (that key's information is simply lost)"].append(
                        "%s.%s: %r" % (en, cn, _kk))
            # (5) **The "name looks like an audit column but no position taken" rule has been deleted.** Measured: of 1041 hits,
            #    **980 were harmless**: det adds `audit: True` by name and records mend, and
            #    no effect says it writes them — "not writable" costs nothing for a column nobody writes.
            #    Only 61 were genuinely ambiguous (name looks like an audit column, and a write effect says the caller writes it),
            #    and those 61 are **already reported separately by the sibling rule below**.
            #    Keeping it would make the miner confirm 980 `created_at`s — and re-mining is not cheap;
            #    work orders flooded with this noise bury the real problems.
            fk = c.get("fk_to")
            if fk and "." not in str(fk):
                V["fk_to has no entity prefix"].append("%s.%s=%r" % (en, c.get("name"), fk))
            elif fk and colmap:
                # Dangling FK: points at a table that **was not declared**, or a table that **has no such column**.
                # The output contradicts itself; no code reading needed to judge. The gate always blocked it as a hard error,
                # but it never appeared in work orders — so the miner never heard of it and handed in the same dangling FK next round.
                # ⚠ Not judged when colmap is empty (no columns mined in the whole repo), or such repos would be flagged wholesale.
                _te, _, _tc = str(fk).partition(".")
                if _k(_te) not in colmap:
                    V["fk_to points at an entity that is not declared"].append(
                        "%s.%s -> %s (declared: %s)"
                        % (en, c.get("name"), fk, ", ".join(sorted(colmap)[:6])))
                elif _k(_tc) not in colmap[_k(_te)]:
                    V["fk_to points at a column that entity does not have"].append(
                        "%s.%s -> %s" % (en, c.get("name"), fk))

        # ── enum ↔ lifecycle consistency (A/B/D/E, mutually exclusive categories) ──
        lf = e.get("lifecycle")
        col = _D(lf).get("col")
        if col:
            st = _D(lf).get("states")
            st = st if isinstance(st, list) else []
            by = {c.get("name"): c for c in cols if isinstance(c, dict)}
            t = by.get(col)
            tt = str(_D(t).get("type") or "").lower()
            if t is None:
                # D: lifecycle points at a column that does not exist (a dotted path, or never collected)
                V["lifecycle.col points at a column that does not exist"].append(
                    "%s.%s (states=%s) — either add this column to columns, or this "
                    "lifecycle should not exist at all" % (en, col, str(st)[:60]))
            elif (any(isinstance(x, str) and "<" in x and ">" in x for x in st)
                  or (tt in TIMEY and len(st) == 2
                      and any(str(x).lower() in NULLY for x in st))):
                # B: not a state machine at all; it is "this timestamp is nullable"
                V["lifecycle is not a state machine (a placeholder or a nullable timestamp)"].append(
                    "%s.%s states=%s — this describes nullability, not a state; delete this entity's "
                    "lifecycle" % (en, col, str(st)[:60]))
            elif not _D(t).get("enum"):
                # A: filling in lifecycle admits the column is a closed set, so enum cannot be omitted
                V["the lifecycle column has no enum"].append(
                    "%s.%s states=%s — put those values in the column's enum; the two "
                    "must agree" % (en, col, str(st)[:60]))
            elif st and {str(x) for x in st} != {str(x) for x in _L(_D(t).get("enum"))}:
                # E: two mutually contradictory value sets, the most dangerous — usually display name vs stored code
                V["enum disagrees with lifecycle.states"].append(
                    "%s.%s enum=%s vs states=%s — both must hold the values **actually "
                    "stored in that column** (guards, filters and seeding all compare stored "
                    "values). A display label has nowhere to live in this contract; do not "
                    "put one in either" % (en, col, str(_D(t).get("enum"))[:46], str(st)[:46]))

    # ── impl layer ──
    for i in _L(d.get("impls")):
        if not isinstance(i, dict):
            V["impls contains a non-object item"].append(type(i).__name__); continue
        idl = _n(i.get("id_local")) or "?"
        _ps = [p for p in _L(i.get("params")) if isinstance(p, dict)]
        _pnames = {_k(p.get("name")) for p in _ps}
        # binds holds "Entity.col"; supply checks look at the column-name half
        _pbound = {_k(str(p.get("binds")).split(".")[-1]) for p in _ps if _n(p.get("binds"))}
        _pblob = [p.get("name") for p in _ps
                  if _k(p.get("type")) in ("object", "json") and p.get("binds") is None]
        op = _k(i.get("op")) or ""
        if "/" in str(op) or (op and op not in (MUT | READY | {"guard"})):
            V["op outside the seven-value vocabulary"].append("%s: %r" % (idl, op))
        if not _n(i.get("id_local")):
            V["impl has no id_local (nothing downstream can refer to it)"].append(str(i.get("operation") or i.get("op")))
        if "entity" in i:
            V["impls[].entity is still present (v3 removed that field)"].append(idl)
        if "required_columns" in i:
            V["still using v2's required_columns"].append(idl)
        if "search_spec" in i:
            V["search_spec was not folded into the row_search effect"].append(idl)

        # params / output_schema
        if "params" not in i:
            V["params missing (the interface face is unknowable)"].append(idl)
        elif not isinstance(i.get("params"), list):
            V["params is not an array"].append("%s(%s)" % (idl, type(i.get("params")).__name__))
        else:
            for pm in _L(i.get("params")):
                if not isinstance(pm, dict):
                    V["a params item is not an object"].append(idl); continue
                if "binds" not in pm:
                    V["param omits binds (write binds:null — it is an answer)"].append("%s(%s)" % (idl, pm.get("name")))
                # The binding is written under a key the contract does not read. **Not reporting it is a dead end**: the model sets `binds` to null
                # (so "param omits binds" stays silent) and puts the real value in an invented `bind`/`column`/...;
                # looking at its output it thinks "I did bind it", while the only feedback it gets is "this column has no parameter supplying it" —
                # the two statements don't line up, and nothing changed for several rounds. Measured: 621 cases, concentrated in
                # openolat (290) / kavita (192) / ever-gauzy (104), together holding up 1731 violations.
                # And build_prep also reads only `binds`, so these bindings are dropped entirely at build time
                # (the probe relies on them to fetch seeds for FK columns — a comment says 11.8% of parameters are FK columns).
                # The criterion is **the shape of the value** (Entity.col), not a synonym guess on the key name: halo's
                # `from: "body"` says the parameter comes from the HTTP body; guessing by key name would misfire on it.
                if not _n(pm.get("binds")):
                    for _bk, _bv in pm.items():
                        if _bk in ("name", "type", "required", "binds", "description",
                                   "default", "example", "enum", "nullable", "note"):
                            continue
                        if isinstance(_bv, str) and re.match(r"^[A-Za-z_]\w*\.\w+$", _bv):
                            V["the binding is written under a key the contract does not read"].append(
                                "%s(%s): %s=%r — the contract reads `binds` and nothing else; "
                                "move the value there (`binds:null` is only for a parameter that "
                                "truly lands on no column)" % (idl, pm.get("name"), _bk, _bv))
                            break
                b = pm.get("binds")
                if b and "." not in str(b):
                    V["binds has no entity prefix"].append("%s(%s)=%r" % (idl, pm.get("name"), b))
                if "required" not in pm:
                    V["param has no required"].append("%s(%s)" % (idl, pm.get("name")))
        if "output_schema" not in i:
            V["output_schema missing"].append(idl)
        # Parameter types share the same seven-value closed vocabulary as columns. Anything that cannot be normalised **silently falls back to text** downstream, so the probe
        # fills an int/datetime parameter with a string — a whole batch of tools falsely reported as error. Same as columns:
        # only report what det cannot absorb either (it has alias tables for dialects and framework types).
        for _p in _ps:
            _pt = _p.get("type")
            if _pt is not None and _k(_pt) not in TYPES and _PREP.norm_type(_pt) is None:
                V["params[].type cannot be normalised (downstream falls back to text)"].append(
                    "%s/%s=%r" % (idl, _p.get("name"), _pt))
        _rcb = _refcode_bad(i.get("ref_code"))
        if _rcb:
            V[_rcb[0]].append("%s: %s" % (idl, _rcb[1]))

        # entry — can a client call this function? **It drives exactly one decision: whether to generate a tool.**
        # The criterion is not "do you think it is public" but "find the line that registers it": if you cannot, it is internal.
        # And entry.locator is usually in **another file** (routes.rb / urls.py / web.php / router.go),
        # so this requirement turns a subjective judgement into a lookup.
        e = i.get("entry")
        if not isinstance(e, dict):
            V["impl has no entry (nobody knows if a client can call it)"].append(idl)
        else:
            ek = _k(e.get("kind"))
            if ek not in ENTRY_KINDS:
                V["entry.kind outside the closed vocabulary"].append("%s: %r" % (idl, e.get("kind")))
            elif ek != "internal":
                if not _n(e.get("route")):
                    V["entry is not internal but gives no route"].append("%s(%s)" % (idl, ek))
                if not _n(e.get("locator")):
                    V["entry is not internal but gives no registration locator"].append("%s(%s)" % (idl, ek))
                # Deleted the "declared external, but impl.locator sits in an
                # internal-implementation directory" tier. It hung off the `locator given`
                # elif — i.e. it **specifically hit those who had already found the registering line**: 1187 hits across the corpus,
                # 100% reported after both route and registering locator were present; not one hit a case of insufficient evidence.
                # Its criterion _INTERNALISH is a path-string match, whose own comment says "only for challenging a claim,
                # never for deciding — covers only 27.4% across the corpus". But in a checker, "challenging" is deciding:
                # violations go into work orders, work orders push the model to change things, and the only way for the model to lower the count is to
                # falsely label a really reachable interface as internal — the gokapi/photoprism agents explicitly refused, and they were right.
                #   Hit breakdown: internal/ or private/ 1032 (87%, of which .go 1023 — Go's
                #   internal/ is a compiler-enforced **package visibility** mechanism about "can other projects import it",
                #   fully orthogonal to "can a client reach it over HTTP"); Manager.<ext> 128 (11%,
                #   suffixes like UserManager.php, the most common class-name suffix in the world); the remaining 27.
                # The insufficient-evidence cases are covered by the two rules above; when evidence is complete, a path guess with 27.4% accuracy
                # should not overturn it — this rule's own original intent was "find the line that registers it".
                _n_entry[ek] += 1
            else:
                _n_entry["internal"] += 1

        # Will this impl become a tool? build_prep has `if _ek in ("internal","cli","job"): drop`
        # — only http/rpc/graphql produce tools. And the row_key checks below all ask
        # "what does the caller use to locate this row", which is meaningless for something **with no caller**.
        # Measured: of 615 ops hit by these checks, 315 (51%) were @Scheduled tasks
        # and event listeners (alf.io's AdminJobProcess.pending, EmailMessage.processQueue,
        # ReservationFinalizer.complete ...), whose route field says `job: @Scheduled(...)`.
        # They should not be required to fit the shape of a "tool"; downstream generates none of them anyway.
        _ge = i.get("entry") if isinstance(i.get("entry"), dict) else {}
        _gen_tool = _k(_ge.get("kind")) in ENTRY_EXPOSED
        # effects
        eff = i.get("effects")
        if eff is None:
            V["effects missing"].append(idl); continue
        if not isinstance(eff, list):
            V["effects is not an array"].append("%s(%s)" % (idl, type(eff).__name__)); continue
        if not eff:
            if op in MUT:
                V["a write operation has empty effects (simply not mined)"].append("%s(%s)" % (idl, op))
            elif op in READY:
                V["a read/search operation has no row_read / row_search effect"].append("%s(%s)" % (idl, op))
        for e in eff:
            if not isinstance(e, dict):
                V["an effect is not an object"].append(idl); continue
            k = _k(e.get("kind"))
            if k not in ALL_KINDS:
                V["effect.kind outside the closed vocabulary"].append("%s: %r" % (idl, k))
            if k != "external" and not e.get("entity"):
                V["effect has no entity (which table it lands on)"].append("%s/%s" % (idl, k))
            if e.get("entity") and ents and _k(e["entity"]) not in ents:
                V["effect.entity is not a declared entity"].append("%s/%s→%s" % (idl, k, e["entity"]))
            _cm = colmap.get(_k(e.get("entity"))) or {}
            _rk = e.get("row_key")
            _rkcols = _L(_rk) if isinstance(_rk, list) else ([_rk] if isinstance(_rk, str)
                                                             else list(_D(_rk)))
            # Object-form row_key: keys are column names, values use the State Value vocabulary. Two independent problems —
            if isinstance(_rk, dict) and _rk:
                # (1) A whole scope clause got stuffed in. **Its own rule**: mixed into "phantom column" it would be
                # reported as "references a non-existent column 'col'", pointing the wrong way — it is not a misspelled column name,
                # the whole shape is wrong (what it means is a column↔parameter mapping, which is the job of binds).
                if set(map(_k, _rk)) <= {"col", "op", "value", "ref", "lit", "sym"}:
                    V["row_key holds a scope clause (its keys must be column names)"].append(
                        "%s/%s: %s" % (idl, k, sorted(map(str, _rk))[:4]))
                    _rkcols = []              # don't report col/ref as phantom column names
                else:
                    for _kk2, _vv2 in _rk.items():
                        _bad = _rkval_bad(_vv2, _pnames)
                        if _bad:
                            V["a row_key value is outside the Value vocabulary"].append(
                                "%s/%s: %s=%s" % (idl, k, _kk2, _bad))
            # (3) Phantom column: references a column this table does not have — **the output contradicts itself**; no code reading
            # needed. But first set aside three **legal** forms, otherwise 14% are false positives:
            #   - `*`      a read's "return/match all columns". Legal; the contract now documents it.
            #   - a.b      a JSON sub-path whose prefix is a real column of this table — harmless on reads; **writes are separate** (see below).
            #   - link/unlink columns live on the **join table**; `entity` does not carry them —
            #     validate against through_table; skip if it is not a declared entity, and don't judge against the wrong table.
            _relm = None
            if k in ("link", "unlink"):
                _tt = e.get("through_table") or e.get("through") or e.get("table")
                _relm = colmap.get(_k(_tt))
                _cmx = _relm if _relm else None      # join table not declared → not judged
            else:
                _cmx = _cm
            if _cmx:
                _read = k in READ_KINDS
                _gh, _jsonw = [], []
                for _pos, _x in ([("fields", x) for x in _L(e.get("fields"))]
                                 + [("sets", x) for x in _D(e.get("sets"))]
                                 + [("row_key", x) for x in _rkcols]):
                    _sx = str(_x)
                    if _k(_x) in _cmx:
                        continue
                    if _sx == "*" and _read and _pos == "fields":
                        continue                      # legal: return/match all columns
                    if "." in _sx and _k(_sx.split(".", 1)[0]) in _cmx:
                        if not _read and _pos in ("fields", "sets"):
                            # runtime writes as `row[col] = v` — writing `payload.location`
                            # **creates a fake column named payload.location**; the value never gets into the JSON.
                            # This is not a phantom column; runtime cannot express it, and the remedy differs.
                            _jsonw.append(_sx)
                        continue                      # a JSON path on the read side is harmless
                    _gh.append(_sx)
                if _gh:
                    V["an effect names a column the entity does not have"].append(
                        "%s/%s: %s" % (idl, k, sorted(set(_gh))[:4]))
                if _jsonw:
                    V["a write side uses a JSON sub-path (runtime writes whole columns only)"].append(
                        "%s/%s: %s" % (idl, k, sorted(set(_jsonw))[:4]))
            # (6) A write effect says "the caller writes this column", and the column is (or looks like) an audit column — self-contradictory.
            if _cm and k in WRITE_KINDS:
                # `audit: false` + the caller writes it = **self-consistent** (measured 166), not a contradiction.
                # Tri-state; only two cases are contradictions: marked true but also said to be written by the caller (524), or **no position taken** while
                # the name looks like an audit column (88). `audit: false` + the caller writes it is **self-consistent** (166) —
                # "I judged it; it is a business field". The `"audit" not in` in the second branch below excludes it,
                # so no separate `is not False` is needed (it would be a dead condition; mutation testing would pass it anyway).
                _ac = sorted({str(x) for x in _L(e.get("fields")) if str(x) != "*"
                              and (_D(_cm.get(_k(x))).get("audit") is True
                                   or ("audit" not in _D(_cm.get(_k(x)))
                                       and AUDIT_RE.match(str(x))))})
                if _ac:
                    V["a write effect says the caller writes an audit column (contradicts audit)"].append(
                        "%s/%s: %s" % (idl, k, _ac[:4]))
            if k in NEED_ROWKEY and not e.get("row_key") and _gen_tool:
                # **"I checked, this operation has no locating column" and "I didn't look" must be kept apart** — that is the contract's
                # discipline from start to finish (`constraints: []` / `no_edges` / `no_guards` all follow
                # this pattern), and this rule used to treat both as the same via `not e.get("row_key")`.
                # Empty has real meaning: a conditional bulk delete (`DELETE FROM jobs`) where no column locates
                # a single row. Forcing it to write `["id"]` only makes it invent a parameter the interface does not take — which is exactly
                # what the neighbouring rule punishes. Measured: two bulk deletes in youtube-dl-server got stuck
                # between this pair of mutually exclusive rules; the model chose faithfulness and wrote its reason into note.
                if "row_key" not in e:
                    V["row_key missing (downstream can only guess the primary key)"].append("%s/%s" % (idl, k))
                elif not (_n(e.get("note")) or _n(e.get("why"))):
                    V["row_key is empty but nothing says why — an empty row_key means "
                      "**this operation locates no single row** (a bulk delete / a "
                      "condition-scoped write). That is a legal thing to say, but it has to be "
                      "said: put the reason in `note` (what the code actually does, and why no "
                      "column addresses a row). Without it, empty is indistinguishable from "
                      "not having looked"].append("%s/%s" % (idl, k))
            elif k in NEED_ROWKEY and isinstance(_rk, list) and _gen_tool:
                # (4) Reachability: every column in the column-name list must have a **required** parameter bound to it via binds.
                # Otherwise downstream can only use the column name as the parameter name — and in the real repo that parameter usually has a different name
                # (user_update takes user_uuid, the column is usr_uuid), so the tool's panel shows
                # **a parameter that does not exist in this app**, and the real parameter becomes dead weight.
                # Keys whose value does not come from a parameter (session / constant) must use the object form, handled by the branch above.
                _req = {_k(p.get("binds")) for p in _L(i.get("params"))
                        if isinstance(p, dict) and p.get("required") is True and _n(p.get("binds"))}
                # **A parameter bound to this column's FK target carries the same value.** `Entry.user_id` has fk_to
                # `User.id`, and the parameter says `binds: "User.id"` — the most natural way to say "this is a user id",
                # not a defect. Measured 1509 cases, all of which used to be false positives.
                #
                # **The reverse direction is the same principle, and used to be only half done.** The column the parameter binds to is itself
                # **an FK pointing at this row_key column** — `Transaction.AccountId → Account.AccountId`,
                # parameter sourceAccountId binds the former, and the effect locates by `Account.AccountId`.
                # The caller clearly passes this id in; the value is identical. The forward direction asks "what does the row_key column
                # point at", but when row_key is the pk it has no fk_to; the FK lives on the other table.
                # Measured: 7 in the current work orders (ezbookkeeping / bitwarden_server / documenso / lobehub).
                _req_fk = set()
                for _p in _L(i.get("params")):
                    if not (isinstance(_p, dict) and _p.get("required") is True):
                        continue
                    _b = _p.get("binds")
                    if not isinstance(_b, str) or "." not in _b:
                        continue
                    _be, _bc = _b.split(".", 1)
                    _t = _D(_D(colmap.get(_k(_be))).get(_k(_bc))).get("fk_to")
                    if isinstance(_t, str):
                        _req_fk.add(_k(_t))
                _un = []
                for c2 in _rkcols:
                    if not isinstance(c2, str):
                        continue
                    if _k("%s.%s" % (e.get("entity"), c2)) in _req:
                        continue
                    if _k("%s.%s" % (e.get("entity"), c2)) in _req_fk:
                        continue
                    _fk = _D(_cm.get(_k(c2))).get("fk_to")
                    if isinstance(_fk, str) and _k(_fk) in _req:
                        continue
                    _un.append(c2)
                # The key is wrapped in an object/json parameter (in `delete(category)`, category is
                # `{id: ...}`) — `binds` only describes scalar parameters and cannot express it. **Its own rule**: the remedy
                # differs (flatten it into scalar parameters), and mixed in it would be invisible.
                _obj = any(isinstance(p, dict) and p.get("binds") is None
                           and _k(p.get("type")) in ("object", "json")
                           for p in _L(i.get("params")))
                # **One rule, split by cause.** "Cannot locate the row" used to be a 9359-item black box;
                # the six causes have completely different fixes, and without saying which, all one can do is guess. Measured distribution (items/repos):
                #   no parameter in the list can supply a value 4689/337 · params never collected 3484/273 ·
                #   wrapped in a blob 1172/224 · same name but no binds 590/127 ·
                #   binds but not required 387/131
                if _un and _obj:
                    V["the row_key is wrapped inside an object parameter — name the parameter after its path inside the object (`obj.field`) and give it its own `binds`; you do not have to change the real API"].append(
                        "%s/%s: %s" % (idl, k, _un[:4]))
                elif _un:
                    # `binds` is `Entity.col`; comparison **must use the full name**. It used to be cut to the last segment
                    # (`DatabaseView.id` → `id`) before comparing with this effect's row_key columns, so
                    # same-named columns in two tables were treated as one — `id` is the most common column name there is; measured,
                    # 1803 of 2060 (88%) collided this way. After colliding it reported "you bound it but
                    # did not mark it required", while that parameter plainly said `required: true`: the model went looking for
                    # that "parameter not marked required", could not find it, concluded the checker was confused, and changed nothing
                    # (appflowy: 16 items unchanged for three rounds). The truth behind a name collision is usually that row_key itself
                    # is wrong — "delete all sorts under a view" written as locating one row by the child table's id —
                    # so it gets its own branch that states plainly "which table the parameter can actually reach", and **explicitly forbids**
                    # inventing a parameter the interface does not have (how airflow invented ti_id in an earlier round).
                    _allb = {_k(p.get("binds")) for p in _ps if _n(p.get("binds"))}
                    _c0 = _un[0]
                    _self = _k("%s.%s" % (e.get("entity"), _c0))
                    _fk0 = _D(_cm.get(_k(_c0))).get("fk_to")
                    _cross = sorted({str(p.get("binds")) for p in _ps
                                     if isinstance(p.get("binds"), str)
                                     and _k(str(p["binds"]).split(".")[-1]) == _k(_c0)
                                     and _k(p["binds"]) != _self})
                    if not _ps:
                        _why = "this operation has no params at all — mine the wire interface's parameters first"
                    elif _self in _allb or (isinstance(_fk0, str) and _k(_fk0) in _allb):
                        _why = ("a parameter binds to it but is not `required` — **a "
                                "parameter the caller may omit cannot locate a row**; either "
                                "it really is required, or this row_key is wrong")
                    elif _k(_c0) in _pnames:
                        _why = ("a same-named parameter exists but has no `binds` — "
                                "downstream does not gamble on names; write "
                                "`binds: \"%s.%s\"`" % (e.get("entity"), _c0))
                    elif _cross:
                        # Two thirds of the collisions are "this table holds the reference", and the sentence above suffices. The rest
                        # are **the reference living on the other side**: the caller names a child row, while this effect lands
                        # on the parent row (`Recipient.remove` takes recipientId but reads Envelope).
                        # In that case **adding a parameter is wrong** (the interface has none), and there are two correct ways out,
                        # neither needing new syntax — measured: of those 14, 9 were permission pre-reads and
                        # 5 were cascading writes; none needed a subquery in row_key.
                        _back = None
                        for _b2 in _cross:
                            _be2 = str(_b2).split(".")[0]
                            for _cn2, _cd2 in (colmap.get(_k(_be2)) or {}).items():
                                _t2 = _D(_cd2).get("fk_to")
                                if isinstance(_t2, str) and _k(str(_t2).split(".")[0]) == _k(e.get("entity")):
                                    _back = (_be2, _cn2); break
                            if _back:
                                break
                        if _back:
                            # Way out (b) used to be only "declare a cascade", which holds for **none** of the 5 write cases:
                            # documenso's Envelope.distribute changes a DocumentMeta row,
                            # which is not an FK cascade (the parent is not deleted, and the child does not change automatically); no
                            # schema declaration can express it. A correct verdict with a dead-end way out — equivalent to
                            # "giving no way out". row_key value slots now accept `{"from": ...}`, so state that real way out directly.
                            #
                            # Way out (a) used to miss half a sentence: **what to do with the original effect**. stash said verbatim
                            # "I left the row_read as-is rather than risk weakening an existing
                            # cover" — it understood and agreed, but did not dare touch it, because nobody told it deleting was safe.
                            _why = ("a parameter binds `%s`, and the reference lives on "
                                    "`%s.%s` — on the other table, not on `%s`. So the "
                                    "caller named a `%s` row and this effect landed on the "
                                    "`%s` it points at. **Adding a parameter is the wrong "
                                    "fix** — the interface does not take one. Pick by what "
                                    "this effect actually is. "
                                    "(a) **It only reads, to check a precondition** "
                                    "(ownership, existence, a status): that is a guard, not "
                                    "an effect. Move it to a `guards`/`requires` edge as a "
                                    "`needs` clause and **delete this effect entry** — "
                                    "deleting it loses nothing, a `row_read` changes no "
                                    "state, and the edge now says the same condition in the "
                                    "place that is checked. `needs` is a list of lists "
                                    "(outer OR, inner AND), and the subquery is legal inside "
                                    "it: `\"needs\": [[{\"col\": \"<column on %s>\", "
                                    "\"op\": \"eq\", \"value\": {\"from\": "
                                    "{\"entity\": \"%s\", \"where\": [...], "
                                    "\"get\": \"%s\"}}}]]`. "
                                    "(b) **It writes**: then keep it here and say how the row "
                                    "is found — `row_key` takes that same subquery, "
                                    "`\"row_key\": {\"%s\": {\"from\": {\"entity\": "
                                    "\"%s\", \"where\": [{\"col\": \"<the column the "
                                    "caller names>\", \"op\": \"eq\", \"value\": "
                                    "{\"ref\": \"$arg.<param>\"}}], \"get\": "
                                    "\"%s\"}}}` — read `%s.%s` to get this row's key. "
                                    "Only if the write is the *automatic* consequence of the "
                                    "named row being deleted is it a cascade — then declare "
                                    "it on the schema (`fk_to` + `on_delete`) and drop this "
                                    "row_%s"
                                    % (_cross[0], _back[0], _back[1], e.get("entity"),
                                       _back[0], e.get("entity"),
                                       e.get("entity"), _back[0], _back[1],
                                       _c0, _back[0], _back[1], _back[0], _back[1],
                                       str(k).replace("row_", "")))
                        else:
                            _why = ("a parameter binds `%s`, not `%s.%s` — same column name, "
                                    "different table, so it cannot locate a row here. If this "
                                    "effect touches every `%s` row that belongs to that `%s`, "
                                    "the row_key is the column holding that reference, not "
                                    "`%s`. Otherwise the parameter that locates the row was "
                                    "never mined — add it, but **do not invent a parameter the "
                                    "interface does not have**"
                                    % (_cross[0], e.get("entity"), _c0, e.get("entity"),
                                       str(_cross[0]).split(".")[0], _c0))
                    else:
                        # "switch to the object form" used to be half a sentence: it did not say what can go in the object form.
                        # The model filled in the handiest `$subject.<col>` and hit another closed-vocabulary rule
                        # (damselfly 7 → 15; all 15 new ones came from this). List the vocabulary in full on the spot,
                        # and explicitly rule out the most likely wrong answer.
                        # The third way out is newly opened. This branch is the largest chunk (527 across the corpus),
                        # and sampling shows a whole class of **"the caller gives a ticket, the row is in another table"**:
                        # documenso's `User.email-verify(token)` changes User, while the token lives on
                        # VerificationToken, and so does userId; `User.password-reset` and
                        # `Envelope.getByToken` have the same shape. They do not collide on column names, so the "reference on the other side" branch
                        # does not catch them; and neither of the original message's two ways out applies — the parameter is already there (it is token),
                        # and this table has no column holding that reference.
                        _why = ("no parameter in the list can supply this column — what "
                                "does this operation use to find that row? Three shapes, "
                                "pick by what the code does. (a) The caller does name it, "
                                "under another name: add the parameter (named after the real "
                                "interface, not after the column) and give it `binds`. "
                                "(b) The value never comes from the caller: switch to the "
                                "object form — its value vocabulary is `\"$arg.<param>\"`, "
                                "`\"$actor.<col>\"`, `\"$session.<key>\"`, a literal, or "
                                "`{\"sym\": \"$now\"}`; **`$subject` is not one of them** — "
                                "it only means something on an edge, a single tool has no "
                                "subject at execution time. (c) **The caller names a "
                                "different row, and this row's key is a column on that one** "
                                "— a token, a code, an invite, a share link. Then read it "
                                "with a subquery: "
                                "`\"row_key\": {\"%s\": {\"from\": {\"entity\": "
                                "\"<the table the caller's parameter does address>\", "
                                "\"where\": [{\"col\": \"<the column that parameter "
                                "binds>\", \"op\": \"eq\", \"value\": {\"ref\": "
                                "\"$arg.<param>\"}}], \"get\": \"<the column on that "
                                "table holding this row\u0027s key>\"}}}`. One level, "
                                "equality only, and the `$arg` must be a parameter this "
                                "operation really declares" % (_c0,))
                    V["a row_key column has no required parameter bound to it (downstream can only use the column name as the parameter name)"].append(
                        "%s/%s: %s —— %s" % (idl, k, _un[:4], _why))
            # (5) `fields` is defined as "the value comes from the caller (some parameter binds to it)". Columns no parameter can supply
            # listed here are **self-contradictory**: downstream can only put the column name itself on the panel as a parameter, and in the real repo that
            # parameter usually has a different name — so the tool's panel shows a batch of parameters that do not exist in this app.
            # Four causes, **with completely different fixes, so every piece of evidence states which one it is** (four separate rules would
            # scatter the same thing across the work order).
            if k in NEED_FIELDS or k == "row_soft_delete":
                _fl = [x for x in _L(e.get("fields")) if isinstance(x, str)]
                _unsup = [x for x in _fl if _k(x) not in _pbound and _k(x) not in _pnames]
                if _unsup:
                    if not _ps:
                        _cause = "this operation's params are empty — mine the wire interface's parameters first"
                    elif _pblob:
                        _cause = ("the value is wrapped in the object/json parameter %r — "
                                  "`params` is the **wire interface**, not the handler's "
                                  "signature. You do NOT have to change the real API: "
                                  "name each parameter after its path inside the object "
                                  "(`%s.<field>`) and give each one its own `binds`. "
                                  "That form is already in use across the corpus "
                                  "(458 params in 50 repos)" % (_pblob[0], _pblob[0]))
                    elif not _D(e.get("sets")):
                        # "Move it to sets" said only where to move it, not **in what shape to write it**. ledgersmb this round
                        # moved them as told, and gained 177 new "sets value outside the vocabulary" — opening them up, all were prose in value slots:
                        # `"currval(...)"`, `"min(id) of prior asset with same tag"`,
                        # `"coalesce(defaults.debug_fixed_assets,true)"`. It was not writing nonsense; it knew the
                        # column was written but had no legal shape to say how, so it fell back to natural language. List the vocabulary in full on the spot, and give
                        # a place (note) for what really cannot be expressed — that is not an amnesty; it measures the gap.
                        _cause = ("the caller does not supply these; the implementation "
                                  "decides them — they belong in `sets` (with their values), "
                                  "not in `fields`. This effect's sets is currently empty. "
                                  "`sets` is keyed by column and each value is one of: "
                                  "`{\"lit\": …}` a fixed value · `{\"sym\": \"$now\"}` "
                                  "a timestamp · `{\"ref\": \"$actor.<col>\"}` / "
                                  "`{\"ref\": \"$session.<key>\"}` something the request "
                                  "context fixes · `{\"from\": {\"entity\": …, "
                                  "\"where\": […], \"get\": …}}` a value read off another "
                                  "row · `{\"expr\": {\"col\": …, \"op\": …, "
                                  "\"by\": …}}` a change to this row's own column. "
                                  "**Do not write prose into a value** — "
                                  "`\"currval(seq)\"` or `\"hash(password)\"` is a "
                                  "description, and it will be read back as the literal "
                                  "string. If a column genuinely fits none of those because "
                                  "the value is generated at run time, name it in this "
                                  "effect's `note` instead and say what produces it")
                    else:
                        _cause = ("no parameter can supply these — what the caller gives "
                                  "goes in `fields`, what the implementation decides goes "
                                  "in `sets`, keyed by column, each value being "
                                  "`{\"lit\"}` / `{\"sym\": \"$now\"}` / "
                                  "`{\"ref\": \"$actor.<col>\"}` / `{\"from\": {…}}` / "
                                  "`{\"expr\": {…}}`. A description is not a value: "
                                  "`\"currval(seq)\"` is read back as that literal string. "
                                  "A column that fits none of the five belongs in this "
                                  "effect's `note`, named, with what produces it")
                    V["a column in fields has no parameter that can supply it"].append(
                        "%s/%s: %s —— %s" % (idl, k, _unsup[:4], _cause))
            if k in NEED_FIELDS and not e.get("fields") and not e.get("sets"):
                # This rule's evidence string used to be only `id_local/kind` — no cause, let alone a way out, and it is
                # the largest remaining chunk (527 across the corpus). After going through samples, it splits into three kinds with completely different fixes:
                #   - **parameters bind to this very table** (about 200). misskey's Meta.updateAdmin has
                #     81 parameters with binds to Meta, yet fields is empty; lidarr notification.add has 19.
                #     This kind is purely mechanical; naming them is enough to fix it — and the original message did not mention it at all.
                #   - **there are parameters, but none binds to this table** (about 318). The caller writes nothing on this table;
                #     every value comes from the implementation. List the four expressible forms on the spot; for what really cannot be expressed (runtime-generated random
                #     strings, fetched content), have it write the column name into note — that is not an amnesty; it **measures the grammar
                #     gap**, so data can decide whether the grammar needs a new token.
                #   - **this operation has no parameters at all**: go mine the interface first.
                _ent_k = _k(e.get("entity"))
                _own = [str(p.get("name")) for p in _ps
                        if isinstance(p.get("binds"), str)
                        and _k(str(p["binds"]).split(".")[0]) == _ent_k]
                if _own:
                    _fs = ("%d of this operation's parameters already bind to `%s` (%s%s) — "
                           "those are exactly the columns the caller writes. List their "
                           "**column** names in `fields`. Anything the implementation decides "
                           "on top of them goes in `sets`, with its value"
                           % (len(_own), e.get("entity"), ", ".join(_own[:6]),
                              ", …" if len(_own) > 6 else ""))
                elif _ps:
                    _fs = ("this operation takes %d parameters and **none of them binds to "
                           "`%s`** — so the caller writes nothing here and every value comes "
                           "from the implementation. Put them in `sets`, keyed by column: a "
                           "fixed value is `{\"lit\": …}`, a timestamp is "
                           "`{\"sym\": \"$now\"}`, a value read off another row is "
                           "`{\"from\": {\"entity\": …, \"where\": […], \"get\": …}}`, "
                           "and a value computed from this row's own column is "
                           "`{\"expr\": {\"col\": …, \"op\": …, \"by\": …}}`. If a "
                           "column fits none of those because the value is **generated at "
                           "run time** — a random token, a hash, text fetched from outside — "
                           "then the Value vocabulary genuinely has no token for it: name "
                           "those columns in this effect's `note` and say what produces them. "
                           "That does not clear this violation, but it is the only thing that "
                           "tells us the gap is real rather than unmined"
                           % (len(_ps), e.get("entity")))
                else:
                    _fs = ("this operation has no params at all — mine the wire interface's "
                           "parameters first; until then nothing can say what was written")
                V["fields and sets both missing (nobody knows what was written)"].append(
                    "%s/%s→%s: %s" % (idl, k, e.get("entity"), _fs))
            if not isinstance(e.get("sets"), (dict, type(None))):
                V["sets is not an object"].append("%s/%s" % (idl, k))
            if not isinstance(e.get("fields"), (list, type(None))):
                V["fields is not an array"].append("%s/%s" % (idl, k))
            ov = {_k(x) for x in _L(e.get("fields"))} & {_k(x) for x in _D(e.get("sets"))}
            if ov:
                V["fields and sets overlap"].append("%s/%s: %s" % (idl, k, sorted(map(str, ov))))
            _setcm = colmap.get(_k(e.get("entity"))) or {}
            for col, v in _D(e.get("sets")).items():
                if not _val_ok(v):
                    V["a sets value is outside the Value vocabulary"].append("%s/%s.%s=%r" % (idl, k, col, v))
                _pb = _prose_bad(v, _setcm.get(_k(col)))
                if _pb:
                    V["a sets value describes the value instead of being it"].append(
                        "%s/%s.%s = %r%s" % (idl, k, col,
                                             (v.get("lit") if isinstance(v, dict) else v), _pb))
                for _rb in (_ref_bad(v),
                            _actor_col_bad(v, _allcols, _allncols)):
                    if _rb:
                        V[_rb[0]].append("%s/%s.%s: %s" % (idl, k, col, _rb[1]))
                _eb = _expr_by_bad(v)
                if _eb:
                    V["expr.by is $now (time arithmetic is forbidden)"].append(
                        "%s/%s.%s: %s" % (idl, k, col, _eb))
            if k == "auth":
                _m = _k(e.get("mode"))
                if _m not in AUTH_MODES:
                    V["auth effect mode missing or invalid (verify / signout / register)"].append(
                        "%s: %r" % (idl, e.get("mode")))
                if _m in ("verify", "register"):
                    for _cc in ("username_col", "password_col"):
                        if not _n(e.get(_cc)):
                            V["auth effect has no credential columns (username_col / password_col)"].append(
                                "%s: missing %s — an auth effect that cannot say which "
                                "column holds the identity and which holds the secret is not "
                                "reproducible; name both, or drop the auth effect" % (idl, _cc))
                        elif _cm and _k(e.get(_cc)) not in _cm:
                            V["the auth effect's credential columns are not on the account table"].append(
                                "%s: %s=%r" % (idl, _cc, e.get(_cc)))
            if k in READ_KINDS:
                sc = e.get("scope")
                if not isinstance(sc, dict) or _k(sc.get("kind")) not in SCOPE_KINDS:
                    V["a read/search effect's scope.kind is missing or invalid"].append("%s/%s: %r" % (idl, k, sc))
                elif sc.get("kind") == "owner" and not sc.get("owner_col"):
                    V["scope kind=owner has no owner_col"].append("%s/%s" % (idl, k))
                if "on_miss" in (sc or {}):
                    V["on_miss moved to the repo-level conventions.read_denied"].append("%s/%s" % (idl, k))
            if k == "row_search":
                if _k(e.get("method")) not in METHODS:
                    V["row_search.method missing or invalid (write unknown when you cannot tell)"].append("%s: %r" % (idl, e.get("method")))
                if not e.get("why"):
                    V["row_search has no why (the evidence in code)"].append(idl)

        # provides is State too; its scope clauses use **the same** operator table as needs.
        # This used to check only "is there a card" — so invented operators (changed / increased / increment)
        # all came in through this gap, none reported. Measured, that whole batch was in provides, not in edges,
        # and the edge-layer checks only cover the edge layer: **one vocabulary, two positions, only one position checked.**
        # `sets: {c: {"col": c}}` = "this column is set to itself", a tautology.
        # Measured origin: it wanted to say `answer_count = answer_count + 1`, but the sets side has no arithmetic,
        # so it wrote filler and lost the fact that "it went up". The correct form: the column name goes into fields,
        # and the change is stated with provides' `{"was": ...}`.
        # `sym` is checked here too: it is a closed vocabulary (only $now); the measured corpus has 8 invented forms
        # ($uuid / $gen / uuid_v4 / random / $newGUID / $generate / $generated).
        for _ef in _L(i.get("effects")):
            if not isinstance(_ef, dict):
                continue
            # When `sets` was written as an array this used to throw AttributeError right here, and the CLI only catches exceptions at the outermost level —
            # so **that repo's entire violation list was replaced by a single "the checker threw"**, and dozens of other
            # findings were lost. The check itself exists (see `sets is not an object` above); this just crashed first.
            # One malformed field should not wreck the whole repo's diagnosis — build_probe's l0 already learned this the hard way.
            _sets = _ef.get("sets")
            if not isinstance(_sets, dict):
                continue                      # wrong shape already reported by `sets is not an object`
            for _c, _v in _sets.items():
                if isinstance(_v, dict) and _v.get("col") == _c:
                    V["a `sets` entry sets a column to itself — a tautology that also loses "
                      "the fact that it changed"].append(
                          "%s: %s = {col: %s} — if it is an increment write "
                          "{expr:{col:%s,op:\"+\",by:{lit:1}}}; if the value comes from the "
                          "caller put the column in `fields`" % (idl, _c, _c, _c))
                if isinstance(_v, dict) and "sym" in _v and _v.get("sym") != "$now":
                    V["`sym` is a closed vocabulary — $now is the only one"].append(
                        "%s: %s = {sym: %r} — a value nobody can predict cannot be asserted "
                        "equal to anything; drop the clause" % (idl, _c, _v.get("sym")))

        for pr in _L(i.get("provides")):
            if not isinstance(pr, dict) or "card" not in pr:
                V["provides is not State-shaped"].append(idl)
                continue
            # ⚠ **The value of `card` itself was never checked here.** The line above only checks "is the key present",
            # while the edge layer (needs) has an identical check — **one vocabulary, two positions, only one checked.**
            # Same disease as the scope-operator comment above, this time it is card's turn.
            # Measured on the new corpus: 0 on the needs side (the edge-layer check works; the feedback round cleaned it up),
            # **95** on the provides side, of which **63 are whole passages of prose**.
            _card = pr.get("card")
            if isinstance(_card, dict):
                _cbad = _k(_card.get("op")) not in CARD_OPS or not isinstance(_card.get("n"), int)
            else:
                _cbad = _card not in ("exists", "not_exists")
            if _cbad:
                _cs = _card if isinstance(_card, str) else ""
                if len(_cs) > 40 or (" " in _cs.strip() and len(_cs) > 12):
                    # "Prose in a value slot" recurs in a third position (the first two are `{"lit": ...}` and sets).
                    # Its own rule: its fix is completely different from "used the wrong alias" — that sentence belongs in
                    # `why`, and card only answers "how many rows".
                    V["a provides `card` narrates what happened instead of counting rows"].append(
                        "%s: card = %r — `card` only answers **how many rows**: "
                        "`\"exists\"` / `\"not_exists\"` / `{\"op\":\"gte\",\"n\":1}`. "
                        "Put the sentence in `why`, and say the countable fact in "
                        "`entity` + `scope` + `card`." % (idl, _cs[:60] + ("…" if len(_cs) > 60 else "")))
                else:
                    V["card is invalid (op from the closed set, n an integer)"].append(
                        "%s (provides): %r — write `\"exists\"` / `\"not_exists\"`, or "
                        "`{\"op\": one of %s, \"n\": <int>}`. `one`/`single` is "
                        "`{\"op\":\"eq\",\"n\":1}`, `none` is `\"not_exists\"`, "
                        "`many` is `{\"op\":\"gte\",\"n\":2}`."
                        % (idl, _card, "/".join(sorted(CARD_OPS))))
            for cl in _L(pr.get("scope")):
                if not isinstance(cl, dict):
                    continue
                _op = _k(cl.get("op"))
                if _op is None or _op in OPS:
                    continue
                _fix = _OP_FIX.get(_op)
                if _fix:
                    V["an invented operator — the grammar can express this, "
                      "you just have to write it the grammar's way"].append(
                          "%s: op=%r — write it as %s" % (idl, cl.get("op"), _fix))
                else:
                    V["State scope.op outside the closed vocabulary"].append(
                        "%s: %r (legal: %s)" % (idl, cl.get("op"), " ".join(sorted(OPS))))

    # Per-repo distribution alerts for entry. All internal = the model gave up (it did not go through the route table);
    # all external = it did not take it seriously (a real repo cannot have zero internal helpers extracted).
    # Neither is "one item is wrong"; it is **this repo's entries as a whole are untrustworthy**, hence separate rules.
    _tot_e = sum(_n_entry.values())
    _repo = str(d.get("repo") or "?").rstrip("/").rsplit("/", 1)[-1]
    if _tot_e >= 8:
        _int = _n_entry.get("internal", 0)
        if _int == _tot_e:
            # This rule used to have only a verdict and no way out; the evidence string was just a repo name. And the repos it hits fall into two kinds
            # with opposite remedies — chartdb / mere-medical / tagspaces stayed unchanged for seven rounds in a row,
            # because they **have no route table to look through**: browser-side IndexedDB / Electron local files,
            # no server side at all. The model mined 8-9 tables and 30-62 impls, all correct,
            # and was then kept out of zero violations by a rule it could not satisfy.
            # "A tool unreachable over the network cannot be an environment" — that is a criterion for **skipping**, not a defect.
            V[RULE_ALL_ENTRY_INTERNAL + " (%d/%d) — the route table was probably never opened" % (_int, _tot_e)].append(
                "%s — all %d entries are internal. Two readings, and only reading the repo tells "
                "them apart. (a) **The route table was never opened**: find where this app "
                "registers its wire surface — a routes file, controller annotations, an OpenAPI "
                "document, the RPC service definition — and set `entry.kind` and `entry.route` "
                "from it. Anything reachable over the wire has to say so, because that is the "
                "only thing that becomes a callable tool. (b) **There is genuinely no wire "
                "surface**: a browser-only or Electron local-first app whose persistence is "
                "IndexedDB or the filesystem, with no server of its own. Then this is not a "
                "defect to fix — it is the skip verdict, because a tool nobody can call over a "
                "network cannot be an environment. Say it the way the skip is defined: replace "
                "the file with `summary` starting with the literal `not a CRUD app, skipped:` "
                "and empty `schemas` / `impls` / `edges`, and use `looked for:` to say where you "
                "searched for a server. The entities you already mined are not wasted work — the "
                "skip is a finding, and it is what stops this repo from being mined again."
                % (_repo, _tot_e))
        # Deleted the "not a single internal" tier (keeping the "all internal" tier above — it points at
        # the model not going through the route table at all, which has empirical meaning). The old reasoning was "a real repo cannot have zero internal helpers
        # extracted", but what it hit were precisely API-first services: photoprism (all 91 impls are HTTP),
        # wildduck (72), solr (69), buku (10), kutt (35), webhook-tester (10)... the public interface
        # is all they are. And collection targets "operations usable as tools" in the first place; not finding internal helpers is not
        # negligence, it is on-topic.
        # 34 repos hit across the corpus, and for **16 of them this was the only violation** — kept out of zero violations by a statistical hunch,
        # while the model had handed in a real route and registering locator for every operation.
        # It and the just-deleted impl.locator-in-internal-dir are two faces of the same flaw: both use a hunch to question
        # "all external" while ignoring the evidence already on the table. The real defences are the two rules below; they demand evidence:
        #   entry is not internal but gives no route
        #   entry is not internal but gives no registration locator
        # A model that fabricates gets caught by those two; this one was only "I feel it should not be all external", with no empirical content.

    # ── edge layer ──
    idl_set = {_n(_D(i).get("id_local")) for i in _L(d.get("impls"))}
    idl_set.discard(None)
    for e in _L(d.get("edges")):
        if not isinstance(e, dict):
            V["edges contains a non-object item"].append(type(e).__name__); continue
        sub = _n(e.get("subject"))
        if sub and idl_set and sub not in idl_set:
            V["edge.subject is not an impls[].id_local"].append(str(sub))
        n = e.get("needs")
        rel = _k(e.get("relation"))
        _cond = (e.get("condition") or "").strip() if isinstance(e.get("condition"), str) else ""
        # **Each relation has a different definition of "hollow" — a generic "no needs" rule would produce 671 bogus reports.**
        # Measured: only 4% of triggers edges carry needs, and that is right — "A calls B" is complete information in itself;
        # by contract the condition for following the edge goes into `condition`; downstream (build_prep) also compiles only guards/requires
        # into real walls, while triggers are downgraded to _candidate_preconditions.
        if rel in ("guards", "requires"):
            if not n and not _cond:
                V["a guards/requires edge says a wall exists but never says what it is "
                  "(no needs, no condition)"].append(
                      "%s -> %s" % (sub, _D(e.get("object")).get("ref")))
            elif not n:
                # The evidence has already been collected; it only needs translating into State — **the cheapest fix of all**,
                # completely different in nature from "both empty" (that one needs the code re-read), hence a separate rule.
                V["a guards/requires edge has the test only as prose in `condition` — "
                  "write it as `needs` so it compiles into a real wall"].append(
                      "%s: %s" % (sub, _cond[:70]))
        elif rel == "triggers":
            o = _D(e.get("object"))
            if _k(o.get("kind")) == "op" and o.get("ref") and idl_set \
                    and _n(o.get("ref")) not in idl_set:
                V["a triggers edge points at an operation that was never mined"].append(
                    "%s -> %s (mine that impl, or drop this edge)" % (sub, o.get("ref")))
        if n and not isinstance(n[0], list):
            V["needs is not one level of DNF (it was flattened)"].append(str(sub))
        for grp in _L(n):
            for st in (grp if isinstance(grp, list) else [grp]):
                if not isinstance(st, dict):
                    continue
                card = st.get("card")
                if isinstance(card, dict):
                    if _k(card.get("op")) not in CARD_OPS or not isinstance(card.get("n"), int):
                        V["card is invalid (op from the closed set, n an integer)"].append("%s: %r" % (sub, card))
                elif card not in ("exists", "not_exists"):
                    V["card is invalid (op from the closed set, n an integer)"].append("%s: %r" % (sub, card))
                for cl in _L(st.get("scope")):
                    if not isinstance(cl, dict):
                        continue
                    if _k(cl.get("op")) not in OPS:
                        _op = _k(cl.get("op"))
                        _fix = _OP_FIX.get(_op)
                        if _fix:
                            V["an invented operator — the grammar can express this, "
                              "you just have to write it the grammar's way"].append(
                                  "%s: op=%r — write it as %s" % (sub, cl.get("op"), _fix))
                        else:
                            V["State scope.op outside the closed vocabulary"].append(
                                "%s: %r (legal: %s)" % (sub, cl.get("op"), " ".join(sorted(OPS))))
                    # Clauses on edges are read by the State evaluator — it has aggregates, whole tables, and the full operator set.
                    for _rb in (_ref_bad(cl.get("value"), state=True),
                                _actor_col_bad(cl.get("value"), _allcols, _allncols)):
                        if _rb:
                            V[_rb[0]].append("%s: %s" % (sub, _rb[1]))
                    _nb = _null_cmp_bad(cl.get("op"), cl.get("value"))
                    if _nb:
                        V["comparing against null with eq/ne — the clause can never be true"].append(
                            "%s: %s %r {\"lit\": null} — write op=%r instead (unary, no value)"
                            % (sub, cl.get("col"), cl.get("op"), _nb))
                    # ⚠ **Unary operators have no right operand**; checking value on them is an unconditional false positive.
                    # The `comparing against null with eq/ne` rule above just made the model rewrite
                    # `ne {lit:null}` as `is_not_null` (unary, no value),
                    # and right here it was told its value is None and not in the vocabulary — the two rules fought each other,
                    # the model flipped between them every round, and **it could never clear**.
                    # Measured: 1645 of this rule's 1652 hits (100%) came from this,
                    # across 92 repos (itflow 457 / bitwarden_server 229 / recipes 186).
                    # A bug from the same source was fixed once in build_prep.py (KeyError: 'value'), but only on
                    # the build side; the checker side was missed. The authoritative arity definition is
                    # FIELD_OPS in runtime/grammar.py (op -> (arity, eval)); **do not hard-code an operator list here** —
                    # when the grammar adds a new unary operator, this must follow automatically.
                    if _arity_of(cl.get("op")) != 1 and not _val_ok(cl.get("value")):
                        V["State scope.value is outside the Value vocabulary"].append("%s: %r" % (sub, cl.get("value")))
    return V


def check_regression(cur, base):
    """Compare with the previous pass; report only "shrank" — growing is not a problem, shrinking needs an explanation.

    No set difference to decide "which edges are gone": id_local normalisation (a woocommerce-style refactor) changes every
    subject, and a set difference would report a legitimate refactor as wholesale deletion. Use counts, plus a few vanished
    subjects as clues, and let whoever wrote it judge whether it is a rename or a deletion."""
    V = collections.defaultdict(list)
    ea, eb = len(_L(base.get("edges"))), len(_L(cur.get("edges")))
    na, nb = len(_L(base.get("no_edges"))), len(_L(cur.get("no_edges")))
    ia, ib = len(_L(base.get("impls"))), len(_L(cur.get("impls")))
    sa, sb = len(_L(base.get("schemas"))), len(_L(cur.get("schemas")))

    if eb < ea:
        gone = ({_n(_D(e).get("subject")) for e in _L(base.get("edges"))} -
                {_n(_D(e).get("subject")) for e in _L(cur.get("edges"))})
        V["edges shrank versus the previous pass (say which kind)"].append(
            "%d → %d, %d fewer; subjects present in the previous pass but not in this one: %s. "
            "Either is possible: (1) these subjects never fit the contract (middleware, permission checkers, "
            "ids missing the entity prefix), and removing them is right — then say so in no_edges or a note; "
            "(2) valid edges really were lost — then add them back. You have read the code; you decide."
            % (ea, eb, ea - eb,
               ", ".join(sorted(str(x) for x in gone)[:6]) or "(all still present; duplicate entries were merged)"))
    if nb - na >= REG_NOEDGE and eb <= ea:
        V["no_edges jumped while edges did not (check them one by one — it is not a shortcut)"].append(
            "no_edges %d → %d (+%d), while edges went %d → %d. "
            "no_edges is only for ops where you **read the code and confirmed there really is no precondition**; "
            "not being able to fill one in does not mean there is none" % (na, nb, nb - na, ea, eb))
    if ib < ia * 0.9:
        V["impls shrank by more than 10% versus the previous pass"].append("%d → %d" % (ia, ib))
    if sb < sa * 0.9:
        V["schemas shrank by more than 10% versus the previous pass"].append("%d → %d" % (sa, sb))
    return V


def _order(out, repo, f, cov_info, violations, smap, collect):
    """Write one work order. File-level fatal problems (not JSON / top level not an object) get a work order too —
    otherwise the dirtiest batch would escape review."""
    sc = os.path.join(collect, "_sessions", repo + ".json")
    try:
        sess = json.load(open(sc, encoding="utf-8"))
    except Exception:
        sess = smap.get(repo)
    os.makedirs(out, exist_ok=True)
    json.dump({"repo": repo, "collect_file": f,
               "session_id": (sess or {}).get("session_id"),
               "config_dir": (sess or {}).get("config_dir"),
               "coverage": (cov_info or {}).get("coverage", 0.0),
               "n_mutating": (cov_info or {}).get("n_mutating", 0),
               "n_missing": 0, "truncated": False, "missing": [],
               "n_violations": sum(len(v) for v in violations.values()),
               "violation_totals": {k: len(v) for k, v in violations.items()},
               "violation_tiers": {r: rule_tier(r) for r in violations},
               "violations": {k: v[:MAX_VIOL] for k, v in violations.items()}},
              open(os.path.join(out, repo + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def main():
    try:
        smap = json.load(open(SESSMAP, encoding="utf-8"))
    except Exception:
        smap = {}
    os.makedirs(OUT, exist_ok=True)
    stat = collections.Counter()
    rule_tot = collections.Counter()
    rule_repos = collections.defaultdict(set)      # rule → repos it appeared in
    for f in sorted(glob.glob(os.path.join(COLLECT, "*.json"))):
        repo = os.path.basename(f)[:-5]
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception as ex:
            stat["JSON parse failed"] += 1
            _order(OUT, repo, f, None, {"the file is not valid JSON": [str(ex)[:80]]}, smap, COLLECT)
            continue
        if not isinstance(d, dict):
            # the agent wrote a subagent's intermediate output into the collect dir (top level is an array) —
            # downstream would read it as collect output, so it must be reported explicitly, not skipped silently
            stat["top level not an object"] += 1
            _order(OUT, repo, f, None,
                   {"the top level is not a CollectOutput object": [type(d).__name__ +
                    " — write only the one output file; intermediate shards do not belong "
                    "in the collect directory"]},
                   smap, COLLECT)
            continue
        impls = _L(d.get("impls"))
        edges = _L(d.get("edges"))
        mut = [i for i in impls if isinstance(i, dict) and (_k(i.get("op")) or "") in MUT]

        # depth-1
        subj = {_n(_D(e).get("subject")) for e in edges if _D(e).get("subject")}
        declared = {_n(x.get("id_local")) for x in _L(d.get("no_edges"))
                    if isinstance(x, dict)}
        declared.discard(None)      # don't let None match None
        missing = []
        for i in mut:
            idl = _n(i.get("id_local"))
            if idl is None:
                missing.append({"id_local": None, "op": i.get("op"), "entity": None,
                                "locator": i.get("locator"),
                                "hints": ["this impl has no id_local; add an identifier before dealing with edges"]})
                continue
            if idl in subj or idl in declared:
                continue
            hints = []
            if idl in {_n(_D(_D(e).get("object")).get("ref")) for e in edges
                       if isinstance(_D(e).get("object"), dict)}:
                hints.append("another edge references it as its object")
            # `entity` was never put in here, and the renderer's `m.get("entity")` got None —
            # so every line of the work order printed a None. In v3 the scope is carried by effects; take the main effect's.
            _en = next((ef.get("entity") for ef in _L(i.get("effects"))
                        if isinstance(ef, dict) and ef.get("entity")), None)
            missing.append({"id_local": idl, "op": i.get("op"), "entity": _en,
                            "locator": i.get("locator"), "hints": hints})
        cov = 1.0 - len(missing) / len(mut) if mut else 1.0

        # ── guard coverage: a **different number** from depth-1 coverage; it asks a different question ──────────────
        # depth-1 coverage asks "has this op been looked at" (being the subject of any edge counts);
        # guard coverage asks "has this op's **wall** been spelled out".
        # Measured: 271 mutating impls (8%) have **only triggers edges** — they satisfy depth-1 coverage,
        # cannot go into no_edges (they do have edges), and nowhere records "I looked for guards and there are none".
        # Examples User.update_password / User.password_reset: almost certainly **have** walls.
        # So "checked, no wall" and "didn't check" look identical — exactly the tier missed by the discipline the prompt itself states
        # ("\"I checked and it's absent\" and \"I didn't look\" must be written differently").
        # `no_guards` gives the first case a place to say so.
        _wall_subj = {_n(_D(e).get("subject")) for e in edges
                      if _k(_D(e).get("relation")) in ("guards", "requires")
                      and _D(e).get("needs")}
        _no_guards = {_n(x.get("id_local")) for x in _L(d.get("no_guards"))
                      if isinstance(x, dict)}
        _no_guards |= {_n(x) for x in _L(d.get("no_guards")) if isinstance(x, str)}
        _no_guards.discard(None)
        _silent = [i for i in mut
                   if _n(i.get("id_local"))
                   and _n(i.get("id_local")) not in _wall_subj
                   and _n(i.get("id_local")) not in _no_guards
                   and _n(i.get("id_local")) not in declared        # the whole op has no edges; already reported by missing
                   and _n(i.get("id_local")) in subj]               # has edges, but none spells out the wall
        gcov = 1.0 - len(_silent) / len(mut) if mut else 1.0

        try:
            V = check_repo(d)
            for i in _silent:
                V["this operation has edges but none of them says what guards it — "
                  "if you looked and there is no wall, say so in `no_guards`"].append(
                      "%s(%s)" % (i.get("id_local"), i.get("locator")))
            if BASELINE:
                bf = os.path.join(BASELINE, repo + ".json")
                if os.path.exists(bf):
                    try:
                        bd = json.load(open(bf, encoding="utf-8"))
                        if isinstance(bd, dict):
                            for r, ex2 in check_regression(d, bd).items():
                                V[r].extend(ex2)
                    except Exception:
                        pass
        except Exception as ex:
            # malformed variants cannot be enumerated — a crashing repo records one violation and never takes the following repos down with it
            import traceback
            V = collections.defaultdict(list)
            V["the checker threw on this repo (malformed output, look by hand)"].append(
                "%s: %s" % (type(ex).__name__, str(ex)[:120]))
            stat["checker exception"] += 1
            traceback.print_exc(limit=2)
        for r, ex in V.items():
            rule_tot[r] += len(ex)
            rule_repos[r].add(repo)
        n_viol = sum(len(v) for v in V.values())

        # The pass gate now includes guard coverage: it used to look at depth-1 only, so repos whose edges were all there but all hollow
        # (modoboa 59 edges / needs 6%, mox 29 edges / 6%, mailu 81 edges / 12%) were judged **passing, no work order**.
        if (not missing or cov >= THRESH) and not _silent and not n_viol:
            stat["passed"] += 1
            continue
        sc = os.path.join(COLLECT, "_sessions", repo + ".json")
        try:
            sess = json.load(open(sc, encoding="utf-8"))
        except Exception:
            sess = smap.get(repo)
        json.dump({"repo": repo, "collect_file": f,
                   "session_id": (sess or {}).get("session_id"),
                   "config_dir": (sess or {}).get("config_dir"),
                   "coverage": round(cov, 3), "n_mutating": len(mut),
                   # **Two coverage numbers; don't mix them.** coverage = have these ops been looked at;
                   # guard_coverage = have their walls been spelled out. A hollow guards edge
                   # (no needs) looks exactly like a fully written one to coverage — that is precisely
                   # the mechanism behind "modoboa: 59 edges / needs 6%, yet passing".
                   "guard_coverage": round(gcov, 3),
                   "n_guard_silent": len(_silent),
                   "n_missing": len(missing), "truncated": len(missing) > MAX_LIST,
                   "missing": missing[:MAX_LIST],
                   "n_violations": n_viol,
                   # The **full** count per rule. Examples keep only MAX_VIOL, and if feedback rendering used
                   # `len(examples)` as the count, it would **actively report a wrong number** — the agent would think fixing
                   # these 40 was the end of it. `missing` always had n_missing/truncated; violations
                   # did not — the same discipline, half missed.
                   "violation_totals": {r: len(ex) for r, ex in sorted(V.items())},
                   "violation_tiers": {r: rule_tier(r) for r in V},
                   "violations": {r: ex[:MAX_VIOL] for r, ex in sorted(V.items())}},
                  open(os.path.join(OUT, repo + ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        stat["work order written"] += 1
        stat["resumable" if (sess or {}).get("session_id") else "no session"] += 1

    # Stale work orders must be cleaned up. **Write-only, never clean** leaves work orders pointing at output that no longer exists: measured on fxa / ghost /
    # navidrome / qloapps, collect produced a version → a work order was written → on re-collection the new output failed and was demoted into
    # partial/ → the work order stayed in place. Whoever runs edge_topup would still pick it up and resume a
    # session to fix a **file that does not exist**.
    _alive = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(COLLECT, "*.json"))}
    _stale = [f for f in glob.glob(os.path.join(OUT, "*.json"))
              if os.path.basename(f)[:-5] not in _alive]
    for f in _stale:
        os.remove(f)
    if _stale:
        print("removed %d stale work orders (their output is no longer in collect/): %s"
              % (len(_stale), " ".join(sorted(os.path.basename(x)[:-5] for x in _stale))[:200]))

    n_files = len(glob.glob(os.path.join(COLLECT, "*.json")))
    n_seen = sum(stat[k] for k in ("work order written", "passed", "JSON parse failed", "top level not an object"))
    print("threshold %.0f%% — %s" % (THRESH * 100, dict(stat)))
    print("processed %d / %d files in dir%s" % (n_seen, n_files,
          "" if n_seen == n_files else "   ← mismatch: some repos were skipped; do not draw conclusions from this batch"))
    if rule_tot:
        # **Report item counts and repo counts together.** Item counts alone are skewed by single-repo outliers — measured:
        # of 3407 hits of `effect.kind outside the closed vocabulary`, 3401 were in one repo, hrms (a single operation carried
        # 258 action effects), while `effect names a column the entity does not have` had a similar count spread over 263
        # repos. The former is one repo's problem, the latter is the contract being unclear — misreading this when ranking spends effort backwards.
        # (This is the aggregate view for **us** to prioritise; in each repo's own work order, the counts are its own.)
        print("\nviolated rules (items / repos affected):")
        _w = max(len(r) for r in rule_tot)
        for r, n in rule_tot.most_common():
            _nr = len(rule_repos[r])
            _flag = "  ← concentrated in %d repos" % _nr if _nr <= 5 and n >= 200 else ""
            print("  %-*s %6d / %3d repos%s" % (min(_w, 46), r[:46], n, _nr, _flag))
    print("\nwork orders written to %s" % OUT)


if __name__ == "__main__":
    main()
