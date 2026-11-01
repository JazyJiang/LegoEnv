"""Register the Ghost publishing spec with packlib; no shared library changes."""
import json

import runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, SEL, F, AND, CNT, OBS_CAP

APP = "ghost"
NEW_SERVER = {APP: "publishing"}
# All domain data is pack-local. Authentication and site configuration stay in the base.
_INFRA = {"User", "Role", "RoleUser", "Permission", "PermissionUser", "PermissionRole", "Setting", "BruteForce", "Session"}
_base_entities = packlib.base(APP)["entities"]
NEW_CONTENT = {APP: [e["name"] for e in _base_entities if e["name"] not in _INFRA]}
NEW_NOTES = {
    APP: "{p}__ is the Ghost publication desk. Sign in with {p}__sign_in_staff(email, password); you are staff user 1. "
         "post_browse(search, limit) finds posts by title; post_read(id) reads the full html. "
         "post_add(title, slug, html, status, type) creates a post; provide a unique slug. "
         "post_edit(id, title, html, status, published_at) edits a seeded authored post; post_destroy(id) permanently deletes it. "
         "Seeded PostAuthor rows grant authorship for the persona. newsletter_browse(search, limit) lists newsletters. "
         "users_browse(search, limit) lists staff. tag_add(name, slug, description) creates metadata. "
         "The compiler spec does not implement post authors/tags/meta relation writes or copying source content; do not assume those effects."
}
LOGIN = {APP: ("sign_in_staff", "email")}
SERVER[APP] = NEW_SERVER[APP]
PFX[APP] = "ghost"
CONTENT[APP] = NEW_CONTENT[APP]
NOTES[APP] = NEW_NOTES[APP]
packlib.LOGIN.update(LOGIN)

_original_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _original_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    login = env.call(NS(APP, "sign_in_staff"), {"email": self.persona, "password": self.password})
    if not login.get("ok"):
        raise RuntimeError(f"Ghost observation login failed: {login}")
    # Measure the real whole-list responses; reject oversized worlds instead of truncating
    # them silently. Builders can narrow browse reads with the patched search argument.
    for tool in ("post_browse", "newsletter_browse", "users_browse"):
        result = env.call(NS(APP, tool), {})
        if not result.get("ok"):
            raise RuntimeError(f"Ghost observation read {tool} failed: {result}")
        report[f"ghost {tool}"] = len(json.dumps(result, ensure_ascii=False, default=str))
    return report, {key: size for key, size in report.items() if size > OBS_CAP}


World.obs_report = _obs_report


def _rows(W, entity):
    return W.spec[APP]["seed_state"].setdefault(entity, [])


def _bind(W, entity, source, count):
    if source:
        W.bindings[NS(APP, entity)] = {"dataset": source, "rows": count}


def add_users(W, rows, src=None):
    """Append staff accounts with integer ids; persona id 1 remains first."""
    for row in rows:
        if type(row.get("id")) is not int or row["id"] == 1:
            raise ValueError("Extra staff ids must be integers other than 1")
        _rows(W, "User").append({"status": "active", "visibility": "public", "created_at": W.now,
                                  "slug": f"staff-{row['id']}", "password": f"pw-{row['id']}", **row})
    _bind(W, "User", src, len(rows))


def publication(W, newsletter_id=10, name="Editorial Briefing", description="", src=None):
    """Seed an active newsletter required by existing publication guards."""
    if type(newsletter_id) is not int:
        raise ValueError("Newsletter id must be an integer")
    _rows(W, "Newsletter").append({"id": newsletter_id, "uuid": f"newsletter-{newsletter_id}",
        "name": name, "slug": f"newsletter-{newsletter_id}", "description": description,
        "status": "active", "sender_reply_to": "newsletter", "sender_email": W.persona,
        "created_at": W.now, "updated_at": W.now})
    _bind(W, "Newsletter", src, 1)
    return newsletter_id


def posts(W, rows, newsletter_id=None, author_id=1, src=None):
    """Seed integer-id Post rows plus matching PostAuthor rows for existing guards."""
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Post id must be an integer")
        post = {"uuid": f"post-{row['id']}", "slug": f"post-{row['id']}", "type": "post",
                "status": "draft", "visibility": "public", "email_recipient_filter": "all",
                "created_at": W.now, "updated_at": W.now, "featured": False, **row}
        if newsletter_id is not None:
            post["newsletter_id"] = newsletter_id
        _rows(W, "Post").append(post)
        _rows(W, "PostAuthor").append({"id": len(_rows(W, "PostAuthor")) + 1,
            "post_id": row["id"], "author_id": author_id, "sort_order": 0})
    _bind(W, "Post", src, len(rows))


def smoke_seed(W):
    newsletter_id = publication(W)
    posts(W, [
        {"id": 101, "title": "Autumn service schedule", "html": "<p>Service times awaiting editorial approval.</p>"},
        {"id": 102, "title": "Contributor checklist", "html": "<p>Policy: publish only approved service schedules; leave contributor drafts unchanged.</p>", "type": "page"},
        {"id": 103, "title": "Contributor profile draft", "html": "<p>Interview awaiting contributor consent.</p>"},
    ], newsletter_id=newsletter_id)
    steps = [(APP, "post_edit", {"id": 101, "status": "published", "html": "<p>Approved autumn service schedule: weekdays 09:00–17:00.</p>"})]
    predicates = [
        ("published", "The service schedule is published", CNT(SEL(NS(APP, "Post"), AND(F("id", "eq", 101), F("status", "eq", "published")))), False),
        ("approved_content", "The schedule contains the approved service times", CNT(SEL(NS(APP, "Post"), AND(F("id", "eq", 101), F("html", "icontains", "weekdays 09:00–17:00")))), False),
        ("consent_draft_unchanged", "The contributor draft remains unpublished", CNT(SEL(NS(APP, "Post"), AND(F("id", "eq", 103), F("status", "ne", "draft"))), "eq", 0), True),
    ]
    return steps, predicates


__all__ = ["NEW_SERVER", "NEW_CONTENT", "NEW_NOTES", "LOGIN", "add_users", "publication", "posts", "smoke_seed"]
