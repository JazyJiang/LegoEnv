#!/usr/bin/env bash
# Stage 1, pass 1: one code-reading agent per open-source repository.
#
#   bash collect.sh --targets TARGETS.tsv --run RUN_DIR [--bridge URL] [--pool N]
#
# TARGETS.tsv: one repo per line, tab-separated: <slug> <git url> <language> [<tag>]
# (lines starting with # are ignored). For each repo: shallow clone -> Claude Code
# agent with the contract prompt (code_collector.md) -> <RUN_DIR>/collect/<slug>.json
# -> delete the clone. Finished repos are skipped on rerun (resumable).
#
# The session id is generated here and passed with --session-id, and a sidecar
# <RUN_DIR>/collect/_sessions/<slug>.json records {session_id, config_dir, cwd}
# before the agent starts, so feedback_round.sh can `claude --resume` the SAME
# session later. Claude Code stores sessions per config dir AND per working
# directory, so the agent always runs with cwd=RUN_DIR (never cd elsewhere).
#
# Environment knobs (defaults are the values the paper's run used):
#   POOL=12          concurrent repos (each repo may run 1.5-3 requests: sub-agents)
#   MAX_MB=400       skip repos larger than this after cloning
#   COLLECT_TO=21600 per-repo wall clock (s); CLONE_TO=1800; CLONE_TRIES=4
#   PROMPT_FILE      contract prompt (default legoenv/atoms/server/prompts/code_collector.md)
#   CC               claude executable (default: claude on PATH)
#   CLAUDE_CONFIG_DIR  Claude Code config dir (default ~/.claude-legoenv)
#   UPSTREAM_PROBE=0 disable the endpoint health probe before each dispatch
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
LEGOENV=$(cd "$HERE/../../../.." && pwd)
TARGETS="" RUN="" BRIDGE_URL=${BRIDGE_URL:-http://127.0.0.1:8092}
while [ $# -gt 0 ]; do
  case "$1" in
    --targets) TARGETS=$2; shift 2;;
    --run)     RUN=$2; shift 2;;
    --bridge)  BRIDGE_URL=$2; shift 2;;
    --pool)    POOL=$2; shift 2;;
    *) echo "unknown argument: $1"; exit 2;;
  esac
done
[ -n "$TARGETS" ] && [ -n "$RUN" ] || { sed -n '2,6p' "$0"; exit 2; }
RUN=$(mkdir -p "$RUN" && cd "$RUN" && pwd)
OUT=$RUN/collect; SCRATCH=$RUN/scratch; CLONES=$SCRATCH/clones; LOGS=$SCRATCH/logs
PROMPT_FILE=${PROMPT_FILE:-$LEGOENV/atoms/server/prompts/code_collector.md}
CC=${CC:-$(command -v claude || echo claude)}
PY=${PYTHON:-$(command -v python3)}
POOL=${POOL:-12}; MAX_MB=${MAX_MB:-400}; CLONE_TO=${CLONE_TO:-1800}
COLLECT_TO=${COLLECT_TO:-21600}; CLONE_TRIES=${CLONE_TRIES:-4}; CLONE_BACKOFF=${CLONE_BACKOFF:-25}
export CLAUDE_CONFIG_DIR=${CLAUDE_CONFIG_DIR:-$HOME/.claude-legoenv}
# Take over the endpoint explicitly: an inherited ANTHROPIC_API_KEY makes recent
# Claude Code versions validate the key locally and refuse to send anything.
export ANTHROPIC_BASE_URL=$BRIDGE_URL ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN:-local}
unset ANTHROPIC_API_KEY
TIMEOUT=${TIMEOUT_BIN:-$(command -v timeout || command -v gtimeout)}

mkdir -p "$OUT/_sessions" "$CLONES" "$LOGS/clone_err"
MASTER=$LOGS/master.log
log(){ echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$MASTER"; }
throttle(){ while [ "$(jobs -rp | wc -l)" -ge "$POOL" ]; do sleep 2; done; }

# A finished output has all three layers, or explicitly says "not a CRUD app".
# Checking only schemas+impls once marked runs killed before the edge layer as done.
valid_out(){
  "$PY" - "$1" <<'PYEOF'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(1)
if not isinstance(d, dict):
    sys.exit(1)
s = (d.get("summary") or "").lower()
if "not a crud" in s or "skipped" in s:
    sys.exit(0)
if not (d.get("schemas") and d.get("impls")):
    sys.exit(1)
if not (d.get("edges") or d.get("no_edges")):
    sys.exit(1)
sys.exit(0)
PYEOF
}

# Files the agent may leave next to its output (helper scripts, shards). Only names
# starting with "_" or non-JSON files are moved; a bare <name>.json is never touched,
# because concurrent repos write into the same directory.
is_scratch_file(){
  case "$1" in _sessions) return 1;; _*) return 0;; *.json) return 1;; *) return 0;; esac
}

collect_one(){
  local slug="$1" url="$2" lang="$3" out="$OUT/$1.json"
  if [ -s "$out" ] && valid_out "$out"; then log "skip(done) $slug"; return; fi
  local dir="$CLONES/$slug" ctry=0 cok=0; rm -rf "$dir"
  while [ $ctry -lt "$CLONE_TRIES" ]; do     # concurrent clones get rate-limited: retry
    if "$TIMEOUT" "$CLONE_TO" git clone --depth 1 --recurse-submodules --shallow-submodules \
         "$url" "$dir" >"$LOGS/clone_err/$slug.txt" 2>&1; then cok=1; break; fi
    ctry=$((ctry+1)); rm -rf "$dir"; [ $ctry -lt "$CLONE_TRIES" ] && sleep $((ctry*CLONE_BACKOFF))
  done
  [ "$cok" = 1 ] || { log "clone-fail $slug"; return; }
  local sz; sz=$(du -sm "$dir" 2>/dev/null | cut -f1)
  if [ "${sz:-0}" -gt "$MAX_MB" ]; then log "too-big-skip $slug (${sz}MB)"; rm -rf "$dir"; return; fi
  local sid; sid=$("$PY" -c "import uuid;print(uuid.uuid4())")
  "$PY" - "$OUT/_sessions/$slug.json" "$sid" "$CLAUDE_CONFIG_DIR" "$RUN" "$slug" <<'PYEOF'
import json, sys, time
json.dump({"repo": sys.argv[5], "session_id": sys.argv[2], "config_dir": sys.argv[3],
           "cwd": sys.argv[4], "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
          open(sys.argv[1], "w", encoding="utf-8"), indent=1)
PYEOF
  local work="$SCRATCH/work/$slug"; rm -rf "$work"; mkdir -p "$work"
  # Bash expansion, not sed: language fields such as "C#" break sed substitutions.
  local prompt; prompt=$(cat "$PROMPT_FILE")
  prompt=${prompt//\{\{REPO\}\}/$dir}; prompt=${prompt//\{\{LANG\}\}/$lang}
  prompt=${prompt//\{\{OUT\}\}/$out};  prompt=${prompt//\{\{WORK\}\}/$work}
  local t0=$SECONDS
  ( cd "$RUN" && "$TIMEOUT" -k 120 "$COLLECT_TO" "$CC" --dangerously-skip-permissions \
      --session-id "$sid" -p "$prompt" </dev/null ) > "$LOGS/$slug.log" 2>&1
  local rc=$? el=$((SECONDS-t0)) wall=finished
  rm -rf "$dir"
  case "$rc" in 124|137) wall=TIMEOUT;; esac
  for f in "$OUT"/*; do
    [ -f "$f" ] || continue
    is_scratch_file "$(basename "$f")" && { mkdir -p "$SCRATCH/stray"; mv -f "$f" "$SCRATCH/stray/"; }
  done
  if [ -s "$out" ] && valid_out "$out"; then log "ok $slug (${sz}MB ${el}s $wall)"
  elif [ -s "$out" ]; then mkdir -p "$SCRATCH/partial"; mv -f "$out" "$SCRATCH/partial/"
    log "partial $slug (${sz}MB ${el}s $wall; moved to scratch/partial)"
  else log "no-output $slug (${sz}MB ${el}s $wall)"; fi
}

if [ "$(id -u)" = 0 ] && [ -z "${IS_SANDBOX:-}" ]; then
  echo "claude refuses --dangerously-skip-permissions as root; run as a normal user (or IS_SANDBOX=1 in a sandbox)"; exit 1
fi
[ -f "$PROMPT_FILE" ] || { echo "prompt not found: $PROMPT_FILE"; exit 1; }
[ -f "$TARGETS" ] || { echo "targets not found: $TARGETS"; exit 1; }
[ -n "$TIMEOUT" ] || { echo "need timeout(1) (coreutils; gtimeout on macOS)"; exit 1; }
command -v "$CC" >/dev/null || { echo "claude CLI not found: $CC"; exit 1; }

# If the endpoint is down, claude exits within seconds and the loop would burn the
# whole target list; probe through the bridge and wait instead.
upstream_ok(){
  [ "${UPSTREAM_PROBE:-1}" = 0 ] && return 0
  [ "$(curl -s -o /dev/null -m "${UPSTREAM_PROBE_TO:-60}" -w '%{http_code}' -X POST "$ANTHROPIC_BASE_URL/v1/messages" \
       -H 'Content-Type: application/json' -H 'x-api-key: local' -H 'anthropic-version: 2023-06-01' \
       -d '{"model":"default","max_tokens":8,"messages":[{"role":"user","content":"hi"}]}')" = 200 ]
}

log "===== collect run=$RUN pool=$POOL collect_to=${COLLECT_TO}s bridge=$BRIDGE_URL ====="
while IFS=$'\t' read -r slug url lang tag _rest; do
  [ -z "${slug:-}" ] && continue
  case "$slug" in \#*) continue;; esac
  throttle
  until upstream_ok; do log "endpoint not answering; waiting 30s"; sleep 30; done
  collect_one "$slug" "$url" "${lang:-}" &
done < "$TARGETS"
wait
log "===== done: $(ls "$OUT"/*.json 2>/dev/null | wc -l | tr -d ' ') outputs in $OUT ====="
