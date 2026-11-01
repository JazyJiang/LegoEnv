The `spec.draft.json` you produced has been run by a deterministic probe. Below is what it
found. **These are results of actual execution, not opinions.**

**This is the only feedback round.** There is no next one. That is deliberate: more rounds push
towards making the report look clean rather than making the spec true. So —

- Whatever you cannot fix is **written down as residual, not silently dropped**. Saying honestly
  "this one is wrong and here is why" is worth more than bending the spec into something that
  merely passes. A spec that passes for the wrong reason is the worst outcome, because nobody
  opens it again.
- Anything marked **`← [REGRESSION]`** was **fine in the candidate spec and broke when you edited
  it**. Those first. (Matched by the operation's `id_local`, so tools whose `_evidence` you removed
  cannot be matched and simply carry no marker — absence of the marker is not evidence of
  innocence.)
- Lists here are truncated where they say so, and the note tells you **how many were actually
  printed out of how many exist** (`40 shown of 137`). The number in `counts:` is always the full
  one. If a list carries no such note, it is complete.

**The hard gate this repo must clear** (miss it and the whole repo is dropped, not just a tool):
`runtime.Env(spec)` builds · at least one write tool actually changed the world · the spec contains
at least one read/search tool. Do not delete your way below that line.

## What the pre-pass changed in your spec before any of this ran

__SEAL__

## L0 — structure (not run; checked against your own declarations)

Two lists, and they mean different things. **ERR** breaks the spec — fix it. **WARN** is a smell:
sometimes correct, so use your judgement and say why if you leave it.

__L0__

## L1 — does it build

Two checks: `runtime.Env(spec)` constructs, and the rows the probe put in the world satisfy the
column declarations you wrote (`nullable: false`, `fk_to`, `pk`).

**The rows are not yours.** The probe replaces `seed_state` with its own synthesised rows before
running — your seed rows are used later, by a different stage, and are not what failed here.
Editing `seed_state` therefore changes **nothing here**. What each failure actually means:

| L1 says | it means |
| --- | --- |
| `runtime.Env(spec) failed to build` | the spec's shape is wrong. The exception text is the diagnosis; nothing else on this page ran. |
| `X.y is declared nullable:false but N rows came out empty` | **the declaration is unsatisfiable** — nothing in the spec can supply that column. Either it is not really required, or the column it depends on is missing. |
| `X.y has N dangling FK values` | one of two things, and the message says which: **`Y` produced no rows at all** (usually `Y` itself is unsatisfiable, or the two tables reference each other in a cycle), or **`fk_to` names a column `Y` does not have**. |
| `the unique(...) constraint is already violated` | the columns you declared unique cannot actually be made distinct — usually a `unique` copied onto a column that is not one. |

Fix the declaration, or the entity it points at.

This one is the hard gate. If L1 is FAILED, L2 and L3 did not run at all, and the whole repo is
dropped — not just this tool.

__L1__

## `bad_exec_spec` — the runtime cannot read this tool's `exec_spec`

If any tool is labelled `bad_exec_spec` below, that is **not** a probe limitation. The probe walked
your `exec_spec` the same way the runtime does and hit an `AttributeError`/`TypeError`. **The runtime
raises the same exception**, so the tool is dead: every call to it returns an error, forever.

Almost always this is a structured field collapsed into the scalar inside it — the pre-pass had
filled it correctly and it got overwritten. For example `exec_spec.target` must be
`{"entity": "Server", "lookup_by": {...}}`; writing `"Server"` loses the row-locator and makes the
field unreadable.

Restore the shape the pre-pass produced. If you deliberately changed it, change it to the correct
**object** form, not to the name of the thing.

Note the two legal shapes you may be tempted to "fix" but must NOT:
- `exec_spec.fields` may be `["col_a", "col_b"]` (values come from the args) **or**
  `{"col": <value|{"$arg": "..."}>}`. Both are correct.
- a State predicate's `card` may be the string `"exists"` / `"not_exists"` **or** `{"op":…, "n":…}`.

**The condition language** — you already have the full table in this conversation (the `## The condition language` section of your first message). Do not work from memory of a shorter one: this file used to carry a flattened 14-operator list with no State wrapper, no Value vocabulary and no DNF, and an agent seeing both would have had two different tables in the same session.

## L2 — real drive (logged in, then every tool called once; classified by world-state diff)

__L2__

## L3 — walls (for each wall you declared, one deliberate violation)

`counts` keys read `<kind>/<verdict>`.

| kind | the wall being tested |
|---|---|
| `requires_auth` | the tool refuses when nobody is logged in |
| `precondition` | a State predicate you declared under `guards.preconditions` |
| `unique` | a uniqueness constraint on the target entity |
| `transition` | a status/state machine edge (`from` → `to`) |
| `required` | a required argument is missing |
| `probe_error` | **not a wall** — see below |

| verdict | |
|---|---|
| `wall_hit` | the violation was refused. The wall works. |
| `wall_missing` | the violation went through. Either the guard is on the wrong tool / in the wrong shape, or that wall does not exist in the real code — **if it is the latter, delete it.** |
| `unverifiable` | the probe could not build the violating scenario. **Read the reason.** |

`probe_error` is **not** in the same family as `unverifiable`. It means the probe crashed while
walking that tool's `exec_spec` — exactly like `bad_exec_spec` above, and the runtime walks it the
same way, so it will crash there too. That is a defect in the spec, not a limit of the probe.

__L3__

## Coverage

__COVERAGE__

## What you need to do

Go through them one by one, edit `__OUT__` (still that one file only), then say in one line what
you changed.

**The judgement is yours; the probe only supplies evidence.** A few classes deserve real thought:

- **`no_op`** — the call succeeded and the world did not change. Across the corpus this splits
  three ways, and they are fixed differently, so check which one you are looking at **before**
  touching anything:
  1. **The columns the tool writes are not on its panel** (26% of cases measured). `exec_spec`
     writes `position` while `input_schema` only offers `state`; or it writes six account
     columns while the panel takes `UserId` and `NewPassword`. Nothing can supply the value, so
     nothing is written. This one is squarely yours: either add the parameter (named after the
     real interface) and bind it, or narrow `fields` to the columns the caller can actually
     supply and move the rest into `set` / `set_on_create` with their values.
  2. **The columns and the panel do line up** (57%). Then the write is probably fine and the
     probe could not stage a row for it to hit — look at `lookup_by` / `row_key` and at the
     preconditions, and see whether the target row can exist at all in a fresh world. If it
     genuinely cannot, say so; do not invent a value to make the probe green.
  3. **`exec_spec` has nothing to write at all** (17%) — no `fields`, no `set`, no
     `set_on_create`. That is upstream: the mined effect never said what this operation writes.
     Record it as such rather than inventing a write.

  **Deleting the tool, or demoting a write to a read, is not the default answer to `no_op`.**
  The tool is in the spec because the mined product carries evidence that the operation writes
  something; a green probe bought by removing the tool is worth less than a red probe that
  tells the truth. Demote only when reading the evidence shows it really never was a write.
- **`wrong_entity`** — something changed, but not the table you declared. The verifier will check
  what you declared, so either the declaration or the `exec_spec` has to move. Do not leave it.
- **A wall with no refusal text.** The L2 section lists these when there are any. `guards.preconditions` with no `messages` and no per-precondition `message` means the runtime answers a refusal with its own generic string — not in the language the caller reads, and silent about *which* wall stopped it. The wall text is the training signal; section 4 of your first message has the shape. This is an addition only: never remove a wall to make the line go away.
- **`wall_missing`** — you declared a wall and the deliberate violation was **not** refused.
  Either the guard sits on the wrong tool or is written in the wrong shape, or that wall does not
  exist in the real code. **If it's the latter, delete it.** A fake wall is worse than no wall:
  downstream agents will hurl themselves at something that isn't there, and the task dies.
- **`error`** — the call failed. Sometimes that's the spec; sometimes the probe could not
  synthesise a sensible argument (FK ids, enum values, formats). Read `ref_code` before rewriting
  anything.
- **`unverifiable`** — the probe could not construct the violating scenario. **Read the reason
  printed next to it before deciding.** "no duplicable row in the seed" / "could not build a state
  outside `from`" really is the probe's limit — leave those alone. But an exception name
  (`TypeError`, `KeyError`) is usually a shape you wrote, and `probe_error` always is.
- **`guarded` and `empty` are NOT defects** — and together they are usually the biggest slice of
  `counts`. `guarded` means the tool refused because a wall you declared was not satisfied (not
  logged in, a precondition unmet): **that is the wall working.** `empty` means a read returned
  nothing on the probe's one-off synthetic seed, which says nothing about the tool — real data
  arrives downstream. Do not weaken a guard or widen a `scope` to make these numbers move.

  **The one exception, and it inverts everything above:** if L2 opens with `!! LOGIN FAILED`, the
  probe never got in, so *every* auth-gated tool is `guarded` for that single reason. A pile of
  `guarded` then means the opposite of a healthy spec — it means nothing below it was really
  exercised, and the repo will miss the hard gate ("at least one write tool actually changed the
  world") no matter how clean the rest looks. Fix `auth` and the login tool first; everything
  else on that page is unreadable until you do.
- If you cannot fix something, or you think the probe got it wrong, **write the reason in your
self-report**. Do not bend the spec into something that merely passes — a spec that passes for
the wrong reason is worse than a failing one, because nobody looks at it again.
