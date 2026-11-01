#!/usr/bin/env python3
"""Per-repository spec cache on top of ``build_node``: build on miss, remember failures.

    python3 spec_builder.py --collect-dir <run>/collect --run <run> [--spec-dir DIR] [repo ...]

For every repo (default: every ``<collect-dir>/<repo>.json``), an existing
``<spec-dir>/<repo>.spec.json`` is reused; otherwise the Build Spec node runs
(prep -> agent -> probe -> feedback -> gate). Repos that fail the gate are recorded
in ``<spec-dir>/_failed.json`` so a batch does not rebuild them; delete that file to
retry everything (there is deliberately no automatic invalidation). A repo that
later builds successfully is removed from the failure list.

The internal one-shot "assembler" engine that preceded the Build Spec node (one LLM
call doing translation and judgement together) is not included: the split into
deterministic translation plus agent judgement replaced it.
"""
import argparse
import fcntl
import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import _rt  # noqa: E402,F401
import runtime  # noqa: E402
import build_node as BN  # noqa: E402


def _failed_path(spec_dir):
    return os.path.join(spec_dir, "_failed.json")


def load_failed(spec_dir):
    try:
        d = json.load(open(_failed_path(spec_dir), encoding="utf-8"))
    except Exception:
        return set()
    return set(d if isinstance(d, list) else (d.keys() if isinstance(d, dict) else []))


def _update_failed(spec_dir, repo, failed):
    p = _failed_path(spec_dir)
    os.makedirs(spec_dir, exist_ok=True)
    with open(p + ".lock", "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        s = load_failed(spec_dir)          # re-read under the lock: concurrent batches
        if failed:
            s.add(repo)
        elif repo in s:
            s.discard(repo)
        else:
            return
        tmp = "%s.tmp.%d" % (p, os.getpid())
        json.dump(sorted(s), open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, p)


def validate_spec(spec):
    """Minimal runtime check: the Env builds, auth/login exist, an account row is seeded."""
    if not isinstance(spec, dict) or not spec.get("entities") or not spec.get("tools"):
        return False, "missing entities/tools"
    auth = spec.get("auth") or {}
    if not auth.get("account_entity"):
        return False, "missing auth.account_entity"
    if not any((t.get("family") or "").startswith("guard.auth") or "login" in (t.get("tool") or "")
               for t in spec["tools"]):
        return False, "missing login tool"
    try:
        env = runtime.Env(spec)
    except Exception as ex:
        return False, "Env build failed: %s" % str(ex)[:120]
    rows = env.state.get(auth["account_entity"], [])
    if not any(isinstance(r, dict) and any(r.values()) for r in rows):
        return False, "account entity has no seed rows"
    return True, ""


def ensure_repo_spec(repo, collect_dir, run_dir, spec_dir, bridge=None, log=print, timeout=3600):
    """-> spec dict or None."""
    p = os.path.join(spec_dir, "%s.spec.json" % repo)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    if repo in load_failed(spec_dir):
        return None
    cp = os.path.join(collect_dir, "%s.json" % repo)
    if not os.path.exists(cp):
        # Not a build failure: stage 1 never produced this repo. Say so in the log.
        log("[spec_builder] %s: no collect output at %s" % (repo, cp))
        _update_failed(spec_dir, repo, True)
        return None
    BN.set_spec_dir(spec_dir)
    res = BN.build(repo, cp, os.path.join(run_dir, "build"), bridge=bridge, log=log,
                   timeout=timeout)
    spec = res.get("spec")
    if not res.get("ok") or spec is None:
        log("[spec_builder] %s did not pass the gate: %s" % (repo, res.get("why")))
        _update_failed(spec_dir, repo, True)
        return None
    _update_failed(spec_dir, repo, False)
    if res.get("residual"):
        log("[spec_builder] %s cached with residual findings: %s" % (repo, res["residual"]))
    return spec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("repos", nargs="*")
    ap.add_argument("--collect-dir", required=True)
    ap.add_argument("--run", required=True, help="run directory (work files under <run>/build)")
    ap.add_argument("--spec-dir", default=None, help="default <run>/repo_specs")
    ap.add_argument("--bridge", default=None, help="bridge base URL (default $BRIDGE_URL)")
    ap.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()
    spec_dir = a.spec_dir or os.path.join(a.run, "repo_specs")
    repos = a.repos or sorted(os.path.basename(f)[:-5]
                              for f in glob.glob(os.path.join(a.collect_dir, "*.json"))
                              if not os.path.basename(f).startswith("_"))
    n_ok = 0
    for r in repos:
        n_ok += ensure_repo_spec(r, a.collect_dir, a.run, spec_dir, bridge=a.bridge,
                                 timeout=a.timeout) is not None
    print("built or cached %d / %d specs in %s" % (n_ok, len(repos), spec_dir))


if __name__ == "__main__":
    main()
