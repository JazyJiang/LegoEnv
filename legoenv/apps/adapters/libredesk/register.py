"""register.py — attach libredesk (the self-hosted Go helpdesk) to packlib WITHOUT editing packlib.py.

    import sys; sys.path.insert(0, "/builder/smoke/pack")
    from packlib import *
    from newspecs3.libredesk.register import *    # adds libredesk to SERVER/PFX/CONTENT/NOTES/LOGIN + the obs hook + seed helpers
    W = World(["libredesk"], persona=("dana.ops@acme.example", "Dana Ops"), now="2026-09-24T09:00:00")
    smoke_seed(W)                                  # (or use the helpers below) seeds conversations/messages/notes
    spec = W.merge(); rep, bad = W.obs_report(); assert not bad

Base: pack/base_specs/libredesk.spec.json. The app stands in for Zendesk/Freshdesk/Intercom. Content entities
(Conversation/ConversationMessage/ContactNote/HelpArticle/CSATResponse) are emptied by World like the other bases —
re-seed them with the helpers below or W.seed(app, entity, rows).
"""
import json, runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

PY = "libredesk"
SERVER.setdefault(PY, "helpdesk")
PFX.setdefault(PY, PY)
CONTENT.setdefault(PY, ["Conversation", "ConversationMessage", "ContactNote", "HelpArticle", "CSATResponse"])
NOTES.setdefault(PY,
    "{p}__ is the customer-support helpdesk (Zendesk-like): sign in with {p}__user_login(email, password). "
    "conversation_list_all(q) lists every conversation (subject substring), conversation_get(uuid) reads one, "
    "conversation_get_messages(uuid) reads its message thread; contact_list(q) and contact_get(id) list/read contacts. "
    "To work a conversation: conversation_send_message(cuuid, content, private) replies (or leaves a private agent note), "
    "conversation_update_status(uuid, status) moves it (Open/Waiting/Resolved), conversation_update_user_assignee(uuid, "
    "assignee_id) and conversation_unassign_user(uuid) manage assignment, conversation_update_priority(uuid, priority_id) "
    "sets priority (1 Low/2 Medium/3 High). contactnote_list(id) and contactnote_create(id, note) hold internal contact "
    "notes; collection_* / article_* manage the help-center knowledge base; csat_show / csat_submit read and answer CSAT "
    "ratings.")
packlib.LOGIN[PY] = ("user_login", "email")

# ───────── whole-list reads the agent makes on libredesk (12k observation cap) ─────────
_orig_obs = World.obs_report
def _obs_report(self):
    rep, bad = _orig_obs(self)
    if PY not in self.apps:
        return rep, bad
    env = runtime.Env(self.world)
    env.call(NS(PY, "user_login"), {"email": self.persona, "password": self.password})
    def rd(tool, args):
        return len(json.dumps(env.call(NS(PY, tool), args), ensure_ascii=False, default=str))
    rep["libredesk conversation_list_all"] = rd("conversation_list_all", {})
    rep["libredesk contact_list"] = rd("contact_list", {})
    bad = {k: v for k, v in rep.items() if v > OBS_CAP}
    return rep, bad
World.obs_report = _obs_report

# ───────── seeding helpers (rows are plain dicts; ids are integers) ─────────
def _ss(W):
    return W.spec[PY]["seed_state"]

def add_contacts(W, rows):
    """extra contact/visitor rows besides the persona agent (id 1). rows = [{id, email, first_name, last_name, ...}].
    Passwords default to pw-<id>."""
    me = _ss(W)["User"][0]
    for r in rows:
        row = {k: v for k, v in me.items() if k not in ("id",)}
        row.update(r)
        row.setdefault("password", f"pw-{r['id']}")
        row.setdefault("type", "contact")
        row.setdefault("enabled", True)
        row.setdefault("availability_status", "offline")
        row.setdefault("custom_attributes", {})
        _ss(W)["User"].append(row)

def conversations(W, convs=(), msgs=(), notes=(), src=None):
    """helpdesk content: convs = [{id, uuid, contact_id, subject, inbox_id?, status_id?, priority_id?, assigned_user_id?}];
    msgs = [{id, conversation_id, sender_id, sender_type?, content}]; notes = [{contact_id, user_id?, note}].
    Opens an empty Conversation/ConversationMessage/ContactNote set (those are content entities, emptied by World)."""
    ss = _ss(W)
    ss["Conversation"] = []
    ss["ConversationMessage"] = []
    ss["ContactNote"] = []
    open_id = next(s["id"] for s in ss.get("ConversationStatus", []) if s["name"] == "Open")
    for c in convs:
        ss["Conversation"].append({
            "id": c["id"], "uuid": c["uuid"], "reference_number": str(c["id"]), "contact_id": c["contact_id"],
            "inbox_id": c.get("inbox_id", 1), "status_id": c.get("status_id", open_id), "priority_id": c.get("priority_id"),
            "assigned_user_id": c.get("assigned_user_id"), "assigned_team_id": c.get("assigned_team_id"),
            "meta": {}, "custom_attributes": {}, "subject": c["subject"]})
    for m in msgs:
        ss["ConversationMessage"].append({
            "id": m["id"], "uuid": f"msg-{m['id']}", "type": m.get("type", "incoming"), "status": m.get("status", "received"),
            "private": m.get("private", False), "conversation_id": m["conversation_id"], "sender_id": m["sender_id"],
            "sender_type": m.get("sender_type", "contact"), "content_type": "text", "content": m["content"], "meta": {}})
    for i, n in enumerate(notes, 1):
        ss["ContactNote"].append({"id": i, "contact_id": n["contact_id"], "user_id": n.get("user_id", 1), "note": n["note"]})
    if src:
        W.bindings[NS(PY, "ConversationMessage")] = {"dataset": src, "rows": len(msgs)}

def smoke_seed(W):
    """seed >= 3 realistic content rows + one policy note in a carrier (ContactNote.note); returns gold steps
    [(app, tool, args), ...] performing one write, and >= 3 contract predicates [(id, semantic, pred, negative)] incl. one negative."""
    add_contacts(W, [
        {"id": 30, "email": "carol@example.com", "first_name": "Carol", "last_name": "Wu"},
        {"id": 31, "email": "diego@example.com", "first_name": "Diego", "last_name": "Cruz"},
    ])
    conversations(W,
        convs=[
            {"id": 1, "uuid": "conv-1", "contact_id": 3,  "subject": "Billing question",    "priority_id": 2, "status_id": 1, "assigned_user_id": 2},
            {"id": 2, "uuid": "conv-2", "contact_id": 30, "subject": "API access request",  "priority_id": 2, "status_id": 1},
            {"id": 3, "uuid": "conv-3", "contact_id": 31, "subject": "Order delay",          "priority_id": 3, "status_id": 1},
        ],
        msgs=[
            {"id": 1, "conversation_id": 1, "sender_id": 3,  "content": "Hi, I need help with my bill"},
            {"id": 2, "conversation_id": 1, "sender_id": 2,  "sender_type": "agent",   "content": "Sure, I can help"},
            {"id": 3, "conversation_id": 2, "sender_id": 30, "content": "Can I get a developer API key?"},
            {"id": 4, "conversation_id": 3, "sender_id": 31, "content": "Where is my order, it is late"},
        ],
        notes=[
            {"contact_id": 3, "user_id": 1, "note": "Company policy: refunds are processed within 30 days of the request."},
        ])
    steps = [
        ("libredesk", "conversation_send_message", {"cuuid": "conv-1", "content": "refund approved, processing now"}),
        ("libredesk", "contactnote_create", {"id": 3, "note": "Liaison: escalate to billing supervisor"}),
    ]
    conv_msg = NS(PY, "ConversationMessage")
    contact_note = NS(PY, "ContactNote")
    preds = [
        ("agent_replied", "an agent reply confirming the refund exists in conv-1",
         CNT(SEL(conv_msg, AND(F("conversation_id", "eq", 1), F("content", "icontains", "refund"))), "gte", 1), False),
        ("note_added", "an internal contact note about the billing supervisor exists for contact 3",
         CNT(SEL(contact_note, AND(F("contact_id", "eq", 3), F("note", "icontains", "billing supervisor"))), "gte", 1), False),
        ("no_escalation", "no message mentions escalating anywhere",
         CNT(SEL(conv_msg, F("content", "icontains", "manager escalation")), "eq", 0), True),
    ]
    return steps, preds

__all__ = ["add_contacts", "conversations", "smoke_seed", "SERVER", "PFX", "CONTENT", "NOTES"]
