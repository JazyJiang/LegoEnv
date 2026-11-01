# skeleton_spec v2: the input contract of the builder

A skeleton_spec is one JSON file that describes the *shape* of a task to build. It contains no concrete names, values or task wording. The builder agent (an open-weight model behind Claude Code) takes it and chooses the real dataset, sets the thresholds, writes the policy text, the task statement, the distractor records and the verifier predicates, and runs the reference replay and admission. **A file that passes `validate_skeleton.py` can go straight to the builder.**

## A complete example

```json
{
 "skeleton_id": "sk3_0007", "domain": "operations", "source": "recombined",
 "apps": ["budibase", "stalwart"],
 "deliverable_atoms": [
   {"app": "budibase", "kind": "update_cell", "pos": 5, "neg": 0, "check_kinds": ["row_cell_equals"]},
   {"app": "stalwart", "kind": "send_email", "pos": 4, "neg": 7, "check_kinds": ["mail_sent", "mail_not_sent"]}
 ],
 "rule_atoms": [
   {"archetype": "compliance_flag", "carrier": "policy_sheet", "has_exception": true,
    "rule_shape": "Records are matched by a common key, and those with mismatched values are flagged and routed for review, except when a note field indicates the mismatch is expected."}
 ],
 "n_intents": 2, "n_distractors_min": 2, "predicate_budget": 11,
 "delivery_shape": "per-record actions",
 "chain": ["read the policy worksheet to learn the business rule",
           "scan the records and select the ones the rule applies to; at least 2 look-alike records must be skipped",
           "for each selected record: update_cell in budibase, send_email in stalwart"]
}
```

## The four blocks

| block | fields | meaning | vocabulary |
|---|---|---|---|
| app combination | `apps` | 1-6 environment ids | `vocab.apps` (`app_role` says which software each one stands in for) |
| deliverable atoms | `deliverable_atoms[]` = {app, kind, pos, neg, check_kinds} | what must exist in the world afterwards: which kind of write on which app, how many positive records (about the fan-out), how many negative ones (distractors / invariants), and to what precision it is checked | `vocab.kind_tools` (kind -> regex of the write tool the app must have); `vocab.check_kinds` (verifier templates) |
| rule atoms | `rule_atoms[]` = {archetype, carrier, has_exception, rule_shape} | which records get the deliverable: the rule's shape, where in the world the rule text lives, whether there is an exception clause, and one abstract sentence | `vocab.archetypes` (8); `vocab.carriers` (each needs a host app in `apps`) |
| skeleton constraints | `n_intents`, `n_distractors_min`, `predicate_budget`, `chain`, `delivery_shape`, `dataset_hint`, `domain` | count constraints, the abstract intent chain, an optional dataset hint, the domain label | `vocab.domains` |

## Hard rules (checked by the validator)

1. Every app in `apps` has a spec; every deliverable atom's `app` is in `apps`, and its `kind` has a matching write tool in that app's spec. An app that is not onboarded yet (a compiled spec listed in `spec_tools.json`) is allowed when the atom names the realizing write tools in `tools`.
2. `check_kinds` only uses names from the vocabulary (each maps to one builder verifier helper: sent_to / stream_post / row_in / event_with ...).
3. A `carrier` needs a host: the hosts of each carrier are listed in `vocab.carriers` (for example policy_sheet in budibase or directus, policy_mail in stalwart, policy_doc in outline). A non-onboarded host must name `carrier_field` as `Entity.field` of its spec.
4. `rule_shape` contains no proper nouns and no number with two or more digits (the builder sets thresholds against the data).
5. `n_distractors_min >= 2`, `predicate_budget >= 8`, `n_intents <= len(deliverable_atoms)`.
6. `dataset_hint`, if given, names dataset slugs that exist in the data pool.

## What the builder decides after it receives a skeleton

Which real dataset, the thresholds and tier boundaries, the literal policy text, the task wording, which rows are distractors and which clause each one trips, the concrete columns and values of the predicates, and the reference steps. **The task statement only points at the carrier and never restates the rule; a predicate may only require what the task statement or the policy text says explicitly.**

## Two ways to produce skeletons

- Mining: abstract atoms from public automation template galleries and SOPs, assemble skeletons, pass the validator, hand them to the builder (`MINING_BRIEF.md`, `mine.sh`).
- Any other method (prompting, an agent with web access, by hand), as long as every JSON file in the output directory passes `validate_skeleton.py --strict`. A new app must first be onboarded (`atoms/server/onboarding/ONBOARD_BRIEF.md`, `skeleton/onboard_check.py`); a new dataset must first be added to the data pool and profiled (`atoms/data/profile_datasets.py`).

## Usage

```bash
python3 legoenv/skeleton/validate_skeleton.py <dir-or-files> [--strict]
```
