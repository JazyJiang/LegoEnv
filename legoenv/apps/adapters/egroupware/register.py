"""Source-bound egroupware adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='egroupware';NEW_SERVER={APP:'egroupware_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Account', 'AclRow']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). infolog_search(query=Policy) reads info_des. infolog_write(info_subject,info_owner,info_des) inserts a new entry; infolog_close(info_id,info_des) closes owned entry and edits body; infolog_delete(info_id) deletes. Source write ACL alternatives permit cross-owner creation; close retains owner guard.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='egroupware';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('infolog_search', {'query': 'Policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'InfoLog',[{'id': 201, 'info_id': 201, 'info_owner': 1, 'info_type': 'task', 'info_subject': 'Policy', 'info_des': 'Policy: close task202 with description Reviewed and approved. Create Approved task owned by1. Keep Reference unchanged.', 'info_status': 'open', 'info_percent': 0}, {'id': 202, 'info_id': 202, 'info_owner': 1, 'info_type': 'task', 'info_subject': 'Pending', 'info_des': 'Pending review.', 'info_status': 'open', 'info_percent': 0}, {'id': 203, 'info_id': 203, 'info_owner': 1, 'info_type': 'task', 'info_subject': 'Reference', 'info_des': 'Retain reference task.', 'info_status': 'open', 'info_percent': 0}])
    steps=[('__APP__', 'infolog_close', {'info_id': 202, 'info_des': 'Reviewed and approved.'}), ('__APP__', 'infolog_write', {'info_subject': 'Approved', 'info_des': 'Approved task.', 'info_owner': 1, 'info_type': 'task'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'InfoLog'),AND(F('info_id','eq',202),F('info_des','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'InfoLog'),AND(F('info_id','eq',202),F('info_status','eq','done'),F('info_percent','eq',100)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'InfoLog'),AND(F('info_subject','eq','Approved'),F('info_owner','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'InfoLog'),AND(F('info_id','eq',203),F('info_des','eq','Retain reference task.')))),True))
    return steps,preds
