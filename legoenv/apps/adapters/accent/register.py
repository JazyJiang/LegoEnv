"""Register Accent's deterministic localization record and comment tools."""
import json

import packlib
import runtime
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP = "accent"
NEW_SERVER = {APP: "localization_collaboration"}
_INFRA = {"User", "AuthProvider", "AccessToken", "Language"}
NEW_CONTENT = {APP: [e["name"] for e in packlib.base(APP)["entities"] if e["name"] not in _INFRA]}
NEW_NOTES = {APP:
    "{p}__ is Accent localization collaboration. Sign in with {p}__sign_in(email, password); your user id is 1. "
    "project_list_viewer(query, limit) lists projects; project_show_viewer(id) reads one. "
    "project_create(name, main_color, language_id) creates a project, its master revision and your owner collaborator row; language_list(query, limit) lists language ids. "
    "document_list_project(project_id, query, limit) and document_show_project(project_id, id) expose the policy in top_of_the_file_comment. "
    "translation_list_project(project_id, query, limit) and translation_list_revision(revision_id, query, limit) read existing translations. "
    "translation_update_settings(id, locked, file_comment, plural, placeholders) edits settings. "
    "comment_create(id=<translation id>, text), comment_update(id=<comment id>, text), comment_delete(id=<comment id>), and comment_list_translation(translation_id, query, limit) manage comments. "
    "prompt_create(project_id, name, content), prompt_update(id, content), prompt_delete(id) manage prompt records. "
    "revision_create(project_id, language_id, name, slug), revision_update(id, name, slug), revision_delete(id) manage revisions. "
    "version_create(project_id, name, tag), version_update(id, name, tag, copy_on_update_translation), and document_update(id, path) manage snapshots and paths. "
    "project_update(id, name, main_color, is_file_operations_locked) edits project settings. "
    "The translation_update/correct tools only log Operations and do not change translation text. Repeated comment_create for one translation can duplicate comment ids. "
    "There is no actual MT/LLM inference or formatted export guarantee."
}
LOGIN = {APP: ("sign_in", "email")}
SERVER[APP] = NEW_SERVER[APP]
PFX[APP] = "accent"
CONTENT[APP] = NEW_CONTENT[APP]
NOTES[APP] = NEW_NOTES[APP]
packlib.LOGIN.update(LOGIN)
_original_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _original_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    login = env.call(NS(APP,"sign_in"), {"email":self.persona,"password":self.password})
    if not login.get("ok"):
        raise RuntimeError(f"Accent observation login failed: {login}")

    def read(tool, args, suffix=""):
        value = env.call(NS(APP,tool),args)
        if not value.get("ok"):
            raise RuntimeError(f"Accent observation read {tool} failed: {value}")
        report[f"accent {tool}{suffix}"] = len(json.dumps(value,ensure_ascii=False,default=str))

    read("project_list_viewer",{})
    read("language_list",{})
    for project in env.state.get(NS(APP,"Project"),[]):
        for tool in ("revision_list_project","document_list_project","version_list_project","translation_list_project","activity_list_project"):
            read(tool,{"project_id":project["id"]},f" {project['id']}")
    for revision in env.state.get(NS(APP,"Revision"),[]):
        read("translation_list_revision",{"revision_id":revision["id"]},f" {revision['id']}")
    for translation in env.state.get(NS(APP,"Translation"),[]):
        read("comment_list_translation",{"translation_id":translation["id"]},f" {translation['id']}")
    return report,{key:size for key,size in report.items() if size>OBS_CAP}


World.obs_report = _obs_report


def _rows(W,entity):
    return W.spec[APP]["seed_state"].setdefault(entity,[])


def _bind(W,entity,src,count):
    if src:
        W.bindings[NS(APP,entity)]={"dataset":src,"rows":count}


def add_users(W,rows,src=None):
    for row in rows:
        if type(row.get("id")) is not int or row["id"]==1:
            raise ValueError("Extra user ids must be integers other than 1")
        _rows(W,"User").append({"password":f"pw-{row['id']}","bot":False,**row})
    _bind(W,"User",src,len(rows))


def localization_project(W,project_id,name,policy="",master_revision_id=None,target_revision_id=None,
                         source_document_id=None,target_document_id=None,src=None):
    """Seed a complete owner-managed project using the base English/French catalog."""
    if type(project_id) is not int:
        raise ValueError("Project id must be an integer")
    master_revision_id=master_revision_id if master_revision_id is not None else project_id*10+1
    target_revision_id=target_revision_id if target_revision_id is not None else project_id*10+2
    source_document_id=source_document_id if source_document_id is not None else project_id*10+3
    target_document_id=target_document_id if target_document_id is not None else project_id*10+4
    if any(type(identifier) is not int for identifier in [master_revision_id,target_revision_id,source_document_id,target_document_id]):
        raise ValueError("Revision and document ids must be integers")
    _rows(W,"Project").append({"id":project_id,"name":name,"main_color":"#2874cb","language_id":1,
        "locked_file_operations":False,"sync_lock_version":0})
    _rows(W,"Collaborator").append({"id":len(_rows(W,"Collaborator"))+1,"email":W.persona,
        "role":"owner","user_id":1,"project_id":project_id,"assigner_id":1})
    _rows(W,"Revision").extend([
        {"id":master_revision_id,"project_id":project_id,"language_id":1,"master":True,
         "master_revision_id":None,"name":"master","slug":"master","marked_as_deleted":False},
        {"id":target_revision_id,"project_id":project_id,"language_id":2,"master":False,
         "master_revision_id":master_revision_id,"name":"French","slug":"fr","marked_as_deleted":False},
    ])
    _rows(W,"Document").extend([
        {"id":source_document_id,"project_id":project_id,"path":f"p{project_id}/en/strings.json","format":"json","top_of_the_file_comment":policy},
        {"id":target_document_id,"project_id":project_id,"path":f"p{project_id}/fr/strings.json","format":"json","top_of_the_file_comment":policy},
    ])
    _bind(W,"Project",src,1)
    return {"master_revision_id":master_revision_id,"target_revision_id":target_revision_id,
            "source_document_id":source_document_id,"target_document_id":target_document_id}


def translations(W,revision_id,document_id,rows,src=None):
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Translation ids must be integers")
        _rows(W,"Translation").append({"revision_id":revision_id,"document_id":document_id,
            "proposed_text":"","corrected_text":None,"conflicted":False,"removed":False,
            "comments_count":0,"value_type":"string","plural":False,"locked":False,"translated":False,
            "placeholders":[],"source_translation_id":None,**row})
    _bind(W,"Translation",src,len(rows))


def comments(W,translation_id,rows,user_id=1,src=None):
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Comment ids must be integers")
        _rows(W,"Comment").append({"translation_id":translation_id,"user_id":user_id,**row})
    _bind(W,"Comment",src,len(rows))


def prompts(W,project_id,rows,author_id=1,src=None):
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Prompt ids must be integers")
        _rows(W,"Prompt").append({"project_id":project_id,"author_id":author_id,**row})
    _bind(W,"Prompt",src,len(rows))


def smoke_seed(W):
    localization_project(W,101,"Service Portal",policy="Policy: approve the service-hours settings and add a review note; leave the legal footer unlocked pending legal review.",
        master_revision_id=301,target_revision_id=302,source_document_id=401,target_document_id=402)
    translations(W,301,401,[{"id":501,"key":"service.hours","proposed_text":"Weekdays 09:00-17:00","corrected_text":"Weekdays 09:00-17:00","translated":True}])
    translations(W,302,402,[
        {"id":502,"key":"service.hours","proposed_text":"Du lundi au vendredi, de 9 h à 17 h.","conflicted":True},
        {"id":503,"key":"legal.footer","proposed_text":"Mentions légales à valider.","conflicted":True},
    ])
    comments(W,502,[{"id":601,"text":"Terminology approval pending."}])
    prompts(W,101,[{"id":701,"name":"Editorial guidance","content":"Prefer approved service terminology."}])
    steps=[
        (APP,"translation_update_settings",{"id":502,"locked":True,"file_comment":"Terminology review approved."}),
        (APP,"comment_create",{"id":502,"text":"Approved service hours for publication."}),
        (APP,"prompt_create",{"project_id":101,"name":"Approved service style","content":"Use approved service terminology and preserve legal-review holds."}),
    ]
    predicates=[
        ("settings_locked","Approved service-hours settings are locked",CNT(SEL(NS(APP,"Translation"),AND(F("id","eq",502),F("locked","eq",True)))),False),
        ("review_note","The publication review note exists",CNT(SEL(NS(APP,"Comment"),AND(F("translation_id","eq",502),F("text","eq","Approved service hours for publication.")))),False),
        ("prompt_created","The approved-service prompt exists",CNT(SEL(NS(APP,"Prompt"),AND(F("project_id","eq",101),F("name","eq","Approved service style")))),False),
        ("legal_unlocked","The legal footer remains unlocked",CNT(SEL(NS(APP,"Translation"),AND(F("id","eq",503),F("locked","eq",True))),"eq",0),True),
    ]
    return steps,predicates


__all__=["NEW_SERVER","NEW_CONTENT","NEW_NOTES","LOGIN","add_users","localization_project","translations","comments","prompts","smoke_seed"]
