'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound formbricks adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='formbricks';NEW_SERVER={APP:'survey_tag_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Organization', 'Membership', 'Workspace']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password). Independent metadata demonstration uses survey_get(surveyId), tag_create(workspaceId,name), tag_update(id,name), tag_delete(id). Full policy-carrier admission blocked: native read tools do not expose the existing description fields on Workflow/ActionClass/ContactAttributeKey; survey config JSON is not replaced by an invented policy body. Source Tag tools require authentication only and do not bind workspace membership.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='formbricks';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('survey_get', {'surveyId': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    raise RuntimeError('No source-readable business policy text carrier; do not fabricate a read tool or repurpose metadata as instructions. Complete admission blocked.')
def metadata_smoke_seed(W):
    survey=dict(packlib.base(APP)['seed_state']['Survey'][0]);survey.update(id=201,name='Operations Survey',slug='operations-survey')
    records(W,'Survey',[survey])
    records(W,'Tag',[{'id':301,'workspaceId':1,'name':'Review'},{'id':302,'workspaceId':1,'name':'Reference'},{'id':303,'workspaceId':1,'name':'Review other'}])
    steps=[(APP,'tag_update',{'id':301,'name':'Reviewed'}),(APP,'tag_update',{'id':303,'name':'Reviewed other'}),(APP,'tag_create',{'workspaceId':1,'name':'Approved'})]
    preds=[('first','First tag renamed.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',301),F('name','eq','Reviewed')))),False),('second','Second tag renamed.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',303),F('name','eq','Reviewed other')))),False),('create','Tag created.',CNT(SEL(NS(APP,'Tag'),AND(F('name','eq','Approved'),F('workspaceId','eq',1)))),False),('reference','Reference tag retained.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',302),F('name','eq','Reference')))),True)]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
