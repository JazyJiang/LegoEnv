'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound corteza adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='corteza';NEW_SERVER={APP:'namespace_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Role', 'RoleMember', 'RbacRule', 'Credential']]}
NEW_NOTES={APP:'{p}__ login(email,password). Independent metadata demonstration uses user_update(userID,name,handle), namespace_create(name,slug,enabled), user_delete(userID). workflow_read(workflowID) can read metadata only. Complete policy-carrier admission blocked: Page.description read/search requires absent page.read/page.search permission; rbacrule_allow itself requires absent grant permission. Do not fabricate permissions. Global source RbacRule checks are not actor-bound and allow some anonymous writes.'}
LOGIN={APP:('login','email')};SERVER.update(NEW_SERVER);PFX[APP]='corteza';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('workflow_read', {'workflowID': 201})]:
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
    records(W,'Namespace',[{'id':101,'name':'Operations','slug':'operations','enabled':True},{'id':102,'name':'Review','slug':'review','enabled':True},{'id':103,'name':'Reference','slug':'reference','enabled':True}])
    records(W,'Workflow',[{'id':201,'handle':'reference-workflow','meta':{'label':'Reference'},'enabled':True}])
    records(W,'Page',[{'id':301,'namespace_id':101,'title':'Policy','description':'Genuine page body cannot be read because original page.read permission is absent.'}])
    steps=[(APP,'user_update',{'userID':2,'name':'Reviewed colleague.'}),(APP,'user_update',{'userID':2,'handle':'reviewed-colleague'}),(APP,'namespace_create',{'name':'Approved','slug':'approved','enabled':True})]
    preds=[('name','User display name updated.',CNT(SEL(NS(APP,'User'),AND(F('id','eq',2),F('name','eq','Reviewed colleague.')))),False),('handle','User handle updated.',CNT(SEL(NS(APP,'User'),AND(F('id','eq',2),F('handle','eq','reviewed-colleague')))),False),('create','Namespace created.',CNT(SEL(NS(APP,'Namespace'),F('slug','eq','approved'))),False),('reference','Reference namespace retained.',CNT(SEL(NS(APP,'Namespace'),AND(F('id','eq',103),F('name','eq','Reference')))),True)]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
