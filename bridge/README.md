# Claude Code → OpenAI bridge

`server.py` is a standard-library-only protocol adapter. Its local messages
endpoint accepts Claude Code text/function-tool traffic; upstream calls use
OpenAI Chat Completions and optional Bearer authentication. There are no
company routing headers, internal service addresses or built-in provider keys.

```bash
export OPENAI_BASE_URL=https://provider.example/v1
export OPENAI_MODEL=your-model
# Set OPENAI_API_KEY privately if required by your provider.
python bridge/server.py --port 8092
```

Point Claude Code's `ANTHROPIC_BASE_URL` at `http://127.0.0.1:8092` and use an
ordinary local placeholder for `ANTHROPIC_API_KEY`. Those variables configure
the local client protocol only. The actual upstream key remains in the bridge
process and is sent as `Authorization: Bearer ...`.

See the current [OpenAI API guide](../legoenv/docs/openai_api.md)
for reasoning extensions and the isolated builder's automatic in-process bridge.
The standalone and builder adapter sources have matching final hashes.

## Pinned Claude Code download

The harness version is **2.1.186**. No executable is committed. The official
npm package is [`@anthropic-ai/claude-code@2.1.186`](https://www.npmjs.com/package/@anthropic-ai/claude-code/v/2.1.186).
Its immutable [tarball](https://registry.npmjs.org/@anthropic-ai/claude-code/-/claude-code-2.1.186.tgz)
and the matching Linux native-package URLs/SRI hashes are recorded in
`claude_code.lock.json`.

For a normal host install with Node/npm:

```bash
npm install --prefix /path/to/private/claude-code-2.1.186 --save-exact @anthropic-ai/claude-code@2.1.186
DISABLE_AUTOUPDATER=1 /path/to/private/claude-code-2.1.186/node_modules/.bin/claude --version
```

The isolated builder mounts a single native executable, so an npm wrapper or
symlink is not sufficient. The provided downloader installs the actual native
binary from the same fixed-version official npm platform package and verifies
its locked SHA512 before extracting it:

```bash
python bridge/install_claude_code.py \
  --platform linux-x64 --dest /path/to/private/claude-code-2.1.186
```

Pass the printed `/path/to/private/claude-code-2.1.186/claude` to the builder's
`--claude` flag. Linux x64 and arm64 glibc are pinned here; other platforms should
use the official version-pinned npm installation. Auto-updating is disabled in
the builder namespace. `--download-only` verifies/extracts without executing the
version command. Downloads and local receipts belong outside the repository.

Official installation guidance: [Claude Code setup](https://code.claude.com/docs/en/setup).
Claude Code retains Anthropic's upstream licence; this project does not grant a
licence for or redistribute the binary.
