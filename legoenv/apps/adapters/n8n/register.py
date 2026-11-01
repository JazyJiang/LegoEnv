"""Source-bound n8n adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='n8n';NEW_SERVER={APP:'workflow_tag_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Role', 'ProjectRelation']]}
NEW_NOTES={APP:'{p}__ auth_login(email,password). project_list() reads owned Project.description policy; original Project rows and ProjectRelation preserved. tag_create(name), tag_update(id,name), tag_delete(id) operate global Tag metadata. Source tag guards only check an existing authenticated user and do not enforce claimed scopes. Semantic Role.slug strings retained. No workflow execution, activation, credentials/crypto, HTTP/webhook, scheduling, models or external effects certified.'}
LOGIN={APP:('auth_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='n8n';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'auth_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('project_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    projects=[dict(row) for row in packlib.base(APP)['seed_state']['Project']]
    for row in projects:
        if row['id']==1:row['description']='Policy: rename tag 301 to Reviewed and tag 302 to Approved other. Create Approved tag. Keep Reference tag unchanged.'
    records(W,'Project',projects)
    records(W,'Tag',[{'id':301,'name':'Review'},{'id':302,'name':'Review other'},{'id':303,'name':'Reference'}])
    steps=[(APP,'tag_update',{'id':301,'name':'Reviewed'}),(APP,'tag_update',{'id':302,'name':'Approved other'}),(APP,'tag_create',{'name':'Approved'})]
    preds=[('first','First tag renamed.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',301),F('name','eq','Reviewed')))),False),('second','Second tag renamed.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',302),F('name','eq','Approved other')))),False),('create','Tag created.',CNT(SEL(NS(APP,'Tag'),F('name','eq','Approved'))),False),('reference','Reference tag retained.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',303),F('name','eq','Reference')))),True)]
    return steps,preds
