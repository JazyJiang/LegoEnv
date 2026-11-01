"""register.py — attach the ever_gauzy (full ERP/HCM suite: HR, candidates, timesheets, projects/tasks,
invoicing/payments, goals/OKRs, integrations, employee & org admin) spec to packlib WITHOUT editing packlib.py.

    import sys; sys.path.insert(0, "/builder/smoke/pack")
    from packlib import *
    from newspecs3.ever_gauzy.register import *     # adds ever_gauzy to SERVER/PFX/CONTENT/NOTES/LOGIN + obs hook + seed helpers

The base (pack/base_specs/ever_gauzy.spec.json, patched from env_compiler's v1 repo_spec) holds the persona account
(User id 1, SUPER_ADMIN, signed in with sign_in(email, password)). Content entities are empty — seed them with the
helpers below (ever_goals / broadcasts) or W.seed(app, entity, rows).

ever_gauzy covers the object/OKR and announcements planes of an ERP: goals (name, description, level, progress) and
organization broadcasts (title, content, category). Both are standalone rows (no required FK parents) and read plainly
through goal_findall/broadcast_findall (+ q keyword filter) — the agent's read/write surface. Candidates / invoices
need FK parents the empty seed lacks (see PATCHES.md), so they stay out of CONTENT.
"""
import json, runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, LOGIN, OBS_CAP, SEL, F, AND, CNT

NEW_SERVER = {"ever_gauzy": "erp"}

# entities that hold task content (seeded per pack; listed in packlib CONTENT)
NEW_CONTENT = {"ever_gauzy": ["Goal", "Broadcast", "OrganizationProject", "OrganizationTeam", "Comment", "Tag"]}

NEW_NOTES = {
    "ever_gauzy": "{p}__ is the ERP/HCM suite (HR, candidates, timesheets, projects/tasks, invoicing, goals/OKRs): sign in with "
                 "{p}__sign_in(email, password); you are the admin (User 1). "
                 "goal_findall(q) lists goals (name, description, level, progress) — omit q for all, pass q to filter by keyword; "
                 "goal_create(name, description, level, progress) adds a goal; goal_update(id, description, progress, level) edits one; "
                 "goal_delete(id) removes it. "
                 "broadcast_findall(q) lists announcements (title, content, category); broadcast_search(q) searches them by keyword; "
                 "broadcast_create(title, content, category) posts an announcement; broadcast_update(id, title, content) edits one. "
                 "user_findall lists accounts; organization_findall lists the orgs. All writes are scoped to your session; "
                 "goal_create/broadcast_create default the org to your current organization."
}
NEW_LOGIN = {"ever_gauzy": ("sign_in", "email")}
for _a in NEW_SERVER:
    SERVER.setdefault(_a, NEW_SERVER[_a]); PFX.setdefault(_a, _a)
    CONTENT.setdefault(_a, NEW_CONTENT[_a]); NOTES.setdefault(_a, NEW_NOTES[_a])
packlib.LOGIN.update(NEW_LOGIN)   # simulate()/login() sign into ever_gauzy too

# ───────── whole-list reads the agent will make on ever_gauzy (12k observation cap) ─────────
_orig_obs = World.obs_report
def _obs_report(self):
    rep, bad = _orig_obs(self)
    if "ever_gauzy" not in self.apps: return rep, bad
    env = runtime.Env(self.world)
    t, col = LOGIN["ever_gauzy"]; env.call(NS("ever_gauzy", t), {col: self.persona, "password": self.password})
    def rd(tool, args): return len(json.dumps(env.call(NS("ever_gauzy", tool), args), ensure_ascii=False, default=str))
    rep["ever_gauzy goal_findall"] = rd("goal_findall", {})
    rep["ever_gauzy broadcast_findall"] = rd("broadcast_findall", {})
    rep["ever_gauzy broadcast_search"] = rd("broadcast_search", {"q": ["."]})
    rep["ever_gauzy user_findall"] = rd("user_findall", {})
    rep["ever_gauzy organization_findall"] = rd("organization_findall", {})
    bad = {k: v for k, v in rep.items() if v > OBS_CAP}
    return rep, bad
World.obs_report = _obs_report

# ───────── seeding helpers ─────────
TS = "2026-01-01T00:00:00"
def _ss(W, app): return W.spec[app]["seed_state"]
def _bind(W, app, ent, src, n):
    if src: W.bindings[NS(app, ent)] = {"dataset": src, "rows": n}

def ever_goals(W, rows, src=None):
    """ever_gauzy OKR / goals content rows. rows = [{id, name, description?, level?, progress?, ownerEmployeeId?}].
    A description can carry a literal policy text (the `notes_field` carrier = Goal.description)."""
    ss = _ss(W, "ever_gauzy")
    for r in rows:
        ss.setdefault("Goal", []).append({
            "id": r["id"], "name": r["name"], "description": r.get("description"), "level": r.get("level", "A"),
            "progress": float(r.get("progress", 0.0)), "organizationId": r.get("organizationId", 1), "tenantId": 1,
            "ownerEmployeeId": r.get("ownerEmployeeId")})
    _bind(W, "ever_gauzy", "Goal", src, len(rows))

def broadcasts(W, rows, src=None):
    """ever_gauzy announcements. rows = [{id, title, content?, category?, visibilityMode?}].
    content can be the carrier policy text (`notes_field` carrier = Broadcast.content)."""
    ss = _ss(W, "ever_gauzy")
    for r in rows:
        ss.setdefault("Broadcast", []).append({
            "id": r["id"], "title": r["title"], "content": r.get("content"), "category": r.get("category", "ops"),
            "visibilityMode": r.get("visibilityMode", "all"), "organizationId": r.get("organizationId", 1), "tenantId": 1})
    _bind(W, "ever_gauzy", "Broadcast", src, len(rows))

def ever_projects(W, rows, src=None):
    """ever_gauzy projects. rows = [{id, name, description?, code?, organizationId?}]."""
    ss = _ss(W, "ever_gauzy")
    for r in rows:
        ss.setdefault("OrganizationProject", []).append({
            "id": r["id"], "name": r["name"], "description": r.get("description"), "code": r.get("code"),
            "organizationId": r.get("organizationId", 1), "tenantId": 1, "public": True, "isActive": True})
    _bind(W, "ever_gauzy", "OrganizationProject", src, len(rows))

def ever_users(W, rows):
    """ever_gauzy colleagues besides the persona (User id 1). rows = [{id, username, email?, firstName?, lastName?,
    roleId?}]. Passwords default to pw-<id>; the persona stays id 1."""
    ss = _ss(W, "ever_gauzy")
    for r in rows:
        ss.setdefault("User", []).append({
            "id": r["id"], "username": r.get("username", f"user{r['id']}"), "email": r.get("email", f"user{r['id']}@evergauzy.example"),
            "firstName": r.get("firstName", f"User{r['id']}"), "lastName": r.get("lastName", ""), "hash": f"pw-{r['id']}",
            "roleId": r.get("roleId", 2), "tenantId": 1, "isActive": True})
    _bind(W, "ever_gauzy", "User", None, len(rows))

def smoke_seed(W):
    """seed >= 3 realistic content rows + one policy text in a carrier field (Goal.description, the `notes_field`
    carrier) and one in a Broadcast.content; return gold steps that perform a write and >= 3 contract predicates
    (incl. one negative), built with SEL/F/AND/CNT on ever_gauzy entities."""
    ever_goals(W, [
        {"id": 101, "name": "Grow recurring revenue 15%", "description": "Expand subscriptions and renewals across the base.", "level": "A", "progress": 0.3},
        {"id": 102, "name": "Cut support backlog", "description": "Bring open support tickets under 40 by quarter end.", "level": "B", "progress": 0.0},
        {"id": 103, "name": "Ship onboarding revamp", "description": "Relaunch customer onboarding with the new flow.", "level": "C", "progress": 0.5},
    ], src=None)
    broadcasts(W, [
        {"id": 201, "title": "Promo approval policy", "content": "Policy: any promotion discount is capped at 20%; larger discounts need finance sign-off before publishing.", "category": "policy"},
        {"id": 202, "title": "Maintenance window", "content": "Production maintenance runs every Sunday 02:00-04:00 UTC.", "category": "ops"},
    ], src=None)
    steps = [
        ("ever_gauzy", "goal_create", {"name": "Improve NRR to 108%", "description": "Raise net revenue retention via expansions.", "level": "A", "progress": 0.0}),
        ("ever_gauzy", "goal_update", {"id": 102, "description": "Cut support backlog below 30 by quarter end.", "progress": 0.2}),
    ]
    preds = [
        ("goal_created", "a goal named 'Improve NRR to 108%' exists",
         CNT(SEL(NS("ever_gauzy", "Goal"), F("name", "eq", "Improve NRR to 108%")), "gte", 1), False),
        ("goal_updated", "the 'Cut support backlog' goal has progress 0.2 with the revised description",
         CNT(SEL(NS("ever_gauzy", "Goal"), AND(F("name", "eq", "Cut support backlog"), F("progress", "eq", 0.2), F("description", "icontains", "below 30"))), "gte", 1), False),
        ("nogoal", "no goal is named 'Zero net retention' (negative)",
         CNT(SEL(NS("ever_gauzy", "Goal"), F("name", "eq", "Zero net retention")), "eq", 0), True),
    ]
    return steps, preds

__all__ = ["NEW_SERVER", "ever_goals", "broadcasts", "ever_projects", "ever_users", "smoke_seed"]
