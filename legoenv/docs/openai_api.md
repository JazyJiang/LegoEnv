# OpenAI-compatible model access

This page covers how the builder, the teacher collector and the bridge reach a model
endpoint, and how to pass reasoning settings.

## Endpoint and configuration

Every model call is `POST <base>/chat/completions` with JSON `messages` and function
`tools` ([reference](https://developers.openai.com/api/reference/resources/chat),
[function calling](https://developers.openai.com/api/docs/guides/function-calling)),
with `Authorization: Bearer <key>` when a key is set. The base should end in `/v1`;
a full `/chat/completions` URL also works. Any compatible server works, including
self-hosted Qwen or DeepSeek.

```bash
export OPENAI_BASE_URL=https://provider.example/v1
export OPENAI_MODEL=your-model-name
export OPENAI_API_KEY=...        # if required
```

`legoenv/.env.example` lists these variables; the commands do not load `.env` files.
Flags override the variables, so builder and teacher can use different endpoints:

| Command | Endpoint | Extra body |
|---|---|---|
| `pipeline.py build-native` | `--provider-base-url` | `--provider-extra-body` |
| `pipeline.py sample`, `tools/collect.py`, `tools/openai_bridge.py` | `--base-url` | `--extra-body` |

All of them also take `--model` and `--api-key-env` (the name of the key variable).

## Builder bridge

`build-native` ([installation](installation.md)) gives Claude Code inside the
namespace only a loopback messages endpoint and a placeholder key. An in-process
bridge translates the traffic to Chat Completions and keeps the real key in the
parent process. It supports streamed text, parallel tool calls, tool results and
returned reasoning. A missing finish event or invalid function-call JSON is an error.
Token counting and multimodal content return an unsupported error.

The same adapter runs standalone on `127.0.0.1`; see
[`bridge/README.md`](../../bridge/README.md) for `bridge/server.py`:

```bash
python tools/openai_bridge.py --port 8092
```

## Teacher

`pipeline.py sample` ([collecting trajectories](runtime_and_training.md#collect-trajectories))
gives the teacher the goal, the access notes and the API-style search/fetch tools
(`sampling/apistyle.py`). Assistant messages, returned reasoning and tool arguments
are recorded exactly and sent back unchanged in later turns.

## Reasoning settings

The default extra body is `{}`; returned thinking is recorded either way. Qwen
thinking on a server that supports these fields:

```bash
python tools/pipeline.py sample --packs /path/to/packs.tsv --out /path/to/episodes \
  --extra-body '{"top_k":20,"chat_template_kwargs":{"enable_thinking":true}}'
```

For a builder endpoint with `reasoning_effort`, pass
`--provider-extra-body '{"reasoning_effort":"high"}'`. `--forward-reasoning` sends
earlier builder thinking back as `reasoning_content`, a non-standard field. The
bridge never produces reasoning the upstream did not return. In `sample` the extra
body cannot override the model, messages, tools or sampling fields.

## Offline tests

```bash
python -B tools/test_openai_bridge.py
```

These use loopback fixture responses and cover request conversion, the Bearer
header, tool results, fragmented parallel tool calls, stream termination and error
handling.
