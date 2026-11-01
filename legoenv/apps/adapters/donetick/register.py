"""Donetick source chore/project scalar records."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='donetick';NEW_SERVER={APP:'chore_coordination'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User','Circle','UserCircle']]}
NEW_NOTES={APP:('{p}__ coordinates scalar chore/project records. user_login(username,password) verifies User1 in circle1. chore_getchores() and chore_getchore(id) read Chore.description policy, project_list reads descriptions. chore_createchore(name,frequencyType,assignStrategy,description,...) inserts metadata; chore_editchore(id,description), chore_updatepriority(id,priority), chore_updateassignee(id,assignee,updatedAt), chore_updateduedate(id,dueDate,updatedAt), chore_archivechore(id), chore_unarchivechore(id) change scalars. project_create(name,description), project_update(id,...), project_delete(id) operate circle-scoped projects. No recurrence engine, complete history/points/approval, assignee fanout or notification execution is certified; timestamps are not optimistic-lock checks.')}
LOGIN={APP:('user_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='donetick';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t in ['chore_getchores','project_list']:
        r=env.call(NS(APP,t),{});assert r.get('ok'),r;rep[APP+' '+t]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def chores(W,rows,src=None):return records(W,'Chore',[{'circle_id':1,'created_by':1,'assigned_to':1,'is_active':True,'status':0,'priority':0,**r} for r in rows],src)
def smoke_seed(W):
    records(W,'Project',[{'id':101,'name':'Operations','description':'Review project','circle_id':1,'created_by':1}]);chores(W,[{'id':201,'name':'Policy','description':'Policy: set chore202 priority2 and assignee2; update project101 description to Reviewed operations. Keep reference chore203 description unchanged.'},{'id':202,'name':'Review task','description':'Pending review.'},{'id':203,'name':'Reference','description':'Retain this reference description.'}])
    steps=[(APP,'chore_updatepriority',{'id':202,'priority':2}),(APP,'chore_updateassignee',{'id':202,'assignee':2,'updatedAt':'2026-09-24T09:00:00'}),(APP,'project_update',{'id':101,'description':'Reviewed operations.'})]
    preds=[('priority','Chore priority updated.',CNT(SEL(NS(APP,'Chore'),AND(F('id','eq',202),F('priority','eq',2)))),False),('assignee','Chore scalar owner updated.',CNT(SEL(NS(APP,'Chore'),AND(F('id','eq',202),F('assigned_to','eq',2)))),False),('project','Project description updated.',CNT(SEL(NS(APP,'Project'),AND(F('id','eq',101),F('description','eq','Reviewed operations.')))),False),('reference','Reference chore unchanged.',CNT(SEL(NS(APP,'Chore'),AND(F('id','eq',203),F('description','eq','Retain this reference description.')))),True)]
    return steps,preds
