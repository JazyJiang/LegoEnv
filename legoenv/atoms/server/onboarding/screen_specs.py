#!/usr/bin/env python3
"""screen_specs.py --out DIR [--spec-tools FILE] [--layer2 + endpoint flags] - screen compiled specs as onboarding candidates.
Layer 1 (deterministic, from spec_tools.json): keep specs with write >= 5, search >= 3, an auth block and <= 350 tools -> DIR/spec_layer1.txt.
Layer 2 (--layer2, one model call per survivor): business relevance, software category, domains, possible carriers (long text
fields), suggested stand-in role, tool families to keep -> DIR/specs/<app>.screen.json + DIR/spec_screen.tsv.
Endpoint flags: --base-url (or OPENAI_BASE_URL), --model (or OPENAI_MODEL), --api-key-env, --extra-body, --max-tokens."""
import argparse, json, os, sys, re, collections, concurrent.futures as cf
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools"))
from llm_client import add_endpoint_args, chat
HERE = os.path.dirname(os.path.abspath(__file__))
ap = add_endpoint_args(argparse.ArgumentParser(description=__doc__.splitlines()[0]), required=False)
ap.add_argument("--out", required=True)
ap.add_argument("--spec-tools", default=os.path.join(HERE, "..", "..", "..", "skeleton", "spec_tools.json"), help="written by export_spec_tools.py")
ap.add_argument("--layer2", action="store_true")
ap.add_argument("--workers", type=int, default=8)
A = ap.parse_args()
IDX = json.load(open(A.spec_tools)); OUT = os.path.join(A.out, "specs"); os.makedirs(OUT, exist_ok=True)
l1 = [app for app, s in sorted(IDX.items()) if len(s["write"]) >= 5 and len(s["search"]) >= 3 and s.get("auth") and len(s["tools"]) <= 350]
print("specs", len(IDX), "layer1 survivors", len(l1))
open(os.path.join(A.out, "spec_layer1.txt"), "w").write("\n".join(l1) + "\n")
if not A.layer2: sys.exit(0)
if not (A.base_url and A.model): ap.error("--layer2 needs --base-url and --model (or OPENAI_BASE_URL / OPENAI_MODEL)")
P = """You classify an open-source web application (exposed to an agent as an API tool set) for use as a BUSINESS-AUTOMATION training environment.
App: {app}
About: {about}
Entities (tables): {ents}
Sample write tools: {wt}
Sample search tools: {st}
Long text fields that could hold a policy text: {tf}
Answer ONE JSON object:
{{"business_relevance": 0-3,   // 3 = core business ops software (CRM/helpdesk/ERP/HR/finance/PM/docs/mail/chat/scheduling); 0 = media/consumer/dev-tooling with no business records
 "software_category": "<short label, e.g. CRM, helpdesk, invoicing, HR, LMS, inventory, wiki, chat, mail, calendar, e-signature, project mgmt, forms, ...>",
 "stand_in_for": ["<well-known SaaS it resembles>", ...],
 "domains": [<1-4 of: sales, marketing, operations, support, finance, hr, legal, procurement, logistics, healthcare, education, real_estate, manufacturing, nonprofit, hospitality, government, it_ops, research, media, other>],
 "record_entities": ["<entities that hold business records an agent would scan and act on>", ...],
 "carriers_possible": [<any of: policy_sheet (tabular rows), policy_mail, notes_field (long text on a record), policy_doc (documents), card_description>],
 "kinds_possible": ["<from: send_email, append_row, update_cell, post_channel, send_dm, update_record, create_record, attach_note_or_task, schedule_event, create_meeting, book_meeting, send_envelope, add_signer, create_or_move_card, create_or_update_issue, create_or_update_doc, manage_subscriber_or_campaign, post_or_schedule_status, append_or_update_item, file_or_folder_op, helpdesk_reply_or_update, other:<name>>", ...],
 "tool_families_to_keep": ["<prefixes of the tools a task would need; drop admin/config/auth-management families>", ...],
 "onboarding_risk": "low|medium|high", "why": "<one sentence>"}}"""
def one(app):
    s = IDX[app]
    msg = P.format(app=app, about=s.get("about", ""), ents=", ".join(list(s["entities"])[:40]), wt=", ".join(s["write"][:30]), st=", ".join(s["search"][:15]), tf=", ".join(s["text_fields"][:15]) or "none found")
    err = None
    for _ in range(3):
        try:
            j = json.loads(re.search(r"\{.*\}", chat(A, msg), re.S).group(0)); j["app"] = app
            j.update({"tools": len(s["tools"]), "write": len(s["write"]), "search": len(s["search"])}); return j
        except Exception as e: err = e
    return {"app": app, "error": type(err).__name__}
res = []
with cf.ThreadPoolExecutor(A.workers) as ex:
    for j in ex.map(one, l1): res.append(j); json.dump(j, open(os.path.join(OUT, f"{j['app']}.screen.json"), "w"), ensure_ascii=False, indent=1)
ok = [j for j in res if "error" not in j]
with open(os.path.join(A.out, "spec_screen.tsv"), "w") as fo:
    fo.write("app\trelevance\tcategory\tdomains\tcarriers\tkinds\ttools\twrite\tsearch\trisk\tonboarded\n")
    for j in sorted(ok, key=lambda j: (-int(j.get("business_relevance") or 0), j["app"])):
        fo.write("\t".join([j["app"], str(j.get("business_relevance")), j.get("software_category", ""), ",".join(j.get("domains", [])), ",".join(j.get("carriers_possible", [])), ",".join(j.get("kinds_possible", [])), str(j["tools"]), str(j["write"]), str(j["search"]), j.get("onboarding_risk", ""), str(int(IDX[j["app"]]["onboarded"]))]) + "\n")
print("classified", len(ok), "errors", len(res) - len(ok)); print("relevance:", collections.Counter(j.get("business_relevance") for j in ok)); print("domains:", collections.Counter(d for j in ok for d in j.get("domains", [])).most_common(20))
