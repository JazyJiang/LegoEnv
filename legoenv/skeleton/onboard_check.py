#!/usr/bin/env python3
"""onboard_check.py <app> — acceptance smoke for an onboarded environment (workstream B). Expects:
  pack/base_specs/<app>.spec.json                       the (patched) base spec
  pack/newspecs3/<app>/register.py                      registers SERVER/PFX/CONTENT/NOTES/LOGIN (+ seed helpers, obs hook) like pack/newspecs/register.py,
                                                        and exposes  smoke_seed(W) -> (steps, preds)  : seeds >= 3 content rows (+ one policy text via the carrier),
                                                        returns gold steps [(app, tool, args)...] and >= 3 contract predicates [(id, semantic, pred, negative)] incl. one negative
  pack/newspecs3/<app>/capability_card.json             per contract/capability_card_schema.json
Checks: card schema · every card kind has a matching write tool in the spec · carriers name real entity.field · World builds · obs_report under 12k ·
seed_check · sim_gold replays the steps · accept --strict passes. Writes the smoke result into the card. Exit 0 = PASS."""
import json, os, sys, re, importlib.util, shutil, subprocess, datetime as dt
from pathlib import Path
app = sys.argv[1]; SM = str(Path(__file__).resolve().parents[2]); sys.path.insert(0, f"{SM}/pack"); sys.path.insert(0, f"{SM}/pack_dpsk")
D = f"{SM}/pack/newspecs3/{app}"; V = json.load(open(f"{SM}/pack_dpsk/contract/vocab.json")); fails = []
def need(cond, msg):
    if not cond: fails.append(msg); print("FAIL", msg)
need(os.path.exists(f"{SM}/pack/base_specs/{app}.spec.json"), "base spec missing"); need(os.path.exists(f"{D}/register.py"), "register.py missing"); need(os.path.exists(f"{D}/capability_card.json"), "capability_card.json missing")
if fails: sys.exit(1)
card = json.load(open(f"{D}/capability_card.json")); spec = json.load(open(f"{SM}/pack/base_specs/{app}.spec.json"))
tools = {t["tool"] for t in spec["tools"]}; ents = {e["name"]: {c["name"] for c in e.get("columns", [])} for e in spec.get("entities", [])}
for k in ("app", "role", "domains", "kinds", "check_kinds", "carriers", "login", "content_entities", "tool_families_to_keep"): need(k in card, f"card: missing {k}")
if fails: sys.exit(1)
need(card["app"] == app, "card.app != app")
for kind, tl in card["kinds"].items():
    need(kind in V["kind_tools"] or kind.startswith("other:"), f"card kind {kind} not in vocab (use other:<name> to propose)")
    need(tl and all(t in tools for t in tl), f"card kind {kind}: tools {tl} not all in spec")
for ck in card["check_kinds"]: need(ck in V["check_kinds"], f"card check_kind {ck} not in vocab")
for c, loc in card["carriers"].items():
    need(c in V["carriers"], f"carrier {c} not in vocab"); need(loc.get("entity") in ents and loc.get("field") in ents.get(loc.get("entity"), set()), f"carrier {c}: {loc} not an entity.field of the spec")
if card["login"] is not None:
    need(isinstance(card["login"], dict) and bool(card["login"].get("tool")) and card["login"].get("tool") in tools, "declared login tool not in spec")
else:
    print("DECLARED", app, "no login; no login call will be made")
for e in card["content_entities"]: need(e in ents, f"content entity {e} not in spec")
from packlib import *; from dklib import *
spec_mod = importlib.util.spec_from_file_location(f"reg_{app}", f"{D}/register.py"); mod = importlib.util.module_from_spec(spec_mod); spec_mod.loader.exec_module(mod)
need(app in SERVER and app in PFX and app in CONTENT and app in NOTES and app in LOGIN, "register.py did not register SERVER/PFX/CONTENT/NOTES/LOGIN")
need(hasattr(mod, "smoke_seed"), "register.py has no smoke_seed(W)")
if card["login"] is None: need(LOGIN.get(app, "undeclared") is None, "explicit no-login card/registration mismatch")
else: need(app in LOGIN and LOGIN[app] is not None, "login card/registration mismatch")
if fails: sys.exit(1)
tid = f"ob_{app}"
for p in (f"{PACK}/{tid}", f"{TASKS}/{tid}"): shutil.rmtree(p, ignore_errors=True)
try:
    W = World([app], persona=(f"ops@{app}.example", "Ops"), now="2026-09-24T09:00:00")
    steps, preds = mod.smoke_seed(W)
    sp = W.merge(); rep, bad = W.obs_report(); need(not bad, f"obs_report over 12k: {bad}")
    need(sum(len(sp["seed_state"].get(NS(app, e), [])) for e in CONTENT[app]) >= 3, "fewer than 3 content rows seeded")
    C = Contract("smoke goal", expected={})
    for pid, sem, pred, neg in preds: C.add(pid, sem, pred, negative=neg)
    need(len(preds) >= 3 and any(p[3] for p in preds), "need >= 3 predicates incl. one negative")
    need(not C.seed_check(sp), f"seed_check failed: {C.seed_check(sp)}")
    write_pack(tid, W, sp, C, [{"id": "a1", "kind": next(iter(card["kinds"])), "text": "smoke"}], skeleton="onboard smoke")
    b, env = sim_gold(tid, sp, W, C, steps); need(not b, f"sim_gold predicates not satisfied: {b}")
    r = subprocess.run([sys.executable, f"{PACK}/accept.py", f"{PACK}/{tid}", f"{TASKS}/{tid}", "--strict"], capture_output=True, text=True); need(r.returncode == 0, "accept --strict failed: " + r.stdout[-600:])
except Exception as e:
    import traceback; fails.append(f"exception: {e}"); traceback.print_exc()
for p in (f"{PACK}/{tid}", f"{TASKS}/{tid}"): shutil.rmtree(p, ignore_errors=True)
card["smoke"] = {"passed": not fails, "date": dt.date.today().isoformat(), "report": "; ".join(fails)[:500] or "ok"}
card["register_file"] = f"{D}/register.py"; card["base_spec"] = f"{SM}/pack/base_specs/{app}.spec.json"
json.dump(card, open(f"{D}/capability_card.json", "w"), ensure_ascii=False, indent=1)
print("ONBOARD", app, "PASS" if not fails else f"FAIL ({len(fails)})"); sys.exit(0 if not fails else 1)
