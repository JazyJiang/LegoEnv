"""Source-bound reactive_resume adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='reactive_resume';NEW_SERVER={APP:'application_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Account']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password). application_list() and application_getbyid(id) read Application.notes policy. application_update(id,company,role), application_delete(id) act on owned records. resume_import(data) stores supplied JSON but source name and slug are literal placeholders. application_create lacks required contacts input and is not certified. Source application_update writes placeholder activity/appliedAt rather than a real timeline. No AI providers, agent send, PDF render/download or external effects certified.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='reactive_resume';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('application_list', {}), ('application_getbyid', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Application',[{'id':201,'userId':1,'company':'Policy','role':'Operations','status':'saved','archived':False,'tags':[],'notes':'Policy: update application 202 company to Reviewed company. and role to Reviewed role. Import resume JSON with basics name Approved operations. Keep Reference notes unchanged.','contacts':[],'activity':[],'appliedAt':'2026-01-01T00:00:00'},{'id':202,'userId':1,'company':'Review','role':'Pending role','status':'saved','archived':False,'tags':[],'notes':'Pending review.','contacts':[],'activity':[],'appliedAt':'2026-01-01T00:00:00'},{'id':203,'userId':1,'company':'Reference','role':'Reference role','status':'saved','archived':False,'tags':[],'notes':'Retain reference notes.','contacts':[],'activity':[],'appliedAt':'2026-01-01T00:00:00'}])
    steps=[(APP,'application_update',{'id':202,'company':'Reviewed company.'}),(APP,'application_update',{'id':202,'role':'Reviewed role.'}),(APP,'resume_import',{'data':{'basics':{'name':'Approved operations.'}}})]
    preds=[('company','Application company updated.',CNT(SEL(NS(APP,'Application'),AND(F('id','eq',202),F('company','eq','Reviewed company.')))),False),('role','Application role updated.',CNT(SEL(NS(APP,'Application'),AND(F('id','eq',202),F('role','eq','Reviewed role.')))),False),('import','Resume JSON imported.',CNT(SEL(NS(APP,'Resume'),AND(F('userId','eq',1),F('data','eq',{'const':{'basics':{'name':'Approved operations.'}}})))),False),('reference','Reference notes retained.',CNT(SEL(NS(APP,'Application'),AND(F('id','eq',203),F('notes','eq','Retain reference notes.')))),True)]
    return steps,preds
