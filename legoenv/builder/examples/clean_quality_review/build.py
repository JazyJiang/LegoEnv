#!/usr/bin/env python3.12
"""dc3_qicheck_sep30 — c_mine_manufacturing_005 (manufacturing.quality-inspection).
Tiering rule on a policy_sheet: classify inspection batches by whether every categorical reading matches its
acceptance value; move failed batches to Status "Review", leave passing batches untouched. Per-record update_cell
in budibase + a summary post in the zulip #quality-control channel.
Data: uci-ai4i-2020-maintenance — real Product ID / Type rows seed the batch register; the categorical readings/
acceptance values are world-config inspection specs (like world-config flags in other packs).
"""
import sys, json
sys.path.insert(0, "./pack"); sys.path.insert(0, "./pack_dpsk")
from packlib import *
from dklib import *

TID = 'clean_quality_review'; SID = "c_mine_manufacturing_005"
DOM = "vanguard-manufacturing.example"; TODAY = "2026-09-30"; NOW = f"{TODAY}T09:00:00"
CH = "quality-control"

# (product_id, type, r1, r2, r3, a1, a2, a3) — id/type from real ai4i rows; categorical readings & acceptance values are world config
B = [
    ("H30501", "H", "One", "Two", "Three", "One", "One", "One"),  # r2 mismatch -> fail (near-miss)
    ("H32278", "H", "One", "One", "Two", "One", "One", "One"),    # r3 mismatch -> fail (near-miss)
    ("M15054", "M", "Three", "Two", "Two", "One", "One", "One"),  # all mismatch -> fail
    ("L47230", "L", "Two", "One", "One", "One", "One", "One"),    # r1 mismatch -> fail
    ("H29424", "H", "One", "One", "One", "One", "One", "One"),    # all match -> pass
    ("H29425", "H", "One", "Two", "One", "One", "Two", "One"),    # all match -> pass
    ("H29434", "H", "One", "One", "Two", "One", "One", "Two"),    # all match -> pass
]

def diffs(b):
    _, _, r1, r2, r3, a1, a2, a3 = b
    return [r1 != a1, r2 != a2, r3 != a3]

FAIL = [b for b in B if any(diffs(b))]
PASS = [b for b in B if not any(diffs(b))]
NEARMISS = [b for b in FAIL if sum(diffs(b)) == 1]
assert len(FAIL) == 4 and len(PASS) == 3, (len(FAIL), len(PASS))
assert len(NEARMISS) >= 2, NEARMISS
print("FAIL:", [b[0] for b in FAIL], "PASS:", [b[0] for b in PASS], "NEARMISS:", [b[0] for b in NEARMISS])

W = World(["budibase", "zulip"], persona=(f"qc.office@{DOM}", "Quality Control Office"), now=NOW)
WS = ("ss_qc", "Quality Control")
COLS = ["Batch_ID", "Type", "Reading_1", "Reading_2", "Reading_3", "Acceptance_1", "Acceptance_2", "Acceptance_3", "Status"]
rows = [dict(zip(COLS, list(b) + ["Pending"])) for b in B]
out = W.sheet("ws_batches", "Inspection Batches", COLS, rows, workspace=WS,
              src="datapool:uci-ai4i-2020-maintenance (Product ID / Type) + world-config inspection specs")
idmap = {r["Batch_ID"]: r["_id"] for r in out}
POL = [("1", "A batch passes inspection only if EVERY reading equals its listed acceptance value (Reading_1=Acceptance_1, Reading_2=Acceptance_2, Reading_3=Acceptance_3)."),
       ("2", "A batch that passes must keep its current Status."),
       ("3", "A batch that fails (any reading does not match its acceptance value) must have its Status set to 'Review'."),
       ("4", "Apply this rule to every batch on the Inspection Batches sheet.")]
W.sheet("ws_policy", "Quality Control Policy", ["Rule", "Requirement"], [{"Rule": a, "Requirement": b} for a, b in POL],
        workspace=WS, src="world config (policy)")
MEM = [(f"lin.ojo@{DOM}", "Lin Ojo"), (f"yem.dey@{DOM}", "Yemi Dey")]
sid_qc = W.stream(CH, MEM, [{"sender": MEM[0][0], "text": "Reminder: sign the daily batch log before the end of shift."},
                            {"sender": MEM[1][0], "text": "Calibration on line 2 is due next week."}],
                  description="Quality control team channel", src="one reminder + datapool-style noise")
spec = W.merge(); spec = flat_row_patch(spec, ["Status"])
rep, bad = W.obs_report(); assert not bad, (rep, bad)

GOAL = (f"Today, {TODAY}, a fresh inspection run is logged on the Inspection Batches sheet of the Quality Control workbook. "
        f"Classify every batch on that sheet using the quality-control policy worksheet in the same workbook: a batch that fails "
        f"inspection must have its Status changed to Review, while batches that pass must be left exactly as they are. When you are "
        f"done, post a short summary to the #{CH} channel naming the batches you moved to Review.")

C = Contract(GOAL, expected={"failed": [b[0] for b in FAIL], "nearmiss": [b[0] for b in NEARMISS],
                             "passing": [b[0] for b in PASS], "review_status": "Review", "pending_status": "Pending"})
def stcell(bid, val): return row_in("ws_batches", Batch_ID=bid, Status=val)
for b in FAIL:
    C.add(f"review_{b[0]}", f"batch {b[0]} ({b[1]}) has Status 'Review' (failed inspection)", CNT(stcell(b[0], "Review")))
for b in PASS:
    C.add(f"keep_{b[0]}", f"batch {b[0]} ({b[1]}) keeps Status 'Pending' (passed inspection, untouched)", CNT(stcell(b[0], "Pending"), "eq", 1), negative=True)
C.add("post_summary", f"the #{CH} channel gets a summary naming at least one batch moved to Review",
      OR(*[CNT(stream_post(CH, b[0])) for b in FAIL]))
bad = C.seed_check(spec); assert not bad, bad

steps = []
for b in FAIL:
    steps.append(("budibase", "row_patch", {"sourceId": "ws_batches", "id": idmap[b[0]], "Status": "Review"}))
steps.append(("zulip", "send_message", {"stream_id": sid_qc,
              "content": f"Inspection review {TODAY}: moved to Review - " + ", ".join(f"{b[0]} ({b[1]})" for b in FAIL),
              "topic": "review"}))
assert_tool_arg_names(spec)

if __name__ == "__main__":
    atoms = [{"id": "a1", "kind": "update_cell", "text": "Inspection Batches: set Status to Review for the batches that fail the policy rule (passing batches unchanged)"},
             {"id": "a2", "kind": "post_channel", "text": "summary post in #quality-control naming the batches moved to Review"}]
    out_p, td = write_pack(TID, W, spec, C, atoms, skeleton=f"{SID}: policy sheet -> classify batches (tiering) -> update_cell + summary post (2 intents)",
                           notes_extra="The Quality Control workbook has the Inspection Batches sheet and the Quality Control Policy worksheet (table_fetchall lists the sheets; row_fetch(sourceId='ws_batches') reads the batches). To move a batch to review, update its Status cell: row_patch(sourceId='ws_batches', id=<row id>, Status='Review').")
    print("GOAL:", GOAL); print("expected:", json.dumps(C.expected)); print("preds", len(C.P), "obs", rep)
    bad, env = sim_gold(TID, spec, W, C, steps); assert not bad, bad
    print("write_pack ->", out_p)
