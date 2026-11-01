#!/usr/bin/env bash
# Stage 1, feedback rounds: validator -> violations -> the SAME agent session revises.
#
#   bash feedback_round.sh --run RUN_DIR --targets TARGETS.tsv [--rounds 4] [--only SLUG]
#                          [--bridge URL] [--pool N]
#
# Each round:
#   1. contract_check.py RUN/collect RUN/topup   writes one work order per repo that
#      still violates the contract (repos that pass get no work order);
#   2. for every work order, render_feedback.py fills edge_topup.md with the
#      violations and their fixes, and the text is sent as a new user turn with
#        claude --resume <session_id> -p "<feedback>"
#      using the session id/config dir/cwd from collect/_sessions/<slug>.json, so the
#      agent that wrote the description revises its own file with its full context;
#   3. the repo is cloned again (stage 1 deletes clones) because every locator in the
#      output points into that source tree.
# After the last round the validator runs once more so RUN/topup reflects the final state.
# Outcome per repo in RUN/scratch/topup_logs/master.log: done | no-change |
# timeout-partial | timeout-nochange | resume-fail (session not found: cwd/config differ).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
LEGOENV=$(cd "$HERE/../../../.." && pwd)
RUN="" TARGETS="" ROUNDS=4 ONLY="" BRIDGE_URL=${BRIDGE_URL:-http://127.0.0.1:8092}
while [ $# -gt 0 ]; do
  case "$1" in
    --run) RUN=$2; shift 2;;  --targets) TARGETS=$2; shift 2;;
    --rounds) ROUNDS=$2; shift 2;;  --only) ONLY=$2; shift 2;;
    --bridge) BRIDGE_URL=$2; shift 2;;  --pool) POOL=$2; shift 2;;
    *) echo "unknown argument: $1"; exit 2;;
  esac
done
[ -n "$RUN" ] && [ -n "$TARGETS" ] || { sed -n '2,5p' "$0"; exit 2; }
RUN=$(cd "$RUN" && pwd)
COLLECT=$RUN/collect TOPUP=$RUN/topup SCRATCH=$RUN/scratch
CLONES=$SCRATCH/clones LOGS=$SCRATCH/topup_logs LOCKS=$SCRATCH/locks
TPL=${TPL:-$LEGOENV/atoms/server/prompts/edge_topup.md}
CC=${CC:-$(command -v claude || echo claude)}
PY=${PYTHON:-$(command -v python3)}
POOL=${POOL:-12} CLONE_TO=${CLONE_TO:-1800} TOPUP_TO=${TOPUP_TO:-10800}
TIMEOUT=${TIMEOUT_BIN:-$(command -v timeout || command -v gtimeout)}
unset ANTHROPIC_API_KEY
mkdir -p "$CLONES" "$LOGS" "$LOCKS"
MASTER=$LOGS/master.log
log(){ echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$MASTER"; }
throttle(){ while [ "$(jobs -rp | wc -l)" -ge "$POOL" ]; do sleep 2; done; }
url_of(){ awk -F'\t' -v s="$1" '$1==s{print $2; exit}' "$TARGETS"; }
jget(){ "$PY" -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]) or '')" "$1" "$2"; }
fsum(){ cksum "$1" 2>/dev/null | cut -d" " -f1-2 || echo 0; }   # content, not mtime (1 s resolution)

topup_one(){
  # One run per repo at a time: two resumes of one session would overwrite each other.
  local slug; slug=$(basename "$1" .json)
  mkdir "$LOCKS/$slug.lock.d" 2>/dev/null || { log "skip-locked $slug"; return; }
  _topup_body "$1"
  rmdir "$LOCKS/$slug.lock.d" 2>/dev/null
}

_topup_body(){
  local order="$1" slug; slug=$(basename "$order" .json)
  local sc="$COLLECT/_sessions/$slug.json" sid cfg cwd
  if [ -s "$sc" ]; then sid=$(jget "$sc" session_id); cfg=$(jget "$sc" config_dir); cwd=$(jget "$sc" cwd)
  else sid=$(jget "$order" session_id); cfg=$(jget "$order" config_dir); cwd=""; fi
  [ -n "$sid" ] || { log "no-session $slug (rerun collect.sh for it)"; return; }
  cwd=${cwd:-$RUN}
  local url; url=$(url_of "$slug"); [ -n "$url" ] || { log "no-url $slug"; return; }
  local dir="$CLONES/$slug" ok=0 w
  for w in 0 5 20 60; do
    [ "$w" -gt 0 ] && sleep "$w"; rm -rf "$dir"
    "$TIMEOUT" "$CLONE_TO" git clone --depth 1 --recurse-submodules --shallow-submodules \
      "$url" "$dir" >/dev/null 2>&1 && { ok=1; break; }
  done
  [ "$ok" = 1 ] || { log "clone-fail $slug"; rm -rf "$dir"; return; }
  local prompt; prompt=$("$PY" "$HERE/render_feedback.py" "$order" "$TPL" "$COLLECT/$slug.json")
  local before after rc cov; before=$(fsum "$COLLECT/$slug.json")
  cov=$("$PY" -c "import json,sys;print('%.0f%%'%(json.load(open(sys.argv[1]))['coverage']*100))" "$order")
  ( cd "$cwd" && CLAUDE_CONFIG_DIR=${cfg:-${CLAUDE_CONFIG_DIR:-$HOME/.claude-legoenv}} \
      ANTHROPIC_BASE_URL=$BRIDGE_URL ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN:-local} \
      "$TIMEOUT" -k 120 "$TOPUP_TO" "$CC" --dangerously-skip-permissions --resume "$sid" -p "$prompt" \
      </dev/null > "$LOGS/$slug.r$ROUND.log" 2>&1 )
  rc=$?; after=$(fsum "$COLLECT/$slug.json"); rm -rf "$dir"
  # The only deliverable of a round is a changed file, so success is judged on that.
  if grep -q "No conversation found" "$LOGS/$slug.r$ROUND.log" 2>/dev/null; then
    log "resume-fail $slug (session not found: cwd/config dir differ from collect; was $cov)"
  elif [ "$rc" = 124 ] || [ "$rc" = 137 ]; then
    [ "$after" != "$before" ] && log "timeout-partial $slug (was $cov)" || log "timeout-nochange $slug (was $cov)"
  elif [ "$rc" != 0 ]; then log "topup-fail $slug (rc=$rc, was $cov)"
  elif [ "$after" = "$before" ]; then log "no-change $slug (was $cov)"
  else log "done $slug (was $cov)"; fi
}

[ -f "$TPL" ] || { echo "template not found: $TPL"; exit 1; }
[ -n "$TIMEOUT" ] || { echo "need timeout(1) (coreutils; gtimeout on macOS)"; exit 1; }
for ROUND in $(seq 1 "$ROUNDS"); do
  rm -rf "$TOPUP"; "$PY" "$HERE/contract_check.py" "$COLLECT" "$TOPUP"
  n=$(ls "$TOPUP"/*.json 2>/dev/null | wc -l | tr -d ' ')
  log "===== feedback round $ROUND/$ROUNDS: $n work order(s) ====="
  [ "$n" = 0 ] && break
  for order in "$TOPUP"/*.json; do
    [ -n "$ONLY" ] && [ "$(basename "$order" .json)" != "$ONLY" ] && continue
    throttle; topup_one "$order" &
  done
  wait
done
rm -rf "$TOPUP"; "$PY" "$HERE/contract_check.py" "$COLLECT" "$TOPUP"
log "===== feedback finished; remaining work orders in $TOPUP ====="
