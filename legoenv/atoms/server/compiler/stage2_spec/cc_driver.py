#!/usr/bin/env python3
"""Headless Claude Code sessions for the Build Spec agent.

The agent is a real ``claude`` process pointed at a local Anthropic-messages
endpoint, normally the repository's bridge (``bridge/server.py``), which forwards
to any OpenAI-compatible model. Two calls are needed by ``build_node``:

  * ``run_cc``    starts a session (prompt on stdin, JSON result on stdout) and
                  returns its ``session_id``;
  * ``resume_cc`` appends a new user turn to that SAME session
                  (``claude --resume <session_id> -p <message>``), so the agent keeps
                  its full context and the revision is incremental, not a restart.

Configuration (environment):
  BRIDGE_URL         bridge base URL (default http://127.0.0.1:8092); a ``bridge``
                     argument (URL or port number) overrides it per call.
  CC_BIN             path to the ``claude`` executable (default: ``claude`` on PATH).
  CLAUDE_CONFIG_DIR  Claude Code config dir; default ``~/.claude-legoenv``.
  CC_MAX_OUTPUT_TOKENS  per-turn output cap passed to Claude Code (default 32000).

Gotcha: ``settings.json`` -> ``env`` inside the config dir OVERRIDES the process
environment. Exporting ANTHROPIC_BASE_URL alone is therefore not enough when a
settings file already names another endpoint, so ``_config_dir`` rewrites the
base URL in ``settings.json`` idempotently. Sessions are stored per config dir and
per working directory, so a resume must use the same config dir and cwd as the
original run.
"""
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request

DEFAULT_BRIDGE = "http://127.0.0.1:8092"
CC_MAX_OUTPUT_TOKENS = os.environ.get("CC_MAX_OUTPUT_TOKENS", "32000")


class UpstreamDown(RuntimeError):
    """The model endpoint is not answering: an infrastructure failure, not a spec problem."""


def _cc_bin():
    return os.environ.get("CC_BIN") or shutil.which("claude") or "claude"


def bridge_url(bridge=None):
    if bridge is None or bridge == "":
        bridge = os.environ.get("BRIDGE_URL") or DEFAULT_BRIDGE
    if isinstance(bridge, int) or str(bridge).isdigit():
        return "http://127.0.0.1:%d" % int(bridge)
    return str(bridge).rstrip("/")


def probe(bridge=None, timeout=90):
    """Send a minimal request through the bridge; True if the upstream returns tokens.
    A listening port is not proof of a live upstream."""
    body = json.dumps({"model": "default", "max_tokens": 16,
                       "messages": [{"role": "user", "content": "say pong"}]}).encode()
    req = urllib.request.Request(
        bridge_url(bridge) + "/v1/messages", data=body,
        headers={"Content-Type": "application/json", "x-api-key": "local",
                 "anthropic-version": "2023-06-01"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except Exception:
        return False
    return int((d.get("usage") or {}).get("output_tokens", 0)) > 0


def _config_dir(url):
    d = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude-legoenv")
    os.makedirs(d, exist_ok=True)
    sp = os.path.join(d, "settings.json")
    try:
        cfg = json.load(open(sp, encoding="utf-8"))
    except Exception:
        cfg = {"skipDangerousModePermissionPrompt": True, "autoCompactEnabled": True,
               "hasCompletedOnboarding": True}
    env = cfg.setdefault("env", {})
    if env.get("ANTHROPIC_BASE_URL") != url:
        env.update({"ANTHROPIC_BASE_URL": url, "ANTHROPIC_AUTH_TOKEN": "local",
                    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": CC_MAX_OUTPUT_TOKENS})
        env.pop("ANTHROPIC_API_KEY", None)
        tmp = "%s.tmp.%d.%d" % (sp, os.getpid(), threading.get_ident())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, sp)
    cj = os.path.join(d, ".claude.json")
    if not os.path.exists(cj):           # headless runs would otherwise stop at onboarding
        with open(cj, "w", encoding="utf-8") as f:
            json.dump({"hasCompletedOnboarding": True}, f)
    return d


def cc_env(bridge=None):
    url = bridge_url(bridge)
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.update({"ANTHROPIC_BASE_URL": url, "ANTHROPIC_AUTH_TOKEN": "local",
                "CLAUDE_CONFIG_DIR": _config_dir(url),
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS": CC_MAX_OUTPUT_TOKENS,
                "DISABLE_TELEMETRY": "1", "DISABLE_AUTOUPDATER": "1"})
    return env


def _parse(out):
    try:
        return json.loads(out[out.index("{"):]) if "{" in out else {}
    except Exception:
        return {}


def run_cc(prompt, cwd, timeout=3600, bridge=None, tag="cc", log=print, max_turns=None):
    """One headless session. -> {"ok", "result", "num_turns", "session_id", "raw"}."""
    os.makedirs(cwd, exist_ok=True)
    # The prompt goes on stdin: a full contract can exceed the per-argument limit.
    cmd = [_cc_bin(), "-p", "--output-format", "json", "--dangerously-skip-permissions"]
    if max_turns and int(max_turns) > 0:
        cmd += ["--max-turns", str(max_turns)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=cc_env(bridge), input=prompt,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log("[%s] cc timed out (%ds)" % (tag, timeout))
        return {"ok": False, "result": "", "num_turns": -1, "session_id": None, "raw": "timeout"}
    out, err = (proc.stdout or "").strip(), (proc.stderr or "").strip()
    d = _parse(out)
    res = {"ok": proc.returncode == 0 and not d.get("is_error"),
           "result": d.get("result") or out[-2000:], "num_turns": d.get("num_turns", -1),
           "session_id": d.get("session_id"), "raw": "" if d else out[-400:]}
    log("[%s] cc done: ok=%s turns=%s %.1fmin" % (tag, res["ok"], res["num_turns"],
                                                  (time.time() - t0) / 60))
    if not res["ok"] and err:
        log("[%s] stderr: %s" % (tag, err[-300:]))
    # Failed with almost no turns and the endpoint is silent: infrastructure, not the spec.
    if not res["ok"] and int(res["num_turns"] or -1) <= 1 and not probe(bridge):
        raise UpstreamDown("[%s] cc failed and the endpoint %s returns no tokens"
                           % (tag, bridge_url(bridge)))
    return res


def resume_cc(session_id, message, cwd, timeout=3600, bridge=None, tag="resume", log=print):
    """Continue the original session with a new user turn (the feedback round)."""
    if not session_id:
        log("[%s] no session_id, skipping resume" % tag)
        return {"ok": False, "result": "", "num_turns": -1, "session_id": None}
    cmd = [_cc_bin(), "--resume", session_id, "-p", message, "--output-format", "json",
           "--dangerously-skip-permissions"]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=cc_env(bridge), capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log("[%s] resume timed out (%ds)" % (tag, timeout))
        return {"ok": False, "result": "", "num_turns": -1, "session_id": session_id}
    out = (proc.stdout or "").strip()
    d = _parse(out)
    ok = proc.returncode == 0 and not d.get("is_error")
    if "No conversation found" in out or "No conversation found" in (proc.stderr or ""):
        log("[%s] resume failed: session not found (different cwd or config dir?)" % tag)
        ok = False
    log("[%s] resume done: ok=%s turns=%s %.1fmin"
        % (tag, ok, d.get("num_turns", -1), (time.time() - t0) / 60))
    return {"ok": ok, "result": d.get("result") or out[-1500:],
            "num_turns": d.get("num_turns", -1), "session_id": session_id}
