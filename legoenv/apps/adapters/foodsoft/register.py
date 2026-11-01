"""Source-bound foodsoft adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='foodsoft';NEW_SERVER={APP:'cooperative_task_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Group', 'Membership', 'Ordergroup', 'Workgroup', 'Supplier']]}
NEW_NOTES={APP:'{p}__ user_login(nick,password). api_order_index() reads genuine Order.note policy (API requires signed-in member). task_create(name,description,required_users,workgroup_id), task_update(id,description,name), task_set_done(id), task_destroy(id) operate Task records. Source Task tools have no auth/member guard; do not infer workgroup access enforcement. No actual purchasing, banking, payments, email, printing or supplier delivery certified.'}
LOGIN={APP:('user_login','nick')};SERVER.update(NEW_SERVER);PFX[APP]='foodsoft';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'nick':self.persona,'password':self.password}).get('ok')
    for t,args in [('api_order_index', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Order',[{'id':201,'supplier_id':1,'note':'Policy: update task 202 description to Reviewed and approved. Mark task 202 done. Create Approved task. Keep reference task description unchanged.','starts':'2026-01-01T00:00:00','ends':'2026-02-01T00:00:00','state':'open','created_by_user_id':1}])
    records(W,'Task',[{'id':202,'name':'Review','description':'Pending review.','done':False,'required_users':1,'duration':1,'workgroup_id':10,'created_by_user_id':1},{'id':203,'name':'Reference','description':'Retain reference task.','done':False,'required_users':1,'duration':1,'workgroup_id':10,'created_by_user_id':1}])
    steps=[(APP,'task_update',{'id':202,'description':'Reviewed and approved.'}),(APP,'task_set_done',{'id':202}),(APP,'task_create',{'name':'Approved','description':'Approved task.','required_users':1,'workgroup_id':10})]
    preds=[('description','Task description updated.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False),('done','Task completed.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',202),F('done','eq',True)))),False),('create','Task created.',CNT(SEL(NS(APP,'Task'),F('name','eq','Approved'))),False),('reference','Reference task retained.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',203),F('description','eq','Retain reference task.')))),True)]
    return steps,preds
