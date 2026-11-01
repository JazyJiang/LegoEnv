# Mining skeletons

A skeleton (`skeleton_spec v2`) is one JSON file that fixes the shape of a task: apps,
deliverable atoms (which write on which app, positive/negative counts, check precision)
and rule atoms (archetype, policy carrier, exception, one abstract sentence). It holds no
names, values or wording; the builder picks those against real data. See
[`atoms/workflow/CONTRACT.md`](../atoms/workflow/CONTRACT.md). The mining brief and driver are in
`legoenv/atoms/workflow/`, dataset cards in `legoenv/atoms/data/`, onboarding in
`legoenv/atoms/server/onboarding/`, and the contract they all write against (schema,
`vocab.json`, validator, recombination) in `legoenv/skeleton/`; see the
[atom provenance map](../atoms/README.md).

## How mining works

One Claude Code agent with web access mines one business domain. `MINING_BRIEF.md` is
its prompt: sources are public automation template galleries, vendor help centres, SOP
libraries and public policies, at most 3 scenarios per page, never an agent benchmark.
Every value must come from `vocab.json`. The batch must cover all 8 archetypes, at
least 3 carriers, 10 app combinations and 6 kinds, with no duplicate (apps, kinds,
archetypes, rule) tuples. The agent writes `mine_<domain>_NNN.json` plus `SOURCES.tsv`
and must finish with every file passing `validate_skeleton.py --strict`.

## Mining one domain

```bash
python3 legoenv/atoms/server/onboarding/export_spec_tools.py   # skeleton/spec_tools.json: needed by the validator and the brief
export OPENAI_BASE_URL=https://provider.example/v1 OPENAI_MODEL=your-model  # + OPENAI_API_KEY
python bridge/server.py --port 8092 &          # Claude Code -> OpenAI-compatible bridge
bash legoenv/atoms/workflow/mine.sh --domain finance --n 40 --out runs/mined/finance \
    --bridge http://127.0.0.1:8092   # optional: --model M --screen spec_screen.tsv
```

`--domain` must be in `vocab.json`; brief and logs go to `_run/`; run as non-root (flags in
the script header). `export_spec_tools.py --release-specs DIR` adds not yet onboarded apps.

## Validation and recombination

```bash
python3 legoenv/skeleton/validate_skeleton.py runs/mined/finance --strict  # no --strict: relaxed profile
python3 legoenv/skeleton/skel4_recombine.py runs/mined runs/recombined 200  # MINED_DIR OUT_DIR N_PER_DOMAIN
```

The validator checks schema, vocabulary, write tools per kind, carrier hosts, counts and
literal numbers in `rule_shape` (relaxed allows an empty one); exit 1 on any FAIL.
`skel4_recombine.py` reads `MINED_DIR/<domain>/mine_*.json` and swaps atoms per domain.

### Compose from the atom pools

```bash
python3 legoenv/skeleton/compose_skeletons.py --intents atoms/intent_atoms.jsonl \
    --rules atoms/rule_atoms.jsonl --out runs/composed --per-domain 30  # [--seed 924] [--domains d1,d2] [--vocab PATH]
```

`compose_skeletons.py` needs no mined skeletons. Per domain it samples 1-2 rule atoms tagged with
the domain (any rule when the domain has fewer than 5) and 1-3 intent atoms with distinct kinds on
1-4 apps, where each kind is defined for its app in `vocab.kind_tools` and each rule's carrier has a
host app in `apps` (a host from the domain's apps is added if needed). Dedupe, count jitter, `chain`
and `predicate_budget` follow `skel4_recombine.py`; files are `cp_<domain>_NNNN.json` with
`source = composed:<intent ids>+<rule ids>`. Domains without intent atoms are reported as blocked.
Validate the output with `validate_skeleton.py --strict`.

## Dataset cards

```bash
python3 legoenv/atoms/data/profile_datasets.py --roots /path/to/datapool --out runs/cards/datasets
python3 legoenv/atoms/data/tag_datasets.py --cards runs/cards/datasets   # optional, model call per card
```

A root has one directory per slug with `raw/**` and an optional `meta.json`. Cards
(`dataset_card_schema.json`) list tables with >= 8 rows, column types, distinct counts,
examples, supported archetypes, size and licence. `tag_datasets.py` adds domains via the
endpoint flags of [OpenAI API](openai_api.md) (`--base-url`, `--model`, `--api-key-env`).

## Onboarding apps

```bash
python3 legoenv/atoms/server/onboarding/screen_specs.py --out runs/screen [--layer2]  # candidates from spec_tools.json
python3 legoenv/atoms/server/onboarding/make_targets.py --screen runs/screen/spec_screen.tsv \
    --datasets runs/cards/datasets --out runs/targets
bash legoenv/atoms/server/onboarding/onboard.sh --workspace runs/ws --spec-dir runs/demo/repo_specs \
    --screen-dir runs/screen/specs my_app=my-app
python3 legoenv/atoms/server/onboarding/cards_to_vocab.py      # merge passed cards into skeleton/vocab.json
```

`onboard.sh` stages a builder workspace (`tools/builder_workspace.py`) if needed, runs
one agent per app on `ONBOARD_BRIEF.md`, then `skeleton/onboard_check.py <app>` (must print
`ONBOARD <app> PASS`). Copy the workspace's `smoke/pack/newspecs3/<app>/` and
`smoke/pack/base_specs/<app>.spec.json` into `apps/adapters/` and `apps/base_specs/`,
then run `cards_to_vocab.py` (`--cards`, `--vocab`, `--out`).
