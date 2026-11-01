# Compiling a server atom

`legoenv/atoms/server/compiler/` turns one open-source web application into an executable
env-spec in the format of `legoenv/apps/base_specs/*.spec.json`. It has two stages.
Agents write; deterministic code checks what they wrote and hands every finding back
to the same agent session. The deterministic layer never edits the agent's output.

## Stage 1: describe the repository (`atoms/server/compiler/stage1_collect/`)

| file | role |
|---|---|
| `atoms/server/prompts/code_collector.md` | the contract (~1,200 lines): schemas, operations (`impls`), guarded behavior `edges` (needs/provides), `no_edges`/`no_guards` |
| `collect.sh` | shallow-clones each target, runs one Claude Code agent per repo, writes `RUN/collect/<repo>.json` |
| `contract_check.py` | validator. Scores every collect JSON against the contract and writes one work order per non-compliant repo to `RUN/topup/<repo>.json` (coverage, missing ops, each violation with its fix, priority tier) |
| `render_feedback.py` | fills `atoms/server/prompts/edge_topup.md` from a work order |
| `feedback_round.sh` | runs N rounds of validator, then feedback, then revision (default `--rounds 4`, as in the paper) |

**Feedback loop.** `collect.sh` generates the session id itself, passes it with
`claude --session-id`, and stores `{session_id, config_dir, cwd}` in
`RUN/collect/_sessions/<repo>.json` before the agent starts. Each feedback round
re-clones the repository, because every locator in the description points into that
source tree. It then injects the rendered validator output as a new user turn with
`claude --resume <session_id> -p "<feedback>"`. The agent that wrote the file revises
it with its full context, so the round is incremental rather than a fresh run.
Claude Code stores sessions per config dir and per working directory, so both scripts
run the agent with `cwd=RUN`. If you change either, the log shows `resume-fail`
("No conversation found"). A round counts as successful only when the collect file
actually changed. `master.log` records one of `done`, `no-change`, `timeout-partial`,
`timeout-nochange` or `resume-fail` for each repo. Delete `RUN/scratch/locks/` if
a round was killed.

## Stage 2: translate to an executable spec (`atoms/server/compiler/stage2_spec/`)

| file | role |
|---|---|
| `build_prep.py` | **prep**. Deterministic translation of collect JSON into `spec.raw.json`, the full candidate set. Every guessed default and every dropped item is listed in `prep_report.json`. `seal()` normalizes the agent's draft mechanically, adding fields but never changing them |
| `build_seed.py` | throwaway in-memory seed rows for the probe (never written into a spec) |
| `build_probe.py` | **probe**. L0 structure, L1 `runtime.Env` builds, L2 every tool is called once and the state diff is classified, L3 every declared guard is deliberately violated |
| `build_node.py` | prep, then probe the candidate, then the agent (`atoms/server/prompts/build_spec.md`) writes `spec.draft.json`, then probe, then feedback via `build_spec_feedback.md` resumed into the same session (`LEGOENV_R_BUILD`, default 1 round), then the gate |
| `cc_driver.py` | headless `claude -p` / `claude --resume` through the bridge |
| `spec_builder.py` | batch cache: build on miss, keep failures in `_failed.json` |

The agent makes the judgement calls: which candidates to keep, names, the account
table and `auth`, and which guards are real. A spec passes the gate when L1 builds,
at least one write tool changes the state and at least one read/search tool exists.
Passing specs are written to `--spec-dir` as `<repo>.spec.json`. Unresolved probe
findings are returned as `residual`.

Runtime: stage 2 imports `grammar` and `runtime` from
`legoenv/builder/legacy_runtime/`, the runtime the compiler and the base specs were
built with. Set `LEGOENV_RUNTIME_DIR=legoenv/runtime` to use the newer runtime,
which has the same API.

## Running one repository

```bash
export OPENAI_BASE_URL=https://provider.example/v1 OPENAI_MODEL=your-model  # + OPENAI_API_KEY
python bridge/server.py --port 8092 &          # Claude Code -> OpenAI-compatible bridge
export BRIDGE_URL=http://127.0.0.1:8092
printf 'mealie\thttps://github.com/mealie-recipes/mealie\tPython\n' > targets.tsv
C=legoenv/atoms/server/compiler
bash $C/stage1_collect/collect.sh --targets targets.tsv --run runs/demo   # needs timeout/gtimeout
bash $C/stage1_collect/feedback_round.sh --targets targets.tsv --run runs/demo --rounds 4
python3 $C/stage2_spec/build_node.py mealie --collect runs/demo/collect/mealie.json \
    --run runs/demo --spec-dir runs/demo/repo_specs
```

Outputs: `runs/demo/collect/mealie.json` (stage-1 description) and
`runs/demo/build/mealie/` (`spec.raw.json`, `prep_report.json`, `build_report_r*.json`,
`spec.draft.json`, `agent_session.json`). The final `runs/demo/repo_specs/mealie.spec.json`
has the same format as `apps/base_specs/`. Run the agent as a non-root user, since
Claude Code refuses `--dangerously-skip-permissions` as root.
