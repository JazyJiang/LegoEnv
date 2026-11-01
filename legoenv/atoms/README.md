# Atom provenance

Every LegoEnv environment is composed from four atom families. This directory holds
everything that produces an atom pool, one sub-directory per family. The composition
contract the atoms are written against (skeleton schema, `vocab.json`, validator,
recombination, onboarding check) lives in [`../skeleton/`](../skeleton/).

## Server atoms (`server/`)

**Atom:** one open-source application compiled from its code into an executable env-spec
(entities, tools, guarded behaviour), in the format of `apps/base_specs/*.spec.json`.

- **Code:** the two-stage compiler. `compiler/stage1_collect/` has an agent read the repository
  and checks its description against the contract over feedback rounds; `compiler/stage2_spec/`
  translates it, probes it in the runtime and has the agent confirm the spec.
- **Prompts:** `prompts/code_collector.md` (stage-1 contract), `prompts/edge_topup.md`
  (validator feedback), `prompts/build_spec.md` and `prompts/build_spec_feedback.md` (stage 2).
- **Onboarding:** `onboarding/` (`ONBOARD_BRIEF.md`, `onboard.sh`) adapts a compiled spec for the
  builder and writes its capability card, which maps operation kinds to the app's tools;
  `skeleton/onboard_check.py` must pass, and `onboarding/cards_to_vocab.py` merges the passed
  cards into `skeleton/vocab.json`. `screen_specs.py` and `make_targets.py` choose candidates;
  `export_spec_tools.py` writes the tool index the validator reads.
- **Output:** `<app>.spec.json` plus an adapter with its capability card (`apps/`).
- Details: [`docs/compiler.md`](../docs/compiler.md).

## Data atoms (`data/`)

**Atom:** one public dataset with a card that says which tables, columns and archetypes it supports.

- **Sources:** datasets collected by the data-miner prompts into a datapool, and datasets the
  builder downloads itself when nothing in the pool fits (see `builder/SKILL.md` §data).
- **Prompts:** `prompts/motif_boundary_plan.md`, `prompts/motif_carve.md` and
  `prompts/motif_plan_materialize.md` cut each compiled app into groundable sub-graphs;
  `prompts/data_miner.md` finds and downloads a real dataset for each sub-graph.
- **Code:** `profile_datasets.py` writes the deterministic card (schema `dataset_card_schema.json`:
  tables with at least 8 rows, column types, distinct counts, examples, supported archetypes,
  size, licence); `tag_datasets.py` optionally adds business domains with one model call per card.
- **Output:** one dataset card per datapool slug.

## Intent and rule atoms (`workflow/`)

**Intent atom:** one write that must or must not happen, with its operation kind and verifier kinds.
**Rule atom:** a business rule given as archetype + carrier + exception + shape.

- **Sources:** both are mined together, as skeletons, from public automation templates, vendor
  help centres, SOP libraries and public policies.
- **Prompt and code:** `MINING_BRIEF.md`, filled and run by `mine.sh` (one agent per domain);
  `CONTRACT.md` defines a skeleton and `examples/` holds a mined one.
- **Checks:** every file must pass `skeleton/validate_skeleton.py --strict`; the verifier-kind
  vocabulary in `skeleton/vocab.json` is a fixed list of 45 kinds that the brief and the
  validator use. `skeleton/skel4_recombine.py` multiplies mined skeletons by swapping atoms within a domain.
  `skeleton/compose_skeletons.py` composes new skeletons directly from the published intent and rule atom pools.
- **Output:** `skeleton_spec v2` JSON files plus `SOURCES.tsv` per domain.
- Details: [`docs/skeleton_mining.md`](../docs/skeleton_mining.md).
