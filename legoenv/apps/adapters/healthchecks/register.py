"""Register Healthchecks monitoring actions for the isolated pack builder."""

import json

import runtime
from packlib import AND, CNT, CONTENT, F, LOGIN, NOTES, NS, OBS_CAP, PFX, SEL, SERVER, World


APP = "healthchecks"
SERVER[APP] = "monitoring"
PFX[APP] = "healthchecks"
CONTENT[APP] = ["Check"]
NOTES[APP] = (
    "{p}__ manages scheduled-job checks. Sign in with sign_in(email, password). "
    "check_list and check_get inspect existing checks and their descriptions. "
    "check_create(name, project_code, slug, timeout, grace) adds a check to an existing project; "
    "check_update_timeout(code, timeout, grace) changes timing; "
    "check_pause(code) and check_resume(code) change the monitoring state."
)
LOGIN[APP] = ("sign_in", "email")


_old_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _old_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    env.call(NS(APP, "sign_in"), {"email": self.persona, "password": self.password})
    response = env.call(NS(APP, "check_list"), {})
    report[f"{APP} check_list"] = len(json.dumps(response, ensure_ascii=False, default=str))
    bad = {name: size for name, size in report.items() if size > OBS_CAP}
    return report, bad


World.obs_report = _obs_report


def smoke_seed(world):
    """Seed a policy and three checks; exercise creation and state/timing writes."""
    world.seed(APP, "Check", [
        {"id": 10, "code": "policy", "project": 1, "name": "Monitoring policy", "slug": "policy", "desc": "Reduce the import check timeout, pause it during maintenance, resume the archive check, and add the finance check. Leave the audit check running.", "status": "up", "timeout": 86400, "grace": 3600},
        {"id": 11, "code": "import-job", "project": 1, "name": "Import job", "slug": "import-job", "desc": "Maintenance window is approved.", "status": "up", "timeout": 86400, "grace": 3600},
        {"id": 12, "code": "archive-job", "project": 1, "name": "Archive job", "slug": "archive-job", "desc": "Ready to resume.", "status": "paused", "timeout": 86400, "grace": 3600},
        {"id": 13, "code": "audit-job", "project": 1, "name": "Audit job", "slug": "audit-job", "desc": "No maintenance is scheduled.", "status": "up", "timeout": 86400, "grace": 3600},
    ])
    steps = [
        (APP, "check_update_timeout", {"code": "import-job", "timeout": 1800, "grace": 300}),
        (APP, "check_pause", {"code": "import-job"}),
        (APP, "check_resume", {"code": "archive-job"}),
        (APP, "check_create", {"project_code": "p-1", "name": "Finance check", "slug": "finance-check", "timeout": 3600, "grace": 600}),
    ]
    preds = [
        ("timeout_import", "Import check timeout is shortened.", CNT(SEL(NS(APP, "Check"), AND(F("code", "eq", "import-job"), F("timeout", "eq", 1800)))), False),
        ("pause_import", "Import check is paused.", CNT(SEL(NS(APP, "Check"), AND(F("code", "eq", "import-job"), F("status", "eq", "paused")))), False),
        ("resume_archive", "Archive check is resumed.", CNT(SEL(NS(APP, "Check"), AND(F("code", "eq", "archive-job"), F("status", "eq", "new")))), False),
        ("create_finance", "Finance check is created in the selected project with a usable code.", CNT(SEL(NS(APP, "Check"), AND(F("name", "eq", "Finance check"), F("project", "eq", 1), F("code", "eq", "finance-check")))), False),
        ("preserve_audit", "Unselected audit check is not paused.", CNT(SEL(NS(APP, "Check"), AND(F("code", "eq", "audit-job"), F("status", "eq", "paused"))), "eq", 0), True),
    ]
    return steps, preds
