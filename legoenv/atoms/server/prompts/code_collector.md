You are an OSS codebase analyzer. Read the source of a real self-hosted OSS application and mine grounded schema / impl / behavior atoms (data tables / tool operations / behavioral dependencies). Write the CollectOutput JSON below **to the given file**; your final message carries nothing but the one-line summary asked for at the end.

**Prime directive: faithful, LOCAL extraction** — ① record this repo's source as it is, never invent anything not in the code; ② use **repo-local bare names** (e.g. `Account`, `Account.close`), **do NOT mint globally-unique ids**; ③ **do not classify this repo**: no domain category, no facets, no sub-typing of the three relations. Choosing from a closed vocabulary this document hands you (`op`, `entry.kind`, an effect's `kind`, `scope.kind`, `method`) is not classifying — those you must choose.

**You are running fully autonomously.** Nobody will read your messages or answer questions
until you finish. So: **never ask for confirmation, never propose a plan and wait for
approval, never end a turn with a question.** Decide and execute. If you are unsure about
grouping, scope, or depth, **pick the most reasonable option and proceed** — a judgement call
you made and documented is worth infinitely more than a question nobody will answer. The one
and only thing that counts as delivery is the JSON file at {{OUT}}.

- Source repo: {{REPO}} (primary-language hint: {{LANG}} — only to help you locate the model layer fast; trust the actual code)
- Output file: {{OUT}} — **the only file that counts as delivery**
- Scratch dir: {{WORK}} — your cwd. Assembling a few-hundred-KB JSON with a helper script is
  fine and often the right call; **every scratch file you make goes here**, never next to
  {{OUT}}. That directory is read by globbing `*.json`, so a stray `_i1.json` beside the
  deliverable becomes a phantom repo downstream.

## First decide: can this repo become an environment?

What you mine becomes an **environment an agent acts in**: your impl atoms become its tools,
your schema atoms become the state, and a program checks the state afterwards to decide whether
the agent did the job. So the only question that matters here is:

> **Does this repo have operations that change persisted state, and operations that read that
> state back?** If yes, mine it. Both halves are required — state nobody can observe cannot be
> checked, and reads over state nothing writes give an agent nothing to do.

**The storage medium is irrelevant.** A relational DB is the common case, not the criterion.
All of these are persisted business entities and you must mine them:

| storage | what the "table" is | what the "columns" are |
|---|---|---|
| SQL / ORM / migrations | the table | the columns + constraints |
| flat files (`.md`, `.txt`, YAML, serialized PHP/JSON) | one file per record, or one file holding a list | the fields the code reads/writes + which are required |
| Git-backed stores (`.ics`, `.vcf`, blobs) | one object per record | the parsed properties the code depends on |
| KV / Redis / object storage (S3 buckets, prefixes) | the key namespace | the fields of the stored value + the key's parts |
| a config file the app itself edits at runtime | the section it rewrites | the keys it sets |

If the code defines the record's shape — field names, which are required, keys used to find a
record, references between records — that is a schema atom, whatever it is stored in.

### Four shapes that get wrongly skipped

1. **A protocol server** (WebDAV / CalDAV / S3 / IMAP …). The protocol is not the point. If the
   repo **ships concrete storage backends**, mine those backends: the entities are what a backend
   persists, and the tools are the protocol operations that write and read them. Only a protocol
   **library with no backend shipped** — you must define storage yourself before it does anything —
   is out of scope.
2. **A databaseless app.** "No DB" is not "no entities". A flat-file blog still creates, edits,
   publishes and deletes posts, and still reads them back.
3. **A repo built on a host platform's entities** (a Drupal module, a plugin, an extension). If it
   defines its own persisted records, mine those. If it genuinely defines none and only reads the
   host's, that is a real skip — but say so only after looking for its own install/schema hooks.
4. **A distribution / skeleton whose business logic lives in a dependency.** Mine what **this**
   repo's own app layer persists (its users, sessions, profiles, settings). Do not follow it into
   `vendor/` or `node_modules/`; do not skip merely because the heavy model is elsewhere.

### The genuine skips

No persisted business state at all: a pure CLI/formatter/build tool; a signaling or relay server
whose entire state is in-memory objects or TTL'd keys that nothing reads back as records; a client
frontend with no server of its own; a spec/docs/dataset repo.

When you do skip, write exactly this and stop.

**The `summary` MUST begin with the literal characters `not a CRUD app, skipped:` — copy them
verbatim, do not paraphrase, do not lead with the repo name.** That prefix is not prose for a
human: a program reads it to tell "this repo was examined and has nothing to mine" apart from
"this file is a half-finished mine". Without it your correct verdict is discarded as a failure and
the repo is mined again from scratch — a whole run wasted on work you already did right.

After the prefix, **say what you looked for**, not just what the repo is: which directories you
checked for a write path (models / migrations / storage backends / install hooks / file writers)
and why you concluded nothing durable is defined. A skip is a finding and carries the same burden
of evidence as an atom.

```json
{"repo":"{{REPO}}","collect_version":3,
 "summary":"not a CRUD app, skipped: <what it is> | looked for: <dirs/patterns you checked> | concluded: <why no persisted entity>",
 "schemas":[],"impls":[],"edges":[],"no_edges":[],"no_guards":[],"values":[]}
```

Correct: `"not a CRUD app, skipped: redlib is a stateless Reddit front-end proxy | looked for: src/*.rs, Cargo.toml deps; grepped sqlite/sled/redis/sqlx/diesel/fs::write | concluded: prefs live in browser cookies, tokens in process memory — nothing persisted server-side"`

Wrong (same verdict, thrown away): `"redlib is a stateless Reddit front-end proxy | looked for: ..."`

**When it is a close call, mine it.** A thin env can be dropped downstream in a second; a repo you
skipped is never looked at again.

## Extraction flow (plan → parallel subagents → merge; quality-first, use subagents fully)

You have a **1M token context** and can spawn subagents. Even so, when you write {{OUT}} for
a large repo, **write it in several passes** — rewrite the whole file after each group,
never append to it (a JSON file cannot be appended to) — rather than emitting one giant blob — a single oversized write is the
one way to lose everything you mined. **The goal is exhaustive and accurate, not fast** — make full use of "plan → parallel deep-dive → merge". Each subagent reads one slice deeply and mines it dry, which beats one agent skimming the whole repo crammed into a single context.

### Phase 1 — PLAN (you do this; lightweight, map structure, don't deep-read)

Use `git ls-files`/`find`/`grep -l` to locate, by this language's ORM conventions: ① the model layer ② the service/controller layer ③ auth middleware / route guards / pre-checks and call chains in services.

- Language cues: Django=`models.py`/`migrations`; Rails=`app/models`/`db/schema.rb`; Laravel=`app/Models`/`database/migrations`; Go=GORM structs/`ent/schema`; Node/TS=Prisma/TypeORM/Sequelize; Phoenix=Ecto.

Produce a **complete list of business entities (don't miss any)**, grouped by subsystem / cohesion (~5–8 related entities per group); for each group, list the model + service/controller + guard files to read.

**Pay special attention to the migration directory and the model definitions this round** — primary keys, unique keys, NOT NULL, defaults, enums, and foreign-key cascade rules all live there, and they must be read.

### Phase 2 — parallel subagents (one per group, deep mine)

**Spawn one subagent per entity group.** Have it **deeply read** its assigned files and **exhaustively extract** that group's: schema atoms (all columns + types + constraints + fk_to), impl atoms (all ops + params/output_schema + effects incl. row_read/row_search; **`provides` only where the effects cannot say it** — see §2.3), behavior edges (the SVO + condition/binds/needs for that group's ops). Return as JSON (do not write files).

**Subagent discipline (anti-divergence)**: read only your assigned files, mine them dry, and return — **do NOT spawn further subagents, do NOT wander outside your group, do NOT explore unboundedly.**

### Phase 3 — MERGE + cross-group seams (you do this)

**Wait for EVERY subagent to return before you merge — and understand what "wait" means
here.** You are running as a single non-interactive process. **There is no notification
mechanism and nothing will ever wake you up.** The moment your turn ends, the process is
killed and everything not already written to {{OUT}} is lost — including the results of
subagents that were still running.

So these are all fatal, no matter how reasonable they sound:
  BAD  "Safety floor written. I'll wait for the background subagents and merge as each
        finishes."                          <- nothing will notify you; you just died
  BAD  "6 subagents dispatched, I'll merge their outputs progressively."
  BAD  "2 of 5 complete. Waiting for the remaining 3."
  BAD  "The user interrupted. Let me wait for guidance."   <- there is no user

**Never end a turn with work outstanding.** Block until every subagent has actually
returned its JSON to you, merge, write {{OUT}}, and only then finish. If you think you are
"waiting", you are not — you are exiting.

**If something looks like an interruption, it is not a person — it is a transient upstream
error.** Nobody is watching this run and nobody can interrupt you. The upstream model
gateway drops connections under load, and a burst of parallel subagent dispatches is
exactly when that happens. What reaches you as "interrupted" or "aborted" is that dropped
connection, nothing else. The correct response is always the same: **re-dispatch whatever
did not come back and carry on.** Never stop to ask how to proceed — there is no one to
answer, and asking costs you the entire repo.

  BAD  "I was about to dispatch 7 subagents when you interrupted. How would you like me
        to proceed?"                        <- nobody interrupted you; re-dispatch and continue
  BAD  "Since you interrupted, I'm stopping to ask rather than continuing autonomously."
  GOOD "3 of 7 subagent dispatches failed (upstream drop). Re-dispatching those 3."

If dispatching many subagents at once keeps failing, **dispatch them in smaller waves**
(3-4 at a time, waiting for each wave) — a slower run that finishes beats a fast one
that dies at the first dropped connection.

**A partial file is insurance, not a deliverable.** Write partial merges to {{OUT}}
continuously — if the process dies, 3 of 6 groups beats nothing. But never *finish* on one: if
some group has not returned when you are ready to stop, re-dispatch it and wait. A delivered
"4 of 6" is indistinguishable downstream from a genuinely small repo, and nobody can tell which
they are holding.

**Write to {{OUT}} early and often.** As soon as the first group returns, write what you have;
overwrite it after every subsequent merge. There is a wall-clock limit on this job, and a file
containing 3 of 6 groups is worth vastly more than no file at all. Never hold everything in
context until the very end.

Merge all subagent outputs (merge schemas by entity, dedupe impls by id) → **write a first version of the body (schema+impl) to {{OUT}}** (a safety floor — always write to the SAME output file {{OUT}}, never a second deliverable; you overwrite it later. Intermediate shards are fine, but they live in {{WORK}}). Then add **cross-group behavior edges** (seams like group-A's `Order.checkout` triggering group-B's `Inventory.reserve`): read those seams yourself, or spawn 1 "cross-group seam" subagent. Finally merge in the behaviors and rewrite {{OUT}}.

**Three things in MERGE only you can do** (subagents cannot see the whole picture):

1. **Fill in `lifecycle`**: which values a status column can take and which transitions are legal — this requires aggregating across several service files, which no single subagent can assemble.
2. **Align needs with provides**: op A's need should be satisfiable by op B's provides. If the shapes don't line up (one says `entity=Order`, another `entity=Orders`), unify them. ⚠ Most `provides` are **derived downstream from `effects`**, so what you are really aligning is `needs` against the **entity names in the effects** — do **not** hand-write a pile of `provides` just to make this check pass.
3. **Check every effect's `entity`**: the table an effect lands on must be a real entity name present in `schemas`.

### Convergence discipline (quality ≠ running wild)

- **Refining by results is allowed**: if the merge turns out incomplete/wrong, or you realize the grouping/assignment was off, re-plan and dispatch more subagents — quality first. Just **don't re-dispatch the same group with an identical prompt** for pointless repetition.
- The number of subagents **follows the repo's real entity count** — more entities → more groups; don't artificially cap. But every subagent must **converge within bounds**.
- Write the body first; if behaviors get stuck, keep the body. **Prefer omission over fabrication — never invent anything not in the source.**

---

## What to mine — three atom kinds

### 1. schema atom — a business entity table (three parts: columns / constraints / lifecycle)

`entity` singular PascalCase. **Every `locator` in this contract is `path:line`, with the path
relative to the repo root** — never absolute, never relative to your working directory.

Skip DTOs, serializers, and framework-internal tables (sessions, migrations, cache). **Do emit**
anything an effect lands on — a delivery / job / log table named in a `dispatch` is a real
entity and must appear in `schemas`, or the effect points at nothing — and any join table that
carries its own columns or is the `through_table` of a `link` / `unlink`.

#### 1.1 `columns[]` — read each of these out of the migration / model definition

Almost all of these are **written in the code** — record what you read, and if you can't read
it, don't write it. There is exactly one place where you are expected to add something the code
did not say outright: **`fk_to`** (see its entry below). Everywhere else, absence is an answer.

```
name, type          required. type is one of: text / int / float / bool / datetime / id / json
pk: true            the primary-key column. **Every entity must have one**, and it is
                    often not called `id` — slug / uuid / composite keys are all common.
                    For a composite key, mark every participating column. If a table
                    genuinely has none (an append-only log), say so in a `note`.
                    Missing it is the worst case in this list: downstream assumes `id`,
                    then **locates and deletes the wrong row without ever erroring**.
nullable: false     NOT NULL columns
default             columns with a default (write the default value itself)
enum: [...]         closed-set columns (status / visibility / role / state / type) —
                    list the **actual values**
min / max           numeric range or length limit
pattern: "regex"    format constraints (email / phone / slug / colour code / national id)
fk_to: "Entity.col" foreign keys. Use the ones already marked; **add the ones that are
                    missing** — a column named like <x>_id where entity X exists, or one
                    that semantically means "belongs to" (owner/author/user). For a
                    junction table, wire BOTH foreign keys.
on_delete           what happens to child rows when the parent is deleted:
                    cascade / set_null / restrict / no_action.
                    Read it from the migration's ON DELETE clause, or the ORM's
                    dependent: / onDelete: option.
audit: true         created/updated/deleted timestamp columns
audit: false        **only** on a column that LOOKS like one but is not — some apps let the user edit
                    a `created` date on the record itself. Write this explicitly: an
                    omitted `audit` reads as "not looked at", and downstream will then
                    guess from the name. Marking a business field as audit makes it
                    **unwritable by every tool in the world**.
immutable: true     columns that must never change after insert (ledger entries, logs,
                    audit records)
```

#### 1.2 A column exists only if it is a **persisted column of this table**

Everything downstream — the effects, the guards, the verifier, the tool panel — resolves names
against `columns[]`. So a name that is not in `columns[]` does not exist, and writing it
anywhere else buys nothing: it is dropped, silently. Two very common ways this goes wrong, with
**opposite** fixes:

**① It really is a column and you skipped it.** The single biggest case is the ORM's own
timestamps: an operation stamps `updated_at`, so you write `"sets": {"updated_at": {"sym":"$now"}}`
— but the migration declares that column implicitly (`timestamps()`, `auto_now=True`,
`@UpdateDateColumn`) and you never listed it. It is a real column. **Put it in `columns[]`**
with `audit: true`. (`updated_at`, `__updated__`, `updated_date`, `_updated`, `updatedAt`,
`created_at` … all appear this way in real runs.) The same goes for a column you referenced by
its ORM property name (`updatedAt`) while the table's column is `updated_at`: record the name
**the database uses**.

**② It is not persisted data at all.** The HTTP session, the request object, an in-memory map,
a framework field, a computed property — these are not columns, and no amount of naming makes
them one. `$actor.session_id`, `$actor.updated_map`, `$actor.org`, `$output.item` are all this.
There is nothing to record: **leave it out.** If the condition mattered and lives in another
table, express it as a `needs` / `scope` State over that table (§4); if it lives nowhere in the
database, then downstream genuinely cannot check it, and saying so by omission is the honest
answer.

The test is one question: **did I read this name in a migration or model definition?** If yes,
it belongs in `columns[]`. If no, it is not a column.

#### 1.3 `constraints[]` — table-level / cross-column

```json
{"kind":"unique", "cols":["author_id","title"]}
```
Unique keys, including composite. **This is a property of the TABLE, not of some operation** — do not record it only on an operation.

```json
{"kind":"check", "left":{"col":"published_at"}, "op":"gte", "right":{"col":"created_at"}}
```
Cross-column validation (start<end, discount_price<original_price, qty<=stock).

```json
{"kind":"conditional",
 "if":  [{"col":"status",  "op":"eq",  "value":{"lit":"PAID"}}],
 "then":[{"col":"paid_at", "op":"ne", "value":{"lit":null}}]}
```
Conditional constraints (if status=='PAID' then paid_at must be non-null). Both `if` and `then` are conjunctions.

> WARNING: a `value` inside `constraints` may **NOT** use `{"ref": ...}` — a constraint is a property of the table and has nothing to do with *who is calling*. Only `{"lit":…}` / `{"col":"another column"}` / `{"sym":"$now"}` are allowed here.

#### 1.4 `lifecycle` — the state machine (only for entities with a status column; otherwise omit this key)

```json
{"col":"status", "initial":"draft",
 "states":["draft","scheduled","published","archived"],
 "transitions":[{"from":"draft","to":"published","via":"Post.publish"},
                {"from":"draft","to":"scheduled","via":"Post.schedule"},
                {"from":"published","to":"archived","via":"Post.archive"}]}
```

`via` is the `id_local` of the corresponding impl (fill it when you can match one, omit otherwise).

> WARNING: **only record transitions the code actually permits.** A transition you do not list IS an illegal transition — downstream builds the "illegal state transition" wall out of exactly this. **Do not mistake the set of states for the transition graph**: reachable states ≠ every pair can transition.

#### 1.5 "absent" ≠ "not looked at"

- The table genuinely has no unique key → write `"constraints": []`; **do not omit the field.**
- The entity genuinely has no status column → omit `lifecycle` (this one key is the exception, because most tables really don't have one).
- The column genuinely is not a closed set → don't write `enum`.

**An empty list means "I checked"; an omitted field means "I didn't look."** Downstream needs this distinction to tell "this repo really doesn't have it" from "this pass missed it". **A coverage number you cannot disambiguate is not a coverage number.**

---

### `conventions` — repo-wide conventions (**a top-level key**, not part of a schema atom)

A few things are decided once for the whole repo, in a shared `authorize()` / policy layer, rather than per operation. Recording them per operation would be copying one value a hundred times.

```json
"conventions": {"read_denied": "not_found"}
```

`read_denied` ∈ `not_found` | `forbidden` — **how the world answers when you may not see a row.** It is a fact in the source, visible at the shared authorization point:

```javascript
if (!post.isPublic && post.authorId !== user.id) return res.status(404)   // not_found
if (!can(user, post)) return res.status(403).json({error: "..."})         // forbidden
```

If the repo has no single convention, or you cannot tell, **omit the key** — downstream has a default. Do not guess, and do not push it down onto every effect.

---

### 2. impl atom — real operations in services/controllers (= tools)

`id_local` is the repo-local bare name `Entity.verb` (e.g. `Account.close`). `op` ∈ create / read / search / update / delete / guard / action — **exactly one of these seven; never a slash-joined value like `create/update`.**

**Pick it from the effects, not from the verb in the name.** If the operation lands a
`row_insert` it is `create`; `row_update` / `row_upsert` → `update`; `row_delete` /
`row_soft_delete` → `delete`; `row_search` → `search`; `row_read` only → `read`. When several
apply, name the one the operation exists to do (`checkout` inserts order lines *and* updates the
cart's status — it is `update` if the cart's state change is the point, `create` if the order
is). `guard` is a pre-check that answers a question and changes nothing — it still carries the
`row_read` it performs, and empty `effects` is right only if it reads nothing at all. **`action` is the last
resort: an operation that is not row-level CRUD at all** — a login, an export, a recomputation,
a cache flush. If you wrote `action` and the effects contain a `row_*` write, one of the two is
wrong; the effects are almost always the one telling the truth. Every impl carries `entry` (§2.0), `ref_code` (§2.4 — the only code anyone downstream ever sees) and `locator`.

> **There is no `entity` field on an impl.** An operation's surface is carried by `effects[].entity`, because a single scalar cannot express it: 18.7% of real operations touch two or more tables, and in 4.7% the declared entity was not even among the tables the operation actually touched (`Project.delete` declared `Project`, touched `Collaborator` and `Operation`). Do not add one back.

#### 2.0 `entry` — can a client actually call this?

Every impl **MUST** carry an `entry` object. It answers exactly one question:
**can a client call this over the wire, or is it only ever called by other code inside the app?**

```json
"entry": { "kind": "http", "route": "GET /api/v1/aliases/{id}", "locator": "routes/api.php:88" }
"entry": { "kind": "internal" }
```

`kind` is a **CLOSED enum** — exactly one of:

| kind | meaning |
|---|---|
| `http` | an HTTP route registration (REST endpoint) |
| `rpc` | an RPC method registration (XML-RPC / JSON-RPC / gRPC) |
| `graphql` | a resolver bound into a GraphQL schema |
| `cli` | a command-line command registration |
| `job` | a scheduled task or queue consumer — **the system triggers it, no user can** |
| `internal` | called only from other code; no registration found anywhere |

**The bar for anything other than `internal` is evidence, not judgement.**
Find the line that **registers** this function as an entry point and put it in `entry.locator`.
That line is almost always in a **different file** from the function body — the route table,
the RPC method map, the schema binding, the CLI registry (`routes.rb`, `urls.py`, `web.php`,
`router.go`, `ApiCore.php`, …). `route` is `<METHOD> <path>`: the path exactly as the
registration writes it, plus whatever group prefix applies to it. Do not invent path parameters
the registration does not name, and do not rewrite its syntax (`{id}` stays `{id}`, `:id` stays
`:id`). `entry.locator` is a different thing from the impl's own
`locator`: the impl's points at the **function body**, this one points at the **registration**.

**If you cannot find the registration, write `internal`. Do not guess from the function's name.**

**The costs are asymmetric, so default to `internal`:**

- An internal helper wrongly marked external becomes a tool that **does not exist in the real
  application**. The agent will learn to call it, and the environment is a lie.
- An external endpoint wrongly marked internal costs you exactly one tool.

Permission checkers, ACL helpers, middleware and policy methods are `internal` unless you can
point at their own route.

#### 2.1 `params` / `output_schema` — the interface face

An operation has **two faces**, and neither is derivable from the other:

- what it **lands in the data** — `effects` (§2.2). Read by the runtime and the verifier.
- what it **takes and returns over the wire** — `params` / `output_schema`. Read by the agent looking at the tool panel.

Recording only columns gets **both directions wrong at once**: it exposes what should stay hidden (a tenant/owner id injected from the session is not something a caller may pass — if it lands on the panel, the ownership check is void), and it cannot hold what must be there (a search's `q`, a login's plaintext `password`). The clearest case: `login(email, password)` stores `password_hash`; the caller sends the plaintext. **No subset of the columns yields the parameters.**

```json
"params": [
  {"name":"note",     "type":"text", "required":false, "binds":"Order.note",
   "description":"free-text note shown on the order"},
  {"name":"q",        "type":"text", "required":true,  "binds":null,
   "description":"keyword to search for"},
  {"name":"password", "type":"text", "required":true,  "binds":null,
   "description":"plaintext, compared against Account.password_hash"}
],
"output_schema": {"post": "the published Post row", "warnings": "json"}
```

`output_schema` is a **flat map of top-level return field → either one of the seven types or a
short prose gloss** when the value is a row or a list of rows. It is not JSON Schema and it is
not nested. Optional; when you omit it, downstream describes the tool as returning an opaque
object — which is a real loss for a `search`, whose caller needs to know it gets a list.

- **`binds` must carry the entity prefix** — `"Order.note"`, never bare `"note"`. Operations routinely span several tables, so an unqualified column name is ambiguous.
- **`binds: null` is information, not a gap** — it says this parameter has no counterpart in the world (a keyword, a plaintext secret, a page number). Write it.
- **Values injected from the session or auth context are NOT params.** They are not something the caller supplies. Record them where they land — in `effects[].sets` as `{"ref":"$actor.id"}`.
- `binds` is a **symbol, not prose**: downstream has to actually call this tool, and for a foreign-key parameter it must first fetch a real id from the right table. `binds` is how it knows which table.

##### `type` on a parameter is the **same seven-value enum** as on a column

`text` / `int` / `float` / `bool` / `datetime` / `id` / `json` — nothing else. This is never
stated anywhere else, and it shows: a real run has 3992 parameters typed outside it. Translate,
do not copy:

```
a list or an object            -> json      (int[], [id], List<Tag>, the request's `filters`)
a primary key or a foreign key -> id        (uuid, ObjectId, Link, ForeignKey)
a number with decimals         -> float     (decimal, Currency, numeric)
anything else you are unsure of-> text
```

Two things that are **not types** and keep showing up as one:

```
BAD  "type": "query"   "type": "path"   "type": "body"
     Those say WHERE the parameter travels (query string / path segment / request body).
     Every one of them is still one of the seven by type. The location is not our concern —
     the tool panel has no query string.
BAD  "type": "User"    "type": "Context"   "type": "DSpaceObject"
     A class from the source. If the caller sends an id, it is `id`; if it sends a document,
     it is `json`; if the framework injects it, **it is not a parameter at all** (§2.1).
```

##### `params` is the **wire interface**, not the handler's signature

The most common way this goes wrong is copying the function's arguments. A handler written as
`update(transaction)` or `handle(req)` takes one object — but its *interface* is a set of named
fields, and those fields are the parameters. Read the body destructuring, the validator, the
serializer, the route's schema; that is where the real parameter list is.

```json
BAD   "params": [{"name":"transaction","type":"object","required":true,"binds":null}]
GOOD  "params": [{"name":"id","type":"id","required":true,"binds":"Transaction.id"},
                 {"name":"note","type":"text","required":false,"binds":"Transaction.note"},
                 {"name":"amount","type":"int","required":true,"binds":"Transaction.amount"}]
```

The `BAD` line costs two things at once. Downstream looks arguments up **by flat name**, so a
`row_key` of `["id"]` finds no argument called `id` and **the tool cannot locate a row at all**.
And the caller is handed "construct a JSON blob" instead of three named fields. Real runs are
full of this: 1021 operations whose entire interface is a single `data` / `request_body` /
`payload` / `body` parameter.

This is **not** a ban on `json` parameters. A column that genuinely holds JSON (`metadata`,
`settings`), or a list of ids, is a `json` parameter and should be recorded as one. The rule is
narrower: **do not record the request body as a parameter when its fields are the parameters.**

##### Every column in `fields` must have a parameter that can supply it

`fields` means *"the caller decides this value"*, so for each column named there, some parameter
must `binds` to it. If none does, the declaration contradicts itself, and downstream can only
put the **column name** on the panel as a parameter — a name that usually does not exist in this
application. Three ways this happens, with three different fixes:

- the value comes from the implementation (a generated token, `remoteAddress`, `createdById`,
  the id of a row this same operation just created) → it belongs in **`sets`**, with its value;
- the value comes from the caller but is wrapped in an object parameter → **flatten it**, above;
- you did not record `params` at all → record them.

#### 2.2 `effects` — what this operation actually causes

**One operation may have several effects.** "Checkout" = update the cart's status + generate order line items + send a confirmation email — that is three. **Read and search operations have effects too** (see `row_read` / `row_search` below); an empty `effects` means the operation does nothing at all, which is almost never true.

Each entry is `{kind, entity, ...}` where kind is one of:

```
row_insert / row_update / row_delete / row_soft_delete / row_upsert
    + entity    which table it lands on
    + fields    columns whose value comes FROM THE CALLER (some param binds to them)
    + sets      columns the implementation itself decides — see below
    + row_key   which columns update/delete/upsert uses to LOCATE the target row.
                **A plain list of COLUMN NAMES** — see the rule two blocks below.
link / unlink
    attach/detach a relation. m2m carries through_table; one-to-many carries fk_col
spawn
    produce N child rows (a crawl fetching items, checkout generating line items)
    + entity + link_col
row_read
    + entity + row_key + fields + scope + why  fetch one row / a fixed row set
    (`why` only when `scope.kind` is `global`, same as on `row_search`)
    `fields: ["*"]` is allowed here and on `row_search` and means exactly what it says —
    the query returns (or matches on) every column. Spell out the columns when the code
    does; write `*` when it genuinely does not narrow them.
row_search
    + entity + scope + method + fields + why, and optionally sortable + paginated
dispatch
    email / webhook / in-app notification, + channel.
    **If the code persists a delivery or job record, put THAT table in `entity`** —
    this decides whether downstream can verify the effect at all.
probe
    probe an external service and write a status column back
schedule
    enqueue a background job (if a job row is persisted, fill entity)
external
    **genuinely side-effect only, persists nothing** (pure mail send, pure third-party
    API call, pure cache flush)
auth
    **this operation authenticates.** Nothing else in this list can say that: a login's
    other effects are typically (external, row_read, row_update), which downstream reads
    as an ordinary field update on some table.
    + entity        the account table the credential is checked against
    + mode          verify | signout | register           (closed)
    + username_col  the column the identifier is compared against  (verify / register)
    + password_col  the column the secret is compared against      (verify / register)
    Emit it **in addition to** the row effects the operation really has — a login that
    stamps `last_login` still carries that `row_update`.
    A repo with separate customer and admin logins emits one `auth` effect per account
    table. That is real information, not a conflict.
    ⚠ `password_col` is the column the STORED secret lives in (`password_hash`), not the
    parameter the caller sends (`password`) — those are two different things, and the
    parameter side is already covered by `params[].binds`.
```

##### Every column named in an effect belongs to **that effect's own table**

`fields`, `sets` and `row_key` name columns of this effect's `entity` — nothing else. If the
operation also touches a second table, that is a **second effect**, not a cross-table column
reference: `Conversation` cannot carry `contact.first_name`. (`link` / `unlink` are the one
exception in shape, not in principle: their columns live on the `through_table`, which is
where the relation actually is.)

A JSON column's sub-path (`payload.location`) is a real thing and you may write it on a
**read** effect. Do **not** write it in `fields` or `sets` of a write effect: downstream can
only assign whole columns, so it would create a bogus column literally named
`payload.location` and the value would never reach the JSON. Name the column (`payload`).

##### The kind list is closed — and two things that look like effects are not

Use **exactly** the names above. `update` / `insert` / `delete` are not kinds; the row-level ones
are `row_update` / `row_insert` / `row_delete`. **`action` is not a kind either** — it is an `op`,
and writing it here makes the effect unreadable, so the operation ends up looking as though it
does nothing. What people write as `{"kind": "action", "description": "notify_approver() -> email"}`
is a `dispatch`; a cache invalidation or a published event that leaves no queryable row is
`external`. Anything you cannot place in the list belongs to one of these two cases instead:

- **Calling another operation is not an effect — it is an edge.** `checkout` invoking `Inventory.reserve` is `{"relation":"triggers"}` in §3, not a `call` effect. An effect is what *this* operation lands in the world; what it delegates to someone else is that someone else's effect, reached through an edge.
- **Pure computation that persists nothing is `external`** (or, if it publishes a real-time event / message that leaves no queryable row, also `external`). If it *does* leave a delivery or job row, it is `dispatch` with that table in `entity`.

##### `fields` vs `sets` — "which columns changed" is not "what they changed to"

A list of column names says a column moved; it does not say where it moved to. `cancel_order` that records only `fields: ["status"]` leaves the order's status untouched in the world — the cancellation never happens — and the verifier has no idea where the `'cancelled'` in `status == 'cancelled'` is supposed to come from.

So split the columns by **who decides the value**:

```json
{"kind":"row_update", "entity":"Order", "row_key":["id"],
 "fields": ["note"],                                 // caller-supplied (a param binds here)
 "sets":   {"status":     {"lit":"cancelled"},       // hard-coded by the implementation
            "updated_at": {"sym":"$now"},            // system
            "author_id":  {"ref":"$actor.id"}}}      // injected from the session
```

- **`fields` and `sets` do not overlap.**
- **Values use the same Value vocabulary as State** (§4): `{lit}` / `{ref}` / `{col}` / `{sym}`. **Do not invent a second notation.** This way the verifier's postcondition and the spec's `sets` are the same language evaluated by the same code, with no translation in between.

##### `row_key` and `fields` carry COLUMN NAMES — `binds` carries the mapping

Write `row_key` and `fields` as plain lists of **column names**. Do **not** put a parameter
name there, and do **not** spell the mapping out a second time as `{"id": "$arg.post_id"}`
for a column some parameter already binds to. `params[].binds` **is** that mapping and it is
the only place it belongs — say it twice and the two can disagree, and downstream has no way
to know which one is wrong.

There is exactly one thing a column list cannot express, and there — and only there — use the
object form: **a key column whose value comes from somewhere other than a parameter.**

```json
"row_key": {"user_id":   {"ref": "$actor.id"}}        // the account behind the current session
"row_key": {"tenant_id": {"ref": "$session.org_id"}}  // fixed by the request context
```

The keys are still **column names**. The values use the **same Value vocabulary as everywhere
else** (§4): `{"lit": …}` / `{"ref": "$…"}` / `{"sym": "$now"}` — the one notation that `sets`,
`needs`, `provides` and `constraints` all use. `{"col": …}` is the single form that does *not*
work here: comparing a row against another of its own columns is a row-internal test, and that
belongs in `constraints`. `binds` describes parameters, so it can never say any of this.

There is a second, rarer case a column list cannot express: **the reference lives on the other
table.** An operation takes an `envelopeId` and updates the `DocumentMeta` row that envelope
points at — but `DocumentMeta` holds no column pointing back (the pointer is
`Envelope.documentMetaId`), so no column of *this* entity can be the key, and the interface
takes no other parameter. Adding one would be inventing an argument the application does not
have. Say where the key comes from, with the same `{"from": …}` subquery §4 already defines:

```json
"row_key": {"id": {"from": {"entity": "Envelope",
                            "where": [{"col": "id", "op": "eq",
                                       "value": {"ref": "$arg.envelopeId"}}],
                            "get": "documentMetaId"}}}
```

Read that as "the row I am changing is the one whose key is `Envelope.documentMetaId`, on the
envelope the caller named". It obeys §4's rules — one level only, equality-only `where`, a real
column in `get`, never an aggregate — and the `$arg` it matches on must be a parameter this
operation really declares.

> **Only for a write.** If the effect merely *reads* that other row to check a precondition —
> ownership, existence, a status — it is not an effect at all: drop the `row_read` and say the
> condition on a `guards`/`requires` edge as `needs`. Deleting it loses nothing, because a read
> changes no state.

**You will almost certainly not need the object form.** Across 433 real repos it was used 181
times and was correct **0** times. Use the list form unless you have actually read code showing
the value is fixed by the session or the request context and the caller cannot supply it at all.

> ⚠ **A parameter whose name differs from the column is NOT a reason to reach for it.** That
> was 136 of those 181: an operation taking `idProfile` while the column is `id_profile`,
> written as `"row_key": {"col":"id_profile", "ref":"$arg.idProfile"}` — a scope clause, not a
> row key. That mapping is precisely what `params[].binds` exists for. Write
> `"row_key": ["id_profile"]` and put `"binds": "HotelAccess.id_profile"` on the `idProfile`
> parameter. The object form is about **where a value comes from**, never about what the
> parameter is called.

**Check this before you move on** — for every column in `row_key`, one of these must hold:

1. a **`required`** parameter `binds` to it, or
2. a **`required`** parameter binds to what that column is a foreign key **to** — a
   parameter declared `binds: "User.id"` supplies `Entry.user_id` just fine, because it is
   the same value, or
3. you wrote the object form above, or
4. the key is not on this entity at all and you read it off the other table with the
   `{"from": …}` form above.

If none of the three holds, downstream can only assume the parameter is named after the column — and in
a real repo it usually is not: `user_update` takes `user_uuid` while the column is `usr_uuid`,
so the tool ends up with a parameter that **does not exist in this application**, and the real
one becomes dead weight on the panel.

`required` is not a preference here: a caller who is allowed to omit the parameter cannot
locate a row with it. A parameter that merely *lands in* the key column is not the same thing
as the one that *identifies* the row — `Category.delete(category, transferId)` binds
`transferId` to `Category.id`, but it means "move the mappings to that category", not
"delete that category".

##### `scope` on reads — and what happens on a miss

`scope` belongs on **both** `row_read` and `row_search`, with the same syntax.

> ⚠ This `scope` is **not** the `scope` of a State (§4). This one is a **single object with a
> `kind`**, and it answers *"whose rows can this call see at all"*. A State's `scope` is a
> **list of `{col, op, value}` clauses** and answers *"which rows match"*. Same word, two
> shapes, no overlap — do not mix them. Putting it only on search makes the search-side scope decorative: if `search` returns only my rows but `fetch(id)` returns anybody's, then **"a needle in a haystack" is bypassed by enumerating ids**. Real apps almost always check ownership on `GET /posts/:id`.

```json
"scope": {"kind":"owner", "owner_col":"author_id"}
```

`kind` is exactly one of four — and it is a **closed vocabulary; never put a value inside the kind**:

```
{"kind":"owner",           "owner_col":"user_id"}
    code shows current_user.xxx / where user_id = ? / controller-level ownership auth
{"kind":"owner_or_public", "owner_col":"user_id",
                           "visibility_col":"visibility", "public":["public"]}
    mine ∪ the public pool
{"kind":"tenant",          "col":"org_id"}
    multi-tenant / fixed-channel static boundary
{"kind":"global"}
    genuinely whole-table: admin backends, public directories
```

Real systems rarely scan the whole table. **Most self-hosted apps' list/search endpoints are scoped to the current user.** **Choosing `global` also REQUIRES a reason in `why` — on `row_read` as much as on `row_search`** — "didn't decide" and "decided it is global" are two different things.

##### `method` on `row_search` — read it from the query, never guess

```
exact      equality / IN filtering
substring  LIKE / ILIKE / contains
keyword    full-text index, tsvector, MATCH ... AGAINST, scored keyword search
semantic   vector search, embeddings, pgvector, cosine distance
hybrid     keyword + vector
unknown    **if you cannot tell, write unknown and say why in `why`.
           Do NOT default to exact.** Downstream does no heuristic fallback —
           an unknown you flagged is usable, a wrong `exact` is not.
```

`fields` on a search are the columns actually **matched against**, not the columns returned.

##### Two things that must not be left out

> **`entity` is required on every effect** — the table the effect LANDS ON, not the entity the tool nominally belongs to. A mail-sending operation's effect usually lands on an XxxLog / XxxJob table.

> **`row_key` and `fields` are required** wherever they apply (update / delete / upsert / read need `row_key`; insert / update / upsert need `fields` or `sets`). Omitting `row_key` forces downstream onto a primary-key guess, which is simply wrong wherever the code looks rows up by slug or by a composite key; omitting `fields` forces it onto "every writable column of the entity", a superset rather than the truth.

> **Do not omit the `external` kind just because "nothing can verify it anyway".** It really happens in the world, it merely leaves no queryable trace. Recording it honestly lets downstream decide whether to give it a record table, or to know that tasks built on it are unverifiable. Omitting it silently loses that.

#### 2.3 `provides` — the world state this operation establishes (the dual of `needs`)

Must be a **list of States** (shape in section 4), even when there is only one. **Never a string.**

```json
[{"entity":"Post",
  "scope":[{"col":"id","op":"eq","value":{"ref":"$arg.id"}},
           {"col":"status","op":"eq","value":{"lit":"published"}}],
  "card":"exists"}]
```

Wrong: `"provides": "Post status becomes published"` — prose, not a State.

⚠ **And for a plain `row_update` like this one you would not write `provides` at all** — the
effect already says `status` was set to `published`, and we derive the State from it. The example
above is here to show you the *shape*, not to say you should type it. See the rule below.

**`effects` and `provides` are not the same thing; do not write the same sentence twice:**

- `effects` = **structurally**, which table's which columns were touched, and to what (the means)
- `provides` = **which checkable state was established** (the result)

For `row_insert` / `row_update` / `row_upsert` / `row_delete` / `row_soft_delete`,
**you do not have to write `provides` at all — we derive it from your `effects`** *unless the
thing you want to assert is a **delta*** (see the exception list below — that one you must write
even for a plain `row_update`). The three
slots of a State are each fixed by the effect (`card` by `kind`, `entity` verbatim, `scope`
from `row_key` / `sets`), so writing it again by hand only adds a place for the two to disagree.

**What you owe instead is correct `effects`**: every write effect needs an `entity`, and
`row_key` (or `sets` for an insert) with real values — that is the raw material, and when it
is missing we can only derive the far weaker "some row exists in that table".

Write `provides` yourself only when the effects genuinely cannot say it:
- **`op=action` / `external` / `dispatch`** — nothing structural to derive from; read the code.
- **a delta** — "this counter went up" is `{"was": …}` (see the Value table). Effects record
  *what was written*, never *how it compares to before*, so this is the one case where a plain
  `row_update` still needs a hand-written `provides`:

  ```json
  "effects":  [{"kind":"row_update","entity":"Question","row_key":["id"],
                "sets":{"answer_count":{"expr":{"col":"answer_count","op":"+","by":{"lit":1}}}}}],
  "provides": [{"entity":"Question",
                "scope":[{"col":"id","op":"eq","value":{"ref":"$arg.id"}},
                         {"col":"answer_count","op":"gt","value":{"was":"answer_count"}}],
                "card":"exists"}]
  ```

  ⚠ **Do not write `"sets": {"answer_count": {"col":"answer_count"}}`.** That says the column is
  set to itself — a tautology, and it throws away *how* it changed. Write the arithmetic:
  `"sets": {"answer_count": {"expr":{"col":"answer_count","op":"+","by":{"lit":1}}}}` (see
  `{"expr": …}` in the Value table). The `provides` above and this `sets` say two different
  things and you want both: **`sets` is what was written, `provides` is what is now assertable.**

A read or a search establishes nothing: write `"provides": []`.

⚠ **`provides` is the one field where omitting it does NOT mean "I didn't look."** Everywhere
else in this contract, leaving a key out means exactly that (§1.5). Here it means *"the effects
already say it — derive it"*, which is the normal case and what we want. The distinction that
still matters is between an empty list and a missing key: `[]` says **"I checked; this operation
establishes nothing assertable"** (reads, searches, pure notifications), while a missing key says
**"derive it from my effects."** Never write `[]` on a mutating operation just to fill the slot —
that is a claim, and it is usually false.

#### 2.4 `ref_code` — the only code anyone downstream will ever see

Everything after this pass works from your JSON. **Nobody downstream can open this repo.**
The next stage writes the tool's description, its parameter descriptions, and the wording of
every error it raises — and about the implementation it is given exactly two things: the atoms
you emitted, and this string. `ref_code` is not a label. It is *the evidence*.

Paste the **actual lines** of the function — the pre-checks, the writes, the status
assignment, whatever it dispatches. Roughly 5–25 lines. It is truncated at 600 characters
downstream, so spend that budget on the lines that decide behaviour; drop imports, logging and
boilerplate. If you must shorten, elide in the middle with `…`, never at the end.

```json
"ref_code": "async publish(id) {\n  const post = await db.posts.findOne({id})\n  if (!post) throw new NotFound()\n  if (post.authorId !== ctx.user.id && !ctx.user.isEditor) throw new Forbidden()\n  await db.posts.update({id}, {status: 'published', published_at: new Date()})\n  await mail.enqueue('post-published', {postId: id})\n  return post\n}"
```

Those seven lines are why the tool downstream can say *"only the author or an editor may
publish"*, *"the post must exist"*, and *"publishing stamps `published_at`"*. A name could not.

**Five things that are not `ref_code`.** All five are common, and each leaves the next stage
with nothing to write from:

```
BAD  ""  or the field left out              19% of a real run — nothing at all
BAD  "AuthController.js:41-58"              that is `locator`. Saying it twice says it once.
BAD  "ModelViewSet.destroy"                 the framework's name is not this app's behaviour
BAD  "DRF default destroy"                  prose about the code, instead of the code
BAD  "Standard admin update."
BAD  "async closeAccount({id,...}) {...}"   a signature with the body elided — and the body
                                            was the only part that carried information
```

Framework defaults are the hardest case and the most common: when the operation really is
`ModelViewSet.destroy` with no override, paste **the lines that configure it** — the queryset,
the permission classes, the serializer — because that is where this app's behaviour actually
lives. If you paste nothing, downstream cannot tell an unguarded delete from a guarded one.

---

---

### 3. behavior edge — SVO + guard

```json
{"subject":  "Account.close",
 "relation": "triggers",
 "object":   {"ref":"Transaction.create", "kind":"op"},
 "condition":"account.balance != 0",
 "binds":    ["transferAccountId"],          // see below: an edge's `binds` is NOT the same thing as `params[].binds`
 "needs":    [[{"entity":"Payee",
                "scope":[{"col":"type","op":"eq","value":{"lit":"transfer"}}],
                "card":"exists"}]],
 "evidence": "accounts/app.ts:683,632"}
```

`object` is `{"ref": <string>, "kind": "op" | "entity"}` — those two values only. When `kind`
is `op`, `ref` must be an exact `impls[].id_local`; when it is `entity`, an exact
`schemas[].entity`.

**Emit only these three coarse relations** (do NOT sub-type into exist/state/own/resource):

- `triggers`: subject calls/triggers object ("X calls Y", call sequences). object is usually an op.
- `requires`: before doing subject, object must already be in some state (a guard / pre-check / early-return / "throws if"). object is usually an entity, paired with `needs`.
- `guards`: auth middleware / a policy gating an operation. **`subject` is the guarded operation's `id_local`** — same rule as the other two relations, no exceptions (see the discipline below; a checker in `subject` is the single largest defect class). `object` is the credential table it checks against, `{"ref":"Account","kind":"entity"}`. The middleware's own name and the call site go in `evidence`.

**The three rich fields are orthogonal — don't conflate:**

- `condition` = a test over **existing data** that decides **whether this edge fires**
- `binds` = the **inputs the subject passes into the object** (a data wire). A plain list of
  the **subject's own parameter names**, unqualified — this is *not* `params[].binds`, which is a
  qualified `"Entity.column"`. Same key name, different thing.
- `needs` = **other states that must hold first** to take this edge

#### `needs` is one level of disjunction (DNF)

`needs` has the shape `[[S1, S2], [S3]]`, read as **"satisfying (S1 AND S2), OR satisfying S3, both let you take this edge."** When there is only one admission path, write `[[S1, S2]]` (single-element outer list).

Why this level exists: real permission guards are overwhelmingly of the form

```
isAdmin || isGlobalMod || (isOwner && !topic.locked)
```

**Do not flatten that into an AND** (you would produce a need nobody can satisfy), and **do not write nested boolean expressions** — one level of DNF only; for anything more complex, pick the main path and drop the rest.

#### Discipline for mining behaviors (this determines whether the edges are usable)

1. **Complete depth-1 coverage**: **every mutating business op must appear at least once as a subject**, mining what it directly triggers/requires. **Never skip an op as a starting point just because it only appeared elsewhere as an object** (otherwise you lose a whole layer of downstream edges).

   Some ops genuinely have none — an unguarded write with no pre-checks that calls nothing. Say so **explicitly** in a top-level `no_edges` array rather than leaving them out:

   ```json
   "no_edges": [{"id_local":"Tag.rename","why":"no auth middleware on this route, no pre-checks, calls nothing"}]
   ```

   **`no_edges` is all-or-nothing — there is a second, much commoner case it cannot express.**
   An operation that *does* call something (a `triggers` edge) but has **no wall** cannot go in
   `no_edges` (it has edges), and nothing else records that you looked. Measured: **271 mutating
   operations (8%)** sit in exactly that hole — `User.update_password`, `User.password_reset`,
   `Event.ingest`. Each recorded what happens *afterwards* and said nothing about who may call it,
   and **"I checked, there is no guard" is indistinguishable from "I never looked"**.

   So there is a second array, `no_guards`, for the guard layer alone:

   ```json
   "no_guards": [{"id_local":"Event.ingest","why":"public ingest endpoint, no auth plug on the route (lib/web/router.ex:88)"}]
   ```

   Use it whenever an operation has edges but **none of them is a `guards` / `requires` edge with
   `needs`**. `why` must name where you looked — a route table, a middleware list, a policy file.
   This is the same discipline as §1.5: **"I checked and it's absent" and "I didn't look" must be
   written differently.**


   Same discipline as `"constraints": []` versus omitting the field: *"I checked and there is nothing"* and *"I did not look"* must be written differently. Without this, a repo that is genuinely edge-poor is indistinguishable from one where the pass ran out of budget — and nobody downstream can tell which they are holding.
2. **`subject` must be an exact string from `impls[].id_local`.** Only 73% of edges currently satisfy this; the failures are overwhelmingly **permission checkers** written into the subject slot — `Authentication.checkBoardWriteAccess`, `RBAC.assert_permission`, `TeamPolicy.update?`, `User.isAdministrator`.

   Read literally, such an edge is a tautology: *"checkBoardWriteAccess requires a BoardMembership to exist"* — that is what the function is for. **It never says which operation was blocked**, and the call site is visible only to you, reading the source right now. Downstream cannot recover it: propagating through the checker was tried and gained 2%, while aggregate nodes such as `--guards--> User` dumped 108 unrelated preconditions onto a single tool — inventing walls that do not exist.

   So: if the wall comes from a permission checker, middleware or policy method that is **not itself an operation**, do not put the checker's name in `subject`. Find every operation that calls it and **emit one edge per operation**, with that operation's `id_local` as the subject and the checker's name plus **that specific call site** in `evidence`. A checker guarding four operations yields four edges; the repetition is not a problem, and the evidence is strictly better because each edge carries its own line number.

   If you truly cannot find the call sites, **omit the edge**. A wall that does not know whom it blocks leaves downstream guessing, and a guessed wall is worse than no wall.

   **But do not overcorrect: a checker may legitimately be an impl.** `LinkedGroup.isAllowed` ("is this group open to join") can be a genuine tool — it has an endpoint, it returns information, it is itself permission-gated. The test is **not** "does it change the world", it is **"is it an independently reachable operation"**. The two are not exclusive: the good pattern is to emit the checker as an impl *and* hang the wall on each caller — `Event.guardOwnership` as an impl, plus one edge each on `Event.update` / `Event.delete` / `Event.publish`, every one carrying its own controller line.
3. **No deep tracing**: record only the **direct one hop**. Deep chains are reconstructed later by traversal — do not drill down the call graph (it repeats, diverges, times out).
4. **Path-conditionality attaches to one hop only**: condition/binds/needs belong only to "the edge that introduces them"; the object op itself **stays unconditional and clean**. If something in `needs` itself depends on more, that belongs on the **depended op's own edges** — don't nest it here.
5. **Faithful**: don't invent edges not in the source; `evidence` gives "file:line".

---

### 4. State — the shape shared by `needs` and `provides`

`needs`, `provides`, `constraints` and every `scope` clause are all written in this one shape.
§2.2 and §3 both point back here.

One checkable assertion about the state of the world. `needs` (what is required) and `provides` (what is established) **share it**.

```json
{"entity": "Payee",
 "scope":  [{"col":"type", "op":"eq", "value":{"lit":"transfer"}}],
 "card":   {"op":"gte", "n":1}}
```

Read as: **"of the rows in `entity` matching `scope`, the count must satisfy `card`."**

```
scope[].op  — one flat table, 14 operators (multiple clauses are ANDed)
    eq  ne  lt  lte  gt  gte            comparison. `ne`, not `neq` — the old spelling is
                                        still tolerated in `scope`, but **`card.op` takes
                                        `ne` only**.
    in  nin                             membership in a list
    contains  icontains                 substring — `icontains` is the case-insensitive one
    startswith  endswith                prefix / suffix
    is_null  is_not_null                unary — write NO `value` for these
    **exactly these spellings** — not `==`, not `band`. An operator outside the table is a hard
    error at runtime, never silently false.

card.op     ∈ gte | eq | lte | ne | gt | lt
    Two aliases you may write directly:
        "card": "exists"      ==  {"op":"gte","n":1}
        "card": "not_exists"  ==  {"op":"eq", "n":0}
    `n` is an integer — not `"1"`, not `"one"`, not `"0..1"`.
```

**Write what the code actually says, not the nearest thing the old table could express.**
`contains` / `icontains` / `startswith` / `endswith` were missing until 2026-08-23, so a check like
"the title mentions X" had to be written as "the title equals X" — which is not the same condition,
and it made a whole class of task deductively unsolvable. If the source does a substring match, say
`icontains`.

**Three-valued, and the strictness is not yours to decide.** A comparison where one side cannot be
resolved is UNKNOWN, not false. What happens to an UNKNOWN depends on WHERE the condition sits, and
the runtime already handles that:
  · a read filter        UNKNOWN -> this row is not returned  (SQL WHERE)
  · an entity constraint UNKNOWN -> counts as satisfied       (SQL CHECK)
  · a guard / a verdict  UNKNOWN -> raises
So: do not add defensive clauses to "make it safe", and do not drop a clause because a column might
be null. Write the condition the code states.

#### `value` has seven forms — choosing the right one is the most important judgement here

```
{"lit": 42}                  A LITERAL — **the bytes the column actually holds**, not a
                             description of how they are produced. The runtime writes this
                             value verbatim, so `{"lit": "bcrypt($arg.password)"}` stores
                             that sentence, character for character, in every row.
                             Measured: 3598 values across 166 repos were written this way,
                             and one of them (`uuid = "(generated uuid)"` against a UNIQUE
                             column) made the create tool work exactly once and left six
                             other tools unable to address any new row.
                             If none of the seven forms can say what is written — a random
                             token, a hash, a sequence number, something fetched from
                             outside — **do not describe it here.** Name the column in this
                             effect's `note` and say what produces it. That is a real answer:
                             it is how the gap gets counted.
                             If the string genuinely *is* what the column stores and it just
                             happens to look like a description (a class name such as
                             `Email::Account`, a label with brackets), say so structurally:
                             `{"lit": "Email::Account", "verbatim": true}`. That is the only
                             two-key Value, and it exists so a wrong accusation can be
                             answered with evidence rather than prose.
{"ref": "$arg.product_id"}   a BINDING REFERENCE — use it when the right-hand side in
                             the source is this call's parameter, the logged-in user, or
                             the row the subject acts on:
                               $arg.<param>    an explicit argument
                               $actor.id       the logged-in user (req.uid / current_user)
                               $actor.<col>    a column ON THE ACCOUNT ROW of that user
                                               (tenant_id / company_id / role) — see below
                               $session.<key>  fixed by the request context
                               $subject.id     the row the subject operation acts on
{"col": "min_stock_amount"}  ANOTHER COLUMN OF THE SAME ROW
{"from": {"entity": "Order",  A VALUE FETCHED FROM ANOTHER TABLE — one column of the
          "where": [...],     matching rows, or an aggregate over them. This is how you
          "get": {"agg":"sum","col":"amount"}}}   say "more than the user has spent".
                             `where` is a list of the same clauses as `scope`. `get` is
                             either `"col_name"` / `{"col": …}` (that column) or
                             `{"agg": …, "col": …}` with agg one of count / count_distinct
                             / sum / avg / min / max (`count` may omit `col`).
                             **One level only** — a `from` inside a `from` is refused.
                             Prefer a plain `scope` clause when one will do: threading the
                             same `$arg` through two States is simpler and seeds better.
{"sym": "$now"}              the current time. **This is the ONLY symbolic constant, and
                             time arithmetic is forbidden** — never write now()-24h
{"expr": {"col":"answer_count",   ARITHMETIC ON A COLUMN OF THE SAME ROW.
          "op":"+",               `op` is one of + - * / ; `by` is an ordinary Value, so
          "by":{"lit":1}}}        `{"col": …}` works there too.
                             This is how an increment is written:
                               "sets": {"answer_count":
                                          {"expr":{"col":"answer_count","op":"+","by":{"lit":1}}}}
                             and how a condition compares against a product:
                               {"col":"balance","op":"gte",
                                "value":{"expr":{"col":"price","op":"*","by":{"col":"qty"}}}}
                             Legal **wherever a Value is** — the same form in `sets` and in a
                             condition. `by` must be a **number-valued** Value:
                             `{"lit": n}` / `{"col": c}` / `{"ref": "$arg.x"}`.
                             ⚠ **`by` may NOT be `{"sym": "$now"}`.** Time arithmetic stays
                             forbidden, and going through `expr` is the back door — the grammar
                             now refuses it outright (it used to compile and then silently
                             evaluate to UNKNOWN, i.e. an assertion that can never hold, with
                             no error anywhere).
                             ⚠ **Never write `{"col": <the same column>}`** to mean
                             "it changes": that says the column is set to itself, a tautology
                             that also throws away *how* it changed. (235 occurrences measured.)
{"was": "view_count"}        THIS ROW'S VALUE OF THAT COLUMN **BEFORE** THIS OPERATION.
                             This is how you say a counter moved. Do **not** invent an
                             operator for it — combine `was` with the ordinary ones:
                               increased   op "gt"  + value {"was": "<same column>"}
                               decreased   op "lt"  + value {"was": "<same column>"}
                               changed     op "ne"  + value {"was": "<same column>"}
                               did not drop  op "gte" + value {"was": "<same column>"}
                             (the last one is why this is a *value* and not an operator —
                             a `decreased` operator could never express it.)
                             **Legal only in `provides`.** A guard runs *before* the
                             operation, so "before" means nothing there; the runtime
                             rejects it in guards, read filters and entity constraints.
```

#### `$actor.<col>` reaches exactly ONE hop, and two shapes never resolve at all

`$actor.<col>` is resolved by copying that column **off the account row itself** when the user
logs in. So `$actor.tenant_id` works when the account table really has a `tenant_id` column —
and `$actor.company_id` does **not** work when the user↔company link is a join table. When the
source reaches the value through a relation, there is no way to say it here: state the
condition with a `needs` / `scope` State over the joined table instead, or write nothing. A
value the world cannot follow is worse than an absent one — it is silently skipped downstream.

These shapes never resolve, wherever a `ref` appears:

```
BAD  "$arg.from.id"  "$actor.membership.id"   two hops. Arguments are looked up by FLAT name,
                                              so a nested field never resolves. Split that
                                              object parameter into scalar parameters.
BAD  "$arg.password (optional)"               a symbol with prose glued on. A ref is a symbol,
BAD  "$actor.name <$actor.email>"             not a sentence and not a template.
BAD  "$output.item"  "$result.song_id"        points at what the call RETURNS — it does not
                                              exist yet when the condition is evaluated.
BAD  "$request.space.id"  "$params.pk"        the HTTP layer. The request's named fields ARE
BAD  "$context.bar.id"  "$header.x"           the parameters — say `$arg.<param>`.
BAD  "$this.id"                               your source language leaking through (PHP).
BAD  "usr_uuid"  "param.id"                   no `$` at all: that is a bare name, not a ref.
BAD  "$actor.session_id"                      the HTTP session, an in-memory object, a
BAD  "$actor.updated_map"                     framework field. `$actor.<col>` is a real
BAD  "$actor.org"                             COLUMN on the account row and nothing else —
                                              if no table in this repo has that column, it
                                              is not data and cannot be written down here.
```

#### WARNING: the most common mistake is writing down the left operand alone and dropping the right

The source says `WHERE user_id = req.uid`, so write:

```json
{"col":"user_id", "op":"eq", "value":{"ref":"$actor.id"}}
```

**Do not** just write `"user_id"`.

Uniqueness checks are the same — "this slug must not be taken" is:

```json
{"entity":"Post",
 "scope":[{"col":"slug","op":"eq","value":{"ref":"$arg.slug"}}],
 "card":"not_exists"}
```

**Do not** just write `"slug"`, and do not write `"slug+user_id"`. A composite unique key becomes several clauses in `scope`:

```json
"scope":[{"col":"hash","op":"eq","value":{"ref":"$arg.hash"}},
         {"col":"user_id","op":"eq","value":{"ref":"$actor.id"}}]
```

#### WARNING: never invent join syntax for cross-table conditions

"this product has an available row in the stock table" is:

```json
{"entity":"Stock",
 "scope":[{"col":"product_id","op":"eq","value":{"ref":"$arg.product_id"}},
          {"col":"qty","op":"gt","value":{"lit":0}}],
 "card":"exists"}
```

Threading the same variable through `ref` links the two tables; that is enough.

#### Three namespaces people keep inventing, and what to write instead

There are exactly four: `$arg` `$actor` `$session` `$subject`. Everything else resolves to
nothing and the whole entry is dropped, silently. Three families account for almost all of it:

| what gets written | what it means | write this instead |
|---|---|---|
| `$return.id` `$result.id` `$generated.id` `$created.id` `$output.id` | **the row this operation just created** | Nothing can name it — it does not exist when conditions are evaluated. If child rows link back to it, that is a **`spawn`** effect with `link_col`, and `link_col` *is* the answer. In `provides`, describe the state the new row is in; do not try to name its id. |
| `$request.space.id` `$context.bar.id` `$params.pk` `$header.x` | something off the HTTP request | The request's **named fields are the parameters** — `$arg.<param>`. If it is fixed by the request context rather than sent by the caller, `$session.<key>`. |
| `$this.id` | your source language leaking through (PHP `$this`, Ruby `self`) | The row the operation acts on: `$subject.id` on an edge. Inside an effect, it is that effect's own `row_key` and needs no reference at all. |

The first row is the one worth reading twice: **"the id of the thing I just made" has no slot on
purpose.** A condition is evaluated against the world as it is; a row that does not exist yet
cannot be referred to. Model the relationship (`spawn` + `link_col`) instead of the identifier.

#### Config switches map to a `Config` pseudo-entity

```json
{"entity":"Config",
 "scope":[{"col":"key","op":"eq","value":{"lit":"machine_translations"}},
          {"col":"value","op":"eq","value":{"lit":"true"}}],
 "card":"exists"}
```

For environment variables / compile-time constants that are not in the database, **omit the need entirely** (do not write it as prose).

#### null semantics (follow this, not your language intuition)

```
{"op":"ne", "value":{"lit":null}}   reads as "this column has a value"
{"op":"eq", "value":{"lit":null}}   reads as "this column is empty"
NULL participates in no comparison other than those two.
```

#### If you cannot express it structurally, omit the whole entry

A need you cannot express structurally cannot be evaluated downstream; keeping it only adds noise. **All of the following are wrong:**

```
BAD  "pred": "deleteMany"           a method name, not a condition -> delete it
BAD  "pred": "matches" / "allowed"  a verdict, not a condition -> delete it
BAD  "scope": "Comment.user_id"     a column name, not a filter -> supply the right
                                    operand, or delete it
BAD  "scope": "machine_translations_config enabled"   prose -> structure it or delete it
```

---

## Discipline

- **Prefer omission over fabrication**: never invent entities / columns / operations absent from the source. But **name normalization (snake_case columns, singular PascalCase entities), adding missing FKs, mining constraints, and mining lifecycle are your job** — do them.
- **"I checked and it's absent" and "I didn't look" must be written differently** (see 1.5). Downstream needs this to tell "this repo really doesn't have it" from "this pass missed it". **A coverage number you cannot disambiguate is not a coverage number.**
- **Account for coverage** — your closing one-line message states: how many schemas / impls / edges (triggers, requires, guards each) · how many subagents you used · **which impls you did NOT turn into atoms, and why**. Do not drop things silently.
- **{{OUT}} is the only file you write outside {{WORK}}**; do not paste the JSON into the conversation. Helper scripts and intermediate shards belong in {{WORK}}.

---

## Output contract — CollectOutput (the only thing written to {{OUT}})

```jsonc
{
  "repo": "{{REPO}}",
  "collect_version": 3,                          // the contract version; leave it at 3
  "summary": "<one line: what this app does, described as-is, no classification>",
  "conventions": {"read_denied": "not_found"},   // omit the key if there is no single
                                                 // repo-wide convention, or you can't tell

  "schemas": [
    {"entity":"Post",
     "columns":[
       {"name":"id","type":"id","pk":true},
       {"name":"slug","type":"text","pattern":"^[a-z0-9-]+$","nullable":false},
       {"name":"title","type":"text","nullable":false,"max":255},
       {"name":"status","type":"text","enum":["draft","published","archived"],
        "default":"draft"},
       {"name":"author_id","type":"id","fk_to":"Account.id",
        "on_delete":"cascade","nullable":false},
       {"name":"published_at","type":"datetime","nullable":true},
       {"name":"excerpt","type":"text","nullable":true},
       {"name":"created_at","type":"datetime","audit":true,"immutable":true}],
     "constraints":[
       {"kind":"unique","cols":["slug"]},
       {"kind":"conditional",
        "if":  [{"col":"status","op":"eq","value":{"lit":"published"}}],
        // "not null" is the UNARY operator. Writing `op:"ne"` + `{"lit":null}` compiles
        // but is **never true** (SQL three-valued logic: `x <> NULL` is UNKNOWN, and a row
        // filter reads UNKNOWN as false), so the whole constraint silently stops existing.
        "then":[{"col":"published_at","op":"is_not_null"}]}],
     "lifecycle":{"col":"status","initial":"draft",
                  "states":["draft","published","archived"],
                  "transitions":[{"from":"draft","to":"published","via":"Post.publish"},
                                 {"from":"published","to":"archived","via":"Post.archive"}]},
     "locator":"core/server/models/post.js:31"},

    {"entity":"Account",
     "columns":[
       {"name":"id","type":"id","pk":true},
       {"name":"email","type":"text","nullable":false},
       {"name":"password_hash","type":"text","nullable":false},
       {"name":"is_editor","type":"bool","default":false}],
     "constraints":[{"kind":"unique","cols":["email"]}],
     "locator":"core/server/models/account.js:9"},

    {"entity":"EmailJob",
     "columns":[
       {"name":"id","type":"id","pk":true},
       {"name":"template","type":"text","nullable":false},
       {"name":"post_id","type":"id","fk_to":"Post.id","on_delete":"cascade"},
       {"name":"sent_at","type":"datetime","nullable":true}],
     "constraints":[],
     "locator":"core/server/models/email-job.js:12"}
  ],

  "impls": [
    {"id_local":"Post.publish","op":"update",
     "entry":{"kind":"http","route":"POST /api/posts/:id/publish",
              "locator":"routes/api.js:42"},
     "params":[
       {"name":"id","type":"id","required":true,"binds":"Post.id",
        "description":"post to publish"}],
     "output_schema":{"post":"the published Post row"},
     "effects":[
       {"kind":"row_update","entity":"Post","row_key":["id"],
        "fields":[],
        "sets":{"status":{"lit":"published"},
                "published_at":{"sym":"$now"}}},
       {"kind":"dispatch","entity":"EmailJob","channel":"email"}],
     "provides":[
       {"entity":"Post",
        "scope":[{"col":"id","op":"eq","value":{"ref":"$arg.id"}},
                 {"col":"status","op":"eq","value":{"lit":"published"}}],
        "card":"exists"}],
     "ref_code":"async publish(id) {\n  const post = await db.posts.findOne({id})\n  if (!post) throw new NotFound()\n  if (post.authorId !== ctx.user.id && !ctx.user.isEditor) throw new Forbidden()\n  await db.posts.update({id}, {status: 'published', published_at: new Date()})\n  await mail.enqueue('post-published', {postId: id})\n  return post\n}",
     "locator":"services/posts.js:88"},

    {"id_local":"Post.search","op":"search",
     "entry":{"kind":"http","route":"GET /api/posts","locator":"routes/api.js:31"},
     "params":[
       {"name":"q","type":"text","required":true,"binds":null,
        "description":"keyword matched against title and excerpt"},
       {"name":"page","type":"int","required":false,"binds":null,"description":"1-based"}],
     "output_schema":{"results":"list of Post rows","total":"int"},
     "effects":[
       {"kind":"row_search","entity":"Post","method":"keyword",
        "fields":["title","excerpt"],
        "scope":{"kind":"owner","owner_col":"author_id"},
        "sortable":["published_at"],"paginated":true,
        "why":"controller filters where author_id = current_user.id; full-text index on title/excerpt (posts.js:120)"}],
     "provides":[],
     "ref_code":"async search(q, page = 1) {\n  const where = { author_id: ctx.user.id }\n  return db.posts.query(where)\n    .whereRaw(\"to_tsvector(title || ' ' || excerpt) @@ plainto_tsquery(?)\", [q])\n    .orderBy('published_at', 'desc')\n    .paginate(page, 20)\n}",
     "locator":"services/posts.js:120"}
  ],

  "edges": [
    {"subject":"Post.publish","relation":"requires",
     "object":{"ref":"Account","kind":"entity"},
     "condition":null,
     "binds":[],
     "needs":[[{"entity":"Account",
                "scope":[{"col":"id","op":"eq","value":{"ref":"$actor.id"}},
                         {"col":"role","op":"in","value":{"lit":["admin","editor"]}}],
                "card":"exists"}],
              [{"entity":"Post",
                "scope":[{"col":"id","op":"eq","value":{"ref":"$arg.id"}},
                         {"col":"author_id","op":"eq","value":{"ref":"$actor.id"}}],
                "card":"exists"}]],
     "evidence":"canPublish: admin/editor or the author themselves (permissions.js:44)"}
  ],

  "no_edges": [       // ops with NO edge at all: "I checked - it calls nothing and has no wall"
    {"id_local":"Tag.rename","why":"no auth middleware, no pre-checks, calls nothing"}
  ],

  "no_guards": [      // ops that DO have edges but no wall - no_edges cannot hold this case.
                      // The two are mutually exclusive: an id_local belongs in at most one of
                      // them, never both. No edges at all -> no_edges. Has edges but none of
                      // them is a guards/requires edge carrying needs -> no_guards.
    {"id_local":"Post.view_count_bump",
     "why":"public route, no auth plug and no policy call (routes/api.js:44)"}
  ],

  "values": []   // leave empty — out of scope for this miner. Value atoms come from a
                 // different source (real datasets), not from reading code; inventing
                 // them here would be fabrication.
}
```
