"""Register Hitobito event application actions for the local pack builder."""

import json

import runtime
from packlib import AND, CNT, CONTENT, F, LOGIN, NOTES, NS, OBS_CAP, PFX, SEL, SERVER, World


APP = "hitobito"
SERVER[APP] = "events"
PFX[APP] = "hitobito"
CONTENT[APP] = ["EventApplication", "Note", "Event"]
NOTES[APP] = (
    "{p}__ manages event applications. Sign in with sign_in(email, password). "
    "note_index exposes policy notes. eventapplication_approve_or_reject(id, approved=true) "
    "approves a listed application; eventapplication_waiting_list_remove(id) removes an expired waitlist offer."
)
LOGIN[APP] = ("sign_in", "email")

_old_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _old_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    env.call(NS(APP, "sign_in"), {"email": self.persona, "password": self.password})
    response = env.call(NS(APP, "note_index"), {})
    report[f"{APP} note_index"] = len(json.dumps(response, ensure_ascii=False, default=str))
    bad = {name: size for name, size in report.items() if size > OBS_CAP}
    return report, bad


World.obs_report = _obs_report


def smoke_seed(world):
    world.seed(APP, "EventApplication", [
        {"id": 11, "approved": False, "rejected": False, "waiting_list": False},
        {"id": 12, "approved": False, "rejected": False, "waiting_list": True},
        {"id": 13, "approved": False, "rejected": False, "waiting_list": False},
        {"id": 14, "approved": False, "rejected": False, "waiting_list": False},
    ])
    world.seed(APP, "Note", [
        {"id": 31, "author_id": 1, "subject_id": 1, "subject_type": "Event", "text": "Approve eligible applications 11 and 14. Remove expired waitlist offer 12. Hold application 13 for review."},
    ])
    steps = [
        (APP, "eventapplication_approve_or_reject", {"id": 11, "approved": True}),
        (APP, "eventapplication_approve_or_reject", {"id": 14, "approved": True}),
        (APP, "eventapplication_waiting_list_remove", {"id": 12}),
    ]
    preds = [
        ("approve_11", "Eligible application 11 is approved.", CNT(SEL(NS(APP, "EventApplication"), AND(F("id", "eq", 11), F("approved", "eq", True)))), False),
        ("approve_14", "Eligible application 14 is approved.", CNT(SEL(NS(APP, "EventApplication"), AND(F("id", "eq", 14), F("approved", "eq", True)))), False),
        ("release_12", "Expired offer 12 leaves the waitlist.", CNT(SEL(NS(APP, "EventApplication"), AND(F("id", "eq", 12), F("waiting_list", "eq", False)))), False),
        ("hold_13", "Held application 13 is not approved.", CNT(SEL(NS(APP, "EventApplication"), AND(F("id", "eq", 13), F("approved", "eq", True))), "eq", 0), True),
    ]
    return steps, preds
