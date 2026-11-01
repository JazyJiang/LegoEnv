#!/usr/bin/env python3.12
"""Expose an env-spec as an MCP server (stdio JSON-RPC) so the trained model / eval can actually connect and do tool-calling.
This is `Env = runtime(MCP)` on the COMPOSITION line: tools/list gives the model its tool panel (name+description+inputSchema),
and tools/call routes to runtime.Env.call() for real execution (mutate state / check guards / return results). One process = one session = one Env (starting from the seed state).

Usage:
  mcp_server.py <env.json>              # start the stdio MCP server (newline-delimited JSON-RPC)
  mcp_server.py <env.json> --tools      # only print tools/list (for debugging description/schema)
Dependencies: standard library + runtime.py (same directory) only. No mcp SDK needed.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime

# ── Character limit for a tool observation before it is handed to the model. **Single point of definition** ─────────────────────────
# Both paths read it from here: `mcp_env` (the stdio service used by op / diagnosis) and
# `trajgen/protocol.trim_observation` (the in-process protocol used by production rollouts).
#
# Before 2026-08-21 each side had its own copy, and they differed in more than one number:
#     op       no row limit  · 6000 chars · **silent truncation**
#     rollout  first 15 rows · 4000 chars · with ...<truncated>
# As a result **solver and op were not seeing the same data at all**: in a measured 85 boards, 61 rollouts
# were truncated while op never showed a single marker (because it left no trace). So the solver failed, and the critic, which
# the prompt asked to attribute op-succeeds/rollout-fails gaps to "unclear task wording", kept pointing the statistics at the wrong upstream node.
# `_MAX_ROWS=15` was especially harmful: it came from trajgen (to bound SFT trajectory length) but was treated as the solver's
# perception limit; using a trajectory-production constraint to limit judging is exactly the kind of confusion the critic design warns against.
#
# The 12000 limit is measured: over 11254 real op calls, p50=231, p75=571, p90=10955,
# while p99=2.24M and the single largest was 46M (get_home_feed dumps everything unconditionally). 12000 keeps the truncated share
# at ~10%, and 30 steps × 12000 ≈ 120K tokens is still safe for a 1M window.
# The few giant tools in the tail are a **missing pagination in the tool surface** problem, to be fixed on the spec side, not patched here.
OBS_MAX_CHARS = int(os.environ.get("V11_OBS_MAX_CHARS", "12000"))
OBS_TRUNC_MARK = " ...<truncated>"


def clip_obs(txt):
    """Truncate overlong observations and **leave a marker**. Never cut silently: unmarked truncation hands the model JSON that is
    broken in the middle with damaged structure, and the model has no reason to suspect it did not see everything."""
    t = txt if isinstance(txt, str) else str(txt)
    return t if len(t) <= OBS_MAX_CHARS else t[:OBS_MAX_CHARS] + OBS_TRUNC_MARK

# env-spec column type → JSON Schema type
TYPE_MAP = {"text": "string", "int": "integer", "float": "number", "bool": "boolean",
            "json": "object", "id": "integer", "datetime": "string"}



LISTY_NAMES = {"to", "cc", "bcc", "from", "reply_to", "rcpt_to", "ids", "tags", "labels", "keywords",
               "members", "recipients", "attachments", "emails", "items", "rows", "values"}

def _json_param_schema(spec, pname):
    """Column type `json` covers both dicts and lists. Advertising every json param as
    `object` made the model send lists as JSON strings ("[2]") or dicts ({"2": true});
    guards like `Mailbox.id in {arg: mailbox_ids}` then fail silently (smoke 1110: 44 wasted
    calls). Infer array-ness from the seed rows of any entity that has a column of this name,
    then from the name; otherwise allow both shapes."""
    seen_list = seen_dict = False
    for ent, rows in (spec.get("seed_state") or {}).items():
        for r in rows or []:
            v = r.get(pname)
            if isinstance(v, list): seen_list = True
            elif isinstance(v, dict): seen_dict = True
    if seen_list and not seen_dict:
        return {"type": "array", "items": {}}
    if seen_dict and not seen_list:
        return {"type": "object"}
    if pname.endswith("_ids") or pname.endswith("ids") or pname in LISTY_NAMES:
        return {"type": "array", "items": {}}
    return {"type": ["object", "array"]}

def _fallback_desc(t):
    sc = (t.get("exec_spec") or {}).get("scope")
    scope = " (only your own)" if sc and sc.get("owner_col") and not sc.get("visibility_col") else ""
    auth = " Requires login." if (t.get("guards") or {}).get("requires_auth") else ""
    return f"On {t.get('entity','?')}, run {t.get('op') or t.get('family','operation')}{scope}.{auth}".strip()


def build_tools(spec):
    """env-spec.tools → MCP tool list (name/description/inputSchema). input_schema accepts both the old ({n:type}) and rich ({n:{type,description,required}}) forms."""
    out = []
    for t in spec.get("tools", []):
        props, required = {}, []
        for pname, pdef in (t.get("input_schema") or {}).items():
            if isinstance(pdef, dict):
                ptype = pdef.get("type", "text")
                prop = _json_param_schema(spec, pname) if ptype == "json" else {"type": TYPE_MAP.get(ptype, "string")}
                if pdef.get("description"):
                    prop["description"] = pdef["description"]
                if pdef.get("enum"):
                    prop["enum"] = pdef["enum"]
                if pdef.get("required"):
                    required.append(pname)
            else:
                prop = _json_param_schema(spec, pname) if pdef == "json" else {"type": TYPE_MAP.get(pdef, "string")}
            props[pname] = prop
        for r in (t.get("required") or []):     # also merge in an explicit required list
            if r not in required:
                required.append(r)
        out.append({"name": t["tool"],
                    "description": t.get("description") or _fallback_desc(t),
                    "inputSchema": {"type": "object", "properties": props, "required": required}})
    return out


def make_embed_fn():
    """For semantic retrieval; only wired up when an embedding client is explicitly configured, otherwise None (the runtime falls back to keyword)."""
    try:
        import embed
        return embed.embed_texts if hasattr(embed, "embed_texts") else None
    except Exception:
        return None


def main():
    spec = json.load(open(sys.argv[1]))
    if "--tools" in sys.argv:
        print(json.dumps(build_tools(spec), ensure_ascii=False, indent=1))
        return
    env = runtime.Env(spec, embed_fn=make_embed_fn())   # session-level Env; __init__ has already reset to the seed state
    tools = build_tools(spec)

    def send(msg):
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        mid, method = req.get("id"), req.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": f"envlib-{spec.get('env_id', 'env')}", "version": "1"}}})
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": tools}})
        elif method == "tools/call":
            p = req.get("params") or {}
            res = env.call(p.get("name"), p.get("arguments") or {})
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}],
                "isError": not res.get("ok", True)}})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}})


if __name__ == "__main__":
    main()
