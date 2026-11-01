# Installation

This page covers the host requirements and the commands that build an environment
from a skeleton with the isolated native builder.

## Requirements

| Component | Notes |
|---|---|
| Linux host | Isolated mount, PID and network namespaces. `--namespace-mode user` (default) needs user namespaces; `root` needs a privileged executor |
| Python | A complete Python 3.12 prefix, including its standard library, passed as `--python-root` |
| Dataset dependencies | A directory of Python packages for the data stage (including `pyarrow` for Parquet), passed as `--data-deps` |
| Claude Code | Native 2.1.186 executable, passed as `--claude`; install with `bridge/install_claude_code.py` ([`bridge/README.md`](../../bridge/README.md)). An npm wrapper or symlink does not work |
| Model endpoints | OpenAI-compatible Chat Completions for builder and teacher ([model access](openai_api.md)) |

Binaries, frameworks and model weights are not included in the repository.

## Offline checks

Run from `legoenv/`. These use only the standard library and make no model requests.

```bash
python -B tools/preflight.py --mode runtime
python -B tools/test_openai_bridge.py
python -B tools/release_check.py
```

`release_check.py` verifies the hashes in `provenance/CODE_MANIFEST.json` and
`prompts/IDENTITIES.json` and Python syntax.

## Data root

`--data` points at a directory containing `datapool/<slug>/...` and optionally
`datapool_ext/`. `--inventory` is a Markdown file that describes the files, schemas
and provenance actually present there. Both are mounted read-only into the builder.

## Build one environment

Run once with `--cpu-probe` to check the namespace and dependencies without a
model request:

```bash
export OPENAI_API_KEY=...
python tools/pipeline.py build-native \
  --data /path/to/data-root --inventory /path/to/DATA_INVENTORY.md \
  --skeleton /path/to/skeleton.json --out /path/to/cpu-probe \
  --python-root /path/to/python312 --data-deps /path/to/data-deps \
  --claude /path/to/claude --provider-base-url https://provider.example/v1 \
  --model your-builder-model --namespace-mode user --cpu-probe
```

Then run the same command without `--cpu-probe` and with a new `--out` directory.

| Flag | Default | Meaning |
|---|---|---|
| `--provider-base-url`, `--model` | `OPENAI_BASE_URL`, `OPENAI_MODEL` | Builder endpoint and model |
| `--api-key-env` | `OPENAI_API_KEY` | Name of the variable holding the key |
| `--provider-extra-body` | `{}` | Provider-specific request fields as JSON |
| `--forward-reasoning` | off | Send earlier thinking back as `reasoning_content` |
| `--max-turns` | 160 | Agent turn limit |
| `--wall-seconds` | 18000 | Wall-clock limit per attempt |
| `--namespace-mode` | `user` | `user` or `root` |
| `--stack` | staged from the repository | A pre-staged workspace (`smoke/` and `LegoEnv/`) |
| `--data-python-root` | `--python-root` | Separate Python prefix for the data stage |

The API key stays in the parent process. The workspace is assembled by
`tools/builder_workspace.py`. Admitted environments are listed in `packs.tsv` and the admission result is in
`RESULT.json`. A failed attempt is kept in the output directory and is not retried.

## Next steps

[Runtime and training](runtime_and_training.md) covers replaying and sampling built
environments; [app integrations](app_integrations.md) lists the apps a skeleton can
use; the [server-atom compiler](compiler.md) adds new apps.
