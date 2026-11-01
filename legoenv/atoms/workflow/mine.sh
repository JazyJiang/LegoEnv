#!/usr/bin/env bash
# Mine skeleton_spec v2 files for one business domain with one Claude Code agent.
#
#   bash mine.sh --domain D --n N --out DIR [--bridge URL] [--model M] [--screen TSV]
#
# Fills MINING_BRIEF.md ({DOMAIN} {N} {OUT} {CONTRACT}=legoenv/skeleton {WORKFLOW} {SCREEN}) into DIR/_run/BRIEF.md
# and runs the agent there in the foreground. The agent writes DIR/mine_<D>_NNN.json and
# DIR/SOURCES.tsv and must finish with `validate_skeleton.py DIR --strict` all valid.
# Use DIR = <mined>/<D> so skel4_recombine.py <mined> ... finds the files.
#
# --bridge  messages endpoint Claude Code talks to (default $BRIDGE_URL or
#           http://127.0.0.1:8092, i.e. `python bridge/server.py --port 8092`)
# --model   model name Claude Code sends (default claude-sonnet-4-5; the bridge
#           replaces it with its own OPENAI_MODEL)
# --screen  optional spec screening table from screen_specs.py (spec_screen.tsv)
#
# Claude Code flags used:
#   -p "<prompt>"                    headless single prompt
#   --max-turns $MAX_TURNS           cap on agent turns (default 200)
#   --dangerously-skip-permissions   no permission prompts (refused as root unless IS_SANDBOX=1)
#   --allowedTools Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch   web access is required
#   --output-format json             final result as one JSON object in DIR/_run/cc.out
# Environment: API_TIMEOUT_MS=3000000 (slow endpoints), CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0
# (do not kill background sub-agents in print mode), MINE_TO=14400 wall clock in seconds,
# CC = claude executable.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); CONTRACT=$(cd "$HERE/../../skeleton" && pwd)
DOMAIN="" N="" OUT="" SCREEN="" BRIDGE_URL=${BRIDGE_URL:-http://127.0.0.1:8092} MODEL=claude-sonnet-4-5
while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN=$2; shift 2;;
    --n)      N=$2; shift 2;;
    --out)    OUT=$2; shift 2;;
    --bridge) BRIDGE_URL=$2; shift 2;;
    --model)  MODEL=$2; shift 2;;
    --screen) SCREEN=$2; shift 2;;
    *) echo "unknown argument: $1"; exit 2;;
  esac
done
[ -n "$DOMAIN" ] && [ -n "$N" ] && [ -n "$OUT" ] || { sed -n '2,9p' "$0"; exit 2; }
python3 -c "import json,sys; sys.exit(0 if sys.argv[1] in json.load(open(sys.argv[2]))['domains'] else 1)" "$DOMAIN" "$CONTRACT/vocab.json" \
  || { echo "domain $DOMAIN is not in vocab.json domains"; exit 2; }
[ -f "$CONTRACT/spec_tools.json" ] || echo "note: $CONTRACT/spec_tools.json missing; run atoms/server/onboarding/export_spec_tools.py first (pool (b) apps and the validator need it)"
if [ "$(id -u)" = 0 ] && [ -z "${IS_SANDBOX:-}" ]; then
  echo "claude refuses --dangerously-skip-permissions as root; run as a normal user (or IS_SANDBOX=1 in a sandbox)"; exit 1
fi
OUT=$(mkdir -p "$OUT" && cd "$OUT" && pwd); RUNDIR=$OUT/_run; mkdir -p "$RUNDIR"
if [ -n "$SCREEN" ]; then SCREEN=$(cd "$(dirname "$SCREEN")" && pwd)/$(basename "$SCREEN")
else SCREEN="the spec screening table (none provided: judge relevance from each spec's about field)"; fi
python3 - "$HERE/MINING_BRIEF.md" "$RUNDIR/BRIEF.md" "$DOMAIN" "$N" "$OUT" "$CONTRACT" "$HERE" "$SCREEN" <<'PY'
import sys
src, dst, d, n, out, contract, workflow, screen = sys.argv[1:]
t = open(src).read()
for k, v in (("{DOMAIN}", d), ("{N}", n), ("{OUT}", out), ("{CONTRACT}", contract), ("{WORKFLOW}", workflow), ("{SCREEN}", screen)):
    t = t.replace(k, v)
open(dst, "w").write(t)
PY
CC=${CC:-$(command -v claude || echo claude)}
TIMEOUT=${TIMEOUT_BIN:-$(command -v timeout || command -v gtimeout)}
[ -n "$TIMEOUT" ] || { echo "needs timeout (coreutils) or gtimeout"; exit 1; }
# Take over the endpoint explicitly: an inherited ANTHROPIC_API_KEY makes Claude Code
# validate the key locally instead of using the bridge.
unset ANTHROPIC_API_KEY
export ANTHROPIC_BASE_URL=$BRIDGE_URL ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN:-local}
export API_TIMEOUT_MS=${API_TIMEOUT_MS:-3000000} CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0
echo "mining $DOMAIN N=$N -> $OUT (log $RUNDIR/cc.out)"
( cd "$RUNDIR" && "$TIMEOUT" -k 120 "${MINE_TO:-14400}" "$CC" -p "Read BRIEF.md in this directory and do exactly what it says." \
    --model "$MODEL" --max-turns "${MAX_TURNS:-200}" --dangerously-skip-permissions \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch" --output-format json \
    > cc.out 2> cc.err < /dev/null )
echo "agent exit $?; validating"
python3 "$CONTRACT/validate_skeleton.py" "$OUT" --strict
