# RL environment interface

This page covers `training/rl/`: the code that serves a LegoEnv world to a policy
during RL, scores the episode with the task verifier and builds the prompt set from
packs. It contains no trainer; plug it into your own RL stack. Commands run from
`training/rl/`. The settings of the reported GRPO run are in
[HYPERPARAMETERS.md](../training/HYPERPARAMETERS.md#grpo).

| Path | Role |
|---|---|
| `rl_env/env_host.py` | Serves one world in a child process over JSON lines |
| `rl_env/episode.py` | `EnvHost`, the client that starts and talks to `env_host.py` |
| `rl_env/tool_env.py` | `LegoEnvToolEnv`: takes assistant-turn text, executes tool calls, returns observations and the reward |
| `rl_env/toolcall.py` | Splits a turn into reasoning and text and parses Qwen3-Coder `<tool_call>` XML |
| `rl_env/render.py` | Renders an episode to token ids with the policy's chat template |
| `rl_env/dataset.py` | Loads and batches the prompt JSONL |
| `rl_env/local_rollout.py` | Framework-free episode loop with reference, no-op and random policies |
| `rl_env/paths.py` | Resolves relative pack paths from `training/rl/` |
| `envlib/collect_oai.py` | Execution adapter used by the env host: prompts, tool schemas and API-style routing over `legoenv/runtime/` and `legoenv/sampling/apistyle.py` |
| `build_prompts.py` | Selects prompts from teacher judgments |
| `tools/env_selfcheck.py` | Runs environments without a model or a trainer |

Prompt sets and seeded worlds are not included (`training/rl/INPUT_DATA.md`). The
environment side needs only the standard library and the LegoEnv runtime; `render.py`
and the template check need a Transformers tokenizer.

## Serving a world

`EnvHost()` starts `python rl_env/env_host.py envlib/` as a child process (interpreter
from `ENVLIB_ENV_PYTHON`, default the current one) and talks to it in one JSON object
per line:

| Operation | Request | Reply |
|---|---|---|
| `reset` | pack record (`tid`, `task_path`, `spec_path`, `system_path`) | `system`, `user`, `tools`: the policy's first two messages and tool list, from a fresh copy of the pack's seed state |
| `call` | `name`, `arguments` | `obs` (tool result text) and `info` (`invalid` and other flags) |
| `verify` | none | `pass` (task verifier on the current state), `verifier_error`, call statistics |
| `gold_next` | `i` | the i-th step of the reference solution as an `api_fetch` call, or `done` |
| `close` | none | the process exits |

One host per episode keeps episodes independent: a crash in a world ends that episode
only. The policy sees three tools, `api_search` (BM25 search over the world's endpoint
catalog), `api_fetch` (call an endpoint by method and URL) and `base64_encode`.

## An episode

`LegoEnvToolEnv` wraps a host with the three calls a trainer makes:

```python
from rl_env.tool_env import LegoEnvToolEnv

env = LegoEnvToolEnv(wall_seconds=1800, tool_timeout_s=120, reset_timeout_s=300)
_, info, _ = env.reset(record=prompt_record)
messages, tools = info["envlib_initial_messages"], info["tools"]   # render with the chat template
while True:
    text = generate(messages, tools)          # your policy; raw decoded turn incl. end-of-turn token
    obs, reward, done, _, step_info = env.step(text)
    if done:
        break
    ...                                       # append the turn and the tool results in obs
# when your trainer stops the episode (turn or context limit):
# env.finalize_truncated("exceed_max_steps" | "exceed_max_length")
```

`step` splits the turn at `</think>`, parses the `<tool_call>` blocks and executes
them in order. A turn with tool calls returns the list of results, reward 0, not
done. A turn without tool calls ends the episode (`stop`), as do a turn cut off before
its end-of-turn token (`length`), a turn ending in a token other than `<|im_end|>`
(`eos_other`), the wall-time cap (`wall_cap`) and
`finalize_truncated` (`max_turns`, `context`). The final step's `info["metrics"]`
reports the finish reason, turns, tool calls and invalid or failed calls.

`render.TurnRenderer(tokenizer, initial_messages, tools)` gives the token form of the
same episode: `first_prompt_ids()`, then after each generated turn
`tool_turn_ids(observations)` for the tool results and the next assistant header. The
trajectory is the concatenation of these with the generated tokens; only generated
tokens carry loss. The generated reasoning therefore stays in context for later turns.

`local_rollout.run_episode(record, policy)` runs this loop without a trainer; a policy
is any callable `policy(env, messages) -> (turn_text, assistant_message)`.

## Reward

When an episode ends, `LegoEnvToolEnv` calls `verify` once on the final world state.
The reward is 1.0 if the task verifier accepts that state and 0.0 otherwise. The
constructor's shaping options (`invalid_call_penalty`, `truncation_penalty`,
`require_stop`) were all off in the reported run. If the environment process fails
(`EnvHostError` on reset, a call or verify), the episode returns reward 0 with
`info["envlib_infra_error"]` set; drop such trajectories from the batch instead of
training on them as failures. Model errors (invalid calls, wrong writes, no answer)
are ordinary failures.

## Prompt set

```bash
python build_prompts.py --judged /path/to/judgments.jsonl --packs-tsv /path/to/packs.tsv \
  --results /path/to/build-results --out-dir data --stage-dir packs --gold-check 4
```

A pack is kept with at least 4 valid teacher attempts, at least one pass and
estimated pass@8 between 1 and 6 inclusive (`--min-valid`, `--min-pass`,
`--min-pass8`, `--max-pass8`); collector interruptions are not counted.
`--gold-check N` replays each reference solution (expects reward 1) and a no-op
(expects 0) with N workers. Output: `prompts.jsonl` and a 32-prompt
`prompts_smoke.jsonl`. Records need `tid`, `task_path`, `spec_path` and optionally
`system_path`; relative paths resolve from `training/rl/`. A record is the whole
prompt: `reset` builds the messages and tools from the pack.
`dataset.PromptDataset(path).batches(prompts_per_step)` yields seeded, shuffled
steps of records.

Check the environments before training:

```bash
python tools/env_selfcheck.py --prompts data/prompts_smoke.jsonl --n 3 \
  [--tokenizer /path/to/Qwen3.8-27B]
```

It expects reward 1 for the reference replay and 0 for the no-op on each of the first
N prompts, and with `--tokenizer` checks that the chat template renders tool turns
prefix-stably.

## GRPO run

The reported run trained the original Qwen3.8-27B with GRPO on 1,516 prompts: group
size 8, 12 prompts per update, 252 updates, binary verifier reward, no KL term. The
released checkpoint is update 200 ([models](models.md)). All recorded settings:
[HYPERPARAMETERS.md](../training/HYPERPARAMETERS.md#grpo).
