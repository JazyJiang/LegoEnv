"""Register TeamPass's actual credential and administrative record tools."""
import json

import packlib
import runtime
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP="teampass"
NEW_SERVER={APP:"credential_vault"}
_INFRA={"User","ApiSession","ApiKey","ApiToken","ApiRateLimit","AuthFailure","UserPrivateKey","WebsocketConnection","WebsocketToken","Token","Language"}
NEW_CONTENT={APP:[e["name"] for e in packlib.base(APP)["entities"] if e["name"] not in _INFRA]}
NEW_NOTES={APP:
    "{p}__ is TeamPass credential and access-review record management. Sign in with {p}__sign_in(login=<your email>, password); you are admin user 1. "
    "apifolder_list(search, limit) lists folder ids/titles; apiuser_list(search, limit) lists users. "
    "apimisc_refreshsettings(search='rotation_policy', limit) reads the policy from Misc.valeur. "
    "items_getpassword(itemId) reads a known item's stored fields when your share key is seeded. There is no item list/search tool. "
    "items_create(label, folder, login, pw, description) creates a record; items_update(itemId, pw, description), items_move(itemId, folder), items_delete(itemId) update/move/soft-delete it. "
    "nestedtree_create(title, parentId) and nestedtree_update(id, title, renewalPeriod) manage folders. "
    "kb_save(id, label, description, category) updates a seeded KB entry; kbcomment_add(kbId, content) comments, kb_delete(id) soft-deletes. "
    "laprpolicy_create(label, frequency_days, password_length), laprpolicy_update(id, frequency_days), laprpolicy_delete(id) manage rotation-policy metadata only. "
    "accessreview_create(label, folder_scope), accessreviewitem_decide(item_id, decision, comment), accessreview_close(review_id), accessreview_export(review_id, search, limit) manage review records. "
    "A new item does not automatically gain share keys; review decisions do not revoke actual grants, and raw pw storage is not real cryptography or external rotation."
}
LOGIN={APP:("sign_in","login")}
SERVER[APP]=NEW_SERVER[APP]
PFX[APP]="teampass"
CONTENT[APP]=NEW_CONTENT[APP]
NOTES[APP]=NEW_NOTES[APP]
packlib.LOGIN.update(LOGIN)
_original_obs_report=World.obs_report


def _obs_report(self):
    report,bad=_original_obs_report(self)
    if APP not in self.apps:
        return report,bad
    env=runtime.Env(self.world)
    login=env.call(NS(APP,"sign_in"),{"login":self.persona,"password":self.password})
    if not login.get("ok"):
        raise RuntimeError(f"TeamPass observation login failed: {login}")

    def read(tool,args,suffix=""):
        result=env.call(NS(APP,tool),args)
        if not result.get("ok"):
            raise RuntimeError(f"TeamPass observation read {tool} failed: {result}")
        report[f"teampass {tool}{suffix}"]=len(json.dumps(result,ensure_ascii=False,default=str))

    for tool in ("apifolder_list","apiuser_list","apimisc_refreshsettings"):
        read(tool,{})
    for review in env.state.get(NS(APP,"AccessReview"),[]):
        read("accessreview_export",{"review_id":review["id"]},f" {review['id']}")
    return report,{key:size for key,size in report.items() if size>OBS_CAP}


World.obs_report=_obs_report


def _rows(W,entity):
    return W.spec[APP]["seed_state"].setdefault(entity,[])


def _bind(W,entity,src,count):
    if src:
        W.bindings[NS(APP,entity)]={"dataset":src,"rows":count}


def add_users(W,rows,src=None):
    for row in rows:
        if type(row.get("id")) is not int or row["id"]==1:
            raise ValueError("Extra user ids must be integers other than 1")
        _rows(W,"User").append({"pw":f"pw-{row['id']}","admin":0,"gestionnaire":0,
            "can_manage_lapr":0,"read_only":0,"disabled":0,**row})
    _bind(W,"User",src,len(rows))


def policy(W,text,src=None):
    _rows(W,"Misc").append({"id":1,"increment_id":1,"type":"policy","intitule":"rotation_policy","valeur":text,"is_encrypted":0})
    _bind(W,"Misc",src,1)


def vault(W,folders=None,src=None):
    """Seed integer-id folders and persona role grants; no live vault is accessed."""
    folders=folders or [{"id":100,"parent_id":0,"title":"Vault Base"},
        {"id":101,"parent_id":100,"title":"Service accounts"},
        {"id":102,"parent_id":100,"title":"Quarantine"}]
    for folder in folders:
        if type(folder.get("id")) is not int:
            raise ValueError("Folder ids must be integers")
        _rows(W,"NestedTree").append({"nleft":0,"nright":0,"nlevel":0,"bloquer_creation":0,
            "bloquer_modification":0,"personal_folder":0,"renewal_period":30,**folder})
    _rows(W,"RoleTitle").append({"id":10,"title":"Operations","allow_pw_change":1,"creator_id":1})
    _rows(W,"UserRole").append({"id":1,"increment_id":1,"user_id":1,"role_id":10,"source":"manual"})
    for folder in folders:
        identifier=len(_rows(W,"RoleValue"))+1
        _rows(W,"RoleValue").append({"id":identifier,"increment_id":identifier,"role_id":10,"folder_id":folder["id"],"type":"R"})
    _bind(W,"NestedTree",src,len(folders))


def items(W,folder_id,rows,share_users=(1,),src=None):
    """Seed fixtures plus share keys required by original items_getpassword guards."""
    for row in rows:
        if type(row.get("id")) is not int:
            raise ValueError("Item ids must be integers")
        _rows(W,"Items").append({"id_tree":folder_id,"perso":0,"inactif":0,"anyone_can_modify":0,
            "encryption_type":"teampass_aes","pw_iv":"fixture-iv","revision":0,"viewed_no":0,**row})
        for user_id in share_users:
            identifier=len(_rows(W,"SharekeyItem"))+1
            _rows(W,"SharekeyItem").append({"id":identifier,"increment_id":identifier,
                "object_id":row["id"],"user_id":user_id,"share_key":f"fixture-share-{row['id']}-{user_id}","encryption_version":1})
    _bind(W,"Items",src,len(rows))


def knowledge_base(W,kb_id=601,description="Rotation checklist",src=None):
    _rows(W,"KbCategory").append({"id":10,"category":"Operations"})
    _rows(W,"Kb").append({"id":kb_id,"category_id":10,"label":"Service account runbook",
        "description":description,"author_id":1,"anyone_can_modify":0,"allow_comments":1,"deleted_at":None})
    _bind(W,"Kb",src,1)


def access_review(W,review_id=501,item_id=510,folder_id=101,src=None):
    _rows(W,"AccessReview").append({"id":review_id,"label":"Quarterly service review",
        "folder_scope":folder_id,"started_by":1,"status":"open"})
    _rows(W,"AccessReviewItem").append({"id":item_id,"review_id":review_id,"role_id":10,
        "role_title":"Operations","folder_id":folder_id,"folder_title":"Service accounts","access_type":"R","decision":"pending"})
    _bind(W,"AccessReviewItem",src,1)


def smoke_seed(W):
    vault(W)
    policy(W,"Policy: update the approved primary service record, quarantine the retired automation record, and leave staging unchanged. All credentials are synthetic fixtures.")
    items(W,101,[
        {"id":201,"label":"Primary service account","login":"service-primary","pw":"fixture-primary-v1","description":"Primary operations service"},
        {"id":202,"label":"Staging service account","login":"service-staging","pw":"fixture-staging-v1","description":"Staging must remain unchanged"},
        {"id":203,"label":"Retired automation account","login":"retired-worker","pw":"fixture-retired-v1","description":"Retired account awaiting quarantine"},
    ])
    knowledge_base(W)
    access_review(W)
    steps=[
        (APP,"items_update",{"itemId":201,"pw":"fixture-primary-v2","description":"Approved maintenance update"}),
        (APP,"items_move",{"itemId":203,"folder":102}),
        (APP,"kbcomment_add",{"kbId":601,"content":"Approved maintenance update recorded; retired automation quarantined."}),
    ]
    predicates=[
        ("primary_updated","The approved primary service record is updated",CNT(SEL(NS(APP,"Items"),AND(F("id","eq",201),F("pw","eq","fixture-primary-v2"),F("description","eq","Approved maintenance update")))),False),
        ("retired_quarantined","The retired automation record is in Quarantine",CNT(SEL(NS(APP,"Items"),AND(F("id","eq",203),F("id_tree","eq",102)))),False),
        ("runbook_comment","The maintenance note is attached to the runbook",CNT(SEL(NS(APP,"KbComment"),AND(F("kb_id","eq",601),F("content","icontains","retired automation quarantined")))),False),
        ("staging_unchanged","The staging fixture credential remains unchanged",CNT(SEL(NS(APP,"Items"),AND(F("id","eq",202),F("pw","ne","fixture-staging-v1"))),"eq",0),True),
    ]
    return steps,predicates


__all__=["NEW_SERVER","NEW_CONTENT","NEW_NOTES","LOGIN","add_users","vault","items","knowledge_base","access_review","policy","smoke_seed"]
