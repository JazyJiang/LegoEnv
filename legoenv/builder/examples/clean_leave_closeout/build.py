#!/usr/bin/env python3.12
"""db_shipping_leave_accrual — a targeted instance of skeleton mine_hr_020.
Skeleton chain: read the policy e-mail in the inbox to learn the business rule → scan the records (worksheet seeded from a real dataset) and
select the ones the rule applies to (≥2 look-alikes skipped) → per selected record: append_row in budibase (grace-period entry) + send_dm in zulip
(notify the employee) → finish with a send_email in stalwart (summary to the payroll office).
Rule archetypes: budget_quota (annual-leave accrual is capped at one full annual entitlement; a 60-day grace row is opened for anyone who reaches it)
+ exclusion (advance written approval from the President's office keeps someone accruing and leaves them off the grace list).
Data: sriharshata-employees-oracle-hr — real Oracle HR employees of dept 50 (Shipping): names, ids, jobs, manager hierarchy; entitlements/balances
are world config assigned to the real people.
Apps kept: budibase (roster + grace target sheets), stalwart (policy mail + summary), zulip (DMs). No app dropped."""
import sys, json
sys.path.insert(0, "./pack"); sys.path.insert(0, "./pack_dpsk"); sys.path.insert(0, "./pack/batches")
from packlib import *
from t02lib import *
from t03lib import mail_of, check_keys
from dklib import sim_gold

TID = 'clean_leave_closeout'
DOM = "baycove.example"; TODAY = "2026-09-24"; NOW = f"{TODAY}T09:00:00"
ACC = "ws_accrual"; GR = "ws_grace"

rows0 = csv_rows(f"{ds('sriharshata-employees-oracle-hr')}/EMPLOYEES.csv")
byid = {r["EMPLOYEE_ID"]: r for r in rows0}
def ro(id_):
    r = byid[str(id_)]
    return {"id": str(id_), "name": f"{r['FIRST_NAME']} {r['LAST_NAME']}", "job": r["JOB_ID"], "dept": r["DEPARTMENT_ID"], "mgr": r["MANAGER_ID"]}
def em(r): return mail_of(r["name"].split()[0], r["name"].split()[-1], DOM)
def last(r): return r["name"].split()[-1]

def P(id_, ent, bal, etype="Permanent", astatus="Active", appr=""):
    r = ro(id_)
    return {"Name": r["name"], "EmployeeID": r["id"], "Department": "50", "Job_Title": r["job"],
            "Annual_Entitlement": ent, "Accrued_Balance": bal, "Employment_Type": etype,
            "Accrual_Status": astatus, "Exec_Approval": appr, "Notes": "", "mgr": r["mgr"], "email": em(r), "last": last(r)}

# (id, entitlement, balance) — all real dept-50 Oracle HR people; ent/bal = world config
ROWS = [P(120, 25, 25),   # Matthew Weiss  -> eligible (reached exactly)
        P(121, 25, 27),   # Adam Fripp     -> eligible (over the cap)
        P(125, 20, 20),   # Julia Nayer    -> eligible
        P(127, 18, 18),   # James Landry   -> eligible
        P(138, 22, 22),   # Stephen Stiles -> eligible
        P(126, 20, 12, appr="", astatus="Active"),                    # D1 under-cap
        P(128, 18, 22, appr="Approved by President"),                 # D2 exclusion exception
        P(142, 22, 30, etype="Fixed-Term"),                           # D3 fixed-term excluded
        P(136, 20, 24, astatus="Ceased"),                             # D4 cease-accrual
        P(129, 19, 6), P(131, 18, 4), P(133, 21, 8), P(143, 17, 5)]   # bystanders (well under)

def eligible(r):
    if int(r["Accrued_Balance"]) < int(r["Annual_Entitlement"]): return False
    if r["Exec_Approval"] == "Approved by President": return False
    if r["Employment_Type"] != "Permanent": return False
    if r["Accrual_Status"] == "Ceased": return False
    return True
ELIG = [r for r in ROWS if eligible(r)]

assert len(ELIG) == 5, [r["Name"] for r in ELIG]
assert [r["Name"].split()[-1] for r in ELIG] == ["Weiss", "Fripp", "Nayer", "Landry", "Stiles"], [r["Name"] for r in ELIG]
D = [r for r in ROWS if not eligible(r) and r["Exec_Approval"]] or [r for r in ROWS if not eligible(r)]
D1 = next(r for r in ROWS if r["EmployeeID"] == "126")
D2 = next(r for r in ROWS if r["EmployeeID"] == "128")
D3 = next(r for r in ROWS if r["EmployeeID"] == "142")
D4 = next(r for r in ROWS if r["EmployeeID"] == "136")
GRANTERS = [r["Name"] for r in ELIG]
print("ELIGIBLE:", GRANTERS)

# ─────────────────────────── world ───────────────────────────
W = World(["budibase", "stalwart", "zulip"], persona=(f"hr.payroll@{DOM}", "HR Payroll Office"), now=NOW)
WS = ("ss_accrual", "Leave Accrual Review")
W.sheet(ACC, "Leave Accrual",
        ["Name", "EmployeeID", "Department", "Job_Title", "Annual_Entitlement", "Accrued_Balance", "Employment_Type", "Accrual_Status", "Exec_Approval", "Notes"],
        [{k: v for k, v in r.items() if k not in ("mgr", "email", "last")} for r in ROWS],
        workspace=WS, src="datapool:sriharshata-employees-oracle-hr (dept-50 names/ids/jobs) + world entitlements/balances")
W.sheet(GR, "Grace Period", ["Name", "EmployeeID", "Balance", "Entitlement", "Grace_Days", "Opened_By"], [],
        workspace=WS, src="target sheet (empty; deliverable)")

ctrl = {"from": f"payroll.controller@{DOM}", "from_name": "Payroll Controller", "when": "2026-09-20T08:00:00",
        "subject": "Leave accrual close-out rules - Shipping",
        "body": ("Leave accrual close-out for the Shipping department.\n"
                 "1. Annual leave accrual stops for any employee whose Accrued_Balance is at or above their Annual_Entitlement - accrual is capped at one full annual entitlement.\n"
                 "2. When an employee reaches that cap, open a 60-day grace-period row for them on the Grace Period worksheet so their balance can be taken back under the cap, "
                 "and let the employee know in the team chat.\n"
                 "3. Exception: an employee holding advance written approval from the President's office (Exec_Approval = 'Approved by President') keeps accruing past the cap "
                 "and is NOT added to the grace-period list.\n"
                 "4. Only permanent employees are covered (Employment_Type = 'Permanent'); fixed-term staff are excluded.\n"
                 "5. Employees already on cease-accrual status (Accrual_Status = 'Ceased', e.g. leave without pay) are not given a grace period.\n"
                 "6. Send a summary naming the employees granted a grace period to payroll.office@baycove.example.\n- Payroll Controller")}
noise = noise_mails(4, 20)
W.inbox([noise[0], ctrl, noise[1], noise[2], noise[3]], src="controller close-out rules + datapool:enron-spam-setfit (4)")

chat = twcs_chat(2, seed=20)
members = [(r["email"], r["Name"]) for r in ROWS]
W.stream("hr-accrual", members,
         [{"sender": members[0][0], "text": "Reminder: submit leave requests before the 25th."},
          {"sender": members[2][0], "text": chat[0]["text"]}], description="Shipping leave & accrual chat",
         src="datapool:sriharshata-employees-oracle-hr (members) + datapool:twcs (1 noise)")
spec = W.merge(); rep, bad = W.obs_report(); assert not bad, (rep, bad); check_keys(spec)

# zulip member id mapping (World.stream numbers members 2.. in order; persona id = 1)
uid = {r["Name"]: i + 2 for i, r in enumerate(ROWS)}
assert len(uid) == len(ROWS)

GOAL = ("We're closing out annual leave accrual for the Shipping department and need the capped employees put on grace-period status. "
        f"Today is {TODAY}. Read the leave-accrual policy e-mail in the mail inbox (from the payroll controller) to learn the accrual close-out rules, "
        "then review the Leave Accrual worksheet in the 'Leave Accrual Review' spreadsheet workbook, which lists every Shipping employee's annual "
        "entitlement and accrued balance. For each employee whose accrual is capped by the policy, append one 60-day grace-period row to the Grace Period "
        "worksheet and direct-message that employee in the team chat channel (their profile is listed there). Finally, send the payroll office a single "
        "summary e-mail naming the employees granted a grace period to payroll.office@baycove.example.")

C = Contract(GOAL, expected={"granted": GRANTERS, "excluded": {"Irene Mikkilineni": "under cap", "Steven Markle": "president approval",
    "Curtis Davies": "fixed-term", "Hazel Philtanker": "ceased accrual"}})
def grace_row(name): return rows(GR, cell("Name", "eq", name))
for r in ELIG:
    k = slug(r["Name"]); lastn = r["last"]
    C.add(f"grace_{k}", f"a Grace Period row is opened for {r['Name']}", CNT(grace_row(r["Name"])))
    C.add(f"dm_{k}", f"the team chat gets a direct message to {r['Name']} telling them a grace period was opened", CNT(dm(uid[r["Name"]], lastn, "grace")))
# stalwart summary mail positive (one email naming all five grantees)
C.add("summary_mail", f"payroll.office@baycove.example gets a summary naming {', '.join(r['last'] for r in ELIG)}",
      CNT(sent_to(f"payroll.office@{DOM}", *[r["last"] for r in ELIG], "grace")))
# budibase negatives: no grace row for the four distractors
for d in (D1, D2, D3, D4):
    C.add(f"nograce_{slug(d['Name'])}", f"no Grace Period row for {d['Name']}", CNT(grace_row(d["Name"]), "eq", 0), negative=True)
# stalwart negatives: no notification mail to the under-cap and president-approval projects
C.add("nomail_d1", f"no mail to {D1['Name']} ({D1['email']})", CNT(sent_to(D1["email"]), "eq", 0), negative=True)
C.add("nomail_d2", f"no mail to {D2['Name']} ({D2['email']})", CNT(sent_to(D2["email"]), "eq", 0), negative=True)
bad = C.seed_check(spec); assert not bad, bad

steps = []
for r in ELIG:
    steps.append(("budibase", "row_save", {"sourceId": GR, "body": {"Name": r["Name"], "EmployeeID": r["EmployeeID"], "Balance": r["Accrued_Balance"],
        "Entitlement": r["Annual_Entitlement"], "Grace_Days": "60", "Opened_By": W.persona_name}}))
    steps.append(("zulip", "send_direct_message", {"user_id": uid[r["Name"]], "content": f"{r['Name']}, your leave balance of {r['Accrued_Balance']} days has reached your annual entitlement. A 60-day grace period was opened for you."}))
to_addr = [{"email": f"payroll.office@{DOM}"}]
summary_body = "Leave accrual close-out " + TODAY + ": granted a grace period to " + ", ".join(GRANTERS) + "."
steps += [("stalwart", "email_set", {"mailbox_ids": [2], "blob_id": 1, "subject": "Leave accrual close-out summary", "from": W.persona,
                                     "to": to_addr, "body": summary_body}),
          lambda env: env.call(NS("stalwart", "emailsubmission_set"), {"identity_id": 1, "email_id": max(e["id"] for e in env.state[NS("stalwart", "Email")]), "rcpt_to": [f"payroll.office@{DOM}"]})]

bad, env = simulate(spec, W, C, steps); assert not bad, bad
assert_tool_arg_names(spec)
if __name__ == "__main__":
    atoms = [{"id": "a1", "kind": "append_row", "text": "a Grace Period row for each eligible capped employee (60-day grant)"},
             {"id": "a2", "kind": "send_dm", "text": "a direct message to each granted employee in the team chat"},
             {"id": "a3", "kind": "send_email", "text": "one summary e-mail to the payroll office naming the granted employees"}]
    out, td = write_pack(TID, W, spec, C, atoms, skeleton="mine_hr_020: policy-mail rules → pick capped employees from the roster (look-alikes skipped) → per-record grace row + DM → summary e-mail",
                         notes_extra="The Leave Accrual and Grace Period are two worksheets of the 'Leave Accrual Review' workbook. To record a grace entry "
                         "append a row to Grace Period: row_save(sourceId='ws_grace', body={Name, EmployeeID, Balance, Entitlement, Grace_Days, Opened_By}).")
    bad, env = sim_gold(TID, spec, W, C, steps); assert not bad, bad
    print("GOAL:", GOAL); print("postconditions", len(C.P), "obs", rep); print(out, td)
