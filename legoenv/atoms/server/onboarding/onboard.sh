#!/usr/bin/env bash
# Onboard new apps: one Claude Code agent per app follows ONBOARD_BRIEF.md, then onboard_check.py judges it.
#
#   bash onboard.sh --workspace WS [--spec-dir DIR] [--screen-dir DIR] [--bridge URL] [--model M] APP[=SLUG] ...
#
# WS        builder workspace; created with `python3 legoenv/tools/builder_workspace.py --out WS` if it
#           does not exist. Agents run with cwd WS/smoke, where the brief's paths (pack/, pack_dpsk/) resolve.
# APP=SLUG  packlib app name (underscores) and the compiler's release slug (may contain hyphens).
# --spec-dir   compiler output with SLUG.spec.json (copied to WS/smoke/apps/base_specs/APP.spec.json)
# --screen-dir screen_specs.py output specs/ with SLUG.screen.json (copied to WS/smoke/pack_dpsk/cards/specs/)
# --bridge  default $BRIDGE_URL or http://127.0.0.1:8092 (`python bridge/server.py --port 8092`)
# --model   model name Claude Code sends (default claude-sonnet-4-5; the bridge substitutes its OPENAI_MODEL)
#
# Claude Code flags: -p, --max-turns $MAX_TURNS (200), --dangerously-skip-permissions,
# --allowedTools Bash,Read,Write,Edit,Glob,Grep (no web), --output-format json.
# Environment: POOL=4 concurrent agents, ONBOARD_TO=14400 s per agent, API_TIMEOUT_MS=3000000, CC.
# Logs: WS/smoke/pack_dpsk/onboardrun/APP/{BRIEF.md,cc.out,cc.err,check.out}. An existing run dir is skipped.
# A PASS leaves WS/smoke/pack/newspecs3/APP/ and WS/smoke/pack/base_specs/APP.spec.json; copy them to
# legoenv/apps/adapters/APP/ and legoenv/apps/base_specs/, then run cards_to_vocab.py.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LEGOENV=$(cd "$HERE/../../.." && pwd)
WS="" SPEC_DIR="" SCREEN_DIR="" BRIDGE_URL=${BRIDGE_URL:-http://127.0.0.1:8092} MODEL=claude-sonnet-4-5 APPS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --workspace)  WS=$2; shift 2;;
    --spec-dir)   SPEC_DIR=$2; shift 2;;
    --screen-dir) SCREEN_DIR=$2; shift 2;;
    --bridge)     BRIDGE_URL=$2; shift 2;;
    --model)      MODEL=$2; shift 2;;
    --*) echo "unknown argument: $1"; exit 2;;
    *) APPS+=("$1"); shift;;
  esac
done
[ -n "$WS" ] && [ ${#APPS[@]} -gt 0 ] || { sed -n '2,6p' "$0"; exit 2; }
if [ "$(id -u)" = 0 ] && [ -z "${IS_SANDBOX:-}" ]; then
  echo "claude refuses --dangerously-skip-permissions as root; run as a normal user (or IS_SANDBOX=1 in a sandbox)"; exit 1
fi
[ -d "$WS" ] || python3 "$LEGOENV/tools/builder_workspace.py" --out "$WS" || exit 1
SM=$(cd "$WS/smoke" && pwd); RUNS=$SM/pack_dpsk/onboardrun; mkdir -p "$RUNS" "$SM/apps/base_specs" "$SM/pack_dpsk/cards/specs"
CC=${CC:-$(command -v claude || echo claude)}
TIMEOUT=${TIMEOUT_BIN:-$(command -v timeout || command -v gtimeout)}
[ -n "$TIMEOUT" ] || { echo "needs timeout (coreutils) or gtimeout"; exit 1; }
unset ANTHROPIC_API_KEY
export ANTHROPIC_BASE_URL=$BRIDGE_URL ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN:-local}
export API_TIMEOUT_MS=${API_TIMEOUT_MS:-3000000} CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0
POOL=${POOL:-4}; LAUNCHED=()
for spec in "${APPS[@]}"; do
  app=${spec%%=*}; slug=${spec#*=}; [ "$slug" = "$spec" ] && slug=$app
  d=$RUNS/$app; [ -d "$d" ] && { echo "skip $app (run dir exists)"; continue; }
  raw=$SM/apps/base_specs/$app.spec.json
  if [ -n "$SPEC_DIR" ] && [ -f "$SPEC_DIR/$slug.spec.json" ]; then cp "$SPEC_DIR/$slug.spec.json" "$raw"
  elif [ ! -f "$raw" ] && [ -f "$SM/pack/base_specs/$app.spec.json" ]; then cp "$SM/pack/base_specs/$app.spec.json" "$raw"; fi
  [ -f "$raw" ] || { echo "skip $app: no $slug.spec.json (pass --spec-dir)"; continue; }
  [ -n "$SCREEN_DIR" ] && [ -f "$SCREEN_DIR/$slug.screen.json" ] && cp "$SCREEN_DIR/$slug.screen.json" "$SM/pack_dpsk/cards/specs/$app.screen.json"
  mkdir -p "$d"; sed "s#{APP}#$app#g" "$HERE/ONBOARD_BRIEF.md" > "$d/BRIEF.md"
  [ -f "$SM/pack_dpsk/cards/specs/$app.screen.json" ] || printf "\nNo screening note exists for this app; work from the spec alone.\n" >> "$d/BRIEF.md"
  [ "$slug" != "$app" ] && printf "\n## Naming\nThe release slug is \`%s\` (hyphen) but the packlib app name MUST be \`%s\` (underscore): use \`%s\` everywhere (PFX \`%s\`).\n" "$slug" "$app" "$app" "$app" >> "$d/BRIEF.md"
  while [ "$(jobs -rp | wc -l)" -ge "$POOL" ]; do sleep 5; done
  ( cd "$SM" && "$TIMEOUT" -k 120 "${ONBOARD_TO:-14400}" "$CC" \
      -p "Read pack_dpsk/onboardrun/$app/BRIEF.md and do exactly what it says. All paths in it are relative to the current directory." \
      --model "$MODEL" --max-turns "${MAX_TURNS:-200}" --dangerously-skip-permissions \
      --allowedTools "Bash,Read,Write,Edit,Glob,Grep" --output-format json > "$d/cc.out" 2> "$d/cc.err" < /dev/null ) &
  LAUNCHED+=("$app"); echo "launched onboard $app ($slug) $(date +%T)"
done
wait
for app in ${LAUNCHED[@]+"${LAUNCHED[@]}"}; do
  ( cd "$SM" && python3 pack_dpsk/contract/onboard_check.py "$app" > "$RUNS/$app/check.out" 2>&1 ); tail -n 1 "$RUNS/$app/check.out"
done
