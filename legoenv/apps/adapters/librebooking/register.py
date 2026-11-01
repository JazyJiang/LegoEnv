"""Register LibreBooking check-in, approval and resource administration."""

import json

import runtime
from packlib import AND, CNT, CONTENT, F, LOGIN, NOTES, NS, OBS_CAP, PFX, SEL, SERVER, World


APP = "librebooking"
SERVER[APP] = "bookings"
PFX[APP] = "librebooking"
CONTENT[APP] = ["Resource", "ReservationSeries", "ReservationInstance"]
NOTES[APP] = (
    "{p}__ manages resource reservations. Sign in with sign_in(email, password). "
    "resource_get(resourceId) shows resource notes and settings; reservation_search() lists the seeded bookings, and reservation_get(referenceNumber) "
    "shows an existing booking. reservation_checkin(referenceNumber, checkinDate) records arrival; "
    "reservationseries_approve(referenceNumber) approves an existing Pending series; "
    "resource_update(resourceId, notes) edits a resource's administrative notes. "
    "Use only the reference numbers and resource ids from the visible records."
)
LOGIN[APP] = ("sign_in", "email")


_old_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _old_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    env.call(NS(APP, "sign_in"), {"email": self.persona, "password": self.password})
    for name, args in (("resource_get", {"resourceId": 1}), ("reservation_get", {"referenceNumber": "RES-LAB"}), ("reservation_search", {})):
        response = env.call(NS(APP, name), args)
        report[f"{APP} {name}"] = len(json.dumps(response, ensure_ascii=False, default=str))
    bad = {name: size for name, size in report.items() if size > OBS_CAP}
    return report, bad


World.obs_report = _obs_report


def smoke_seed(world):
    """Seed linked bookings and resource permissions with two near misses."""
    world.seed(APP, "Resource", [
        {"resource_id": 1, "name": "Teaching lab", "schedule_id": 1, "status_id": 1, "enable_check_in": 1, "requires_approval": 0, "allow_display": 1, "notes": "Booking policy: check in the lab session with a confirmed arrival; approve the safety-reviewed seminar; update the seminar room's access notes. Leave the routine meeting pending and the quiet room unchanged."},
        {"resource_id": 2, "name": "Seminar room", "schedule_id": 1, "status_id": 1, "enable_check_in": 0, "requires_approval": 1, "allow_display": 1, "notes": "Access instructions pending review."},
        {"resource_id": 3, "name": "Quiet room", "schedule_id": 1, "status_id": 1, "enable_check_in": 0, "requires_approval": 1, "allow_display": 1, "notes": "No change requested."},
    ])
    world.seed(APP, "ReservationSeries", [
        {"series_id": 11, "owner_id": 1, "title": "Lab session", "description": "Arrival confirmed at reception.", "status_id": 1, "type_id": 1},
        {"series_id": 12, "owner_id": 2, "title": "Safety-reviewed seminar", "description": "Safety review complete.", "status_id": 3, "type_id": 1},
        {"series_id": 13, "owner_id": 2, "title": "Routine meeting", "description": "Review incomplete.", "status_id": 3, "type_id": 1},
    ])
    world.seed(APP, "ReservationInstance", [
        {"reservation_instance_id": 11, "reference_number": "RES-LAB", "series_id": 11, "start_date": "2026-09-25T09:00:00", "end_date": "2026-09-25T10:00:00"},
        {"reservation_instance_id": 12, "reference_number": "RES-SEMINAR", "series_id": 12, "start_date": "2026-09-25T11:00:00", "end_date": "2026-09-25T12:00:00"},
        {"reservation_instance_id": 13, "reference_number": "RES-ROUTINE", "series_id": 13, "start_date": "2026-09-25T13:00:00", "end_date": "2026-09-25T14:00:00"},
    ])
    world.spec[APP]["seed_state"]["ReservationResource"] = [
        {"series_id": 11, "resource_id": 1},
        {"series_id": 12, "resource_id": 2},
        {"series_id": 13, "resource_id": 3},
    ]
    world.spec[APP]["seed_state"]["UserResourcePermission"] = [
        {"user_id": 1, "resource_id": resource_id, "permission_id": 1, "permission_type": 1}
        for resource_id in (1, 2, 3)
    ]
    steps = [
        (APP, "reservation_checkin", {"referenceNumber": "RES-LAB", "checkinDate": "2026-09-25T09:03:00"}),
        (APP, "reservationseries_approve", {"referenceNumber": "RES-SEMINAR"}),
        (APP, "resource_update", {"resourceId": 2, "notes": "Access instructions confirmed for the seminar."}),
    ]
    preds = [
        ("lab_checked_in", "Confirmed lab arrival is recorded.", CNT(SEL(NS(APP, "ReservationInstance"), AND(F("reference_number", "eq", "RES-LAB"), F("checkin_date", "eq", "2026-09-25T09:03:00")))), False),
        ("seminar_approved", "Safety-reviewed seminar is approved.", CNT(SEL(NS(APP, "ReservationSeries"), AND(F("series_id", "eq", 12), F("status_id", "eq", 1)))), False),
        ("access_notes", "Seminar access instructions are recorded.", CNT(SEL(NS(APP, "Resource"), AND(F("resource_id", "eq", 2), F("notes", "eq", "Access instructions confirmed for the seminar.")))), False),
        ("routine_not_approved", "Routine meeting stays pending.", CNT(SEL(NS(APP, "ReservationSeries"), AND(F("series_id", "eq", 13), F("status_id", "eq", 1))), "eq", 0), True),
        ("quiet_unchanged", "Quiet room notes are unchanged.", CNT(SEL(NS(APP, "Resource"), AND(F("resource_id", "eq", 3), F("notes", "eq", "Access instructions confirmed for the seminar."))), "eq", 0), True),
    ]
    return steps, preds
