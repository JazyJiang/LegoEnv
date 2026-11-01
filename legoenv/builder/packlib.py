#!/usr/bin/env python3.12
"""packlib.py — shared library for the v3 (fast) task-pack workflow.

A pack = goal_nl + world (per-app specs with real-data seeds, merged into one env) + contract (grammar IR) + one gold witness + accept report.
The model decides: skeleton, dataset(s), goal text, expected solution, predicates. Everything mechanical lives here.

Typical builder (see pack/wardcover_w37_v3/build.py):
    from packlib import *
    W = World(["budibase", "gladys", "stalwart"], persona=("rota.office@wardcare.example", "Rota Office"), now="2026-09-07T08:00:00")
    W.sheet("ws_roster", "Week 37 Roster", COLS, rows)          # rows: list[dict] with exactly COLS keys
    W.events([...]); W.inbox(enron_mails(8) + [...])
    spec = W.merge()                                             # namespaced single env (budibase__*, gladys__*, ...)
    C = Contract(goal=GOAL, expected={...}); C.add("book_x", "…", CNT(...)); C.add("nomail_y", "…", CNT(..., "eq", 0), negative=True)
    write_pack("wardcover_w37_v3", W, spec, C, atoms=[...], data_bindings={...}, notes_extra="")
    # then:  run_gold(tid) (blocking; call from a background shell)  →  accept(tid)  →  finish(tid)
"""
import csv, json, os, re, sys, glob, copy, random, subprocess, shutil, time
from pathlib import Path
from datetime import datetime, timedelta
csv.field_size_limit(1 << 28)
SMOKE = str(Path(__file__).resolve().parents[1]); PACK = f"{SMOKE}/pack"; TASKS = f"{SMOKE}/tasks"; BASES = f"{PACK}/base_specs"
REPO = str(Path(SMOKE).parent / "LegoEnv"); DP = str(Path(SMOKE).parent / "datapool"); DPX = str(Path(SMOKE).parent / "datapool_ext")
for p in (f"{REPO}/runtime", f"{REPO}/compose", PACK):
    if p not in sys.path: sys.path.insert(0, p)
import runtime, ignite  # noqa

OBS_CAP = 12000            # mcp_server.clip_obs: a whole-table read must stay under this (chars of the JSON reply)
SERVER = {"budibase": "sheets", "gladys": "gcal", "stalwart": "gmail", "zulip": "slack", "opensign": "docusign", "espocrm": "salesforce",
          "espocrm_hs": "hubspot", "openmeetings": "zoom", "easyappointments": "calendly", "librechat": "chatgpt"}
PFX = {a: ("espocrm" if a.startswith("espocrm") else a) for a in SERVER}
CONTENT = {"budibase": ["Workspace", "Table", "DynamicRow", "Row"], "gladys": ["CalendarEvent"], "stalwart": ["Blob", "Thread", "Email", "EmailSubmission"],
           "zulip": ["Stream", "Recipient", "Subscription", "Message", "UserMessage"],
           "espocrm": ["Account", "Contact", "Opportunity", "Lead", "Note", "Task", "Call", "Meeting", "Campaign", "CampaignMember", "Case", "Email"],
           "espocrm_hs": ["Account", "Contact", "Opportunity", "Lead", "Note", "Task", "Call", "Meeting", "Campaign", "CampaignMember", "Case", "Email"],
           "opensign": ["ContractsDocument", "EnvelopeSigner"], "openmeetings": ["Room", "Registrant", "Participant"], "easyappointments": ["Appointment"], "librechat": ["Conversation"]}
def NS(app, ent): return f"{PFX[app]}__{ent}"

# ─────────────────────────── base specs (step-1 patched per-app specs + in-pack patches) ───────────────────────────
def collect_bases(force=False):
    """copy one per-app spec per server from the step-1 task dirs into pack/base_specs/, apply the known patches."""
    os.makedirs(BASES, exist_ok=True)
    for app, srv in SERVER.items():
        dst = f"{BASES}/{app}.spec.json"
        if os.path.exists(dst) and not force: continue
        cands = sorted(glob.glob(f"{TASKS}/[0-9]*/{srv}.spec.json"), key=lambda p: (len(json.load(open(p)).get("seed_state", {})), p))
        if not cands: print("no base for", app); continue
        s = json.load(open(cands[-1]))
        _patch(app, s); json.dump(s, open(dst, "w"), ensure_ascii=False); print("base", app, "<-", cands[-1], len(s["tools"]), "tools")

def _patch(app, s):
    for t in s["tools"]:
        if app == "gladys" and t["tool"] == "calendarevent_getevents":
            t["exec_spec"]["filter"] = {"col": "start", "mode": "range", "val": {"min": {"$arg": "from"}, "max": {"$arg": "to"}}, "optional": True}
            t["description"] = "List calendar events, optionally restricted to start between `from` and `to` (ISO 8601). Returns id, calendar_id, name, start, end, location, description, attendees, status."
        if app == "budibase" and t["tool"] == "row_search":
            t["input_schema"] = {"sourceId": {"type": "id", "description": "The table id.", "required": True}, "limit": {"type": "int", "description": "Max rows (default all).", "required": False}}
            t["guards"] = {"required": ["sourceId"], "messages": {"required": "A sourceId is required."}}
            t["description"] = "Return the rows of a table. No server-side filtering/paging: every row comes back (up to limit); filter yourself."
        if app.startswith("espocrm") and t["tool"] == "opportunity_create":
            (t.get("exec_spec", {}).get("set_on_create") or {}).pop("assigned_user_id", None)
            t.setdefault("input_schema", {})["assigned_user_id"] = {"type": "id", "description": "Owner (User id). Pass the owner explicitly."}
        if app == "stalwart" and t["tool"] == "email_list":
            g = t.setdefault("guards", {}); g["required"] = [x for x in g.get("required", []) if x != "accountId"]

def base(app):
    p = f"{BASES}/{app}.spec.json"
    if not os.path.exists(p): collect_bases()
    return json.load(open(p))

# ─────────────────────────── datasets ───────────────────────────
def ds(slug):
    for root in (DPX, DP):
        if os.path.isdir(f"{root}/{slug}/raw"): return f"{root}/{slug}/raw"
    raise FileNotFoundError(f"dataset {slug} not in datapool/datapool_ext — download it (see skill §data) into {DPX}/{slug}/raw + meta.json")
def csv_rows(path, limit=None, where=None, encoding="utf-8"):
    out = []
    with open(path, newline="", encoding=encoding, errors="replace") as f:
        for r in csv.DictReader(f):
            if where and not where(r): continue
            out.append(r)
            if limit and len(out) >= limit: break
    return out
def parquet_rows(path, columns=None, limit=None):
    try: import pyarrow.parquet as pq   # python3 (3.11) has pyarrow on the box; python3.12 does not
    except ImportError:                  # fallback: read through a python3 subprocess (JSON over stdout)
        code = ("import sys,json,pyarrow.parquet as pq; a=json.loads(sys.argv[1]); t=pq.read_table(a[0],columns=a[1]); "
                "t=t.slice(0,a[2]) if a[2] else t; print(json.dumps(t.to_pylist(),default=str))")
        r = subprocess.run(["python3", "-c", code, json.dumps([path, columns, limit])], capture_output=True, text=True, check=True)
        return json.loads(r.stdout)
    t = pq.read_table(path, columns=columns); rows = t.slice(0, limit).to_pylist() if limit else t.to_pylist(); return rows
def enron_mails(n, seed=1):
    R = random.Random(seed); rows = []
    for r in csv_rows(f"{DP}/enron-spam-setfit/raw/enron_spam_data.csv", limit=None, where=lambda r: r["Spam/Ham"] == "ham"):
        s, m = (r["Subject"] or "").strip(), (r["Message"] or "").strip()
        if 8 <= len(s) <= 70 and 60 <= len(m) <= 400: rows.append({"subject": s, "body": m, "_src": f"datapool:enron-spam-setfit#{r['Message ID']}"})
        if len(rows) >= 3000: break
    return R.sample(rows, n)
def twcs_chat(n, seed=1):
    R = random.Random(seed); rows = []
    for r in csv_rows(f"{DP}/twcs-twitter-customer-support/raw/twcs.csv", where=lambda r: r.get("inbound") == "False"):
        t = re.sub(r"@\w+\s*", "", r["text"] or "").strip()
        if 25 <= len(t) <= 160 and "http" not in t: rows.append({"text": t, "_src": f"datapool:twcs-twitter-customer-support#{r['tweet_id']}"})
        if len(rows) >= 3000: break
    return R.sample(rows, n)

def profile_rank(rows, group_col, k=3, where=None):
    """counts per group_col value (optionally filtered) → (ranking list[(value,count)], tie_free_at_k: bool)"""
    import collections
    c = collections.Counter(r[group_col] for r in rows if (where is None or where(r))); rk = c.most_common()
    tie_free = len(rk) > k and rk[k - 1][1] > rk[k][1]
    return rk, tie_free
def est_chars(rows, cols=None):
    """rough size of a whole-table read reply for these rows (compare with OBS_CAP before seeding)"""
    return sum(len(json.dumps({c: r.get(c, "") for c in (cols or r.keys())}, ensure_ascii=False)) + 90 for r in rows)

# ─────────────────────────── base-spec fixes folded from the production run (applied by World to new builds only) ───────────────────────────
def _tool(s, name): return next((t for t in s["tools"] if t["tool"] == name), None)
def fix_base(app, s):
    """per-app (unprefixed) fixes, applied in World.__init__. Each was an in-pack patch in ≥ 2 packs; see pack/batches/INFRA_FINDINGS.md."""
    if app == "gladys":        # calendarevent_destroy looked events up by selector, which calendarevent_create leaves null (b17)
        t = _tool(s, "calendarevent_destroy")
        if t and "event_id" not in t["input_schema"]:
            t["exec_spec"]["lookup_by"] = {"id": {"$arg": "event_id"}}
            t["input_schema"] = {"event_id": {"type": "id", "required": True, "description": "Event id (from calendarevent_getevents or the create reply)."}}
            t["guards"]["required"] = ["event_id"]; t["guards"].setdefault("messages", {})["required"] = "Provide the id of the event to delete."
            t["description"] = "Delete a calendar event by its id."
    if app == "stalwart":
        t = _tool(s, "email_set")      # create-only: update/destroy args silently created EMPTY mails that could then be submitted (b05, b17, b19, lt01)
        if t and "update" in t["input_schema"]:
            for k in ("update", "destroy", "onDestroyRemoveEmails", "create", "ifInState"): t["input_schema"].pop(k, None)
            for k in ("to", "body"):
                if isinstance(t["input_schema"].get(k), dict): t["input_schema"][k]["required"] = True
            g = t.setdefault("guards", {}); g["required"] = sorted(set(g.get("required", [])) | {"blob_id", "to", "body"})
            g.setdefault("messages", {})["required"] = ("email_set creates a NEW email and needs blob_id, to and body. Existing emails cannot be edited with it: "
                                                        "to correct a draft, create a new email with the full corrected content and submit that one.")
            t["description"] = (t.get("description") or "") + " Creates a new email (use email_update to change keywords/mailboxes of an existing one)."
        if not _tool(s, "email_update"):   # JMAP Email/set update of keywords / mailboxIds: mark read, label, move (b07, b12, b17)
            s["tools"].append({"tool": "email_update", "op": "update", "family": "update.field_set", "entity": "Email",
                "exec_spec": {"entity": "Email", "row_key": {"id": {"$arg": "id"}}, "fields": ["keywords", "mailbox_ids"]},
                "input_schema": {"id": {"type": "id", "description": "Id of the email to change.", "required": True},
                                 "keywords": {"type": "json", "description": "Full new keyword list: [\"seen\"] marks it read, [] unread; labels are keywords (pass the current ones plus the label)."},
                                 "mailbox_ids": {"type": "json", "description": "Full new list of mailbox ids (move the mail)."}},
                "guards": {"requires_auth": True, "required": ["id"], "messages": {"auth": "Sign in before changing emails.", "required": "An email id is required.", "not_found": "No such email."}},
                "description": "Change an existing email: its keywords (labels, read/unread, flagged) or the mailboxes it is in. Mirrors JMAP Email/set update (only keywords and mailboxIds may change)."})
    return s
CRM_RELINK = {"Account": ["assigned_user_id"], "Contact": ["assigned_user_id", "account_id"], "Lead": ["assigned_user_id"],
              "Opportunity": ["assigned_user_id", "account_id", "contact_id"], "Case": ["assigned_user_id", "account_id", "contact_id", "lead_id"],
              "Task": ["assigned_user_id", "parent_id", "account_id", "contact_id"], "Call": ["assigned_user_id", "parent_id", "account_id"], "Meeting": ["assigned_user_id", "parent_id", "account_id"]}
def fix_merged(world, apps):
    """fixes on the merged (namespaced) world, applied in World.merge()."""
    if any(a.startswith("espocrm") for a in apps):   # the runtime never writes id-typed columns on update → *_update(assigned_user_id=…) returned ok and changed nothing (b18)
        for e in world["entities"]:
            ent = e["name"].split("__", 1)[-1]
            if not e["name"].startswith(PFX["espocrm"] + "__") or ent not in CRM_RELINK: continue
            for c in e["columns"]:
                if c["name"] in CRM_RELINK[ent] and c.get("type") == "id": c["type"] = "int"
    return world

# ─────────────────────────── world ───────────────────────────
# Explicit native login argument templates, declared by a capability card.
# Apps without a template keep the original persona/password behaviour.
LOGIN_ARGUMENTS = {}
def login_arguments(W, app):
    if app in LOGIN_ARGUMENTS:
        return {k: (W.password if v == "$password" else W.persona if v == "$persona" else v)
                for k, v in LOGIN_ARGUMENTS[app].items()}
    tool, user_field = LOGIN[app]
    return {user_field: W.persona, "password": W.password}

class World:
    def __init__(self, apps, persona=("ops@company.example", "Operations"), now="2026-01-05T09:00:00", password="pw-operations"):
        self.apps = list(apps); self.persona, self.persona_name, self.password, self.now = persona[0], persona[1], password, now
        self.spec = {}; self.notes = []; self.bindings = {}
        for app in self.apps:
            s = base(app); s["now"] = now
            a = s.get("auth") or {}; acct = (s["seed_state"].get(a.get("account_entity")) or [{}])[0]
            old_user, old_pw = acct.get(a.get("username_col")), acct.get(a.get("password_col"))
            if app in LOGIN_ARGUMENTS:
                user_field = LOGIN[app][1]
                identity = LOGIN_ARGUMENTS[app].get(user_field)
                if identity is not None and identity not in ("$persona", "$password"):
                    acct[a["username_col"]] = identity
                    old_user = None  # Preserve the declared native selector/id; never relabel it as an email.     # the step-1 persona of this base (<domain>@company.example.com / pw-<domain>)
            js = json.dumps(s["seed_state"])
            if old_user: js = js.replace(json.dumps(old_user)[1:-1], self.persona)
            if old_pw: js = js.replace(json.dumps(old_pw)[1:-1], self.password)
            js = re.sub(r'"(Operations|Marketing|Sales)"', f'"{self.persona_name}"', js)
            s["seed_state"] = json.loads(js)
            keep_conv = [c for c in s["seed_state"].get("Conversation", []) if c.get("conversationId") == "conv-1"] if app == "librechat" else []
            for ent in CONTENT.get(app, []): s["seed_state"].pop(ent, None)
            if keep_conv: s["seed_state"]["Conversation"] = [dict(c, title="Assistant") for c in keep_conv]   # chat_send_prompt writes conversationId="conv-1" (FK)
            if app.startswith("espocrm"):   # the CRM persona must be id 1: the merged world shares one session and the other systems' persona ids are 1
                for u in s["seed_state"].get("User", []):
                    if u.get("id") == "me": u["id"] = 1
                s["seed_state"] = json.loads(json.dumps(s["seed_state"]).replace('"me"', '1'))
            self.spec[app] = fix_base(app, s)
        self._n = {}
    def set_persona_id(self, app, new_id=1):
        """give the persona account row of `app` id `new_id` and rewrite every seed reference to its old id (espocrm bases use "me")."""
        s = self.spec[app]; a = s.get("auth") or {}; rows = s["seed_state"].get(a.get("account_entity")) or []
        if not rows: return
        old = rows[0].get("id"); rows[0]["id"] = new_id
        for ent, rs in s["seed_state"].items():
            for r in rs:
                for k, v in list(r.items()):
                    if v == old and k != "id": r[k] = new_id
    def _nid(self, key):
        self._n[key] = self._n.get(key, 0) + 1; return self._n[key]
    def seed(self, app, entity, rows, src=None):
        self.spec[app]["seed_state"][entity] = list(rows)
        if src: self.bindings[NS(app, entity)] = {"dataset": src, "rows": len(rows)}
        return rows
    # budibase: worksheets = tables; rows flat (no <dynamic>) so a whole-table read stays small
    def sheet(self, tid, title, cols, rows, workspace=("ss_main", "Workbook"), src=None):
        ss = self.spec["budibase"]["seed_state"]
        ss.setdefault("Workspace", []) or ss["Workspace"].append({"_id": workspace[0], "appId": workspace[0], "name": workspace[1], "url": "/" + workspace[0], "status": "published", "tenantId": "default", "createdAt": self.now, "updatedAt": self.now, "id": workspace[0]})
        ss.setdefault("Table", []).append({"_id": tid, "name": title, "type": "table", "sourceType": "internal", "sourceId": workspace[0], "schema": {c: {"type": "string", "name": c} for c in cols},
                                           "primaryDisplay": cols[0], "sql": False, "created": True, "id": tid, "spreadsheet": workspace[1]})
        out = []
        for r in rows:
            n = self._nid("row"); cells = {c: ("" if r.get(c) is None else str(r.get(c))) for c in cols}
            out.append({"_id": n, "type": "row", "tableId": tid, "_viewId": None, **cells, "_ab_row_id": n + 1, "id": n})
        ss.setdefault("DynamicRow", []).extend(out); ss.setdefault("Row", []).extend(copy.deepcopy(out))
        if src: self.bindings[f"{NS('budibase', 'DynamicRow')}({tid})"] = {"dataset": src, "rows": len(out), "columns": cols}
        return out
    def events(self, evs, src=None):
        """evs: [{name, start, end, attendees:[emails], description?, full_day?, organizer_email?}]"""
        out = []
        for e in evs:
            k = self._nid("event")
            out.append({"id": k, "calendar_id": 1, "name": e["name"], "selector": f"ev_{k}", "external_id": f"ev_{k}", "url": None, "location": e.get("location"), "description": e.get("description"),
                        "start": e["start"], "end": e["end"], "full_day": bool(e.get("full_day", False)), "attendees": list(e.get("attendees", [])), "status": "confirmed", "organizer_email": e.get("organizer_email"), "ab_id": None})
        self.spec["gladys"]["seed_state"].setdefault("CalendarEvent", []).extend(out)
        if src: self.bindings[NS("gladys", "CalendarEvent")] = {"dataset": src, "rows": len(out)}
        return out
    def inbox(self, mails, src=None, senders=None):
        """mails: [{from?, subject, body, when?}] → stalwart Blob/Thread/Email in Inbox (mailbox 1). Missing `from` → rotated over `senders` (or generic addresses)."""
        ss = self.spec["stalwart"]["seed_state"]; out = []; dom = self.persona.split("@")[1]
        for i, m in enumerate(mails):
            m = dict(m); m.setdefault("from", (senders[i % len(senders)] if senders else f"user{i+1}@{dom}"))
            if "when" not in m and "date" in m: m["when"] = m.pop("date")   # alias
            unknown = set(m) - {"from", "from_name", "subject", "body", "when"}
            assert not unknown, f"inbox(): unknown mail keys {sorted(unknown)} (use from/from_name/subject/body/when)"
            k = self._nid("mail"); when = m.get("when") or (datetime.fromisoformat(self.now) - timedelta(hours=7 * (len(mails) - i))).strftime("%Y-%m-%dT%H:%M:%S")
            ss.setdefault("Blob", []).append({"id": k, "size": len(m["body"]), "class": "email"}); ss.setdefault("Thread", []).append({"id": k, "email_ids": [k]})
            row = {"id": k, "blob_id": k, "thread_id": k, "mailbox_ids": [1], "keywords": ["seen"], "size": len(m["body"]), "received_at": when, "has_attachment": False, "preview": m["body"][:120],
                   "subject": m["subject"], "message_id": f"m-{k}", "in_reply_to": None, "references": None, "from": [{"name": m.get("from_name", ""), "email": m["from"]}], "to": [{"name": "", "email": self.persona}],
                   "cc": [], "bcc": [], "reply_to": [], "sender": [{"name": "", "email": m["from"]}], "sent_at": when, "text_body": None, "html_body": None, "attachments": [], "attachment": [], "body": m["body"]}
            ss.setdefault("Email", []).append(row); out.append(row)
        if src: self.bindings[NS("stalwart", "Email")] = {"dataset": src, "rows": len(out)}
        return out
    def stream(self, name, members, msgs, description="", src=None):
        """members: [(email, full_name)] besides the persona; msgs: [{sender: email, text, when?}]. First call creates the member profiles."""
        ss = self.spec["zulip"]["seed_state"]
        if "UserProfile" not in ss or len(ss["UserProfile"]) <= 1 or not ss.get("_members_done"):
            me = ss["UserProfile"][0]; users = [me]
            for i, (em, nm) in enumerate(members):
                users.append({**{k: v for k, v in me.items() if k not in ("id", "delivery_email", "email", "password", "full_name", "api_key", "uuid", "role")}, "id": i + 2, "delivery_email": em, "email": em, "password": f"pw-{i+2}", "full_name": nm, "api_key": f"key-{i+2}", "uuid": f"u-{i+2}", "role": 400})
            ss["UserProfile"] = users; ss["Recipient"] = [{"id": u["id"] + 100, "type": 1, "type_id": u["id"]} for u in users]; ss["Stream"] = []; ss["Subscription"] = []; ss["Message"] = []; ss["UserMessage"] = []; ss["_members_done"] = True
        sid = len(ss["Stream"]) + 1; rid = 1000 + sid
        ss["Stream"].append({"id": sid, "realm_id": 1, "name": name, "creator_id": 1, "date_created": "2026-01-01T00:00:00", "deactivated": False, "description": description, "rendered_description": "", "subscriber_count": len(ss["UserProfile"]), "recipient_id": rid, "folder_id": None, "invite_only": False, "history_public_to_subscribers": True, "is_web_public": False, "message_retention_days": None, "default_push_notifications": False, "first_message_id": None, "is_recently_active": True, "topics_policy": 0})
        ss["Recipient"].append({"id": rid, "type": 2, "type_id": sid})
        for u in ss["UserProfile"]: ss["Subscription"].append({"id": len(ss["Subscription"]) + 1, "user_profile_id": u["id"], "recipient_id": rid, "active": True, "is_user_active": True, "is_muted": False, "pin_to_top": False})
        byemail = {u["email"]: u["id"] for u in ss["UserProfile"]}
        for i, m in enumerate(msgs):
            k = len(ss["Message"]) + 1; when = m.get("when") or (datetime.fromisoformat(self.now) - timedelta(minutes=41 * (len(msgs) - i))).strftime("%Y-%m-%dT%H:%M:%S")
            ss["Message"].append({"id": k, "sender_id": byemail.get(m.get("sender"), 2), "recipient_id": rid, "realm_id": 1, "subject": m.get("topic", "general"), "content": m["text"], "rendered_content": m["text"], "sending_client_id": 1, "date_sent": when, "has_attachment": False, "has_image": False, "has_link": False, "type": "stream", "is_channel_message": True})
            ss["UserMessage"].append({"id": k, "user_profile_id": 1, "message_id": k, "flags": 1})
        if src: self.bindings[NS("zulip", "Message") + f"({name})"] = {"dataset": src, "rows": len(msgs)}
        return sid
    def merge(self):
        for s in self.spec.values(): s["seed_state"].pop("_members_done", None)
        specs = [self.spec[a] for a in self.apps]
        world, pfx, _ = ignite.merge_world(specs, log=lambda *a: None); world["now"] = self.now
        world = fix_merged(world, self.apps)
        self.pfx = dict(zip(self.apps, pfx)); assert all(self.pfx[a] == PFX[a] for a in self.apps), self.pfx
        self.world = world; return world
    def obs_report(self):
        """size of every whole-table / inbox / calendar read the agent will make (chars of the JSON reply); warn above OBS_CAP."""
        env = runtime.Env(self.world); rep = {}
        for app in self.apps:
            login = {"budibase": ("auth_login", {"email": self.persona, "password": self.password}), "gladys": ("sign_in", {"email": self.persona, "password": self.password}),
                     "stalwart": ("sign_in", {"email": self.persona, "password": self.password}), "zulip": ("sign_in", {"delivery_email": self.persona, "password": self.password})}.get(app)
            if login: env.call(NS(app, login[0]), login[1])
        if "budibase" in self.apps:
            for t in env.state.get(NS("budibase", "Table"), []):
                rep[f"row_fetch {t['_id']}"] = len(json.dumps(env.call(NS("budibase", "row_fetch"), {"sourceId": t["_id"]}), ensure_ascii=False))
        if "stalwart" in self.apps: rep["email_list"] = len(json.dumps(env.call(NS("stalwart", "email_list"), {"accountId": 1}), ensure_ascii=False))
        if "gladys" in self.apps: rep["calendarevent_getevents"] = len(json.dumps(env.call(NS("gladys", "calendarevent_getevents"), {}), ensure_ascii=False))
        bad = {k: v for k, v in rep.items() if v > OBS_CAP}
        return rep, bad

# ─────────────────────────── contract (grammar IR) ───────────────────────────
def F(col, op, value=None):
    d = {"node": "field", "col": col, "op": op}
    if value is not None: d["value"] = value
    return d
def AND(*a): return {"node": "and", "args": list(a)} if len(a) > 1 else a[0]
def OR(*a): return {"node": "or", "args": list(a)}
def NOT(a): return {"node": "not", "args": [a]}
def SEL(entity, where=None, get=None):
    d = {"node": "select", "entity": entity}
    if where: d["where"] = where
    if get: d["get"] = get
    return d
def CNT(sel, op="gte", n=1): return {"node": "count", "select": sel, "op": op, "n": n}
def sent_to(addr, *terms):       # a mail actually submitted to addr (To header or envelope rcpt_to) whose body contains every term
    body = SEL(NS("stalwart", "Email"), AND(*[F("body", "icontains", t) for t in terms]), {"col": "id"}) if terms else None
    hdr = SEL(NS("stalwart", "Email"), AND(F("to", "icontains", addr), *[F("body", "icontains", t) for t in terms]), {"col": "id"})
    env_rcpt = AND(F("rcpt_to", "icontains", addr), F("email_id", "in", body)) if terms else F("rcpt_to", "icontains", addr)
    return SEL(NS("stalwart", "EmailSubmission"), OR(F("email_id", "in", hdr), env_rcpt))
def stream_post(stream, *terms):  # the persona's own post in a stream containing every term
    # join through Recipient(type=2, type_id=stream id): zulip create_channel inserts the Recipient row but never sets Stream.recipient_id
    rec = SEL(NS("zulip", "Recipient"), AND(F("type", "eq", 2), F("type_id", "in", SEL(NS("zulip", "Stream"), F("name", "eq", stream), {"col": "id"}))), {"col": "id"})
    return SEL(NS("zulip", "Message"), AND(OR(F("recipient_id", "in", rec), F("recipient_id", "in", SEL(NS("zulip", "Stream"), F("name", "eq", stream), {"col": "recipient_id"}))),
                                           F("sender_id", "eq", 1), *[F("content", "icontains", t) for t in terms]))
def dm(user_id, *terms):  # the persona's direct message to zulip member user_id (World.stream numbers members 2.. in the order given) containing every term
    rec = SEL(NS("zulip", "Recipient"), AND(F("type", "eq", 1), F("type_id", "eq", user_id)), {"col": "id"})
    return SEL(NS("zulip", "Message"), AND(F("recipient_id", "in", rec), F("sender_id", "eq", 1), *[F("content", "icontains", t) for t in terms]))
def vikunja_live(*conds):   # vikunja cards that are not soft-deleted (task_delete only stamps deleted_at). Use in positives; negatives should count deleted cards too.
    return SEL(NS("vikunja", "Task"), AND(F("deleted_at", "is_null"), *conds))
def event_with(attendee, start_prefix, end_prefix=None):
    args = [F("attendees", "icontains", attendee), F("start", "startswith", start_prefix)]
    if end_prefix: args.append(F("end", "startswith", end_prefix))
    return SEL(NS("gladys", "CalendarEvent"), AND(*args))
def row_in(tid, **eq):  # DynamicRow of a table with flat cell equalities (seed rows are flat; agent-added rows live under <dynamic>.col)
    return SEL(NS("budibase", "DynamicRow"), AND(F("tableId", "eq", tid), *[OR(F(k, "eq", v), F(f"<dynamic>.{k}", "eq", v)) for k, v in eq.items()]))

class Contract:
    def __init__(self, goal, expected=None, tier="strong"):
        self.goal, self.expected, self.tier, self.P, self.A = goal, expected or {}, tier, [], []
    def anchor(self, entity, where, col, value, provenance):
        self.A.append({"at": {"node": "select", "entity": entity, "where": where, "get": {"col": col}}, "value": value, "provenance": provenance, "discoverable": True}); return len(self.A) - 1
    def add(self, pid, semantic, pred, negative=False, refs=()):
        self.P.append({"id": pid, "semantic": semantic, "kind": "not_exists" if negative else "exists", "pred": pred, "anchor_refs": list(refs), "vacuous_ok": None, "expect_final": True, "expect_seed": bool(negative)})
    def to_json(self, tid):
        return {"proposal_id": f"{tid}-p01", "final_intent": self.goal, "tier": self.tier, "anchor_values": self.A, "pivot_rows": [], "postconditions": self.P,
                "grammar": "runtime/grammar.py IR; judge = runtime.eval_node(pred, _StateView(state), None, None, site='postcondition')", "expected_solution": self.expected}
    def seed_check(self, spec):
        st = runtime.Env(spec).state; bad = []
        for p in self.P:
            try: v = bool(runtime.eval_node(p["pred"], runtime._StateView(st, spec.get("now")), None, None, site="postcondition"))
            except Exception as e: v = f"ERR {e}"
            if v != p["expect_seed"]: bad.append((p["id"], v))
        return bad

# ─────────────────────────── pack writer / runner ───────────────────────────
NOTES = {"budibase": "{p}__ is the spreadsheet app: sign in with {p}__auth_login(email, password). Each worksheet is a table whose _id is the worksheet id; table_fetchall lists them, row_fetch(sourceId=<worksheet id>) reads all rows of one worksheet, row_save(sourceId, body) appends a row.",
         "gladys": "{p}__ is the shared calendar: sign in with {p}__sign_in(email, password). calendar_get lists calendars (selector 'primary'); calendarevent_getevents(from, to) lists events whose start is in the range; calendarevent_create(calendar_selector, name, start, end, attendees, description) creates one; calendarevent_destroy(event_id) deletes one.",
         "stalwart": "{p}__ is mail: sign in with {p}__sign_in(email, password); your accountId is 1; mailboxes Inbox=1, Sent=2; email_list(accountId=1) lists the inbox with bodies. To send: email_set(mailbox_ids=[2], blob_id=1, subject, from, to, body) then emailsubmission_set(identity_id=1, email_id=<new id>, rcpt_to=[addresses]). email_set only creates (to correct a draft, create a new one); email_update(id, keywords, mailbox_ids) changes an existing mail (keywords ['seen'] = read, labels are keywords, mailbox_ids moves it).",
         "zulip": "{p}__ is team chat: sign in with {p}__sign_in(delivery_email, password). Streams are channels: get_streams lists them, get_stream_messages reads one, send_message(stream_id, content, topic) posts.",
         "espocrm": "{p}__ is the CRM: sign in with {p}__sign_in(user_name, password). account_list lists every account (id, name); account_find(q) / contact_find(q) / opportunity_find(q) / user_find(q) search by keywords; opportunity_create(name, amount, account_id, stage, assigned_user_id, close_date, description) opens a deal; note_create(post, parent_type, parent_id) adds a note.",
         "espocrm_hs": "{p}__ is the CRM: sign in with {p}__sign_in(user_name, password); account_find/contact_find/lead_find/opportunity_find search by text, *_list list, *_create create, note_create adds a note.",
         "easyappointments": "{p}__ is the booking scheduler (Calendly-style): sign in with {p}__sign_in(username=<your email>, password). api_appointment_index(from, till) lists bookings; user_list lists hosts/providers and api_service_index lists event types (services); booking_register_customer_and_book(id_services, id_users_provider, start_datetime, end_datetime, invitee_email, invitee_name) books one.",
         "openmeetings": "{p}__ is video meetings (Zoom-style): sign in with {p}__sign_in(login=<your email>, password). A meeting is a room: meeting_list / meeting_find(q) / meeting_get(meeting_id) read meetings; create_room(name, start_time, duration, agenda, ...) creates one (a meeting at a time is a single call); registrant_add(meeting_id, email, first_name, last_name) and registrant_list(meeting_id) manage registrants; participant_list(meeting_id) lists who attended (includes the host; duration in minutes).",
         "librechat": "{p}__ is the AI assistant (ChatGPT-style): sign in with {p}__sign_in(email, password). chat_send_prompt(prompt) records your prompt; the reply is not generated here, so produce the answer with your own reasoning and use it downstream.",
         "opensign": "{p}__ is e-signature: sign in with {p}__sign_in(email, password); template_list lists templates; envelope_create(TemplateId, subject) then envelope_add_signer(envelope id, name, email) then envelope_send(id); workspace_create / workspace_add_member manage shared workspaces."}
SHARED_SESSION = " All systems share ONE login session: sign in to a system again right before using it if you have signed into another one since."

def write_pack(tid, W, spec, C, atoms, data_bindings=None, skeleton="", notes_extra="", persona_password=None):
    out = f"{PACK}/{tid}"; td = f"{TASKS}/{tid}"; os.makedirs(f"{td}/run", exist_ok=True)
    def w(p, o): os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(o, open(p, "w"), ensure_ascii=False, indent=1)
    for app, s in W.spec.items(): w(f"{out}/03_spec/{SERVER[app]}.spec.json", s)
    w(f"{out}/03_spec/template.spec.json", spec); w(f"{out}/06_distractor/fork.spec.json", spec); w(f"{out}/06_distractor/distractor_patch.json", [])
    w(f"{out}/05_verifier/contract.json", C.to_json(tid)); w(f"{out}/05_verifier/verdict.json", {"proposal_id": f"{tid}-p01", "supportable": True, "final_intent": C.goal, "tier": C.tier, "conclusion": "v3 fast pack"})
    w(f"{out}/01_intent/proposal.json", {"proposal_id": f"{tid}-p01", "nl_draft": C.goal, "menu_ids": [], "generated": [{"repo": a, "reason": "v3 data-first"} for a in W.apps], "reason": skeleton, "needs": {"data": [], "op": [], "cross_env": len(W.apps) > 1},
                                         "complexity": len(atoms), "grounding": [], "runtime_regrounding_required": False, "seed_realization_status": "generated", "ts": None, "atoms": atoms, "source_skeleton": skeleton})
    w(f"{out}/02_data/data_bindings.json", data_bindings or W.bindings); w(f"{out}/02_data/weld_report.json", {"welds": [], "misses": [], "datasets_considered": []}); w(f"{out}/02_data/build_spec.json", {"tid": tid, "apps": W.apps, "now": W.now})
    w(f"{out}/04_operation/operation_report.json", {"outcome": "pending_gold_run", "blocked_reasons": [], "steps": [], "discoverability_dag": {"descriptors": [], "value_nodes": [], "edges": []}})
    json.dump(spec, open(f"{td}/env.spec.json", "w"), ensure_ascii=False)
    json.dump({"mcpServers": {"env": {"command": "python3.12", "args": [f"{SMOKE}/mcp_env_smoke.py", f"{td}/env.spec.json", "--witness", f"{td}/run/witness_env.jsonl", "--dump-state", f"{td}/run/state_env.json"], "env": {"ENVLIB_RUNTIME_DIR": f"{REPO}/runtime"}}}}, open(f"{td}/mcp.json", "w"), indent=1)
    open(f"{td}/prompt.txt", "w").write(C.goal)
    head = ("You are a workflow automation agent. Execute the requested tasks using the available tools. Do not ask clarifying questions - use the information provided and make reasonable assumptions when needed. "
            "Favor parallel tool calls and avoid duplicate searches. When summarizing your work, list only items you acted on; handle exclusions silently in the action, not narratively in the output.")
    notes = " ".join(NOTES.get(a, "{p}__ prefix.").format(p=PFX[a]) for a in W.apps)
    sysa = f"{head}\n\nEnvironment notes: every tool name carries its system prefix. Credentials for all systems: {W.persona} / {W.password}. {notes}{SHARED_SESSION if len(W.apps) > 1 else ''} {notes_extra} Read tool descriptions carefully; the APIs differ from the SaaS originals but provide the same functions. Only use the MCP tools."
    open(f"{td}/system_append.txt", "w").write(sysa)
    json.dump({"example_id": tid, "task": tid, "persona": {"email": W.persona, "password": W.password, "name": W.persona_name}, "now": W.now, "pack": out, "prefixes": {a: PFX[a] for a in W.apps}}, open(f"{td}/translation.json", "w"), indent=1)
    return out, td

def run_gold(tid, turns=60, retries=3):
    """blocking: run the external agent on tasks/<tid>; retry on the gateway's AUP false positive. Returns out.json dict."""
    for i in range(retries):
        subprocess.run(["bash", f"{SMOKE}/run_task.sh", tid, str(turns)], cwd=SMOKE)
        try: d = json.load(open(f"{TASKS}/{tid}/run/out.json"))
        except Exception: d = {}   # empty out.json = the run was killed (killrun.sh) → never retry that
        res = str(d.get("result", ""))
        kind = ("EMPTY" if not d else "AUP" if "Usage Policy" in res else "PARSE" if "could not be parsed" in res
                else "BAD400" if ("400" in res and ("invalid_request" in res or "does not match" in res or "input_schema" in res)) else
                "ERR0" if d.get("is_error") and (d.get("num_turns") or 0) <= 2 else "ok")
        with open(f"{TASKS}/{tid}/cost_ledger.tsv", "a") as fh:   # every attempt, incl. gateway failures (reports otherwise show only the last)
            fh.write(f"{time.strftime('%F %T')}\t{d.get('session_id')}\t{d.get('total_cost_usd')}\t{d.get('num_turns')}\t{kind}\n")
        if kind == "BAD400": print(f"attempt {i+1}: request rejected (400, deterministic — fix the spec, e.g. tool-arg names): {res[:200]}"); return d
        if kind in ("AUP", "PARSE", "ERR0"): print(f"attempt {i+1}: gateway failure ({kind}), retrying"); continue
        return d
    return d

def archive_attempt(tid, name):
    src, dst = f"{TASKS}/{tid}/run", f"{PACK}/{tid}/rollouts/{name}"; os.makedirs(dst, exist_ok=True)
    for f in os.listdir(src): shutil.copy(f"{src}/{f}", dst)
    shutil.copy(f"{TASKS}/{tid}/prompt.txt", dst)
    if os.path.exists(f"{PACK}/{tid}/accept/report.json"): shutil.copy(f"{PACK}/{tid}/accept/report.json", f"{dst}/accept_report.json")

def accept(tid, strict=True):   # new packs must pass --strict (every negative falsified)
    r = subprocess.run(["python3.12", f"{PACK}/accept.py", f"{PACK}/{tid}", f"{TASKS}/{tid}"] + (["--strict"] if strict else []), capture_output=True, text=True)
    print(r.stdout[-3000:]); return r.returncode == 0

def finish(tid):
    subprocess.run(["python3.12", f"{PACK}/fill_witness.py", f"{PACK}/{tid}", f"{TASKS}/{tid}"]); subprocess.run(["python3.12", f"{PACK}/emit_task.py", f"{PACK}/{tid}", tid])
    t = json.load(open(f"{PACK}/{tid}/emit/{tid}.task.json")); sp = json.load(open(f"{PACK}/{tid}/emit/{tid}.spec.json"))
    ok = runtime.run_task(sp, t, verbose=False); print("runtime.run_task:", ok); return ok

def flat_row_patch(spec, cols):
    """make budibase row_patch update flat sheet cells: seeded rows keep flat cells, but stock row_patch writes a <dynamic> blob and the old
    value keeps showing → agents think the edit failed. Call on the merged spec for any task whose deliverable edits sheet rows."""
    ent = [e for e in spec["entities"] if e["name"] == NS("budibase", "DynamicRow")][0]
    have = {c["name"] for c in ent["columns"]}
    for c in cols:
        if c not in have: ent["columns"].append({"name": c, "type": "text", "nullable": True})
    t = [t for t in spec["tools"] if t["tool"] == NS("budibase", "row_patch")][0]
    bad = [c for c in cols if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", c)]
    if bad: print(f"flat_row_patch: skipping columns whose names are not valid tool-argument names (API 400): {bad} — rename them (e.g. Campaign_ID) or patch only the edited column")
    cols = [c for c in cols if c not in bad]
    for c in cols: t["input_schema"][c] = {"type": "text", "description": f"New value for the '{c}' cell."}
    t["input_schema"]["body"] = {"type": "json", "description": "Legacy: extra fields stored as a dynamic blob. Prefer passing each column as its own argument.", "required": False}
    t["guards"]["required"] = ["id", "sourceId"]; t["guards"].setdefault("messages", {})["required"] = "id and sourceId are required."
    t["description"] = ("Update cells of an existing row: id = row _id, sourceId = table _id, and pass each column you change as its own argument "
                        f"(columns: {', '.join(cols)}). Only the cells you pass change; the row keeps its other values.")
    if isinstance(t["exec_spec"].get("fields"), list): t["exec_spec"]["fields"] = list(dict.fromkeys(t["exec_spec"]["fields"] + list(cols)))
    return spec

LOGIN = {"budibase": ("auth_login", "email"), "gladys": ("sign_in", "email"), "stalwart": ("sign_in", "email"), "zulip": ("sign_in", "delivery_email"),
         "espocrm": ("sign_in", "user_name"), "espocrm_hs": ("sign_in", "user_name"), "opensign": ("sign_in", "email"), "openmeetings": ("sign_in", "login"),
         "librechat": ("sign_in", "email"), "easyappointments": ("sign_in", "username")}
def login(env, W, app):
    entry = LOGIN[app]
    if entry is None: return None  # Only an explicit no-login registration skips auth.
    t, k = entry; return env.call(NS(app, t), login_arguments(W, app))
def simulate(spec, W, C, steps, verbose=False):
    """dry-run a hand-written gold solution before the gold run (b12: 10/10 first try).
    steps: list of (app, tool, args) or callables(env); re-logs in on every app switch. Returns (predicates not True, env)."""
    env = runtime.Env(spec); cur = None
    for st in steps:
        if callable(st): st(env); continue
        app, tool, args = st
        if app != cur: login(env, W, app); cur = app
        r = env.call(NS(app, tool), args)
        if verbose or (isinstance(r, dict) and (r.get("error") or r.get("isError") or r.get("ok") is False)): print("  ", tool, json.dumps(r, default=str)[:300])
    bad = []
    for p in C.P:
        try: v = bool(runtime.eval_node(p["pred"], runtime._StateView(env.state, spec.get("now")), None, None, site="postcondition"))
        except Exception as e: v = f"ERR {e}"
        if v is not True: bad.append((p["id"], v))
    return bad, env

def assert_tool_arg_names(spec):
    """the Anthropic API rejects tool input properties outside ^[a-zA-Z0-9_.-]{1,64}$ with a 400 on turn 1; call before write_pack."""
    bad = [(t["tool"], k) for t in spec["tools"] for k in (t.get("input_schema") or {}) if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", k)]
    assert not bad, f"invalid tool-argument names: {bad[:10]}"

if __name__ == "__main__":
    if sys.argv[1:] == ["bases"]: collect_bases(force=True)
