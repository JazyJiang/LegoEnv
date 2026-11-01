"""register.py — attach the paperless_ngx spec (a self-hosted document management system) to packlib
WITHOUT editing packlib.py (the main session folds this in later via `from newspecs3.paperless_ngx.register import *`).

    import sys; sys.path.insert(0, "/builder/smoke/pack")
    from packlib import *
    from newspecs3.paperless_ngx.register import *     # registers paperless_ngx into SERVER/PFX/CONTENT/NOTES/LOGIN + obs hook + seed helpers + smoke_seed

The base lives in pack/base_specs/paperless_ngx.spec.json (built from the Env Compiler release spec by make_base.py;
patch ledger in register.txt and smoke/PATCHES.md). It holds the persona account (id 1, ops@…/pw-operations, renamed by
World like the other bases); content entities are empty — seed them with the helpers below or W.seed(app, entity, rows).

The environment is paperless-ngx (a DMS), a stand-in for document-management SaaS (Dropbox Business / M-Files / DocuWare).
Documents are the records; correspondents are senders/recipients; tags categorize; document types / storage paths /
custom fields add structure; notes attach to documents. A document's `content` field holds its full text, so a policy
document (carrier `policy_doc` = {Document, content}) is the natural place to seed rule text.
"""
import json, runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP = "paperless_ngx"
NEW_SERVER = {APP: "dms"}
NEW_CONTENT = {APP: ["Document", "Note", "Correspondent", "Tag", "DocumentType", "StoragePath", "CustomField"]}
NEW_NOTES = {APP: ("{p}__ is the document management system (paperless style): sign in with {p}__sign_in(username, password). "
                   "document_list(q, title_search, archive_serial_number, correspondent) lists documents (filter by a title/content "
                   "substring, an archive serial number, or a correspondent); document_retrieve(pk) reads one in full (its `content` "
                   "is the document text). Metadata: correspondent_list / tag_list / documenttype_list / customfield_list. Write tools: "
                   "document_update(pk, title, content, correspondent, document_type, storage_path, tags, archive_serial_number, "
                   "custom_fields) updates a document; document_note_create(pk, note) adds a note; tag_create(name) / "
                   "correspondent_create(name) / documenttype_create(name) create metadata; document_post_document uploads a new file "
                   "(spawns an async consume task).")}
LOGIN = {APP: ("sign_in", "username")}

SERVER.setdefault(APP, NEW_SERVER[APP]); PFX.setdefault(APP, APP)
CONTENT.setdefault(APP, NEW_CONTENT[APP]); NOTES.setdefault(APP, NEW_NOTES[APP])
packlib.LOGIN.update({APP: LOGIN[APP]})   # simulate()/login() sign in to this app too

# ───────── whole-list reads the agent will make (12k observation cap) ─────────
_orig_obs = World.obs_report
def _obs_report(self):
    rep, bad = _orig_obs(self)
    if APP not in self.apps: return rep, bad
    env = runtime.Env(self.world)
    env.call(NS(APP, "sign_in"), {"username": self.persona, "password": self.password})
    def rd(tool, args): return len(json.dumps(env.call(NS(APP, tool), args), ensure_ascii=False, default=str))
    rep["paperless_ngx document_list"] = rd("document_list", {})
    rep["paperless_ngx tag_list"] = rd("tag_list", {})
    rep["paperless_ngx correspondent_list"] = rd("correspondent_list", {})
    bad = {k: v for k, v in rep.items() if v > OBS_CAP}
    return rep, bad
World.obs_report = _obs_report

# ───────── seeding helpers ─────────
TS = "2026-01-01T00:00:00"
def _ss(W, app): return W.spec[app]["seed_state"]
def _bind(W, app, ent, src, n):
    if src: W.bindings[NS(app, ent)] = {"dataset": src, "rows": n}

def seed_documents(W, docs, src=None):
    """paperless_ngx: `docs = [{id, title, content, created?, correspondent_id?, document_type_id?, tags?: int-id?}]`.
    Fills the NOT NULL defaults (content_length, mime_type, checksum, added). Owner = persona (id 1)."""
    ss = _ss(W, APP)
    for d in docs:
        ss.setdefault("Document", []).append({
            "id": d["id"], "title": d["title"], "content": d.get("content", ""), "created": d.get("created", TS),
            "added": d.get("created", TS), "correspondent_id": d.get("correspondent_id"), "document_type_id": d.get("document_type_id"),
            "storage_path_id": d.get("storage_path_id"), "owner_id": 1, "mime_type": d.get("mime_type", "application/pdf"),
            "checksum": d.get("checksum", f"chk{d['id']}"), "content_length": int(d.get("content_length") or len(d.get("content", ""))),
            "archive_serial_number": d.get("archive_serial_number")})
    _bind(W, APP, "Document", src, len(docs))

def seed_metadata(W, correspondents=(), tags=(), doc_types=(), storage_paths=(), custom_fields=(), src=None):
    """paperless_ngx metadata: all take (id, name) tuples; custom_fields take (id, name, data_type). Owner = persona (id 1)."""
    ss = _ss(W, APP)
    for cid, nm in correspondents: ss.setdefault("Correspondent", []).append({"id": cid, "name": nm, "owner_id": 1})
    for tid, nm in tags: ss.setdefault("Tag", []).append({"id": tid, "name": nm, "owner_id": 1})
    for dtid, nm in doc_types: ss.setdefault("DocumentType", []).append({"id": dtid, "name": nm, "owner_id": 1})
    for spid, nm, path in storage_paths: ss.setdefault("StoragePath", []).append({"id": spid, "name": nm, "path": path, "owner_id": 1})
    for cfid, nm, dt in custom_fields: ss.setdefault("CustomField", []).append({"id": cfid, "name": nm, "data_type": dt})
    _bind(W, APP, "Correspondent", src, len(correspondents))

def seed_notes(W, notes):
    """paperless_ngx: `notes = [{id, document_id, note, user_id?}]` (user_id defaults to the persona, 1)."""
    ss = _ss(W, APP)
    for n in notes:
        ss.setdefault("Note", []).append({"id": n["id"], "document_id": n["document_id"], "note": n["note"],
                                          "user_id": n.get("user_id", 1), "created": TS})

# ───────── smoke: seeds >= 3 content rows + one policy text (carrier policy_doc = Document.content),
#          returns gold steps [(app, tool, args)...] that do one write, and >= 3 contract predicates incl. one negative. ─────────
def smoke_seed(W):
    # Three invoices + one policy document whose `content` holds the literal policy text (the carrier).
    seed_documents(W, [
        {"id": 101, "title": "AP Approval Policy", "content": ("Invoice approval policy: any invoice at or above $1,000 must be "
                                                                "approved by finance. The approved invoice is noted in the documents. "*4)},
        {"id": 102, "title": "Invoice #2291 - Acme Corp", "content": "Invoice #2291 from Acme Corp for $1,200.00, payable in 30 days.", "correspondent_id": 1},
        {"id": 103, "title": "Invoice #1121 - Beta Ltd", "content": "Invoice #1121 from Beta Ltd for $400.00, payable in 30 days.", "correspondent_id": 2},
        {"id": 104, "title": "Receipt - Office Supplies", "content": "Office supplies receipt for $80.00.", "correspondent_id": 3},
    ])
    seed_metadata(W, correspondents=[(1, "Acme Corp"), (2, "Beta Ltd"), (3, "Office Mart")], tags=[(1, "invoice")])
    seed_notes(W, [{"id": 1, "document_id": 104, "note": "matched to petty cash"}])

    # gold solution: one write — note the over-threshold invoice as approved by finance (doc 102, the $1,200 one).
    steps = [(APP, "document_note_create", {"pk": 102, "note": "approved by finance"})]

    # contract predicates built with packlib SEL/F/AND/CNT on this app's entities.
    # Every positive is witnessed by the single write (dropping it flips it False); the negative is falsifiable.
    D = NS(APP, "Document"); N = NS(APP, "Note")
    preds = [
        ("p_ok_approved", "a note was added to document 102 saying approved by finance",
         CNT(SEL(N, AND(F("document_id", "eq", 102), F("note", "icontains", "approved")))), False),
        ("p_ok_finance", "the note on document 102 names finance",
         CNT(SEL(N, AND(F("document_id", "eq", 102), F("note", "icontains", "finance")))), False),
        ("p_neg_not_103", "no note was added to document 103 (the below-threshold invoice)",
         CNT(SEL(N, F("document_id", "eq", 103)), "eq", 0), True),
    ]
    return steps, preds

__all__ = ["NEW_SERVER", "seed_documents", "seed_metadata", "seed_notes", "smoke_seed"]
