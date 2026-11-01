# Runtime, sampling and training data

This page covers the deterministic runtime, teacher trajectory collection, export of
trajectories to SFT data, and what a trainer must preserve. Commands run from `legoenv/`.

## Prompts

`prompts/BUILDER.md` is the builder prompt and `prompts/AGENT_BRIEF.md` the
failure-diagnosis prompt; their hashes are in `prompts/IDENTITIES.json`.
`atoms/server/prompts/` and `atoms/data/prompts/` hold the prompts behind the server and
data atom pools (see [compiler](compiler.md) and the [atom provenance map](../atoms/README.md))
and `sampling/prompts/` the teacher's rollout prompt. The builder prompt points at the reference packs
`builder/examples/clean_quality_review` and `clean_leave_closeout`, which need the
source datasets named in their READMEs.

## Requirements

Python 3.12 or later. The runtime and the demo use only the standard library;
Parquet inputs also need `pyarrow`. No trainer is included: the exporter below writes
standard chat-format JSONL for any SFT stack, and [RL](rl.md) describes the
environment interface for an RL loop.

## Demo environment

```bash
python tools/preflight.py --mode runtime
python tools/pipeline.py build-demo --out /tmp/legoenv-demo
python tools/pipeline.py verify --task /tmp/legoenv-demo/demo.task.json \
                                --spec /tmp/legoenv-demo/demo.spec.json
```

`build-demo` writes a two-record spec, task and `packs.tsv` into a new directory.
`verify` replays the task's reference solution (`witness`) and passes when the
verifier is false on the seed state, true after the replay and false again on a
fresh world.

## Render the builder prompt

```bash
python tools/pipeline.py render-builder --skeleton /path/to/skeleton.json \
  --contract skeleton --base-specs apps/base_specs --out /tmp/builder-prompt.md
```

This validates the skeleton strictly against `skeleton/` and writes the filled
builder prompt without a model request. Apps a skeleton may name:
[app integrations](app_integrations.md).

## Collect trajectories

```bash
export OPENAI_API_KEY=...
python tools/pipeline.py sample --packs /path/to/packs.tsv --out /path/to/episodes \
  --base-url https://provider.example/v1 --model your-teacher --samples 8 --dry-run
```

`--dry-run` prints the command without sending requests. `sample` runs
`tools/collect.py` with 100 turns, an 8-hour wall cap, temperature 1.0, top-p 0.95
and 4 workers by default. Endpoint and reasoning flags: [model access](openai_api.md).

The pack list has four tab-separated columns: pack set, task JSON, spec JSON, and a
notes file or `-`. Relative paths resolve from the list's directory. The notes file
holds the operator accounts and ordinary environment instructions the goal omits; it
must not contain reference actions or verifier clauses.

Each episode starts from a fresh world. Records keep returned `reasoning_content`,
tool calls and literal tool arguments (including the string `None`). Episode ids hash
the task, spec, sample index, model, endpoint, notes, sampling settings, tool schemas
and code, so re-running with the same inputs skips recorded episodes. API keys are
not recorded. Transport and protocol failures are recorded, not resampled.

## Export to SFT JSONL

```bash
python training/sft/tools/episodes_to_jsonl.py /path/to/episodes -o /path/to/sft.jsonl \
  --filter complete_verifier_pass --check-tool-names
```

| `--filter` | Keeps episodes where |
|---|---|
| `keep` (default) | `keep` is true |
| `verifier_pass` | `verifier_pass` is true |
| `complete_verifier_pass` | the verifier passed and collection ended normally (`stop`/`end_turn`, no error) |
| `all` | no selection; structural checks still apply |
| `/path/file.py:fn` | a custom function returns true |

The exporter keeps existing `step_loss_mask` fields but does not infer loss masks
for error turns, and does not tokenize. A message with `step_loss_mask` other than 1
stays in the input with no loss.

Thinking is exported unchanged; how it is rendered depends on the model's chat
template. The Qwen3.5 template ignores `preserve_thinking` and drops reasoning before
a later user turn. The Qwen3.6 template supports `preserve_thinking`. A single user
request followed by tool interactions keeps all reasoning in both. Render a few
exported conversations with your tokenizer's `apply_chat_template(messages,
tools=tools)` and inspect them before training.

For Qwen3.5, first replace `None`-valued tool arguments with the string `"null"`
(its template renders `None` where Qwen3.8 renders `null`):

```bash
python training/sft/tools/derive_q35.py /path/to/sft.jsonl /path/to/sft_q35.jsonl
```

## Training

LegoEnv provides training data and environments, not a trainer. For SFT, export
trajectories as above and train with any stack that renders `messages` and `tools`
through the base model's chat template. For RL, serve the environments with the
interface in [RL](rl.md). The settings of the reported SFT and GRPO runs (base models,
corpora, batch sizes, learning rates, schedules, loss mask, parallelism) are recorded
in [HYPERPARAMETERS.md](../training/HYPERPARAMETERS.md); released checkpoints are in
[models](models.md).

What the trained model must preserve to match the environments and the reported
runs: reasoning stays in context across the tool turns of an episode (the SFT loss
covers each assistant turn's reasoning, `</think>`, content and tool calls, and RL
appends each generated turn, reasoning included, to the context), and tool calls use
the Qwen3-Coder format the chat templates render, `<tool_call><function=NAME>` with
one `<parameter=KEY>` block per argument, parsed back by
`training/rl/rl_env/toolcall.py`. Tool results are returned as `tool` messages and
are never trained on.

## Synthetic table data

`tools/schema_data.py` plans exact row ranges from schema cards, validates generated
chunks and merges them. It makes no model requests; the cards, prompt, generator
identity file and chunks are supplied by the caller.

```bash
python tools/schema_data.py plan --cards /path/to/cards --prompt /path/to/prompt.txt \
  --identity /path/to/generator.json --out /tmp/schema-plan --max-rows 2
python tools/schema_data.py register --plan /tmp/schema-plan/your-card.json \
  --job-id t0000-c00000000 --chunks /tmp/schema-chunks --output /path/to/part0.json
python tools/schema_data.py merge --plan /tmp/schema-plan/your-card.json \
  --chunks /tmp/schema-chunks --out /tmp/schema-merged.json --receipt /tmp/schema-merged.receipt.json
```

Chunks are bound to the schema, prompt, generator identity and code hashes and are
not reused under different inputs. Missing, duplicate or shifted ranges, edited
outputs and wrong types or counts are rejected; unconfirmed cards are skipped.
Cross-table consistency is not checked. The identity file must not contain
credentials.

## Copy the reference packs into another workspace

Workspaces staged by `tools/builder_workspace.py` already contain both reference
packs. For one staged elsewhere:

```bash
python tools/stage_reference_examples.py --stack /path/to/workspace/smoke \
  --examples /path/to/reference-packs
```

`--examples` must contain `IDENTITIES.json` and both packs; existing packs are not
overwritten.
