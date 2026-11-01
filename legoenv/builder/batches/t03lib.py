"""t03lib — batch tgt_03 helpers: shared imports, claim/log, finish + report line, README writer, money forms."""
import sys, json, os, re, csv, glob, random, collections, subprocess
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from packlib import *
from newspecs.register import *
from newspecs2.register import *
import packlib
import datetime as dt

B = "/builder/smoke/pack/batches"; REPORT = f"{B}/tgt_03.report.tsv"; BATCH = "tgt_03"

def claim(tid):
    try: os.mkdir(f"{PACK}/{tid}"); open(f"{PACK}/{tid}/.t03", "w").write(BATCH); return True
    except FileExistsError: return os.path.exists(f"{PACK}/{tid}/.t03")
def log_dataset(tid, sid, slug):
    have = open(f"{B}/datasets_used.tsv").read()
    if f"{tid}\t{sid}\t{slug}\t{BATCH}" in have: return
    subprocess.run(["flock", f"{B}/.ds.lock", "-c", f"echo '{tid}\t{sid}\t{slug}\t{BATCH}' >> {B}/datasets_used.tsv"], check=True)

def ascii_fold(s):
    import unicodedata; return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
def mail_of(first, last, domain): return f"{re.sub(r'[^a-z]', '', ascii_fold(first).lower())}.{re.sub(r'[^a-z]', '', ascii_fold(last).lower())}@{domain}"

def money_forms(v, tol_cents=1):
    """string forms of a 2-decimal amount (abs value) incl. +-tol cents, with and without thousands separator"""
    out = []
    c0 = round(abs(v) * 100)
    for d in range(-tol_cents, tol_cents + 1):
        c = c0 + d
        if c < 0: continue
        s = f"{c / 100:.2f}"; out += [s, f"{c / 100:,.2f}"]
    return list(dict.fromkeys(out))

KEY_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")
def check_keys(spec):
    bad = [(t["tool"], k) for t in spec["tools"] for k in t.get("input_schema", {}) if not KEY_RE.match(k)]
    assert not bad, bad

def ledger(tid):
    led = [l.rstrip("\n").split("\t") for l in open(f"{TASKS}/{tid}/cost_ledger.tsv")] if os.path.exists(f"{TASKS}/{tid}/cost_ledger.tsv") else []
    cost = sum(float(l[2]) for l in led if len(l) > 2 and l[2] not in ("None", ""))
    runs = sum(1 for l in led if len(l) > 4 and l[4].startswith("ok")); retr = sum(1 for l in led if len(l) > 4 and not l[4].startswith("ok"))
    return cost, runs, retr

def fin(tid, att):
    archive_attempt(tid, att)
    ok = finish(tid)
    cost, runs, retr = ledger(tid)
    turns = json.load(open(f"{TASKS}/{tid}/run/out.json")).get("num_turns")
    c = json.load(open(f"{PACK}/{tid}/05_verifier/contract.json")); P = c.get("postconditions") or []
    neg = sum(1 for p in P if p.get("kind") == "not_exists"); pos = len(P) - neg
    st = {"run_task": ok, "cost": round(cost, 2), "gold_runs": runs, "retries": retr, "turns": turns, "pos": pos, "neg": neg}
    print(json.dumps(st)); return st


def readme(tid, sid, one_line, skel, intent, goal, world, expected, runs, accept_line, findings, standin=""):
    """pack/<tid>/README.md (skill template). skel = [(step, instance)]; world/expected/findings = lists; runs = [(n, result, turns_cost, note)]"""
    L = [f"# {tid} · {one_line}", "", f"Skeleton source {sid}" + (f"; stand-in app: {standin}" if standin else ""), "", "## Skeleton → instance", "| Skeleton step | This pack's instance |", "|---|---|"]
    L += [f"| {a} | {b} |" for a, b in skel]
    L += ["", f"Intent: {intent}.", "", "## Task", "", "> " + goal, "", "## World"] + [f"- {x}" for x in world]
    L += ["", "## Expected solution"] + [f"- {x}" for x in expected]
    L += ["", "## Live runs", "| Run | Result | Turns/cost | Note |", "|---|---|---|---|"] + [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in runs]
    L += ["", "## Acceptance", accept_line, "", "## Findings"] + ([f"- {x}" for x in findings] or ["- None"])
    open(f"{PACK}/{tid}/README.md", "w").write("\n".join(L) + "\n")

def send_steps(W, to, subject, body):
    """simulate() steps for one sent mail"""
    return [("stalwart", "email_set", {"mailbox_ids": [2], "blob_id": 1, "subject": subject, "from": W.persona, "to": to, "body": body}),
            lambda env: env.call(NS("stalwart", "emailsubmission_set"), {"identity_id": 1, "email_id": max(e["id"] for e in env.state[NS("stalwart", "Email")]), "rcpt_to": [to]})]
def sent_any(addr, *term_groups):
    """OR over alternative term tuples: sent_any(a, ("x","1.00"), ("x","1,00")) -> OR(CNT(sent_to(a,*g))...)"""
    cs = [CNT(sent_to(addr, *g)) for g in term_groups]
    return cs[0] if len(cs) == 1 else OR(*cs)

def noise(n, seed=1):
    """enron ham mails without the _src key (World.inbox rejects unknown keys)"""
    return [{k: v for k, v in m.items() if k != "_src"} for m in enron_mails(n, seed=seed)]

SIGNIN = ("Sign in to every system with its sign-in tool and the credentials above before you use it: some reads work without signing in, "
          "but sending, posting and every change are refused until you have signed in.")

def signin_note(W):
    return (f"Your own account on every system is {W.persona} with password {W.password} (the persona you act as; nobody else will provide credentials). " + SIGNIN)

def auth_hint(spec, W):
    """tonight's tclaude gold runs often end with 'I have no credentials' although the system notes carry them (8/22 runs at 02:10):
    make every auth refusal point at the credentials (pack-local guard message; runtime/spec semantics unchanged)."""
    n = 0
    for app in W.apps:
        if app not in packlib.LOGIN: continue
        lt, key = packlib.LOGIN[app]; pfx = PFX[app]
        msg = (f"Not signed in. Sign in first with {pfx}__{lt}({key}='{W.persona}', password='{W.password}') - "
               f"the account given under 'Credentials for all systems' in your Environment notes - then retry.")
        for t in spec["tools"]:
            if t["tool"].startswith(pfx + "__") and (t.get("guards") or {}).get("requires_auth"):
                t["guards"].setdefault("messages", {})["auth"] = msg; n += 1
    return n

def session_guard(spec, W, drop_mail_calendar=True):
    """pack-local fix for the shared-session trap seen tonight: a signed-in session of ANOTHER system makes this system's scoped reads return []
    silently (quill run 1: zulip get_streams -> [] -> the updates channel was never read). Tag each app's login with its realm and make that app's
    auth-guarded tools require the realm, with a message telling the agent to sign in to this system again. Also sets the auth hint.
    drop_mail_calendar: remove stalwart's JMAP calendar/contact tools when gladys is the calendar (the agent booked interviews in the mail app's calendar)."""
    auth_hint(spec, W)
    for app in W.apps:
        if app not in packlib.LOGIN: continue
        lt, key = packlib.LOGIN[app]; pfx = PFX[app]
        msg = (f"You are not signed in to this system (all systems share one session, and it currently belongs to another system). "
               f"Sign in again with {pfx}__{lt}({key}='{W.persona}', password='{W.password}') and retry.")
        for t in spec["tools"]:
            if not t["tool"].startswith(pfx + "__"): continue
            if t["tool"] == f"{pfx}__{lt}": t["auth_realm"] = app; continue
            g = t.get("guards") or {}
            if g.get("requires_auth"):
                g["auth_realm"] = app; g.setdefault("messages", {})["realm"] = msg; t["guards"] = g
    if drop_mail_calendar and "gladys" in W.apps and "stalwart" in W.apps:
        spec["tools"] = [t for t in spec["tools"] if not re.match(r"stalwart_ab__(calendar|contactcard)", t["tool"])]
    return spec

def budibase_str_ids(spec):
    """budibase worksheet / workspace ids are strings ('ws_po'), but every id-typed tool argument is declared as a JSON integer to the MCP client:
    voltline run 1 began with row_search {"sourceId": ws_rules} (unquoted), after which every call came back as __unparsedToolInput and no write landed.
    Declare the table/workspace/view id arguments of the spreadsheet tools as text (row ids stay integers)."""
    n = 0
    for t in spec["tools"]:
        if not t["tool"].startswith(PFX["budibase"] + "__"): continue
        for k, v in (t.get("input_schema") or {}).items():
            if k in ("sourceId", "tableId", "appId", "viewId", "datasourceId", "workspaceId"):
                if isinstance(v, dict) and v.get("type") == "id": v["type"] = "text"; n += 1
                elif v == "id": t["input_schema"][k] = "text"; n += 1
    return n

def sent_where(addr, where):
    """a mail actually submitted to addr whose Email row satisfies `where` (e.g. body contains X and NOT Y)"""
    E = NS("stalwart", "Email")
    return SEL(NS("stalwart", "EmailSubmission"), OR(F("email_id", "in", SEL(E, AND(F("to", "icontains", addr), where), {"col": "id"})),
                                                     AND(F("rcpt_to", "icontains", addr), F("email_id", "in", SEL(E, where, {"col": "id"})))))

def helpdesk_patch(spec):
    """chatwoot as a helpdesk (helpscout / zendesk / freshdesk / zoho desk stand-in); probed on the base spec (tgt_03):
    - conversation_update_labels inserted a Tagging row with no tag and no conversation (labels never stuck) -> set Conversation.cached_label_list
    - conversation_toggle_priority keyed on (display_id, $arg account_id) -> always 'not found' unless account_id passed -> key on display_id only
    - contact_create required phone_number (SMS stand-in) -> name required, phone optional
    - conversation_create had no subject / priority -> both added (Conversation.subject is a new text column)"""
    P = PFX["chatwoot"] + "__"
    ent = next(e for e in spec["entities"] if e["name"] == P + "Conversation")
    if not any(c["name"] == "subject" for c in ent["columns"]): ent["columns"].append({"name": "subject", "type": "text", "nullable": True})
    for t in spec["tools"]:
        n = t["tool"][len(P):] if t["tool"].startswith(P) else None
        if n == "conversation_update_labels":
            t.update({"op": "update", "family": "update.field_set", "entity": P + "Conversation",
                      "exec_spec": {"entity": P + "Conversation", "row_key": {"id": {"$arg": "conversation_id"}}, "set": {"cached_label_list": {"$arg": "labels"}}},
                      "description": "Set the labels (tags) of a conversation: labels is the FULL new list, e.g. [\"bug-report\", \"triaged\"] - pass the labels it already has plus the new one."})
            t["input_schema"] = {"conversation_id": {"type": "id", "required": True, "description": "Conversation id."}, "labels": {"type": "json", "required": True, "description": "Full list of label names."}}
            t.setdefault("guards", {})["required"] = ["conversation_id", "labels"]
            t["guards"].pop("preconditions", None)
        elif n == "conversation_toggle_priority":
            t["exec_spec"]["row_key"] = {"display_id": {"$arg": "id"}}
            t["input_schema"]["id"] = {"type": "id", "required": True, "description": "The conversation's display_id (equal to its id for every conversation here)."}
        elif n == "contact_create":
            t["input_schema"]["phone_number"] = {"type": "text", "required": False, "description": "Phone number (optional)."}
            t["input_schema"].setdefault("name", {"type": "text"})
            t["guards"]["required"] = ["name"]; t["guards"].setdefault("messages", {})["required"] = "A contact needs at least a name."
            t["description"] = "Create a contact (name, email, optional phone number)."
        elif n == "conversation_create":
            es = t["exec_spec"]; es["fields"] = list(dict.fromkeys(es.get("fields", []) + ["priority", "subject"]))
            (es.get("set_on_create") or {}).pop("priority", None)
            es.setdefault("set_on_create", {})["display_id"] = {"$auto": "max(id)+1"}
            t["input_schema"]["subject"] = {"type": "text", "required": False, "description": "Ticket subject."}
            t["input_schema"]["priority"] = {"type": "text", "required": False, "description": "low / medium / high / urgent."}
            t["description"] = "Open a conversation (ticket) with a contact in an inbox: subject, first message, optional priority."
    return spec
