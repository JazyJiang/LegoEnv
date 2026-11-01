#!/usr/bin/env python3.12
"""dklib.py — deterministic gold run + acceptance for agent-built packs.
Use after packlib:   from packlib import *; from dklib import *
  bad, env = sim_gold(TID, spec, W, C, steps)   # replaces run_gold: replays your steps, records witness + final state like the real runner
  check(TID, SKELETON_ID)                       # accept --strict + finish; writes pack_dpsk/results/<tid>.json; prints PASS / FAIL
"""
import json, os, sys, time, subprocess, fcntl
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pack"))
from packlib import *   # noqa
DK = str(Path(__file__).resolve().parent); RESULTS = f"{DK}/results"

def sim_gold(tid, spec, W, C, steps, verbose=False):
    """steps: list of (app, tool, args) — the gold solution. Re-logs in on every app switch (the login calls are part of the witness,
    exactly as a real agent run). Writes tasks/<tid>/run/{witness_env.jsonl,state_env.json,out.json,DONE,...} so accept/finish work
    unchanged. Returns (predicates that are not True on the final state, env). Every predicate must be True here before check()."""
    td = f"{TASKS}/{tid}"; run = f"{td}/run"; os.makedirs(run, exist_ok=True)
    for f in os.listdir(run): os.remove(f"{run}/{f}")
    env = runtime.Env(spec); cur = None; wit = []; t0 = int(time.time())
    def call(tool, args):
        r = env.call(tool, args)
        ok = bool(isinstance(r, dict) and r.get("ok"))
        wit.append({"tool": tool, "args": args, "ok": ok, "obs": json.dumps(r, ensure_ascii=False, default=str)[:12000]})
        if verbose or not ok: print("  ", tool, json.dumps(r, default=str)[:300])
        return r
    for st in steps:
        if callable(st):                      # callable steps: every env.call they make is recorded too
            orig = env.call
            def wrapped(tool, args=None, _o=orig):
                r = _o(tool, args); ok = bool(isinstance(r, dict) and r.get("ok"))
                wit.append({"tool": tool, "args": args or {}, "ok": ok, "obs": json.dumps(r, ensure_ascii=False, default=str)[:12000]})
                if verbose or not ok: print("  ", tool, json.dumps(r, default=str)[:300])
                return r
            env.call = wrapped
            try: st(env)
            finally: env.call = orig
            continue
        app, tool, args = st
        if app != cur:
            entry = LOGIN[app]
            if entry is not None:
                t, k = entry; call(NS(app, t), login_arguments(W, app))
            cur = app
        call(NS(app, tool), args)
    with open(f"{run}/witness_env.jsonl", "w") as fh:
        for w in wit: fh.write(json.dumps(w, ensure_ascii=False) + "\n")
    json.dump({"state": env.state, "events": [], "session": getattr(env, "session", {})}, open(f"{run}/state_env.json", "w"), ensure_ascii=False, default=str)
    json.dump({"result": "sim_gold: deterministic replay of the build.py gold steps", "num_turns": len(wit), "total_cost_usd": 0.0, "is_error": False, "session_id": "sim_gold"}, open(f"{run}/out.json", "w"))
    for f, v in (("t0", t0), ("t1", int(time.time())), ("exit_code", 0), ("err.log", ""), ("DONE", "")): open(f"{run}/{f}", "w").write(str(v))
    bad = []
    for p in C.P:
        try: v = bool(runtime.eval_node(p["pred"], runtime._StateView(env.state, spec.get("now")), None, None, site="postcondition"))
        except Exception as e: v = f"ERR {e}"
        if v is not True: bad.append((p["id"], v))
    if bad: print("sim_gold: predicates not satisfied by your steps:", bad)
    else: print(f"sim_gold: all {len(C.P)} predicates True after {len(wit)} calls")
    return bad, env

def check(tid, skeleton_id=None, dataset="", note=""):
    """accept --strict, then finish (fill_witness + emit + runtime.run_task). Result JSON -> pack_dpsk/results/<tid>.json."""
    os.makedirs(RESULTS, exist_ok=True)
    r = subprocess.run(["python3.12", f"{PACK}/accept.py", f"{PACK}/{tid}", f"{TASKS}/{tid}", "--strict"], capture_output=True, text=True)
    rp = f"{PACK}/{tid}/accept/report.json"; rep = json.load(open(rp)) if os.path.exists(rp) else {}
    acc = r.returncode == 0
    fin = False
    if acc:
        try: fin = bool(finish(tid))
        except Exception as e: print("finish error:", e)
    con = json.load(open(f"{PACK}/{tid}/05_verifier/contract.json"))
    P = con["postconditions"]
    out = {"tid": tid, "skeleton_id": skeleton_id, "accept_strict": acc, "finish": fin, "pass": bool(acc and fin), "dataset": dataset,
           "n_pos": sum(1 for p in P if not p.get("expect_seed")), "n_neg": sum(1 for p in P if p.get("expect_seed")),
           "vacuous_negatives": rep.get("vacuous_negatives"), "judgeable": {k: rep.get("judgeable", {}).get(k) for k in ("seed_bad", "final_bad", "dumped_bad", "final_pass")},
           "runnable": (rep.get("runnable") or {}).get("all_ok"), "resettable": rep.get("resettable"), "hard_failed": rep.get("hard_failed") or rep.get("failed"),
           "goal_chars": len(con.get("final_intent", "")), "note": note, "ts": time.strftime("%F %T")}
    json.dump(out, open(f"{RESULTS}/{tid}.json", "w"), ensure_ascii=False, indent=1)
    with open(f"{DK}/results.tsv", "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX); fh.write(f"{out['ts']}\t{skeleton_id}\t{tid}\t{'PASS' if out['pass'] else 'FAIL'}\t{out['n_pos']}+{out['n_neg']}\t{dataset}\t{note}\n")
    print("=" * 60); print("CHECK", "PASS" if out["pass"] else "FAIL", json.dumps({k: out[k] for k in ("accept_strict", "finish", "n_pos", "n_neg", "vacuous_negatives", "judgeable", "runnable")}, ensure_ascii=False))
    if not acc: print(r.stdout[-3000:]); print(r.stderr[-1500:])
    return out["pass"]
