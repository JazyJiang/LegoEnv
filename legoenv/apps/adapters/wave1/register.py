"""Register local task, issue, wiki, list, drive, table and social metadata adapters.
Read capability cards and helper interfaces before seeding. Upstream provenance remains in the release attribution ledger.
"""
import json, runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP

NEW_SERVER = {"vikunja": "tasks", "mantisbt": "tracker", "outline": "wiki", "listmonk": "lists", "cloudreve": "drive", "directus": "tables", "mastodon": "social"}
NEW_CONTENT = {
    "vikunja": ["Project", "ProjectView", "Bucket", "TaskBucket", "Task", "TaskAssginee", "TaskComment", "Label", "LabelTask", "Team", "TeamMember", "TimeEntry"],
    "mantisbt": ["Project", "Category", "Bug", "BugText", "Bugnote", "BugnoteText", "BugTag", "Tag", "BugMonitor", "BugRelationship", "ProjectVersion"],
    "outline": ["Collection", "Document", "Revision", "Comment", "Star", "Pin", "Share", "UserMembership", "Group", "GroupUser", "GroupMembership"],
    "listmonk": ["Lists", "Subscribers", "SubscriberLists", "SubscriberTag", "Campaigns", "CampaignLists", "Templates", "Bounces"],
    "cloudreve": ["File", "Entity", "Metadata", "Share", "DirectLink"],
    "directus": ["Collection", "Field", "Item", "Comment", "Activity", "Revision"],
    "mastodon": ["Status", "Favourite", "Follow", "Bookmark", "StatusPin", "MediaAttachment", "List", "ListAccount", "Tag", "StatusTag", "Notification", "Mention", "Poll", "PollVote"],
}
NEW_NOTES = {
    "vikunja": "{p}__ is the task board (projects / boards): sign in with {p}__sign_in(username, password). project_list, task_list(project, q, done), task_read(id), task_create(project, title, description, due_date, priority, percent_done), task_update(id, ...), bucket_list(project) = board columns / sections, task_move_to_bucket(task_id, bucket, view=<bucket's project_view_id>), taskbucket_list(bucket), label_list / label_create(title) / task_add_label(task, label_id), taskcomment_create(task, comment), user_search(q) + taskassignee_assign(task, user_id). task_delete is a soft delete (sets deleted_at; the card still shows in task_list).",
    "mantisbt": "{p}__ is the issue tracker: sign in with {p}__sign_in(username, password). project_search(q), bug_search(project_id, q, status, handler), bug_read(id), bug_add(project, summary, description, issue_type, category, handler, priority, severity, due_date), bug_update(id, status, handler, priority, ...), bugnote_add(id, text), bugnote_list(bug_id), category_list(project_id), user_list(q). Codes: priority 10 none/20 low/30 normal/40 high/50 urgent/60 immediate; status 10 new/20 feedback/30 acknowledged/40 confirmed/50 assigned/80 resolved/90 closed.",
    "outline": "{p}__ is the wiki: sign in with {p}__sign_in(email, password). collection_list(q), document_list(collectionId, parentDocumentId, q), document_search(query), document_info(id), document_create(title, text, collectionId, parentDocumentId), document_update(id, title, text), comment_create(documentId, text).",
    "listmonk": "{p}__ is the mailing-list manager: sign in with {p}__sign_in(username, password). lists_search(query), subscribers_search(search), subscription_list(list_id, subscriber_id, status), subscribers_create(email, name, attribs), subscription_set(subscriber_id, list_id, status: confirmed | unconfirmed | unsubscribed | archived), subscriber_tag_add / subscriber_tag_remove(subscriber_id, tag), subscriber_tag_list.",
    "cloudreve": "{p}__ is the file drive: sign in with {p}__sign_in(email, password). file_list(parent_id, q, type: 1 folder / 2 file) — a row's file_children is its PARENT folder id; file_search_fts(query) over names and text; file_get_info(file_id) incl. content; file_move(id, dst), file_rename(id, new_name), file_create_folder(name, parent_id), file_create(name, content, parent_id).",
    "directus": "{p}__ is the table store (bases of tables): sign in with {p}__sign_in(email, password). list_collections, list_items(collection) returns every record (fields in `data`), get_item(pk), create_item(collection, data={{field: value}}), update_item(key, data = the complete new object — fields you omit are dropped, so pass every field you keep), delete_item(key), create_comment(collection, item, comment).",
    "mastodon": "{p}__ is the social network: sign in with {p}__sign_in(email, password). account_search(q), account_lookup(acct), account_statuses(account_id), timeline_home, status_search(q, account_id), status_show(id), status_replies(status_id), status_create(status, in_reply_to_id, media_url, media_description), status_favourite(status_id), status_reblog(status_id), follow_create(target_id), follow_list(account_id).",
}
LOGIN = {"vikunja": ("sign_in", "username"), "mantisbt": ("sign_in", "username"), "outline": ("sign_in", "email"), "listmonk": ("sign_in", "username"),
         "cloudreve": ("sign_in", "email"), "directus": ("sign_in", "email"), "mastodon": ("sign_in", "email")}
for _a in NEW_SERVER:
    SERVER.setdefault(_a, NEW_SERVER[_a]); PFX.setdefault(_a, _a); CONTENT.setdefault(_a, NEW_CONTENT[_a]); NOTES.setdefault(_a, NEW_NOTES[_a])
packlib.LOGIN.update({_a: LOGIN[_a] for _a in NEW_SERVER})   # simulate()/login() sign in to the new apps too

# ───────── whole-list reads the agent will make on the new apps (12k observation cap) ─────────
_orig_obs = World.obs_report
def _obs_report(self):
    rep, bad = _orig_obs(self)
    new = [a for a in self.apps if a in NEW_SERVER]
    if not new: return rep, bad
    env = runtime.Env(self.world)
    def rd(app, tool, args): return len(json.dumps(env.call(NS(app, tool), args), ensure_ascii=False, default=str))
    for app in new:
        t, col = LOGIN[app]; env.call(NS(app, t), {col: self.persona, "password": self.password})
        st = lambda e: env.state.get(NS(app, e), [])
        if app == "vikunja":
            for p in st("Project"): rep[f"vikunja task_list {p['id']}"] = rd(app, "task_list", {"project": p["id"]})
        elif app == "mantisbt":
            for p in st("Project"): rep[f"mantisbt bug_search {p['id']}"] = rd(app, "bug_search", {"project_id": p["id"]})
        elif app == "outline":
            for c in st("Collection"): rep[f"outline document_list {c['id']}"] = rd(app, "document_list", {"collectionId": c["id"]})
        elif app == "listmonk":
            rep["listmonk subscribers_search"] = rd(app, "subscribers_search", {}); rep["listmonk subscription_list"] = rd(app, "subscription_list", {})
        elif app == "cloudreve":
            for f in [f for f in st("File") if f.get("type") == 1] + [{"id": None}]: rep[f"cloudreve file_list {f['id']}"] = rd(app, "file_list", {"parent_id": f["id"]} if f["id"] else {})
        elif app == "directus":
            for c in st("Collection"): rep[f"directus list_items {c['collection']}"] = rd(app, "list_items", {"collection": c["collection"]})
        elif app == "mastodon":
            rep["mastodon timeline_home"] = rd(app, "timeline_home", {}); rep["mastodon account_search"] = rd(app, "account_search", {})
    bad = {k: v for k, v in rep.items() if v > OBS_CAP}
    return rep, bad
World.obs_report = _obs_report

# ───────── seeding helpers (rows are plain dicts; ids may be ints or data-derived strings) ─────────
TS = "2026-01-01T00:00:00"
def _ss(W, app): return W.spec[app]["seed_state"]
def _bind(W, app, ent, src, n):
    if src: W.bindings[NS(app, ent)] = {"dataset": src, "rows": n}
def add_users(W, app, rows):
    """colleagues besides the persona (id 1). vikunja: {id, username, name, email}; mantisbt: {id, username, realname, email}; outline: {id, email, name};
    cloudreve: {id, email, nick}; directus: {id, email, first_name, last_name}; mastodon: seed declared entities using W.seed. Passwords default to pw-<id>."""
    a = W.spec[app]["auth"]; ent = a["account_entity"]; tmpl = dict(_ss(W, app)[ent][0])
    for r in rows:
        row = {**tmpl, **{k: None for k in ("last_login", "loggedin_at")}, **r}; row.setdefault(a["password_col"], f"pw-{r['id']}")
        if app == "mantisbt": row.setdefault("cookie_string", f"ck-{r['id']}"); row["access_level"] = r.get("access_level", 55)
        if app == "outline": row["role"] = r.get("role", "member")
        if app == "directus": row["role"] = r.get("role", 2)
        _ss(W, app)[ent].append(row)
def tasks_board(W, project_id, title, buckets=(), tasks=(), description=None, src=None, view_id=None):
    """vikunja: one project with a kanban view; buckets = [(bucket_id, title)]; tasks = [{id, title, description?, due_date?, priority?, percent_done?, done?, bucket?, labels?:[label_id], assignees?:[user_id]}].
    Returns the kanban view id (an integer: next free ProjectView id unless view_id is given) — the agent passes it as task_move_to_bucket(view=…)."""
    ss = _ss(W, "vikunja")
    vid = view_id if view_id is not None else 1 + max([v["id"] for v in ss.get("ProjectView", []) if isinstance(v.get("id"), int)] or [0])
    ss.setdefault("Project", []).append({"id": project_id, "title": title, "owner_id": 1, "is_archived": False, "identifier": str(project_id)[:10], "position": len(ss.setdefault("Project", [])) + 1, "description": description, "created": TS, "updated": TS})
    ss.setdefault("ProjectView", []).append({"id": vid, "title": "Board", "project_id": project_id, "view_kind": "kanban", "bucket_configuration_mode": "manual", "position": 1, "created": TS, "updated": TS})
    for bid, bt in buckets: ss.setdefault("Bucket", []).append({"id": bid, "title": bt, "project_view_id": vid, "project_id": project_id, "limit": 0, "position": len(ss.setdefault("Bucket", [])) + 1, "created_by_id": 1, "created": TS, "updated": TS})
    for t in tasks:
        ss.setdefault("Task", []).append({"id": t["id"], "title": t["title"], "project_id": project_id, "created_by_id": t.get("created_by_id", 1), "done": bool(t.get("done")), "repeat_mode": 0, "index": len(ss.setdefault("Task", [])) + 1,
                           "priority": t.get("priority", 0), "description": t.get("description"), "due_date": t.get("due_date"), "percent_done": t.get("percent_done"), "created": t.get("created", TS), "updated": TS})
        if t.get("bucket"): ss.setdefault("TaskBucket", []).append({"task_id": t["id"], "project_view_id": vid, "bucket_id": t["bucket"]})
        for l in t.get("labels", []): ss.setdefault("LabelTask", []).append({"id": len(ss.setdefault("LabelTask", [])) + 1, "task_id": t["id"], "label_id": l, "created": TS})
        for u in t.get("assignees", []): ss.setdefault("TaskAssginee", []).append({"id": len(ss.setdefault("TaskAssginee", [])) + 1, "task_id": t["id"], "user_id": u, "created": TS})
    _bind(W, "vikunja", f"Task({project_id})", src, len(tasks))
    return vid
def labels(W, rows):
    """vikunja labels: [(id, title)]"""
    for lid, t in rows: _ss(W, "vikunja").setdefault("Label", []).append({"id": lid, "title": t, "created_by_id": 1, "created": TS, "updated": TS})
def tracker_project(W, project_id, name, key=None, categories=("General",), bugs=(), description=None, src=None):
    """mantisbt: bugs = [{id, summary, description?, issue_type?, category?(name), handler_id?, priority?, severity?, status?, due_date?, date_submitted?, notes?:[text]}]"""
    ss = _ss(W, "mantisbt")
    ss.setdefault("Project", []).append({"id": project_id, "name": name, "key": key, "description": description, "status": 10, "enabled": True, "view_state": 10, "file_path": "", "inherit_global": True})
    cat = {}
    for c in categories:
        cid = 1 + max([x["id"] for x in ss.get("Category", []) if isinstance(x.get("id"), int)] or [0]); cat[c] = cid   # integer: bug_add(category) is typed id
        ss.setdefault("Category", []).append({"id": cid, "project_id": project_id, "user_id": 1, "name": c, "status": 0})
    for b in bugs:
        ss.setdefault("Bug", []).append({"id": b["id"], "project_id": project_id, "reporter_id": b.get("reporter_id", 1), "handler_id": b.get("handler_id"), "priority": b.get("priority", 30), "severity": b.get("severity", 50),
                          "status": b.get("status", 10), "resolution": b.get("resolution", 10), "category_id": cat.get(b.get("category")), "summary": b["summary"], "description": b.get("description"),
                          "issue_type": b.get("issue_type"), "due_date": b.get("due_date"), "date_submitted": b.get("date_submitted", TS), "last_updated": b.get("date_submitted", TS), "view_state": 10})
        for n in b.get("notes", []): ss.setdefault("Bugnote", []).append({"id": len(ss.setdefault("Bugnote", [])) + 1, "bug_id": b["id"], "reporter_id": 1, "note": n, "note_type": "BUGNOTE", "view_state": 10, "date_submitted": TS})
    _bind(W, "mantisbt", f"Bug({project_id})", src, len(bugs))
def wiki_collection(W, coll_id, name, docs=(), description=None, src=None):
    """outline: docs = [{id, title, text, parent?}]"""
    ss = _ss(W, "outline")
    ss.setdefault("Collection", []).append({"id": coll_id, "urlId": str(coll_id), "name": name, "description": description, "sharing": True, "permission": "read_write", "createdById": 1, "teamId": 1, "documentStructure": [], "index": str(len(ss.setdefault("Collection", [])) + 1), "createdAt": TS, "updatedAt": TS})
    for d in docs:
        ss.setdefault("Document", []).append({"id": d["id"], "urlId": str(d["id"]), "title": d["title"], "text": d.get("text", ""), "collectionId": coll_id, "parentDocumentId": d.get("parent"), "previousTitles": [], "fullWidth": False, "template": False,
                               "isWelcome": False, "revisionCount": 1, "popularityScore": 0.0, "views": 0, "createdById": d.get("createdById", 1), "lastModifiedById": 1, "teamId": 1, "publishedAt": d.get("at", TS), "createdAt": d.get("at", TS), "updatedAt": d.get("at", TS)})
    _bind(W, "outline", f"Document({coll_id})", src, len(docs))
def mail_lists(W, lists, subscribers, src=None):
    """listmonk: lists = [(id, name)]; subscribers = [{id, email, name, attribs?, lists: {list_id: status}, tags?: [tag]}]"""
    ss = _ss(W, "listmonk")
    for lid, nm in lists: ss.setdefault("Lists", []).append({"id": lid, "uuid": f"list-{lid}", "name": nm, "type": "private", "optin": "single", "status": "active", "tags": [], "created_at": TS, "updated_at": TS})
    for s in subscribers:
        ss.setdefault("Subscribers", []).append({"id": s["id"], "uuid": f"sub-{s['id']}", "email": s["email"], "name": s.get("name") or s["email"].split("@")[0], "attribs": s.get("attribs") or {}, "status": "enabled", "created_at": TS, "updated_at": TS})
        for lid, stt in (s.get("lists") or {}).items(): ss.setdefault("SubscriberLists", []).append({"subscriber_id": s["id"], "list_id": lid, "meta": {}, "status": stt, "created_at": TS, "updated_at": TS})
        for tg in s.get("tags") or []: ss.setdefault("SubscriberTag", []).append({"id": len(ss.setdefault("SubscriberTag", [])) + 1, "subscriber_id": s["id"], "tag": tg, "created_at": TS})
    _bind(W, "listmonk", "Subscribers", src, len(subscribers))
def drive_tree(W, folders=(), files=(), src=None):
    """cloudreve: folders = [(id, name, parent_id|None)]; files = [{id, name, parent, content?, mime_type?, modified?}]"""
    ss = _ss(W, "cloudreve")
    for fid, nm, par in folders: ss.setdefault("File", []).append({"id": fid, "type": 1, "name": nm, "owner_id": 1, "size": 0, "file_children": par, "is_symbolic": False, "created_at": TS, "updated_at": TS, "mime_type": "folder"})
    for f in files:
        ss.setdefault("File", []).append({"id": f["id"], "type": 2, "name": f["name"], "owner_id": 1, "size": len(f.get("content") or ""), "file_children": f.get("parent"), "is_symbolic": False, "created_at": f.get("modified", TS),
                           "updated_at": f.get("modified", TS), "content": f.get("content"), "mime_type": f.get("mime_type", "text/plain")})
    _bind(W, "cloudreve", "File", src, len(files))
def table(W, collection, records, base=None, src=None):
    """directus: one collection (an Airtable-style table); records = [{id?, **fields}] -> Item(data=fields)"""
    ss = _ss(W, "directus")
    ss.setdefault("Collection", []).append({"collection": collection, "icon": "table", "note": f"base {base}" if base else None, "hidden": False, "singleton": False})
    for i, r in enumerate(records, 1):
        r = dict(r); rid = r.pop("id", None)
        if rid is None: rid = 1 + max([x["id"] for x in ss.get("Item", []) if isinstance(x.get("id"), int)] or [0])   # integer: item tools take key/pk typed id
        ss.setdefault("Item", []).append({"id": rid, "collection": collection, "data": r, "date_created": TS})
    _bind(W, "directus", f"Item({collection})", src, len(records))
def statuses(W, rows, src=None):
    """mastodon: rows = [{id, account_id, text, in_reply_to_id?, created_at?, like_count?, reblog_count?, reply_count?, media_url?, media_description?}]"""
    ss = _ss(W, "mastodon")
    for r in rows: ss.setdefault("Status", []).append({"visibility": "public", "local": True, "reply": bool(r.get("in_reply_to_id")), "sensitive": False, "created_at": TS, "updated_at": TS, **r})
    _bind(W, "mastodon", "Status", src, len(rows))

__all__ = ['NEW_SERVER', 'add_users', 'tasks_board', 'labels', 'tracker_project', 'wiki_collection', 'mail_lists', 'drive_tree', 'table', 'statuses']
