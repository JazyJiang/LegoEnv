"""Register Tolgee's existing translation review and record-management tools."""
import json

import packlib
import runtime
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP = "tolgee_platform"
NEW_SERVER = {APP: "localization"}
_INFRA = {"UserAccount", "Pat", "ApiKey", "EmailVerification", "UserPreferences", "AuthProviderChangeRequest", "DismissedAnnouncement"}
NEW_CONTENT = {APP: [e["name"] for e in packlib.base(APP)["entities"] if e["name"] not in _INFRA]}
NEW_NOTES = {APP:
    "{p}__ is a Tolgee localization and translation review manager. Sign in with {p}__useraccount_authenticate(username=<your email>, password); your user id is 1. "
    "project_list(search, limit) lists project ids and description policies; project_get(projectId) reads one. "
    "key_search(projectId, search, limit), language_list(projectId, search, limit), and namespace_list(projectId, search, limit) read scoped rows. "
    "exportservice_export(format='json', keyId, languageId, limit) reads existing Translation rows including ids/text/state. "
    "translation_setstate(translationId, state) changes UNTRANSLATED/TRANSLATED to REVIEWED. "
    "translationcomment_create(translationId, text) adds a comment; translationcomment_update(commentId, translationId, text) and translationcomment_delete(commentId) edit/delete your comments. "
    "key_edit(id, name, maxCharLimit) edits an existing key; key_softdelete(ids=<one integer id>) soft-deletes it. "
    "project_edit(projectId, name, description), language_create(projectId, tag, name), language_edit(projectId, languageId, tag, name), namespace_edit(id, name) manage existing project records. "
    "The raw spec lacks a usable translation-text write, key creation and complete project creation in this login context; do not assume these operations work. "
    "Export returns records rather than a formatted file. Existing project base-language/namespace FKs cannot be reassigned by project_edit."
}
LOGIN = {APP: ("useraccount_authenticate", "username")}
SERVER[APP] = NEW_SERVER[APP]
PFX[APP] = "tolgee_platform"
CONTENT[APP] = NEW_CONTENT[APP]
NOTES[APP] = NEW_NOTES[APP]
packlib.LOGIN.update(LOGIN)

_original_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _original_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    login = env.call(NS(APP, "useraccount_authenticate"), {"username": self.persona, "password": self.password})
    if not login.get("ok"):
        raise RuntimeError(f"Tolgee observation login failed: {login}")

    def read(tool, args, suffix=""):
        value = env.call(NS(APP, tool), args)
        if not value.get("ok"):
            raise RuntimeError(f"Tolgee observation read {tool} failed: {value}")
        report[f"tolgee_platform {tool}{suffix}"] = len(json.dumps(value, ensure_ascii=False, default=str))

    read("project_list", {})
    read("project_list_with_stats", {})
    read("exportservice_export", {"format": "json"})
    for project in env.state.get(NS(APP, "Project"), []):
        for tool in ("key_search", "language_list", "namespace_list", "namespace_list_used"):
            read(tool, {"projectId": project["id"]}, f" {project['id']}")
    return report, {key: size for key, size in report.items() if size > OBS_CAP}


World.obs_report = _obs_report


def _rows(W, entity):
    return W.spec[APP]["seed_state"].setdefault(entity, [])


def _bind(W, entity, src, count):
    if src:
        W.bindings[NS(APP, entity)] = {"dataset": src, "rows": count}


def add_users(W, rows, src=None):
    """Add integer-id local accounts while retaining persona id 1."""
    for row in rows:
        if type(row.get("id")) is not int or row["id"] == 1:
            raise ValueError("Extra account ids must be integers other than 1")
        _rows(W, "UserAccount").append({"name": f"User {row['id']}", "password": f"pw-{row['id']}",
            "role": "USER", "account_type": "LOCAL", "deleted_at": None, "disabled_at": None, **row})
    _bind(W, "UserAccount", src, len(rows))


def localization_project(W, project_id, name, description="", organization_id=10,
                         languages=None, namespace_id=None, branch_id=None, src=None):
    """Seed a project, its owner memberships/permissions, languages, namespace and branch."""
    if type(project_id) is not int or type(organization_id) is not int:
        raise ValueError("Project and organization ids must be integers")
    languages = languages or [(project_id * 10 + 1, "en", "English")]
    namespace_id = namespace_id if namespace_id is not None else project_id * 10 + 3
    branch_id = branch_id if branch_id is not None else project_id * 10 + 4
    if type(namespace_id) is not int or type(branch_id) is not int or any(type(row[0]) is not int for row in languages):
        raise ValueError("Language, namespace and branch ids must be integers")
    if not any(row["id"] == organization_id for row in _rows(W, "Organization")):
        _rows(W, "Organization").append({"id": organization_id, "name": "Localization Operations",
            "address_part": f"localization-{organization_id}", "deleted_at": None})
        _rows(W, "OrganizationRole").append({"id": len(_rows(W, "OrganizationRole")) + 1,
            "organization_id": organization_id, "user_id": 1, "type": "OWNER", "managed": False})
    _rows(W, "Project").append({"id": project_id, "name": name, "description": description,
        "address_part": f"project-{project_id}", "organization_owner_id": organization_id, "user_owner_id": 1,
        "base_language_id": languages[0][0], "default_namespace_id": namespace_id,
        "is_public": False, "use_namespaces": True, "use_branching": False, "deleted_at": None})
    _rows(W, "Permission").append({"id": len(_rows(W, "Permission")) + 1,
        "organization_id": organization_id, "project_id": project_id, "user_id": 1, "type": "MANAGE"})
    for language_id, tag, language_name in languages:
        _rows(W, "Language").append({"id": language_id, "tag": tag, "name": language_name,
            "project_id": project_id, "deleted_at": None})
    _rows(W, "Namespace").append({"id": namespace_id, "name": "main", "project_id": project_id})
    _rows(W, "Branch").append({"id": branch_id, "name": "main", "project_id": project_id,
        "is_default": True, "is_protected": False, "pending": False, "revision": 1, "author_id": 1})
    _bind(W, "Project", src, 1)
    return {"project_id": project_id, "namespace_id": namespace_id, "branch_id": branch_id}


def keys(W, project_id, rows, namespace_id=None, branch_id=None, src=None):
    """Seed integer-id translation keys with existing project/namespace/branch references."""
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Key ids must be integers")
        item = {"project_id": project_id, "is_plural": False, "max_char_limit": 60, "deleted_at": None, **row}
        if namespace_id is not None:
            item["namespace_id"] = namespace_id
        if branch_id is not None:
            item["branch_id"] = branch_id
        _rows(W, "Key").append(item)
    _bind(W, "Key", src, len(rows))


def translations(W, rows, src=None):
    """Seed translations for review; no translation-text write tool is fabricated."""
    for row in rows:
        if any(type(row.get(key)) is not int for key in ("id", "key_id", "language_id")):
            raise ValueError("Translation, key and language ids must be integers")
        _rows(W, "Translation").append({"state": "TRANSLATED", "auto": False, "outdated": False,
            "qa_checks_stale": False, **row})
    _bind(W, "Translation", src, len(rows))


def comments(W, translation_id, rows, author_id=1, src=None):
    """Seed owned translation comments for update/delete tools."""
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Comment ids must be integers")
        _rows(W, "TranslationComment").append({"translation_id": translation_id, "author_id": author_id,
            "state": 0, **row})
    _bind(W, "TranslationComment", src, len(rows))


def smoke_seed(W):
    project = localization_project(W, 101, "Service Portal",
        description="Policy: review the approved French service-hours translation only; leave the legal footer pending legal review.",
        languages=[(201, "en", "English"), (202, "fr", "French")], namespace_id=301, branch_id=401)
    keys(W, 101, [{"id":501,"name":"service.hours"}, {"id":502,"name":"signup.cta"},
                  {"id":503,"name":"legal.footer"}], namespace_id=301, branch_id=401)
    translations(W, [
        {"id":601,"key_id":501,"language_id":202,"text":"Horaires : du lundi au vendredi, de 9 h à 17 h."},
        {"id":602,"key_id":502,"language_id":202,"text":"Créer un compte"},
        {"id":603,"key_id":503,"language_id":202,"text":"Mentions légales en attente de validation."},
    ])
    comments(W, 601, [{"id":701,"text":"Terminology review pending."}])
    steps = [
        (APP,"translation_setstate",{"translationId":601,"state":"REVIEWED"}),
        (APP,"translationcomment_create",{"translationId":601,"text":"Approved service hours after terminology review."}),
        (APP,"key_edit",{"id":501,"maxCharLimit":80}),
    ]
    predicates = [
        ("translation_reviewed","The approved French service-hours translation is reviewed", CNT(SEL(NS(APP,"Translation"), AND(F("id","eq",601),F("state","eq","REVIEWED")))),False),
        ("review_comment","The terminology-review note is attached", CNT(SEL(NS(APP,"TranslationComment"), AND(F("translation_id","eq",601),F("text","eq","Approved service hours after terminology review.")))),False),
        ("key_limit_updated","The service-hours key character limit is updated", CNT(SEL(NS(APP,"Key"), AND(F("id","eq",501),F("max_char_limit","eq",80)))),False),
        ("legal_unreviewed","The legal footer remains unreviewed", CNT(SEL(NS(APP,"Translation"), AND(F("id","eq",603),F("state","eq","REVIEWED"))),"eq",0),True),
    ]
    return steps, predicates


__all__ = ["NEW_SERVER", "NEW_CONTENT", "NEW_NOTES", "LOGIN", "add_users", "localization_project", "keys", "translations", "comments", "smoke_seed"]
