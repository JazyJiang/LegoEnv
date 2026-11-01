---
name: build_pack
description: Build one data-first task pack (goal + world seeded from a real dataset + grammar-IR contract + one gold run + acceptance) from a supplied abstract skeleton, using pack/packlib.py.
---

# build_pack — one task pack, the fast way

Working dir on the box: `.` (`pack/` = packs + library, `tasks/` = runnable dirs). Never touch the library repository.
Reference packs: use the two implementation examples named in the builder brief.
Library: `pack/packlib.py` (read its docstring first). Data catalogue: `pack/DATA_INVENTORY.md`; datasets live in `../datapool/<slug>/raw` (read-only) and `../datapool_ext/<slug>/raw`.

## Inputs
`/build_pack <skeleton> [dataset-slug] [apps]` — use the supplied skeleton JSON; do not read task corpora or reconstruct a source question.

## The five rules (do not bend)
1. **Only the skeleton survives from the source.** Keep: the app combination, the abstract intent chain (e.g. "check groups against a threshold → book members of covered groups → notify about short groups"), the delivery shape. Drop: the scenario, every noun, every sentence. The finished goal must share no noun or phrase with the source prompt.
2. **Data first.** Pick the dataset before writing a word: the task's rows, groups, thresholds, recipients, second system all come from real rows or statistics of them (medians/percentiles so the sample splits naturally). Record provenance (`src=` on every seed call). If the datapool has nothing that fits, download one (§data).
3. **Intent count policy** (count = independently verifiable deliverables; reads/logins/lookups don't count): source has 1 → keep 1; source has 2 → 1, 2 or 3; source has 3 → 2 or 3; source has ≥4 → 3 or fewer. Say the count in the README.
4. **Rules come from the goal or from the data, never from a hand-written rules sheet.** Either state the rule in the goal (one or two sentences) or use a dataset column that carries it (status, credit_limit, price list, team list, invoice status). Both at once is fine.
5. **Every whole-table read stays under 12,000 chars** (`W.obs_report()` asserts it): split tables by group, keep inboxes ≤ 8 mails, keep queues ≤ 10 rows. Keep the expected write count ≤ ~20 tool calls (one event per group beats one per person).

## Steps
1. **Skeleton** — write the abstract chain in one line (the `skeleton=` argument of `write_pack`).
2. **Dataset** — scan `pack/DATA_INVENTORY.md` for the structure the chain needs (roster/queue/log/ledger/pipeline + owners/contacts). Profile it with a few lines of python (`csv_rows`, `parquet_rows`, `profile_rank` for tie-free top-k, `est_chars(rows)` for the 12k budget before seeding): groups, counts, natural splits. If nothing fits → §data.
3. **World** — `W = World([apps], persona=(email, name), now=...)`; for CRM packs call `W.set_persona_id('espocrm', 1)` (actor guards compare the shared session id with the row id); check every write tool you expect the agent to use for required params it cannot learn from the goal (`input_schema … required`, e.g. espocrm `opportunity_create.close_date`) and put them in `notes_extra`; seed with `W.sheet / W.events / W.inbox / W.stream / W.seed(app, entity, rows)`; noise from `enron_mails`, `twcs_chat`; `spec = W.merge()`; `rep, bad = W.obs_report(); assert not bad`.
4. **Expected solution** — compute it from the seeded rows in code (never type it). Assert the sample splits (some pass, some fail).
5. **Goal** — plain English, any length that reads naturally; names the sheets/systems it needs, states the rule(s) if they are not in the data, never lists fields/ids/recipients that the world already contains. Read it once as the agent: can every value it needs be found by reading the world?
6. **Contract** — `C = Contract(GOAL, expected=…)`; positives with `C.add(id, semantic, CNT(...))`, negatives with `negative=True` (`eq 0` counts). Helpers: `sent_to`, `stream_post` (pins sender_id = 1), `event_with`, `row_in`, `SEL/AND/OR/F/CNT`. Sub-selects must use `in`, not `eq`. `assert not C.seed_check(spec)`.
7. **Write** — `write_pack(tid, W, spec, C, atoms=[...], skeleton=...)`; tid = a name from the data (`wardcover_w37`, `poack_dec25`), never the source id.
8. **Gold run** — use deterministic `sim_gold` as specified in the builder brief. Preserve the replay records and acceptance output.
9. **Accept** — `python3.12 pack/accept.py pack/<tid> tasks/<tid> --strict` must print `passed: true` (new packs: `--strict` is required — every negative must get a counter-example; `packlib.accept(tid)` still runs non-strict, so call accept.py directly or check `vacuous_negatives == 0` in `pack/<tid>/accept/report.json`) (runnable, judgeable on seed/final/dumped, resettable, every positive witnessed by a dropped write, every negative falsifiable). If it fails: fix only contract or world-data bugs; never rewrite the goal to fit the agent's mistake unless the wording was genuinely ambiguous (say so in README). Archive every attempt: `python3.12 -c "from packlib import *; archive_attempt('<tid>','attempt_1')"`.
10. **Finish** — `python3.12 pack/fill_witness.py pack/<tid> tasks/<tid>`; `python3.12 pack/emit_task.py pack/<tid> <tid>`; `runtime.run_task(emitted spec, task)` must be True (`packlib.finish(tid)` does both). Then README.md (template below) and one line in `pack/SUMMARY.md`. `python3.12 pack/regress.py` must stay green.

## §data — when the datapool has nothing that fits
Search Hugging Face (`https://huggingface.co/api/datasets?search=<terms>&limit=20`; prefer CSV/parquet, permissive license, 500–200k rows, ≤ 200 MB). Download on the box with `huggingface_hub` (`HF_ENDPOINT=https://hf-mirror.com` if huggingface.co is unreachable) into `../datapool_ext/<slug>/raw/`, write `meta.json` in the datapool format (copy keys from any existing `meta.json`: `dataset_slug, source{hub,id_or_url,license}, downloaded, size_bytes, raw_path, raw_format, n_rows_est, carried_schema[{name,type}], extract_recipe, example_file`) plus `README_source.md` (URL, license, row/column summary) and `data_example.jsonl` (3 rows). Kaggle needs `~/.kaggle/kaggle.json`; if it is absent, say so and stay on HF. Append the new slug to `pack/DATA_INVENTORY.md`. Never store more than 1.5 GB in datapool_ext.

## README.md template
`# <tid> · <one-line summary>` → Skeleton → instance table (skeleton step | this pack's instance) → Task (verbatim) → World (each table/calendar/inbox: source, row count, why it was sliced this way) → Expected solution (results derived by code) → Live runs table (run, result, turns/cost, note) → Acceptance summary → Findings (spec/runtime issues, logged to the v1.1 ledger).

## Known environment facts
- Merged worlds share ONE login session; the system notes already tell the agent to re-sign-in before switching systems. All persona account ids are 1 in every base spec; keep it that way (CRM persona id must be 1, not "me").
- Runtime patches in place: range filter accepts `$arg` bounds and ignores timezone suffixes; `Verifier.eval` accepts grammar-IR trees. Base specs carry: gladys getevents range filter, budibase row_search honest schema, espocrm opportunity_create explicit owner, stalwart email_list without accountId guard.
- `cc` injects the real date into the agent's system prompt; write "This is ISO week N" / "this morning" rather than "It is Monday …" when the world's `now` differs from today.
- Predicates may only demand identifiers the world actually contains: if a roster has names but no mailboxes, accept the name (`OR(icontains name, icontains derived_email)`), never a derived address alone (wardcover_w37_v3 lost 64 clauses to this).
- Agents over-report: a run that says "27 created" may have created 20. Only `accept.py` decides.

## Lessons from the production run (batches 01–10) — binding
- **Negatives check state, not wording.** Agents mention excluded items ("X is within budget") even when told not to. Write a negative as "the action did not happen" (no event/mail/row/opportunity for X; X's phone unchanged), never "the body does not mention X". Avoid short names in `icontains` negatives (Promi ⊂ promise). One `icontains` term per column per negative — two on one column can pass accept vacuously.
- **Positives on free text accept the common forms**: counts may be written `5`, `**Promoters (9-10):** 5`, `Promoters: 5`; no regex operator exists, so OR a few forms. URLs that prefix other URLs need a terminator after them.
- **Editing sheet rows**: call `spec = flat_row_patch(spec, COLS)` after `W.merge()` whenever a deliverable edits existing rows (stock `row_patch` writes a `<dynamic>` blob and the old flat value keeps showing).
- **CRM / calendly / zoom / chatgpt lists are not measured by `obs_report`**: CRM `contact_list`/`lead_list` ≈ 300 chars per record, easyappointments `event_list` ≈ 375 per booking → keep ≤ 30 records per list or check with `est_chars`.
- **hubspot = `espocrm_hs`**: `sign_in(user_name, password)` and `W.set_persona_id("espocrm_hs", 1)`, same as espocrm.
- **Delivery shapes that list exclusions conflict with the shared system head** ("do not enumerate skipped items") → make the delivery list the acted-on items.
- **Seeds must avoid gateway false positives**: filter geopolitical/violent topics out of scraped text before seeding.
- `parquet_rows` works under python3.12 (python3 subprocess fallback).
- An app listed in the source that only carried a policy mail, or was offered but never needed, may be dropped (say so in README); every other app of the combination stays.
- **Relative windows name their reference date**: write "in the 14 days before 2024-03-01", not "in the last 14 days" (cc injects the real 2026 date). Legal/contract text (CUAD) trips the gateway filter more often — expect a retry.
- **Negatives over sheet cells**: use `CNT(SEL(..., OR(flat, dynamic)), "eq", 0)`, never `NOT(OR(flat col, <dynamic> col))` — rows the agent adds have no flat column, so NOT(unknown) is not true. After `from packlib import *`, use `import datetime as dt` (packlib exports the datetime class). easyappointments: username = persona email; `services_store` needs service_id even on create.
- **Sheet column names must not be `id`, `type` or `tableId`** (budibase overwrites them with the row id). Zulip member lists are ~650 chars per person: keep ≤ 15 members. easyappointments base Appointment seeds have id null: give seeded rows ids. `stream_post` now also matches posts in channels the agent creates; librechat keeps its conv-1 conversation automatically (do not re-seed it).
- **Write predicates per instance, not per recipient** (each conflict → the right person gets a mail naming both items); ids that prefix each other (ATMEGA328P-AU / -AUR) need `eq`, not icontains; amounts accept a thousands separator (`2683.42` / `2,683.42`). A "conflict/clash" skeleton needs data that really clashes (fleet trips do; real conference schedules almost never double-book).
- **Invariants are negatives** ("record X stays unchanged" as a positive is true on the seed and seed_check rejects it). espocrm Lead has both `source` (enum) and `lead_source` (text): accept either; espocrm Account has no parent field (put hierarchies in a sheet). Prefer `nin [..]` over `ne` in negatives (accept can falsify nin).
- **Ids that are digit strings break lookups** (the MCP layer turns "80677599998" into a number): seed such ids as integers or give them a letter prefix. Say "a separate message for each X" when one message per item is wanted. Dates the goal treats as past (history sheets, earlier issues) must precede the world's now.
- **Check an identifier is unique in the seeded world before writing a negative on it** (NPPES providers share a hospital phone).
- **Dry-run before the gold run**: write the gold solution as steps and call `bad, env = simulate(spec, W, C, steps)` (packlib); `bad` must be empty. It catches contract bugs for free (b12 went 10/10 first try with it).
- **Post-only deliveries**: when the post/mail IS the list, state-only negatives cannot catch over-inclusion; then the goal says "list only …" and a negative may forbid an excluded item's unique identifier (full name / id), never a short or common word.
- Zoom (openmeetings): a meeting is a room (create_room, registrant_add/registrant_list, participant_list includes the host); `create_room` hard-codes host_email, so never assert on the host.
- **"today" needs its date in the goal** too ("today, 2024-03-12"). `OR()` takes counts: `OR(CNT(sent_to(a)), CNT(sent_to(b)))`, not SELs. Zulip direct messages: `dm(user_id, *terms)` (tool send_direct_message; World.stream numbers members 2.. in order).
- **Numbers in free text**: accept both roundings when a real rate lands on .x5, and "100%" for "100.0%"; avoid instances whose amount is 0 (icontains "0" always matches). ASCII-fold accented names before deriving mail addresses. python3.12 lacks pyarrow/zstandard/yaml/duckdb → run a python3 prep.py that writes a `_*.json` cache. Zoom registrant rows: drop null columns to stay under 12k. Real zoom-style attendance: `pack/_b16_irc_meetings.json` (1,422 real #ubuntu-meeting meetings).
- **Seed ids the agent passes back to tools must be integers** (the MCP schema types every id argument as a JSON integer; with string ids like `opp_001` the agent passes 1 and writes the wrong row). Zulip streams: ≤ 19 messages (≈550 chars each).

## Folded defaults (after the 250-task run) — no more in-pack patches for these
- **gladys** `calendarevent_destroy(event_id)` deletes by id. **stalwart** `email_set` only creates (needs to + body); `email_update(id, keywords, mailbox_ids)` marks read / labels / moves an existing mail — don't append your own email_update. `sent_to(addr, *terms)` also matches envelope-only recipients (`rcpt_to`).
- **espocrm / espocrm_hs** updates now write `assigned_user_id`, `account_id`, `contact_id`, `parent_id`, `lead_id` (Account/Contact/Lead/Opportunity/Case/Task/Call/Meeting). Updates do not check that the id exists → predicates pin the exact id. Seed users/accounts with integer ids.
- **vikunja** `task_move_to_bucket` moves cards that are already in a bucket; `tasks_board()` returns the integer kanban view id (pass it as `view=`); `labels()` works without a Label table; `task_delete` is soft → use `vikunja_live(*conds)` in positives (negatives count deleted cards too).
- **mastodon** id arguments are typed id: seed Status/Account ids as integers. **mantisbt** `bug_add` without optional args is clean; `tracker_project()` category ids are integers. **directus** `table()` keys are integers; `update_item` replaces the whole `data` object.
- `simulate()` / `login()` work on the seven new apps (register adds them to `packlib.LOGIN`). `run_gold` also retries unparsable-tool-call and zero-turn gateway errors; a killed run (empty out.json) is never retried.
- **Tool-argument names must match ^[a-zA-Z0-9_.-]{1,64}$** (API 400 on turn 1 otherwise): name sheet columns without spaces when they become `row_patch` arguments; call `assert_tool_arg_names(spec)` before write_pack. opensign `envelope_list` only lists rows with Type == "Envelope".
- Multi-day events: date predicates accept range forms ("25–27 May", "May 25-27"). Company names: agents normalise raw org strings (gitbutlerapp → GitButler) — match on the stem.
- Agents have no calculator: when the goal asserts a ratio, state the precision ("two decimals") and pick values away from rounding boundaries. Never seed real personal e-mail addresses from a dataset (GHTorrent, mailing lists): keep the names, use <org>.example addresses.
