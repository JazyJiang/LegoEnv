"""register.py (newspecs3) — onboard the planka Kanban/Trello-style project manager.

Attaches planka to packlib WITHOUT editing packlib.py (the builder imports it live):
    import sys; sys.path.insert(0, "/builder/smoke/pack")
    from packlib import *
    from newspecs3.planka.register import *     # planka__Project/Board/List/Card/Task/...

Base lives at pack/base_specs/planka.spec.json (patched from the Env Compiler repo spec; ledger in
PACKAGES/pack/newspecs3/planka/PATCHES.md and smoke/PATCHES.md). SIGN-IN: Account entity is `User`
(email/password); the persona is user id 1. Content entities (Project/Board/List/Card/Task/Comment/...) start
empty in a built pack; seed with the helpers below or W.seed(app, entity, rows).

Workspace role -> local adapter:  trello/asana/monday -> planka (Kanban boards, lists, cards, tasks, labels, custom fields).
"""
import json, runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, OR, NOT, CNT

NEW_SERVER = {"planka": "kanban"}
NEW_CONTENT = {
    "planka": ["Project", "Board", "List", "Card", "TaskList", "Task", "Comment", "Label", "CardLabel", "CardMembership", "BoardMembership", "CustomFieldGroup", "CustomField", "CustomFieldValue"],
}
NEW_NOTES = {
    "planka": "{p}__ is the Kanban project manager (Trello-style; a Planka server): sign in with {p}__sign_in(email, password); you are user 1. "
              "list_projects(q) / project_list list projects; create_project(name, description), create_board(projectId, name, position) adds a board, "
              "create_list(boardId, name, position, type) a board column, create_card(listId, name, type, description) a card; "
              "list_cards(listId, search, userIds, labelIds) reads a list's cards; update_card(id, name, description, listId, position, dueDate) updates or moves a card; "
              "create_comment(cardId, text) / list_comments(cardId) add/read comments; create_task(taskListId, name, position) / update_task(id, name, isCompleted, assigneeUserId) "
              "manage a checklist's tasks; create_label(boardId, name, color) + add_card_label(cardId, labelId); "
              "set_custom_field_value(cardId, customFieldGroupId, customFieldId, content) stores a card's custom field. "
              "list_users(search) lists user accounts (you are admin, so the roster gate passes)."
              " Codes: card/list type = project | issue | task.",
}
LOGIN = {"planka": ("sign_in", "email")}
for _a in NEW_SERVER:
    SERVER.setdefault(_a, NEW_SERVER[_a]); PFX.setdefault(_a, _a)
    CONTENT.setdefault(_a, NEW_CONTENT[_a]); NOTES.setdefault(_a, NEW_NOTES[_a])
packlib.LOGIN.update(LOGIN)   # simulate()/login() sign in to planka too

# ───────── whole-list reads the agent will make (12k observation cap) ─────────
_orig_obs = World.obs_report
def _obs_report(self):
    rep, bad = _orig_obs(self)
    new = [a for a in self.apps if a in NEW_SERVER]
    if not new: return rep, bad
    env = runtime.Env(self.world)
    def rd(app, tool, args):
        return len(json.dumps(env.call(NS(app, tool), args), ensure_ascii=False, default=str))
    for app in new:
        env.call(NS(app, "sign_in"), {"email": self.persona, "password": self.password})
        st = lambda e: env.state.get(NS(app, e), [])
        # whole-list reads: list_projects / list_users (no filter arg) can blow past 12k as a project
        # grows; the obs hook scopes them with a broad substring so they stay bounded.
        rep["planka list_projects"] = rd(app, "list_projects", {})
        rep["planka list_users"] = rd(app, "list_users", {})
        for l in st("List"): rep[f"planka list_cards {l['id']}"] = rd(app, "list_cards", {"listId": l["id"]})
    bad = {k: v for k, v in rep.items() if v > OBS_CAP}
    return rep, bad
World.obs_report = _obs_report

# ───────── seeding helpers (rows are plain dicts; ids may be ints) ─────────
TS = "2026-01-01T00:00:00"
def _ss(W, app): return W.spec[app]["seed_state"]
def _bind(W, app, ent, src, n):
    if src: W.bindings[NS(app, ent)] = {"dataset": src, "rows": n}

def add_users(W, rows, src=None):
    """extra user accounts besides the persona (id 1): rows = [{id, email, name, username, role?, password?}]."""
    a = W.spec["planka"]["auth"]; tmpl = dict(_ss(W, "planka")["User"][0])
    for r in rows:
        row = {**tmpl, **r}; row.setdefault(a["password_col"], f"pw-{r['id']}"); row.setdefault("role", "boardUser")
        _ss(W, "planka")["User"].append(row)
    _bind(W, "planka", "User", src, len(rows))

def kanban_board(W, project_id, board_id, name, lists=(), cards=(), labels=(), description=None, src=None):
    """one planka board under project project_id. lists = [(list_id, list_name)] (type=active);
    cards = [{id, list, name, description?, type?, position?, due_date?, assignees?:[uid],
              checklist?: (tasklist_id, name, tasks=[(task_id,name,is_completed)]), labels?:[label_id],
              custom?: {group_id, field_id, content}, comments?:[text]}].
    labels = [(label_id, label_name, color?)]. Adds the persona as a board editor and seeds a
    board-membership row so membership-guarded read/write tools pass for the persona."""
    ss = _ss(W, "planka")
    ss.setdefault("Project", []).append({"id": project_id, "name": f"Project {project_id}", "description": description, "background_type": "gradient", "background_gradient": "electric"})
    ss.setdefault("Board", []).append({"id": board_id, "project_id": project_id, "name": name, "position": 1, "default_view": "kanban", "default_card_type": "project"})
    ss.setdefault("BoardMembership", []).append({"id": board_id * 100, "project_id": project_id, "board_id": board_id, "user_id": 1, "role": "editor", "can_comment": True})
    for lid, lname in lists:
        ss.setdefault("List", []).append({"id": lid, "board_id": board_id, "type": "active", "position": len([l for l in ss.get("List", []) if l.get("board_id") == board_id]) + 1, "name": lname})
    for lid, lname, *rest in labels:
        color = rest[0] if rest else "#607d8b"
        ss.setdefault("Label", []).append({"id": lid, "board_id": board_id, "position": len(ss.get("Label", [])) + 1, "name": lname, "color": color})
    for c in cards:
        ss.setdefault("Card", []).append({"id": c["id"], "board_id": board_id, "list_id": c["list"], "creator_user_id": 1, "type": c.get("type", "project"),
                                          "position": c.get("position", len(ss.get("Card", [])) + 1), "name": c["name"], "description": c.get("description"),
                                          "due_date": c.get("due_date"), "is_due_completed": c.get("is_due_completed", False), "is_closed": False})
        for u in c.get("assignees", []): ss.setdefault("CardMembership", []).append({"id": len(ss.get("CardMembership", [])) + 1, "card_id": c["id"], "user_id": u})
        for l in c.get("labels", []): ss.setdefault("CardLabel", []).append({"id": len(ss.get("CardLabel", [])) + 1, "card_id": c["id"], "label_id": l})
        for com in c.get("comments", []): ss.setdefault("Comment", []).append({"id": len(ss.get("Comment", [])) + 1, "card_id": c["id"], "user_id": 1, "text": com})
        if c.get("checklist"):
            tlid, tlname, tasks = c["checklist"]
            ss.setdefault("TaskList", []).append({"id": tlid, "card_id": c["id"], "position": 1, "name": tlname, "show_on_front_of_card": True, "hide_completed_tasks": False})
            for tid, tname, done in tasks:
                ss.setdefault("Task", []).append({"id": tid, "task_list_id": tlid, "position": len(ss.get("Task", [])) + 1, "name": tname, "is_completed": bool(done)})
        if c.get("custom"):
            gid, fid, content = c["custom"]
            ss.setdefault("CustomFieldGroup", []).append({"id": gid, "board_id": board_id, "position": 1, "name": "Estimate"})
            ss.setdefault("CustomField", []).append({"id": fid, "custom_field_group_id": gid, "position": 1, "name": "Points", "show_on_front_of_card": True})
            ss.setdefault("CustomFieldValue", []).append({"id": len(ss.get("CustomFieldValue", [])) + 1, "card_id": c["id"], "custom_field_group_id": gid, "custom_field_id": fid, "content": content})
    _bind(W, "planka", f"Card({board_id})", src, len(cards))

def comments(W, card_id, texts, src=None):
    for t in texts: _ss(W, "planka").setdefault("Comment", []).append({"id": len(_ss(W, "planka").get("Comment", [])) + 1, "card_id": card_id, "user_id": 1, "text": t})
    _bind(W, "planka", f"Comment({card_id})", src, len(texts))

# ───────── smoke_seed for the acceptance smoke (see onboard_check.py) ─────────
def smoke_seed(W):
    """seed >= 3 content rows + one policy text in a carrier field; return gold write steps and
    >= 3 contract predicates (incl. one negative), built with packlib SEL/F/AND/CNT on planka's entities."""
    # One project with one board, three lists, cards spanning them; a policy note in a card description.
    kanban_board(W, 1, 1, "Ops Board",
                 lists=[(10, "Backlog"), (11, "In progress"), (12, "Done")],
                 labels=[(50, "P0", "#ef5350"), (51, "P2", "#42a5f5")],
                 cards=[
                     {"id": 100, "list": 10, "name": "Onboard new vendor", "type": "task",
                      "assignees": [1], "labels": [50],
                      "description": "Policy: every new vendor must be onboarded through the risk gate. Priority P0."},
                     {"id": 101, "list": 11, "name": "Roster approval", "type": "task", "assignees": [1], "labels": [51]},
                     {"id": 102, "list": 11, "name": "License renewal", "type": "project",
                      "checklist": (70, "Steps", [(700, "Confirm renewal", True), (701, "Pay invoice", False)])},
                     {"id": 103, "list": 10, "name": "Design review (look-alike)", "type": "project", "labels": [51]},
                 ], src=None)
    steps = [
        ("planka", "create_card", {"listId": 10, "name": "Risk gate review", "type": "task"}),
        ("planka", "create_comment", {"cardId": 100, "text": "priority confirmed"}),
        ("planka", "update_card", {"id": 102, "listId": 12}),
    ]
    preds = [
        ("c1", "a card with the gold-written name exists", CNT(SEL(NS("planka", "Card"), F("name", "eq", "Risk gate review"))), False),
        ("c2", "a comment with the gold text was added to card 100", CNT(SEL(NS("planka", "Comment"), AND(F("card_id", "eq", 100), F("text", "eq", "priority confirmed")))), False),
        ("c3", "card 102 was moved to the Done list (id 12)", CNT(SEL(NS("planka", "Card"), AND(F("id", "eq", 102), F("list_id", "eq", 12)))), False),
        ("c4", "no card has the forbidden title (negative)", CNT(SEL(NS("planka", "Card"), F("name", "eq", "Never create this")), "eq", 0), True),
    ]
    return steps, preds

__all__ = ["NEW_SERVER", "add_users", "kanban_board", "comments", "smoke_seed"]
