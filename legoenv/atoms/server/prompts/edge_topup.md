A deterministic checker has re-read the file you produced for this repo. Below is what it found. **These are mechanical facts computed from your own output, not opinions** — the checker cannot read code and has no view on what is correct.

## What it checked

Three separate things. **Do not read the first number as a grade for the whole file** — a repo can
cover 100% of its edges and still have hundreds of contract violations.

**1. Depth-1 edge coverage.** Every mutating op (`create` / `update` / `delete` / `action`) must
appear **at least once as the `subject` of an edge**, recording what it directly triggers or
requires. Ops that only ever appear as an `object` are not covered — the contract calls that out
explicitly. Your output covers **__COVERAGE__** of this repo's mutating ops
(__N_COVERED__ of __N_MUTATING__).

**2. Guard coverage.** Of those same mutating ops, how many have a wall that is actually spelled
out. An op whose only edges are `triggers` is covered by the first number and **silent** on this
one. Your output is at **__GUARD_COVERAGE__** here (__N_GUARD_SILENT__ op(s) have edges but no
wall and are not in `no_guards`). **Both numbers have to clear the bar** — the first one alone
never did.

**3. The output contract, field by field** — the larger list below. Your output has
**__N_VIOLATIONS__** of them. Counts there are **full counts**; the examples after each one are a
sample, not the list. **This is the number this round is judged on.** The two coverage percentages
above are prerequisites, not the goal: a file at 100% on both with hundreds of violations left is
not done.

## The ops with no edge of their own

__MISSING_LIST__

__TRUNCATION_NOTE__

## Contract violations

These are **mechanical checks against the output contract** — each one names the exact field and the exact place. `unknown` and empty lists count as compliant; an omitted field does not, because *"I checked and there is nothing"* and *"I did not look"* have to stay distinguishable downstream.

__VIOLATIONS__

## Which to do first

**The list below is already grouped into tiers — work them in order.** The tier is decided by
the checker, not by you, and it is not the same as "biggest count first": a rule with 3000
occurrences in one file can be cheaper to fix than one with 40 spread across every operation.

What each tier means, and why it sits where it does:

1. **the file itself is unreadable** — not valid JSON, the top level is not an object, an array is not an array,
   the checker threw. Nothing downstream can read any of it. Fix before anything else.
2. **unfixed = this repo yields zero tools** — an impl with no `entry` **produces no tool at all**, so a repo where
   this is unfixed contributes *nothing*, however good the rest is. Find the line that
   **registers** the function (route table, RPC map, GraphQL binding, CLI registry — usually a
   different file from the body), copy it into `entry.locator` with the verbatim `route`.
   **No registration found → `internal`.** Never guess from the name.
3. **the only source code anyone downstream sees** — `ref_code`. The stage that writes each tool's description, its parameter
   descriptions and the wording of every error it raises **cannot open this repo**. Paste the
   real lines: pre-checks, writes, the status assignment, what it dispatches. 5–25 lines, under
   600 characters. A file path is `locator`, a framework's name is not this app's behaviour, and
   a signature with the body elided to `{...}` has thrown away the only part that mattered.
4. **self-contradictory (visible without reading code)** — a column an effect names that the entity does not have; an `effect.entity` that
   is not a declared entity; `fields` and `sets` naming the same column; a `ref` pointing at a
   namespace that does not exist (`$output.item`, `$request.space.id`, `$this.id`) or at a column
   no table in this repo has. **These need no code reading to see that something is wrong** —
   though you do need the code to decide which side is right. The cheapest wins here.
5. **no position taken (unknown / null / [] all count; omitting does not)** — `unknown`, `null` and `[]` all count as compliant; an omitted field does not.
   `binds` on every parameter (`null` is an answer), `method` on a search, `scope.kind` on a read,
   `constraints` on an entity, `why` on a global scope. One token, and it is the difference
   between "there is none" and "nobody looked".
6. **shape and closed vocabularies (mechanical, but downstream has to guess)** — a `type` outside the seven **that the downstream normaliser also cannot
   place** (`varchar` and `CharField` it handles silently; `num_integer` it cannot), a key on a
   column it has no alias for, an `effect.kind` outside the list, an operator outside
   `grammar`'s table. Mechanical, but each one is a place where downstream has to guess.
7. **needs the code re-read (slowest per fix, hence last — not least important)** — `row_key` that cannot locate a row; `fields` naming a column no parameter can
   supply; a write op with empty `effects`; an entity with no `pk`. **Last because they are the
   slowest per fix, not because they matter least** — the `row_key` and `fields` ones are the two
   largest by number of repos affected in the whole corpus. Each of their entries tells you which
   of several causes it is; the fix differs per cause, so read that clause before you start.

**Counts are full counts; examples are a sample.** When a line says "this rule has N occurrences" and shows
you eight, fixing those eight has fixed eight of N. Use the same judgement on the rest.

## What to do about missing edges

Go through that list and, for each op, **look at the code again** (`ref_code` and `locator` are in your output; the repo is still at the same path) and do one of two things:

1. **Emit its depth-1 edges** — what it directly calls (`triggers`), what state must already hold before it runs (`requires` + `needs`), what guards it (`guards`). Same rules as before: direct one hop only, never nest, `evidence` gives file:line.
2. **Record that it genuinely has none.** Some ops really are standalone — an unguarded write with no preconditions and no downstream call. If that is the case, say so **explicitly** by adding it to a top-level array. **There are two of them, and they are not interchangeable:**

```json
"no_edges":  [{"id_local": "Tag.rename",           "why": "no auth middleware on this route, no pre-checks, calls nothing"}]
"no_guards": [{"id_local": "Post.view_count_bump", "why": "public route, no auth plug and no policy call (routes/api.js:44)"}]
```

| array | use it when | do NOT use it when |
| --- | --- | --- |
| `no_edges` | the op has **no edge at all** — calls nothing, requires nothing, is guarded by nothing | it has any edge |
| `no_guards` | the op **does** have edges (typically a `triggers`) but **none of them is a `guards` / `requires` edge carrying `needs`** — i.e. you looked for the wall and there is none | it has no edges at all → that is `no_edges` |

They are **mutually exclusive**: an `id_local` belongs in at most one of them, never both.

⚠ **`no_edges` alone does not clear this repo.** The checker measures two coverages, and the report above prints both. An op that got a `triggers` edge but no wall is **covered** by the first number and **silent** on the second — `no_edges` cannot hold it (it has edges), so without `no_guards` there is nowhere to record "I looked and there is no wall". Measured: **271 mutating ops (8%) sit in exactly that hole.**

**Do not skip an op silently.** Every id in the list above must end up as the `subject` of at least one edge, or in `no_edges`; and every op that has edges but no wall must be either given a `guards`/`requires` edge with `needs`, or listed in `no_guards`. This is the same discipline as `"constraints": []` vs omitting the field: *"I checked and there is nothing"* and *"I did not look"* must be written differently, because downstream cannot tell them apart otherwise — and right now it cannot tell whether this repo is genuinely edge-poor or whether the first pass simply ran out of budget.

### The shape of a wall (`needs`)

Several of the violations below are about `needs`, so the shape has to be here rather than only in
your first message. A `guards` / `requires` edge carries its test as `needs`: a **list of AND-groups**
(one level of DNF — `[[A, B], [C]]` reads *(A and B) or C*), and each element is one State:

```json
"needs": [[{"entity": "Membership",
            "scope":  [{"col": "user_id", "op": "eq", "value": {"ref": "$actor.id"}},
                       {"col": "role",    "op": "in", "value": {"lit": ["admin", "owner"]}}],
            "card":   "exists"}]]
```

Read it as **"rows of `entity` matching `scope`, counted by `card`"**. `card` is `"exists"` /
`"not_exists"` / `{"op": "gte", "n": 1}`. Two things the checker keeps catching:

- **one level only.** `[[A],[B]]` is DNF; `[A, B]` is accepted and read as a single AND-group; a
  nested `[[[A]]]` is flattened and reported. If you meant OR and wrote it flat, you silently get a
  **stricter** wall than the code has.
- **`op` and `value` come from the closed vocabularies** you already have in your first message
  (`## The condition language`). An operator outside the table is a hard error, never silently false.

The `hints` on each entry are **evidence, not conclusions** — they tell you where to look first. A hint can be wrong; if you read the code and there is no guard there, `no_edges` with that reason is the correct answer.

## If the violations mention `enum` or `lifecycle`

These two describe the same thing — the set of values legal in one column — so they have to agree. The contract's own example fills both, with identical values:

```json
{"name":"status","type":"text","enum":["draft","published","archived"],"default":"draft"}
"lifecycle":{"col":"status","initial":"draft",
             "states":["draft","published","archived"], "transitions":[…]}
```

Emitting `lifecycle.col = C` is itself an assertion that `C` is a closed set. Leaving `C.enum` empty, or filling it with different values, is a contradiction **inside your own output** — no code reading is needed to see that something is wrong, though you do need the code to decide which side is right.

It matters because one consumer seeds rows from `columns[].enum` while another compares that column against the literals baked into guards and filters. When the two disagree, rows land in the table but are **invisible to every read path**, and the file still looks perfectly fine. That has already happened: a status column seeded as `'available'` while the tools compared against `1`, and ~1800 rows silently vanished.

- **`the lifecycle column has no enum`** — copy the state values into that column's `enum`.
- **`enum disagrees with lifecycle.states`** — usually **display names on one side, stored codes on the other** (`states:["Unknown","Identified"]` vs `enum:["0","1"]`). Read the migration or model definition, find out **what is actually stored**, and put the stored values in *both*. Display names have nowhere to live in this contract — do not keep them in either field. **Fix the values; do not delete the `lifecycle`** — that entity does have a real state machine, and deleting it throws away the transitions.
- **`lifecycle.col points at a column that does not exist`** — either add the missing column to `columns`, or the lifecycle was invented and should go. A dotted path like `flags.classSelected` is not a column name.
- **`lifecycle is not a state machine (a placeholder or a nullable timestamp)`** — `["null","<datetime>"]` describes a nullable timestamp, not states. **This** is the case where you delete the `lifecycle`.

**Do not add `lifecycle` to entities that don't have one.** A column having an `enum` is not a defect — `visibility` / `role` / `type` are closed sets but not state machines. Only entities with a genuine status column get a lifecycle; the checker deliberately never flags that direction.

## Rules that still apply

- **Fix the contract violations as well**, not only the missing edges — same file, same pass. A repo is done when both lists are empty.
- **Keep everything you already produced** — do not drop existing edges, and do not reshape parts of the file nobody asked about. **But everything a violation names is in scope, and that includes structural changes.** This rule used to read "do not rewrite `impls`", which was written when this pass only added edges; most of what the checker now reports lives *inside* `impls`, and reading it as "leave the impls alone" is why whole classes of violation survived several rounds untouched. So: if a violation says an effect cannot locate its own row, the honest fix may well be that **the effect itself is wrong** — re-key it, or move a precondition read onto a `guards`/`requires` edge as `needs`, or delete an effect the operation does not actually have. **That last one is narrow, and it is the one that gets misread.** Deleting an effect — or a column out of a `sets` — is a claim that the operation *never writes it*. It is the opposite of "I cannot express this value", not a softer version of it. Measured on 2026-09-06: two repos answered a violation about unsayable `sets` values by deleting 55 of them, and 30 of those columns were `nullable: false` or read by another operation — including the column a `guard.auth` compares passwords against, so every account the register tool created could no longer log in. If the code does write the column, it stays, and what you cannot express goes in `note`. If a violation names a `schemas` field, write that field: `fk_to`, `on_delete`, `pk`, `enum`, `lifecycle` are all fair game **when a violation names them**. What stays off limits is everything the checker did *not* flag — leave that byte-identical.
- **Write the same file, `__OUT__`**, and overwrite it as you go — do not hold results until the end. **This job has a wall-clock limit and you will be killed at it without warning.** A file on disk is insurance; a perfect answer still in your context is worth nothing. Measured on 2026-08-26: two 90-minute rounds on a 214KB repo produced **zero bytes** because the agent planned the whole rewrite before writing any of it — while a repo that overwrote after each group cut its violations 461 → 44 in the same budget. Fix a batch, write, fix the next batch, write again.
- Same non-interactive rules as before: nobody will answer questions, there is no notification when a subagent finishes, and anything that looks like an interruption is the upstream dropping the connection — re-dispatch the ones that did not come back rather than asking.
- If the list is long, dispatch subagents by entity group as before, **in waves of 3–4**, and merge after every wave.
- **Write exactly one file: `__OUT__`.** Helper scripts are fine — for bulk edits they are safer than editing by hand, because they rewrite the file in one go instead of leaving it half-modified if something interrupts. But put them under `/tmp/collect_work/`, not in the output directory and not next to the repo. No `*_fixed.json`, no `*_bak`, no partial dumps beside the real output: anything that lands in the output directory gets read downstream as if it were a collected repo.

When you are done, give a one-line summary with **four** numbers: how many edges added, how many ops recorded as `no_edges`, **how many contract violations you started with and how many remain**, and whether any op in the list you could not resolve either way.

**If you leave a class of violation unfixed, say which class, how many, and what specifically stopped you.** "Tier 7, inherently slow" is not a reason — it restates the tier. Running out of wall-clock is a real reason: say so, and say which ones you did get to. "It does not affect the coverage metrics" is not a reason either: the violation count is its own number, and it is the one that decides whether this repo is done.
