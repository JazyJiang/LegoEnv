"""Source-bound grocy adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='grocy';NEW_SERVER={APP:'grocy_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'UserPermission', 'PermissionHierarchy']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). tasks_current() reads Task.description and actually lists completed rows too. tasks_markcomplete(taskId,done_time) sets done1/timestamp; tasks_undo(taskId,name,description) resets done0/timestamp and edits native scalar metadata. Native UserPermission existence guard retained; regular account without permission cannot write.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='grocy';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('tasks_current', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Task',[{'id': 201, 'name': 'Policy', 'description': 'Policy: mark tasks202 and203 done at 2026-10-20T09:00:00. Keep Reference unchanged.', 'done': 0}, {'id': 202, 'name': 'Pending', 'description': 'Pending review.', 'done': 0}, {'id': 203, 'name': 'Pending2', 'description': 'Pending review2.', 'done': 0}, {'id': 204, 'name': 'Reference', 'description': 'Retain reference task.', 'done': 0}])
    steps=[('__APP__', 'tasks_markcomplete', {'taskId': 202, 'done_time': '2026-10-20T09:00:00'}), ('__APP__', 'tasks_markcomplete', {'taskId': 203, 'done_time': '2026-10-20T09:00:00'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',202),F('done','eq',1)))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',202),F('done_timestamp','eq','2026-10-20T09:00:00')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',203),F('done','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',204),F('description','eq','Retain reference task.')))),True))
    return steps,preds
