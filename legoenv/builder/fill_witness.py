#!/usr/bin/env python3.12
"""fill_witness.py <packdir> <taskdir> : write op_witness.jsonl + steps into operation_report.json (Discovery shape), outcome from accept/report.json."""
import json, sys, shutil, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from argnorm import normalize
packdir, taskdir = sys.argv[1], sys.argv[2]
wit = [json.loads(l) for l in open(f"{taskdir}/run/witness_env.jsonl")]
shutil.copy(f"{taskdir}/run/witness_env.jsonl", f"{packdir}/04_operation/op_witness.jsonl")
rep = json.load(open(f"{packdir}/04_operation/operation_report.json"))
world = json.load(open(f"{packdir}/06_distractor/fork.spec.json"))
rep["steps"] = [{"did": "", "tool": w["tool"], "args": normalize(world, w["tool"], w["args"]), "ok": bool(w.get("ok"))} for w in wit]
acc = json.load(open(f"{packdir}/accept/report.json")) if os.path.exists(f"{packdir}/accept/report.json") else None
rep["outcome"] = "achieved" if (acc and acc["judgeable"]["final_pass"]) else "blocked"
rep["blocked_reasons"] = [] if rep["outcome"] == "achieved" else [{"kind": "world", "detail": "contract not satisfied by the gold run"}]
rep.pop("note", None)
json.dump(rep, open(f"{packdir}/04_operation/operation_report.json", "w"), indent=1, ensure_ascii=False)
print("steps", len(rep["steps"]), "outcome", rep["outcome"])
