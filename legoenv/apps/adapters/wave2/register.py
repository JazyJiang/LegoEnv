"""register.py (newspecs2) — the last 45 long-tail tasks: two new specs + three stand-ins. Does NOT edit packlib.py (other forks import it live).

    import sys; sys.path.insert(0, "/builder/smoke/pack")
    from packlib import *
    from newspecs.register import *        # the seven wave-1 long-tail specs (jira/notion/monday/drive… in the same tasks)
    from newspecs2.register import *       # misskey (linkedin), chatwoot (twilio) + stand-ins for buffer / google_ads / canva

Workspace role -> local adapter used by a pack
  linkedin    -> misskey (NEW spec, base pack/base_specs/misskey.spec.json). profile = user (description = headline + summary, fields = Title/Company/Email/…,
                 url = profile URL); 1st-degree connection = follow (Following followerId=1); invitation = follow_create(userId) (+ chat message for the note);
                 message/InMail = chatmessage_create_to_user(toUserId, text) -> ChatMessage(fromUserId=1, toUserId, text); personal post = note_create(text);
                 company page = Channel, company update = note_create(text, channelId); job opening = a Note on the company's channel.
  twilio      -> chatwoot (NEW spec, base pack/base_specs/chatwoot.spec.json). our SMS line = Inbox 1 (Channel::TwilioSms); a number = a Contact(phone_number);
                 SMS to a new number = contact_create + conversation_create(inbox_id=1, contact_id, message) (the first message is side-inserted);
                 SMS in an existing thread = message_create(conversation_id, content). Voice calls: none — reshape "call X" into "text X" or cut it.
  buffer      -> mastodon (wave-1 spec) + `mastodon_scheduled(spec)` below: channels = accounts you manage (Organization accounts seeded using W.seed),
                 add to queue = scheduledstatus_create(account_id, status, scheduled_at) -> ScheduledStatus(text, scheduled_at, account_id);
                 the queue = scheduledstatus_index(account_id). Base mastodon has scheduledstatus_update/destroy/index but NO create — hence the patch
                 (also written to newspecs2/mastodon_scheduled_patch.json for fork `fold` to put into base_specs/mastodon).
  google_ads  -> budibase "ad console" workbook (`ad_console` below): sheet Campaigns (Campaign ID, Campaign, Status, Daily Budget, Impressions, Clicks, CTR,
                 Conversions, Cost) — pausing/enabling = editing Status with flat_row_patch; sheet Audience Lists (List, Email, Added) — adding an email
                 to a customer list = appending a row; sheet Offline Conversions — sending a conversion = appending a row.
  canva       -> cloudreve drive (wave-1 spec, `newspecs.register.drive_tree`): a Designs folder with one file per design (content = design brief: size,
                 template, text), an Exports folder; "create a design" = file_create in Designs, "export" = file_copy / file_create "<design>.pdf" in Exports.

Worked stand-in snippets
    # google_ads -> ad console
    W = World(["budibase", "stalwart"], persona=("paid.media@acme.example", "Paid Media"), now="2026-03-02T09:00:00")
    COLS = ad_console(W, campaigns=[{"Campaign ID": "C-1042", "Campaign": "Spring Sale — Search", "Status": "Enabled", "Daily Budget": "120.00",
                                    "Impressions": "18400", "Clicks": "212", "CTR": "1.15%", "Conversions": "9", "Cost": "388.20"}],
                      audiences=[{"List": "High intent — trials", "Email": "ana@example.org", "Added": "2026-02-20"}], src="datapool:<slug>")
    spec = W.merge(); spec = flat_row_patch(spec, ["Status"])  # only the edited column: names with spaces are invalid tool args       # Status edits land in the flat cell the agent reads back
    # predicate: row_in("ws_campaigns", **{"Campaign ID": "C-1042", "Status": "Paused"})
    # canva -> drive
    from newspecs.register import drive_tree
    drive_tree(W, folders=[(10, "Designs", None), (11, "Exports", None)],
               files=[{"id": 101, "name": "Spring Sale — IG post.design", "parent": 10, "content": "Canva design · 1080x1080 · template: Bold Sale · headline: 30% off"}], src="…")
    # predicate: CNT(SEL(NS("cloudreve","File"), AND(F("file_children","eq",11), F("name","icontains","Spring Sale"))))
"""
import json, copy
import packlib   # puts LegoEnv/runtime on sys.path
import runtime
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP

NEW_SERVER = {"misskey": "linkedin", "chatwoot": "sms"}
NEW_CONTENT = {"misskey": ["Note", "ChatMessage", "Following", "FollowRequest", "Channel", "ChannelFollowing", "UserList", "UserListMembership", "NoteReaction", "Clip", "ClipNote", "Page", "DriveFile", "DriveFolder"],
               "chatwoot": ["Contact", "ContactInbox", "Conversation", "Message", "Label", "Tagging", "Note", "Campaign", "CannedResponse"]}
NEW_NOTES = {
    "misskey": "{p}__ is the professional network (LinkedIn-style; a Misskey server): sign in with {p}__sign_in(email, password); you are user 1. user_searchusers(query) / user_showuser(userId) read profiles (description = headline + summary, fields = Title/Company/Email/Location, url = profile URL); user_following(userId=1) = your connections; follow_create(userId) sends a connection invitation; chatmessage_create_to_user(toUserId, text) sends a message; chatmessage_read_user(userId) reads a thread; note_create(text[, channelId]) publishes a post (with channelId: an update on that company page); channel_search(query) finds company pages; note_timeline / note_search / channel_timeline read posts.",
    "chatwoot": "{p}__ is the SMS / messaging inbox (Twilio-style, a Chatwoot workspace): sign in with {p}__sign_in(email, password). inbox_list shows the lines (inbox 1 = SMS); contact_search(q) finds a contact by name or phone (E.164, +15551234567); to text a new number: contact_create(name, phone_number) then conversation_create(inbox_id=1, contact_id, message) — that sends the first SMS; in an existing thread (conversation_list(contact_id)) use message_create(conversation_id, content); message_list(conversation_id) shows the history. There are no voice calls.",
}
LOGIN2 = {"misskey": ("sign_in", "email"), "chatwoot": ("sign_in", "email")}
for _a in NEW_SERVER:
    SERVER.setdefault(_a, NEW_SERVER[_a]); PFX.setdefault(_a, _a); CONTENT.setdefault(_a, NEW_CONTENT[_a]); NOTES.setdefault(_a, NEW_NOTES[_a])
packlib.LOGIN.update(LOGIN2)
# wave-1 long-tail logins (newspecs/register.py does not add them; simulate()/login() need them) — additive, same values as newspecs.register.LOGIN
for _a, _v in {"vikunja": ("sign_in", "username"), "mantisbt": ("sign_in", "username"), "outline": ("sign_in", "email"), "listmonk": ("sign_in", "username"),
               "cloudreve": ("sign_in", "email"), "directus": ("sign_in", "email"), "mastodon": ("sign_in", "email")}.items():
    packlib.LOGIN.setdefault(_a, _v)

# ───────── whole-list reads the agent will make on the new apps (12k observation cap) ─────────
_orig_obs2 = World.obs_report
def _obs_report2(self):
    rep, bad = _orig_obs2(self)
    new = [a for a in self.apps if a in NEW_SERVER or a == "mastodon"]
    if not new: return rep, bad
    env = runtime.Env(self.world)
    def rd(app, tool, args):
        return len(json.dumps(env.call(NS(app, tool), args), ensure_ascii=False, default=str))
    for app in new:
        if app == "mastodon":
            if any(t["tool"] == NS("mastodon", "scheduledstatus_create") for t in self.world["tools"]):
                env.call(NS("mastodon", "sign_in"), {"email": self.persona, "password": self.password}); rep["mastodon scheduledstatus_index"] = rd(app, "scheduledstatus_index", {})
            continue
        t, col = LOGIN2[app]; env.call(NS(app, t), {col: self.persona, "password": self.password})
        st = lambda e: env.state.get(NS(app, e), [])
        if app == "misskey":
            rep["misskey user_listusers"] = rd(app, "user_listusers", {}); rep["misskey note_timeline"] = rd(app, "note_timeline", {})
            rep["misskey channel_search"] = rd(app, "channel_search", {}); rep["misskey chatmessage_history"] = rd(app, "chatmessage_history", {})
        elif app == "chatwoot":
            rep["chatwoot contact_search"] = rd(app, "contact_search", {}); rep["chatwoot conversation_list"] = rd(app, "conversation_list", {})
            for v in st("Conversation"): rep[f"chatwoot message_list {v['id']}"] = rd(app, "message_list", {"conversation_id": v["id"]})
    bad = {k: v for k, v in rep.items() if v > OBS_CAP}
    return rep, bad
World.obs_report = _obs_report2

# ───────── seeding helpers (World clears the content tables first, so every helper setdefaults its table) ─────────
TS = "2026-01-01T00:00:00"
def _ss(W, app): return W.spec[app]["seed_state"]
def _bind(W, app, ent, src, n):
    if src: W.bindings[NS(app, ent)] = {"dataset": src, "rows": n}
def _slug(x):
    import re
    return re.sub(r"[^a-z0-9_]+", "_", str(x or "").lower()).strip("_")[:40] or "user"

# misskey (linkedin)
def people(W, rows, src=None):
    """misskey users besides the persona (id 1). rows = [{id (int ≥ 2), name, headline?|title?+company?, summary?, location?, email?, url?, username?, fields?: {k: v}, followers?}]"""
    ss = _ss(W, "misskey")
    for r in rows:
        head = r.get("headline") or (f"{r['title']} at {r['company']}" if r.get("title") and r.get("company") else (r.get("title") or r.get("company") or ""))
        fields = [{"name": n, "value": str(v)} for n, v in (("Title", r.get("title")), ("Company", r.get("company")), ("Location", r.get("location")), ("Email", r.get("email"))) if v]
        fields += [{"name": k, "value": str(v)} for k, v in (r.get("fields") or {}).items()]
        un = r.get("username") or (_slug(r["url"].rstrip("/").rsplit("/", 1)[-1]) if r.get("url") else _slug(r["name"]))
        ss.setdefault("User", []).append({"id": r["id"], "username": un, "usernameLower": un.lower(), "name": r["name"], "description": head + (f"\n{r['summary']}" if r.get("summary") else ""), "fields": fields,
                                          "url": r.get("url"), "location": r.get("location"), "followersCount": int(r.get("followers") or 0), "followingCount": 0, "notesCount": 0, "isSuspended": False,
                                          "isLocked": False, "isBot": bool(r.get("bot")), "createdAt": TS, "updatedAt": TS})
    _bind(W, "misskey", "User", src, len(rows))
def connections(W, user_ids):
    """1st-degree connections of the persona: Following(followerId=1, followeeId=u)"""
    ss = _ss(W, "misskey")
    for u in user_ids: ss.setdefault("Following", []).append({"id": len(ss.setdefault("Following", [])) + 1, "followerId": 1, "followeeId": u, "isFollowerHibernated": False, "withReplies": False, "createdAt": TS})
def company_pages(W, rows, src=None):
    """rows = [{id (channel id, int), name, description?, admin? (True = the persona administers it)}]"""
    ss = _ss(W, "misskey")
    for r in rows:
        ss.setdefault("Channel", []).append({"id": r["id"], "userId": 1 if r.get("admin") else r.get("owner_user", 1), "name": r["name"], "description": r.get("description") or "", "notesCount": 0, "usersCount": 0,
                                             "isArchived": False, "isSensitive": False, "allowRenoteToExternal": True, "pinnedNoteIds": [], "createdAt": TS})
    _bind(W, "misskey", "Channel", src, len(rows))
def li_posts(W, rows, src=None):
    """rows = [{id, userId, text, channelId?, at?, likes?, replies?}]"""
    ss = _ss(W, "misskey")
    for r in rows:
        ss.setdefault("Note", []).append({"id": r["id"], "userId": r["userId"], "channelId": r.get("channelId"), "text": r["text"], "visibility": "public", "localOnly": False, "renoteCount": 0, "repliesCount": int(r.get("replies") or 0),
                                          "clippedCount": 0, "pageCount": 0, "reactions": {"like": int(r.get("likes") or 0)}, "fileIds": [], "attachedFileTypes": [], "visibleUserIds": [], "mentions": [], "emojis": [], "tags": [],
                                          "hasPoll": False, "createdAt": r.get("at", TS)})
    _bind(W, "misskey", "Note", src, len(rows))
def dms(W, rows):
    """rows = [{fromUserId, toUserId, text, at?}] — existing message history"""
    ss = _ss(W, "misskey")
    for r in rows: ss.setdefault("ChatMessage", []).append({"id": len(ss.setdefault("ChatMessage", [])) + 1, "fromUserId": r["fromUserId"], "toUserId": r["toUserId"], "text": r["text"], "reads": [], "createdAt": r.get("at", TS)})
def pending_invites(W, rows):
    """rows = [(followerId, followeeId)] — connection requests not yet accepted"""
    ss = _ss(W, "misskey")
    for a, b in rows: ss.setdefault("FollowRequest", []).append({"id": len(ss.setdefault("FollowRequest", [])) + 1, "followerId": a, "followeeId": b, "requestId": f"rq{a}-{b}", "withReplies": False, "createdAt": TS})
def li_msg_to(user_id, *terms):
    """predicate helper: the persona's message to misskey user user_id containing every term"""
    from packlib import SEL, AND, F
    return SEL(NS("misskey", "ChatMessage"), AND(F("fromUserId", "eq", 1), F("toUserId", "eq", user_id), *[F("text", "icontains", t) for t in terms]))
def li_invited(user_id):
    from packlib import SEL, AND, F
    return SEL(NS("misskey", "Following"), AND(F("followerId", "eq", 1), F("followeeId", "eq", user_id)))

# chatwoot (twilio)
def sms_line(W, number, name=None):
    """set our SMS number (inbox 1 = Channel::TwilioSms)"""
    ss = _ss(W, "chatwoot")
    for c in ss.get("ChannelTwilioSms", []): c["phone_number"] = number
    for i in ss.get("Inbox", []):
        if i["id"] == 1: i["name"] = name or f"SMS {number}"
def sms_contacts(W, rows, src=None):
    """rows = [{id (int), name, phone_number (E.164), email?}]"""
    ss = _ss(W, "chatwoot")
    for r in rows: ss.setdefault("Contact", []).append({"id": r["id"], "account_id": 1, "name": r["name"], "phone_number": r["phone_number"], "email": r.get("email"), "blocked": False, "created_at": TS, "updated_at": TS})
    _bind(W, "chatwoot", "Contact", src, len(rows))
def sms_history(W, rows, src=None):
    """rows = [{contact_id, text, direction: 'in'|'out', at?}] -> one conversation per contact in inbox 1, messages in order"""
    ss = _ss(W, "chatwoot"); conv = {v["contact_id"]: v["id"] for v in ss.get("Conversation", [])}
    for r in rows:
        if r["contact_id"] not in conv:
            vid = len(ss.setdefault("Conversation", [])) + 1; conv[r["contact_id"]] = vid
            ss["Conversation"].append({"id": vid, "uuid": vid, "account_id": 1, "inbox_id": 1, "contact_id": r["contact_id"], "status": "open", "display_id": 1000 + vid, "created_at": r.get("at", TS), "updated_at": r.get("at", TS), "last_activity_at": r.get("at", TS)})
        out = r.get("direction", "out") == "out"
        ss.setdefault("Message", []).append({"id": len(ss.setdefault("Message", [])) + 1, "account_id": 1, "inbox_id": 1, "conversation_id": conv[r["contact_id"]], "message_type": "outgoing" if out else "incoming",
                                             "content": r["text"], "content_type": "text", "status": "delivered", "sender_type": "User" if out else "Contact", "sender_id": 1 if out else r["contact_id"], "private": False, "created_at": r.get("at", TS)})
    _bind(W, "chatwoot", "Message", src, len(rows))
def sms_to(phone, *terms):
    """predicate helper: an outgoing SMS to phone (E.164) containing every term (joins Message -> Conversation -> Contact)"""
    from packlib import SEL, AND, F
    cont = SEL(NS("chatwoot", "Contact"), F("phone_number", "eq", phone), {"col": "id"})
    convs = SEL(NS("chatwoot", "Conversation"), F("contact_id", "in", cont), {"col": "id"})
    return SEL(NS("chatwoot", "Message"), AND(F("conversation_id", "in", convs), F("message_type", "eq", "outgoing"), *[F("content", "icontains", t) for t in terms]))

# google_ads -> budibase ad console
AD_CAMPAIGN_COLS = ["Campaign ID", "Campaign", "Status", "Daily Budget", "Impressions", "Clicks", "CTR", "Conversions", "Cost"]
def ad_console(W, campaigns, audiences=(), conversions=None, workspace=("ss_ads", "Ad Console"), campaign_cols=None, src=None):
    """google_ads stand-in on budibase. campaigns: rows with campaign_cols (default AD_CAMPAIGN_COLS); audiences: rows (List, Email, Added);
    conversions: None = no sheet, [] = empty "Offline Conversions" sheet (Campaign ID, Email, Value, Converted At) the agent appends to.
    Returns {"campaigns": cols, ...} — pass cols["campaigns"] to flat_row_patch(spec, …) so Status edits are visible."""
    cc = campaign_cols or AD_CAMPAIGN_COLS; out = {"campaigns": cc}
    W.sheet("ws_campaigns", "Campaigns", cc, [{c: r.get(c, "") for c in cc} for r in campaigns], workspace=workspace, src=src)
    if audiences:
        ac = ["List", "Email", "Added"]; W.sheet("ws_audiences", "Audience Lists", ac, [{c: r.get(c, "") for c in ac} for r in audiences], workspace=workspace, src=src); out["audiences"] = ac
    if conversions is not None:
        vc = ["Campaign ID", "Email", "Value", "Converted At"]; W.sheet("ws_conversions", "Offline Conversions", vc, [{c: r.get(c, "") for c in vc} for r in conversions], workspace=workspace, src=src); out["conversions"] = vc
    return out

# buffer -> mastodon scheduled statuses
SCHED_PATCH = {
    "entity_columns": {"ScheduledStatus": [["text", "text"], ["media_url", "text"], ["media_description", "text"], ["visibility", "text"], ["created_at", "datetime"]]},
    "add_tools": ["scheduledstatus_create"],
    "replace_tools": ["scheduledstatus_index", "scheduledstatus_update"],
    "why": "base mastodon can list/update/cancel ScheduledStatus but nothing creates one (status_create has no scheduled_at), and scheduledstatus_index was a single-row fetch keyed on the session; the post text lived only in the params JSON",
}
def mastodon_scheduled(spec, now=None):
    """patch a merged spec (or a base mastodon spec: pass it with its own tool names) in place: scheduledstatus_create + list/update fixes. Returns spec."""
    pre = "mastodon_ab__" if any(t["tool"].startswith("mastodon_ab__") for t in spec["tools"]) else ""
    E = {e["name"]: e for e in spec["entities"]}; ent = pre + "ScheduledStatus"
    have = {c["name"] for c in E[ent]["columns"]}
    for c, t in SCHED_PATCH["entity_columns"]["ScheduledStatus"]:
        if c not in have: E[ent]["columns"].append({"name": c, "type": t, "nullable": True})
    now = now or spec.get("now") or TS
    spec["tools"] = [t for t in spec["tools"] if t["tool"] not in (pre + "scheduledstatus_create", pre + "scheduledstatus_index", pre + "scheduledstatus_update")]
    acct = pre + "Account"
    spec["tools"] += [
        {"tool": pre + "scheduledstatus_create", "op": "create", "family": "crud.insert", "entity": ent,
         "exec_spec": {"entity": ent, "fields": {"account_id": {"$arg": "account_id"}, "text": {"$arg": "status"}, "scheduled_at": {"$arg": "scheduled_at"}, "media_url": {"$arg": "media_url"},
                                                 "media_description": {"$arg": "media_description"}, "visibility": {"$arg": "visibility"}}, "set_on_create": {"params": {}, "created_at": now}},
         "input_schema": {"account_id": {"type": "id", "required": True, "description": "The channel = the account to post as (1 = your own account; managed pages via account_search)."},
                          "status": {"type": "text", "required": True, "description": "Post text."}, "scheduled_at": {"type": "datetime", "required": True, "description": "When to publish (ISO 8601)."},
                          "media_url": {"type": "text", "description": "Image/video URL (optional)."}, "media_description": {"type": "text", "description": "Alt text (optional)."}, "visibility": {"type": "text", "description": "public | unlisted (optional)."}},
         "guards": {"requires_auth": True, "required": ["account_id", "status", "scheduled_at"],
                    "preconditions": [[{"node": "count", "select": {"node": "select", "entity": acct, "where": {"node": "field", "col": "id", "op": "eq", "value": {"arg": "account_id"}}}, "op": "gte", "n": 1}]],
                    "messages": {"auth": "Sign in first.", "precondition": "That account (channel) does not exist."}},
         "description": "Queue a post for later (a scheduled status) on a channel = an account you post as. It is published at scheduled_at."},
        {"tool": pre + "scheduledstatus_index", "op": "search", "family": "search", "entity": ent,
         "exec_spec": {"entity": ent, "filter": {"col": "account_id", "mode": "exact", "val": {"$arg": "account_id"}, "optional": True}, "rank": {"method": "exact"}, "sort": [{"col": "scheduled_at", "dir": "asc"}]},
         "input_schema": {"account_id": {"type": "id", "description": "Channel account id (optional: omit for every queue)."}}, "guards": {"requires_auth": True, "messages": {"auth": "Sign in first."}},
         "description": "The queue: scheduled posts (id, account_id, text, scheduled_at, media_url), soonest first."},
        {"tool": pre + "scheduledstatus_update", "op": "update", "family": "update.field_set", "entity": ent,
         "exec_spec": {"entity": ent, "row_key": {"id": {"$arg": "id"}}, "fields": {"scheduled_at": {"$arg": "scheduled_at"}, "text": {"$arg": "status"}}, "set": {"scheduled_at": {"$arg": "scheduled_at"}, "text": {"$arg": "status"}}},
         "input_schema": {"id": {"type": "id", "required": True, "description": "Scheduled post id."}, "scheduled_at": {"type": "datetime", "description": "New time (optional)."}, "status": {"type": "text", "description": "New text (optional)."}},
         "guards": {"requires_auth": True, "required": ["id"], "messages": {"auth": "Sign in first.", "not_found": "No such scheduled post."}},
         "description": "Reschedule or edit a queued post."},
    ]
    return spec
def queued(W, rows, src=None):
    """existing queue: rows = [{id, account_id, text, scheduled_at, media_url?}] (call after the spec is patched or before merge — columns are added by mastodon_scheduled)"""
    for r in rows: _ss(W, "mastodon").setdefault("ScheduledStatus", []).append({"id": r["id"], "account_id": r["account_id"], "text": r["text"], "scheduled_at": r["scheduled_at"], "media_url": r.get("media_url"), "params": {}, "created_at": TS})
    _bind(W, "mastodon", "ScheduledStatus", src, len(rows))
