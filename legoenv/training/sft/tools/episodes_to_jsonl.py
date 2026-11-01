#!/usr/bin/env python3
"""Collector episode JSON -> SFT jsonl (one line per episode).

Output line schema (the OpenAI-style messages + tools any chat-template SFT loader reads):

    {"messages": [...], "tools": [...], "meta": {...}}

* messages keep only the fields the chat template reads:
    system/user : {role, content}
    assistant   : {role, content, reasoning_content?, tool_calls?}
                  tool_calls[i] = {id, type: "function", function: {name, arguments: <dict>}}
                  (``arguments`` is json.loads-ed from the collector's JSON string,
                   which is what vLLM does to history tool calls before templating)
    tool        : {role, tool_call_id, content}
* tools are the OpenAI function schemas exactly as the collector exposed them.
* meta is informational only (id, pack_set, verifier_pass, keep, turns, src); a loader
  should ignore it.

Selection happens in a filter hook:
    --filter keep            (default) episode["keep"] is True
    --filter verifier_pass   episode["verifier_pass"] is True
    --filter complete_verifier_pass
                            verifier success + normal stop + complete tool results
    --filter all             no selection (structural checks still apply)
    --filter /path/to/file.py:fn_name
                             custom hook: fn(episode: dict) -> bool | (bool, str reason)

Structural checks that always apply (a failing episode is dropped and counted):
    empty messages, last message not assistant, unparsable tool arguments,
    tool message whose tool_call_id has no matching earlier call, unknown roles,
    tool name not in the episode's tool list (when --check-tool-names).
--max-assistant-turns N (smoke tests only) keeps each episode up to its N-th assistant message.

Usage:
    python3 episodes_to_jsonl.py IN [IN ...] -o out.jsonl [--filter keep] [--limit N]
IN may be an episode .json file, a directory (searched recursively for *.json
under any 'episodes' dir, or all *.json if none), or a collector manifest.jsonl.
Standard library only; runs with any python >= 3.8.
"""
import argparse
import glob
import importlib.util
import json
import os
import sys
from collections import Counter

ROLES = ("system", "user", "assistant", "tool")


# --------------------------------------------------------------------------- filters
def _f_keep(ep):
    return (ep.get("keep") is True, "not_keep")


def _f_verifier_pass(ep):
    return (ep.get("verifier_pass") is True, "not_verifier_pass")


def _f_all(ep):
    return (True, "")


def _f_complete_verifier_pass(ep):
    if ep.get("verifier_pass") is not True:
        return False, "not_verifier_pass"
    if ep.get("finish") not in ("stop", "end_turn") or ep.get("error_type") is not None:
        return False, "incomplete_collection"
    return True, ""


BUILTIN_FILTERS = {"keep": _f_keep, "verifier_pass": _f_verifier_pass,
                  "complete_verifier_pass": _f_complete_verifier_pass, "all": _f_all}


def load_filter(spec):
    if spec in BUILTIN_FILTERS:
        return BUILTIN_FILTERS[spec]
    if ":" not in spec:
        raise SystemExit(f"--filter must be one of {sorted(BUILTIN_FILTERS)} or /path/file.py:fn")
    path, fn = spec.rsplit(":", 1)
    mod_spec = importlib.util.spec_from_file_location("_sft_filter_mod", path)
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    return getattr(mod, fn)


def run_filter(fn, ep):
    r = fn(ep)
    if isinstance(r, tuple):
        ok, reason = bool(r[0]), (r[1] if len(r) > 1 else "filtered")
    else:
        ok, reason = bool(r), "filtered"
    return ok, (reason or "filtered")


# --------------------------------------------------------------------------- inputs
def iter_episode_paths(inputs):
    for inp in inputs:
        if os.path.isdir(inp):
            hits = sorted(glob.glob(os.path.join(inp, "**", "episodes", "**", "*.json"), recursive=True))
            if not hits:
                hits = sorted(glob.glob(os.path.join(inp, "**", "*.json"), recursive=True))
            for p in hits:
                if os.path.basename(p) in ("run_config.json",):
                    continue
                yield p
        elif inp.endswith(".jsonl"):  # collector manifest
            with open(inp) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if rec.get("path"):
                        yield rec["path"]
        else:
            for p in sorted(glob.glob(inp)) or [inp]:
                yield p


# --------------------------------------------------------------------------- conversion
class Drop(Exception):
    pass


def _as_text(x):
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    return json.dumps(x, ensure_ascii=False)


def _parse_args(raw):
    if isinstance(raw, dict):
        return raw
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return {}
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
        except json.JSONDecodeError:
            raise Drop("bad_tool_args_json")
        if not isinstance(val, dict):
            raise Drop("tool_args_not_object")
        return val
    raise Drop("tool_args_bad_type")


def convert_messages(msgs, tool_names=None):
    out = []
    open_calls = set()
    for m in msgs:
        role = m.get("role")
        if role not in ROLES:
            raise Drop(f"unknown_role:{role}")
        if role in ("system", "user"):
            content = m.get("content")
            if not isinstance(content, str):
                # multimodal / list content is not expected from the collector
                raise Drop(f"{role}_content_not_str")
            out.append({"role": role, "content": content})
        elif role == "assistant":
            nm = {"role": "assistant", "content": _as_text(m.get("content"))}
            rc = m.get("reasoning_content")
            if rc is None:
                rc = m.get("reasoning")  # some endpoints use this key
            if isinstance(rc, str) and rc != "":
                nm["reasoning_content"] = rc
            if "step_loss_mask" in m:
                # This is a controller-provided training flag, not a rendered
                # chat-template field. Preserve it; do not infer new masks here.
                nm["step_loss_mask"] = m["step_loss_mask"]
            tcs = m.get("tool_calls") or []
            if tcs:
                ntcs = []
                for tc in tcs:
                    fn = tc.get("function") or {}
                    name = fn.get("name")
                    if not name:
                        raise Drop("tool_call_no_name")
                    if tool_names is not None and name not in tool_names:
                        raise Drop("tool_call_unknown_name")
                    tid = tc.get("id") or ""
                    ntcs.append({
                        "id": tid,
                        "type": "function",
                        "function": {"name": name, "arguments": _parse_args(fn.get("arguments"))},
                    })
                    if tid:
                        open_calls.add(tid)
                nm["tool_calls"] = ntcs
            out.append(nm)
        else:  # tool
            tid = m.get("tool_call_id") or ""
            if tid and tid not in open_calls:
                raise Drop("tool_result_without_call")
            out.append({"role": "tool", "tool_call_id": tid, "content": _as_text(m.get("content"))})
    if not out:
        raise Drop("empty_messages")
    if out[-1]["role"] != "assistant":
        raise Drop("last_not_assistant")
    if not any(m["role"] == "assistant" for m in out):
        raise Drop("no_assistant")
    return out


def cut_after_assistant(msgs, n):
    """Keep messages up to and including the n-th assistant message (smoke-test helper)."""
    seen = 0
    for i, m in enumerate(msgs):
        if m.get("role") == "assistant":
            seen += 1
            if seen == n:
                return msgs[:i + 1]
    return msgs


def check_complete_tool_exchange(messages):
    """Require matching results only for a declared complete collected episode.

    Single-turn call-only examples and intentional prefixes retain the old
    behavior with the other filters. IDs may be reused after their call closes.
    """
    pending = set()
    for message in messages:
        if message['role'] == 'assistant':
            if pending:
                raise Drop('assistant_before_tool_results')
            for call in message.get('tool_calls') or []:
                identity = call.get('id')
                if not isinstance(identity, str) or not identity:
                    raise Drop('missing_tool_call_id')
                if identity in pending:
                    raise Drop('duplicate_pending_tool_call_id')
                pending.add(identity)
        elif message['role'] == 'tool':
            identity = message.get('tool_call_id')
            if identity not in pending:
                raise Drop('unexpected_or_duplicate_tool_result')
            pending.remove(identity)
        elif pending:
            raise Drop('message_before_tool_results')
    if pending:
        raise Drop('missing_tool_results')


def convert_episode(ep, check_tool_names=False, max_assistant_turns=0, require_complete_tools=False):
    tools = ep.get("tools") or []
    names = None
    if check_tool_names:
        names = {((t.get("function") or {}).get("name")) for t in tools}
    raw = ep.get("messages") or []
    if max_assistant_turns:
        raw = cut_after_assistant(raw, max_assistant_turns)
    msgs = convert_messages(raw, names)
    if require_complete_tools:
        check_complete_tool_exchange(msgs)
    meta = {k: ep.get(k) for k in ("pack_set", "id", "sample", "task_id", "env_id", "verifier_pass",
                                     "keep", "turns", "tools_mode", "model")}
    return {"messages": msgs, "tools": tools, "meta": meta}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True, help="output .jsonl ('-' for stdout)")
    ap.add_argument("--filter", default="keep")
    ap.add_argument("--limit", type=int, default=0, help="stop after N kept episodes (0 = all)")
    ap.add_argument("--check-tool-names", action="store_true",
                    help="drop episodes that call a tool not in their own tool list")
    ap.add_argument("--expect-tools", default="",
                    help="comma list; drop episodes whose tool-name set differs (e.g. api_search,api_fetch,base64_encode)")
    ap.add_argument("--no-meta", action="store_true")
    ap.add_argument("--max-assistant-turns", type=int, default=0,
                    help="SMOKE TESTS ONLY: cut each episode after its N-th assistant message")
    args = ap.parse_args(argv)

    filt = load_filter(args.filter)
    expect = set(x for x in args.expect_tools.split(",") if x) or None
    stats = Counter()
    seen = set()
    fout = sys.stdout if args.out == "-" else open(args.out + ".tmp", "w")
    try:
        for p in iter_episode_paths(args.inputs):
            rp = os.path.realpath(p)
            if rp in seen:
                continue
            seen.add(rp)
            stats["read"] += 1
            try:
                with open(p) as f:
                    ep = json.load(f)
            except Exception:
                stats["drop:unreadable"] += 1
                continue
            if not isinstance(ep, dict) or "messages" not in ep:
                stats["drop:not_episode"] += 1
                continue
            ok, reason = run_filter(filt, ep)
            if not ok:
                stats[f"drop:{reason}"] += 1
                continue
            if expect is not None:
                got = {((t.get("function") or {}).get("name")) for t in (ep.get("tools") or [])}
                if got != expect:
                    stats["drop:tool_set_mismatch"] += 1
                    continue
            try:
                rec = convert_episode(ep, args.check_tool_names, args.max_assistant_turns,
                                      require_complete_tools=args.filter == 'complete_verifier_pass')
            except Drop as d:
                stats[f"drop:{d}"] += 1
                continue
            rec["meta"]["src"] = rp
            if args.no_meta:
                rec.pop("meta")
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            stats["written"] += 1
            if args.limit and stats["written"] >= args.limit:
                break
    finally:
        if fout is not sys.stdout:
            fout.close()
    if args.out != "-":
        os.replace(args.out + ".tmp", args.out)
    print(json.dumps(dict(sorted(stats.items())), ensure_ascii=False), file=sys.stderr)
    return 0 if stats["written"] else 1


if __name__ == "__main__":
    sys.exit(main())
