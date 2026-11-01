"""Source-bound habitica adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='habitica';NEW_SERVER={APP:'habit_task_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Group']]}
NEW_NOTES={APP:'{p}__ signs in with sign_in(auth.local.username,password); dotted source credentials remain actual flat keys. task_get(taskId) reads Task.notes policy by known numeric id. task_create(text,type,notes,alias), task_update(taskId,notes,text), task_delete(taskId) operate owned task scalars. post_chat_message(groupId,message) inserts Chat.text records and get_chat_messages(groupId) reads them. Task scoring source sets value="scored" and completed=false; it does not implement real gamification. No cron/quest, network delivery or complete chat membership/Task read ACL certified.'}
LOGIN={APP:('sign_in','auth.local.username')};SERVER.update(NEW_SERVER);PFX[APP]='habitica';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'auth.local.username':self.persona,'password':self.password}).get('ok')
    for t,args in [('task_get', {'taskId': 201}), ('task_get', {'taskId': 202}), ('task_get', {'taskId': 203}), ('get_chat_messages', {'groupId': 2})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Task',[{'id':201,'_id':201,'userId':1,'type':'todo','text':'Review policy','notes':'Policy: update task202 notes Reviewed and approved.; create Approved task alias approved; post Review recorded. to group2. Keep reference task203 notes unchanged.'},{'id':202,'_id':202,'userId':1,'type':'todo','text':'Review task','notes':'Pending review.'},{'id':203,'_id':203,'userId':1,'type':'todo','text':'Reference task','notes':'Retain reference task notes.'}])
    steps=[(APP,'task_update',{'taskId':202,'notes':'Reviewed and approved.'}),(APP,'task_create',{'text':'Approved task','type':'todo','notes':'Approved task note','alias':'approved'}),(APP,'post_chat_message',{'groupId':2,'message':'Review recorded.'})]
    preds=[('update','Owned task notes updated.',CNT(SEL(NS(APP,'Task'),AND(F('_id','eq',202),F('notes','eq','Reviewed and approved.')))),False),('create','Owned task created.',CNT(SEL(NS(APP,'Task'),AND(F('alias','eq','approved'),F('userId','eq',1)))),False),('chat','Group chat record created.',CNT(SEL(NS(APP,'Chat'),AND(F('groupId','eq',2),F('text','eq','Review recorded.')))),False),('reference','Reference notes unchanged.',CNT(SEL(NS(APP,'Task'),AND(F('_id','eq',203),F('notes','eq','Retain reference task notes.')))),True)]
    return steps,preds
