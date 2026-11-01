"""Source-bound homarr adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='homarr';NEW_SERVER={APP:'dashboard_shortcut_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Group', 'GroupPermission', 'GroupMember', 'Board', 'SearchEngine']]}
NEW_NOTES={APP:'{p}__ uses user_login(name,password). app_all() reads App.description policy globally. app_create(name,iconUrl,href,description), app_update(id,description,name), app_delete(id) operate shortcut metadata. Source GroupPermission checks are global and not tied to actor group/auth, so anonymous creation may succeed. No widget execution/HTTP request, dashboard layout rendering, integration discovery, credential storage, scheduler or network effects certified.'}
LOGIN={APP:('user_login','name')};SERVER.update(NEW_SERVER);PFX[APP]='homarr';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'name':self.persona,'password':self.password}).get('ok')
    for t,args in [('app_all', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'App',[{'id':201,'name':'Policy app','description':'Policy: update app202 description Reviewed and approved. and name Reviewed operations; create Approved app shortcut. Keep reference app203 description unchanged.','iconUrl':'https://icon.invalid/policy','href':'https://policy.invalid'},{'id':202,'name':'Pending review','description':'Pending review.','iconUrl':'https://icon.invalid/review','href':'https://review.invalid'},{'id':203,'name':'Reference app','description':'Retain reference app description.','iconUrl':'https://icon.invalid/reference','href':'https://reference.invalid'}])
    steps=[(APP,'app_update',{'id':202,'description':'Reviewed and approved.'}),(APP,'app_update',{'id':202,'name':'Reviewed operations'}),(APP,'app_create',{'name':'Approved app','description':'Approved app metadata','iconUrl':'https://icon.invalid/approved','href':'https://approved.invalid'})]
    preds=[('description','App description updated.',CNT(SEL(NS(APP,'App'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False),('name','App name updated.',CNT(SEL(NS(APP,'App'),AND(F('id','eq',202),F('name','eq','Reviewed operations')))),False),('create','App shortcut created.',CNT(SEL(NS(APP,'App'),F('name','eq','Approved app'))),False),('reference','Reference description unchanged.',CNT(SEL(NS(APP,'App'),AND(F('id','eq',203),F('description','eq','Retain reference app description.')))),True)]
    return steps,preds
