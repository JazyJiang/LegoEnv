# BUILDER BRIEF — build one task pack from a skeleton spec

You are the builder. Box: this machine, work dir `.`, python = `python3.12`. You own ONE skeleton: `{SK}`.
Execute directly; do not spawn agents; the user is not watching. Report honestly (FAIL is fine). Never run `claude`, `gold_bg.sh`,
`run_task.sh` or `killrun.sh`: the gold run in this experiment is deterministic (`sim_gold`, below).

## Read first (once, in this order)
1. `./.claude/skills/build_pack/SKILL.md` — the five rules, the ten steps and the "Lessons" / "Folded defaults" sections are binding.
2. The docstring plus the `World`, `Contract`, `simulate` sections of `./pack/packlib.py`.
3. `./pack_dpsk/dklib.py` (two functions: `sim_gold`, `check`).
4. Two reference packs, read `build.py` and `README.md` of each:
   `./pack/clean_quality_review/` (rule in a policy worksheet, expected solution computed in code, one negative per skipped row)
   `./pack/clean_leave_closeout/` (rules in a controller e-mail, per-record fan-out + summary post)
5. `./pack/DATA_INVENTORY.md` — the real datasets you may seed from (`./datapool/<slug>/raw` read-only,
   `./datapool_ext/<slug>/raw`). Prefer datasets that fit the skeleton; downloading a new one is allowed per the skill's §data.

## Your input: the skeleton spec
```json
{SKELETON_JSON}
```
Field meaning:
- `apps`: the app combination of the world (`budibase`=spreadsheet, `stalwart`=mail, `zulip`=team chat, `espocrm`/`espocrm_hs`=CRM, `gladys`=calendar,
  `easyappointments`=booking, `openmeetings`=video meetings, `librechat`=AI assistant, `opensign`=e-signature). Keep every app unless an app would only
  carry a policy mail or is never needed (then drop it and say so in the README).
- `deliverable_atoms`: what the task must produce, one atom per (app, kind). `pos` = how many positive checks the pack must carry for this atom,
  `neg` = how many negative checks. `check_kinds` says to what precision the pack must check this atom (vocabulary + meaning in `./pack_dpsk/contract/vocab.json` → `check_kinds`;
  e.g. `mail_sent_to_with_terms` → a mail to the right address whose body names the record and the amount; `row_cell_equals` → the exact cell value).
- `rule_atoms`: the business rule(s) the task turns on. `rule_shape` is an abstract description of the rule's shape (no names, no literal thresholds): instantiate it on your data, do not copy its wording into the goal. `has_exception` = the rule needs an override clause (hold / opt-out / already done / VIP …) and at least one distractor must trip exactly that clause. `archetype` is the rule's shape (threshold_routing / deadline_escalation / tiering / approval_chain /
  exclusion / reconciliation / budget_quota / compliance_flag); `carrier` says WHERE the rule text lives in the world: `policy_sheet` = a worksheet in the
  budibase workbook, `policy_mail` = an e-mail in the stalwart inbox, `notes_field` = a notes/description field on a CRM record. **The rule text must be literal
  and complete in the carrier, and must NOT be restated in the goal.** The goal only points at the carrier ("follow the payment rules the controller sent",
  "the workbook's policy worksheet has the requirements").
- `chain`: the abstract intent chain (read rule → select records → per-record actions → summary). Instantiate every step; do not add unrelated steps.
- `n_intents`: number of independently verifiable deliverables (reads/logins do not count). Keep it.
- `n_distractors_min`: at least this many records that LOOK eligible but fail exactly one clause of the rule; each gets its own NEGATIVE predicate
  ("the action did not happen for X": no mail to X, no row for X, X's cell unchanged).
- `predicate_budget`: positives + negatives must be ≥ this number.
- `delivery_shape`: per-record actions and/or one summary message.

## What to build (the skill's ten steps, adapted)
1. **tid** = `dk_` + a short name taken from the data (never the skeleton id); the `dk_` prefix is mandatory. Claim it: `mkdir ./pack/<tid>` must succeed.
2. **Dataset**: pick from DATA_INVENTORY.md. **Diversity rule**: count the slug's uses in `pack/batches/datasets_used.tsv` (column 3) and `pack_dpsk/datasets_used.tsv` (column 3); prefer a slug with ≤ 12 uses in total and never pick one with ≥ 25; downloading a new real dataset (skill §data, HF preferred) is encouraged when the skeleton's records do not fit any inventory slug well — the datapool_ext cap for this run is 30 GB total. After choosing, append `<tid>\t{SK}\t<slug>` with `flock ./pack_dpsk/.ds.lock -c "echo -e '<tid>\t{SK}\t<slug>' >> ./pack_dpsk/datasets_used.tsv"`. Profile it with a few lines of python; the records, groups, thresholds, dates, recipients all come from real rows or
   statistics of them. Record `src=` on every seed call.
3. **World**: `W = World(apps, persona=(email, name), now=...)`; seed the record table/inbox/calendar/CRM; seed the **policy carrier** with the literal rule;
   add a little noise (`enron_mails`, `twcs_chat`, unrelated events); `spec = W.merge(); rep, bad = W.obs_report(); assert not bad`; `assert_tool_arg_names(spec)`.
4. **Expected solution computed in code, never typed**: write the rule as a python function over the seeded rows, derive the matched records and the
   skipped ones, and `assert` the split (e.g. exactly 4 matches, ≥2 distractors each failing a different clause, no ties).
5. **GOAL**: plain, natural English, 3–6 sentences; names the sheets/systems/channels it needs and the carrier of the rule; states dates it depends on
   ("today, 2026-03-12"); never lists the rules, the eligible records, the distractors, ids or recipients that the world already contains. Read it once as the
   agent: every value it needs must be findable by reading the world.
6. **Contract**: `C = Contract(GOAL, expected=...)`; positives from the computed expected (per matched record + summary), negatives per distractor and per
   invariant, all state-based (see the skill's "Negatives check state, not wording"); `assert not C.seed_check(spec)`.
   **A predicate may only demand what the goal or the policy text explicitly asks for.** If the goal says "repeat their feedback and name the product", do not
   also require a ticket number or a subject line; if the policy names the channel, the goal or policy must name it too. Re-read every positive against the
   goal + policy text before writing it: a solver that follows both to the letter must pass it. (In the first 250 packs, 66 were unsolvable for this reason.)
7. **Gold steps** (the correct solution as tool calls, computed from the same expected): `steps = [(app, tool, args), ...]` then
   `bad, env = sim_gold(TID, spec, W, C, steps); assert not bad, bad`. This replaces the LLM gold run.
8. `out, td = write_pack(TID, W, spec, C, atoms, skeleton="<skeleton_id>: <chain in one line>", notes_extra=...)` — call it BEFORE `sim_gold` (write_pack creates the task dir).
   `atoms` = `[{"id": "a1", "kind": <deliverable kind>, "text": <one line>}, ...]` from the skeleton's deliverable_atoms.
9. `check(TID, "{SK}", dataset="<slug>", note="<≤80 chars>")` must print `CHECK PASS` (accept --strict: every positive witnessed by a dropped write,
   every negative falsifiable, seed False / final True, resettable; then finish: runtime.run_task True).
10. `README.md` in the pack dir (Chinese, the skill's template; first line `骨架 {SK}`), plus the rule text and where it lives.

Put all of it in ONE script `./pack/<tid>/build.py` that starts with
```python
import sys; sys.path.insert(0, "./pack"); sys.path.insert(0, "./pack_dpsk")
from packlib import *; from dklib import *
```
and run it with `cd ./pack && python3.12 <tid>/build.py`. Iterate on its asserts and on `check`'s report (≤ 25 runs).
When a check fails: fix the contract, the world data or the gold steps. Only reword the goal if it was genuinely ambiguous, and say so in the README.
Helper functions from `pack/batches/t0*lib.py` may be imported read-only (`mail_of`, `money_forms`, `noise`, `SIGNIN`, ...); do not copy their batch reporting.

## Stand-in apps (only when the skeleton has `needs_newspecs: true`)
`standin_apps` maps an app the skeleton names but the library does not host to our stand-in (asana/monday/trello/pipefy → vikunja boards, jira → mantisbt, notion/confluence → outline docs,
mailchimp → listmonk, google_drive → cloudreve, airtable → directus, twitter/facebook/instagram → mastodon). Add `from newspecs.register import *` right after
`from packlib import *`, read `./pack/newspecs/README.md` and the `register.py` docstring first (seeding helpers, NOTES, LOGIN entries),
and read one long-tail pack of the same app (`grep -l "newspecs.register" ./pack/*/build.py | head`). The README states the stand-in.
`rule_atoms[].rule_shape` is an abstract description of the rule's shape; instantiate it on your data, do not copy its wording into the goal.
`n_intents` may be lower than `n_intents_source` (intent-count policy: ≥4 → ≤3); keep exactly `n_intents` deliverables.

## Newly onboarded apps (`pack/newspecs3/<app>/`, 13 apps — use these exactly like the 19 base apps)
akaunting, ever_gauzy, ledgersmb, libredesk, paperless_ngx, planka, bar_assistant, ckan, foodcoopshop, healthchecks, hitobito,
librebooking, suitecrm. Each has `pack/base_specs/<app>.spec.json`, `pack/newspecs3/<app>/register.py` (SERVER/PFX/CONTENT/NOTES/LOGIN
+ seed helpers + obs hook), `capability_card.json` (what it can hold: `content_entities`, which `kinds` map to which write tools, `check_kinds`, `carriers`,
`login`, `seed_helpers`) and usually `PATCHES.md`. In build.py add `from newspecs3.<app>.register import *` right after `from packlib import *`
(one line per app in `apps`). **Read the capability card and the register.py docstring before seeding**: seed only the entities the card lists
(e.g. ever_gauzy holds Goal/Broadcast/OrganizationProject/OrganizationTeam/Comment/Tag — no Employee/Candidate/Invoice; paperless_ngx cannot create a
Document through the agent, only update/tag/note it), if the card has a `login` tool, sign in with it (explicit `login: null` means use the app directly), and realize each deliverable atom with the tools the card lists
for its `kind` (kinds spelled `other:<name>` in a skeleton are the card's `<name>`). Predicates on these apps use the generic record_* / note_or_task_* /
action_done templates the card lists. A skeleton may also name a release spec that is NOT onboarded (its atoms then carry explicit `tools`); onboard it first
per `contract/ONBOARD_BRIEF.md` or, if that is out of budget, stop and record the reason in README — do not fake the app with a stand-in.

## Known library gotchas (from the first 30 builds)
- `enron_mails()` / noise helpers return rows with a `_src` key that `W.inbox` rejects: strip it before seeding.
- `check_keys`, `sheet_ids_as_text`, `mail_of`, `money_forms`, `noise` live in `pack/batches/t02lib.py` / `t03lib.py`, not in packlib (import read-only).
- Gold `steps`: prefer plain `(app, tool, args)` tuples with deterministic ids (new ids = max seeded id + 1); callable steps are recorded too, but they do not auto sign-in.
- `write_pack` must run before `sim_gold` (it creates the task dir); order = write_pack → sim_gold → check.
- State negatives need `negative=True` (seed_check expects them True on the seed); a negative must not reuse a positive's `gte 1` shape.
- Datasets often repeat ids/names across rows: select seed rows by several columns, never by id alone; seeded ids the agent passes back must be integers.

## Hard limits
- Write only under `pack/<tid>/`, `tasks/<tid>/` and this directory. Everything else in `./` is read-only (packlib, accept.py, SKILL, base_specs, other packs,
  SUMMARY.md, batches/*, datasets). Never touch the library repository.
- Every whole-table read ≤ 12,000 chars (`obs_report`), ≤ ~20 expected write calls, gold steps ≤ 30 calls.
- Seeded ids the agent passes back to tools must be integers; sheet column names without spaces and not `id`/`type`/`tableId`.
- No real personal e-mail addresses from datasets; use `<org>.example` addresses.

## Final message (≤ 10 lines; nothing else is read)
tid, dataset slug, apps kept/dropped, rule archetype + carrier, n_intents, preds pos+neg, number of build.py runs, CHECK PASS/FAIL, and ≤ 4 lines of findings
(library gaps, spec bugs, what you could not express).


## Explicit optional capabilities (author decision, 2026-10-24)

`login: null` means no login call and no fabricated account/login tool. If a card
declares `login.arguments`, retain its native parameter names and types: literal
service selectors and numeric account IDs are not persona emails. `$password`
and `$persona` refer to the world credentials. Use `login_arguments(W, app)`.

`carriers: {}` means this app cannot host a policy body. Do not invent one or
repurpose opaque configuration as policy. Every combined skeleton must include
at least one declared carrier host in its app set; use that host for the rule.
All other source capability and strict-admission requirements remain in force.
