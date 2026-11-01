"""Register narrow SuiteCRM alert workflows for isolated task packs."""

import json

import runtime
from packlib import AND, CNT, CONTENT, F, LOGIN, NOTES, NS, OBS_CAP, PFX, SEL, SERVER, World


APP = "suitecrm"
SERVER[APP] = "crm"
PFX[APP] = "suitecrm"
CONTENT[APP] = ["SugarBeanModule", "Alert"]
NOTES[APP] = (
    "{p}__ holds CRM alert records and a small module-scoped case register. "
    "Sign in with user_login(user_name, password). "
    "module_getlist(module='TriagePolicies' or module='Cases') reads policy/case summaries. "
    "alert_create(name, description, target_module) creates an internal alert for the signed-in user; "
    "alert_markasread(record) marks an existing alert read. "
    "The generic module_create tool is not available as a business-record writer in these tasks."
)
LOGIN[APP] = ("user_login", "user_name")


_old_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _old_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    env.call(NS(APP, "user_login"), {"user_name": self.persona, "password": self.password})
    for module in ("TriagePolicies", "Cases"):
        response = env.call(NS(APP, "module_getlist"), {"module": module})
        report[f"{APP} module_getlist {module}"] = len(json.dumps(response, ensure_ascii=False, default=str))
    bad = {name: size for name, size in report.items() if size > OBS_CAP}
    return report, bad


World.obs_report = _obs_report


def smoke_seed(world):
    # World replaces the first username as text before replacing the password.
    # The release's pw-ada includes that username, so restore the persona hash.
    world.spec[APP]["seed_state"]["User"][0]["user_hash"] = world.password
    world.seed(APP, "SugarBeanModule", [
        {"id": "policy-1", "module_name": "TriagePolicies", "name": "Internal alert policy", "item_summary": "Create an internal alert for the urgent inspection case, mark the resolved alert as read, and leave the routine reminder unread.", "deleted": 0},
        {"id": "case-urgent", "module_name": "Cases", "name": "Urgent inspection", "item_summary": "High-priority site inspection needs an internal alert.", "deleted": 0},
        {"id": "case-routine", "module_name": "Cases", "name": "Routine reminder", "item_summary": "Routine follow-up; do not create an urgent alert.", "deleted": 0},
    ])
    world.seed(APP, "Alert", [
        {"id": "alert-resolved", "name": "Resolved follow-up", "description": "The old follow-up is complete.", "is_read": 0, "assigned_user_id": world.spec[APP]["seed_state"]["User"][0]["id"], "deleted": 0},
        {"id": "alert-routine", "name": "Routine reminder", "description": "Keep this visible for the next shift.", "is_read": 0, "assigned_user_id": world.spec[APP]["seed_state"]["User"][0]["id"], "deleted": 0},
        {"id": "alert-distractor", "name": "Unrelated account", "description": "No action required.", "is_read": 1, "assigned_user_id": world.spec[APP]["seed_state"]["User"][0]["id"], "deleted": 0},
    ])
    steps = [
        (APP, "alert_create", {"name": "Urgent inspection", "description": "Review case-urgent before the next site visit.", "target_module": "Cases"}),
        (APP, "alert_markasread", {"record": "alert-resolved"}),
    ]
    preds = [
        ("urgent_alert", "Urgent inspection alert is created.", CNT(SEL(NS(APP, "Alert"), AND(F("name", "eq", "Urgent inspection"), F("description", "icontains", "case-urgent")))), False),
        ("resolved_read", "Resolved follow-up alert is read.", CNT(SEL(NS(APP, "Alert"), AND(F("id", "eq", "alert-resolved"), F("is_read", "eq", 1)))), False),
        ("routine_unread", "Routine reminder remains unread.", CNT(SEL(NS(APP, "Alert"), AND(F("id", "eq", "alert-routine"), F("is_read", "eq", 1))), "eq", 0), True),
    ]
    return steps, preds
