#!/usr/bin/env python3.12
"""emit_task.py <packdir> <tid> : compose emit/<tid>.task.json + <tid>.spec.json in emit.py's shape (contract stripped; verifier = and-of-IR clauses)."""
import json, sys, os, copy
packdir, tid = sys.argv[1], sys.argv[2]
contract = json.load(open(f"{packdir}/05_verifier/contract.json")); verdict = json.load(open(f"{packdir}/05_verifier/verdict.json"))
rep = json.load(open(f"{packdir}/04_operation/operation_report.json")); world = json.load(open(f"{packdir}/06_distractor/fork.spec.json"))
prop = json.load(open(f"{packdir}/01_intent/proposal.json")); groups = json.load(open(f"{packdir}/06_distractor/distractor_patch.json"))
acc = json.load(open(f"{packdir}/accept/report.json"))
steps = [{"tool": s["tool"], "args": s["args"]} for s in rep["steps"] if s.get("ok") is not False]
verifier = {"op": "and", "clauses": [p["pred"] for p in contract["postconditions"]]}
ents = set()
for s in steps:
    t = next((x for x in world["tools"] if x["tool"] == s["tool"]), None)
    if t: ents.add((t.get("exec_spec") or {}).get("entity") or t.get("entity"))
def walk(n):
    if isinstance(n, dict):
        if n.get("node") == "select": ents.add(n.get("entity"))
        for v in n.values(): walk(v)
    elif isinstance(n, list):
        for v in n: walk(v)
walk(verifier); ents.discard(None)
pfx = sorted({e.split("__")[0] for e in ents if "__" in e})
task = {"goal_nl": verdict["final_intent"], "witness": steps, "verifier": verifier,
        "intent_provenance": {"status": "generated", "menu_ids": prop.get("menu_ids", []), "grounding": prop.get("grounding", []), "abandoned_grounding": [], "rewrite_history": []},
        "use_entities": sorted(ents),
        "type_vector": {"combine": {"achieved": "dataflow"}, "dependency": {"achieved": "dependent"}, "n_envs": {"target": 4, "achieved": len(pfx)},
                        "domains": {"target": ["operations"], "achieved": ["operations"]}, "retrieval": {"achieved": "cross_env"},
                        "distractor": {"achieved": {"content": sum((g.get("tactics", []) for g in groups), []), "groups": len(groups), "rows": sum(len(b["rows"]) for g in groups for b in g["group"]), "invariants": 0, "tool_surplus": len(world["tools"]) - len({s["tool"] for s in steps})}},
                        "grounding": {"achieved": "natural"}, "intent_class": {"achieved": None}, "quality": {"achieved": "pass" if acc["passed"] else "partial"}, "tier": verdict["tier"]},
        "trace": [{"stage": "handbuilt_pack", "tid": tid, "source": prop.get("source_task")}], "tier": verdict["tier"],
        "rollout": {"n": 1, "pass": 1 if acc["judgeable"]["final_pass"] else 0, "max_iter": 60, "n_error": 0, "infra_error": False, "diag": [{"verifier_pass": acc["judgeable"]["final_pass"], "steps": len(steps)}]},
        "workorder_id": f"package_{tid}", "tid": tid, "env_id": world["env_id"]}
os.makedirs(f"{packdir}/emit", exist_ok=True)
json.dump(task, open(f"{packdir}/emit/{tid}.task.json", "w"), indent=1, ensure_ascii=False)
json.dump(world, open(f"{packdir}/emit/{tid}.spec.json", "w"), indent=1, ensure_ascii=False)
print("emitted", f"{packdir}/emit/{tid}.task.json", "witness", len(steps), "clauses", len(verifier["clauses"]), "use_entities", len(ents))
