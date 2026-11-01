"""Source-bound linkace adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='linkace';NEW_SERVER={APP:'linkace_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Role']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password). linklist_read(list=201) reads genuine description with owner/private guard. linklist_create(name,description,visibility), linklist_update(list,name,description), linklist_delete(list) change local lists and trash flag. Original owner checks and source roles preserved.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='linkace';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('linklist_read', {'list': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'LinkList',[{'id': 201, 'user_id': 1, 'name': 'Policy', 'description': 'Policy: review list202 description to Reviewed and approved. and name Reviewed. Create Approved list. Keep Reference unchanged.', 'visibility': 3}, {'id': 202, 'user_id': 1, 'name': 'Pending', 'description': 'Pending review.', 'visibility': 3}, {'id': 203, 'user_id': 1, 'name': 'Reference', 'description': 'Retain reference list.', 'visibility': 3}])
    steps=[('__APP__', 'linklist_update', {'list': 202, 'description': 'Reviewed and approved.', 'name': 'Reviewed'}), ('__APP__', 'linklist_create', {'name': 'Approved', 'description': 'Approved list.', 'visibility': 3})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'LinkList'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'LinkList'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'LinkList'),AND(F('name','eq','Approved'),F('description','eq','Approved list.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'LinkList'),AND(F('id','eq',203),F('description','eq','Retain reference list.')))),True))
    return steps,preds
