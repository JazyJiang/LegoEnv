"""Source-bound kanboard adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='kanboard';NEW_SERVER={APP:'kanban_coordination'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Project', 'ProjectUserRole', 'Column', 'Swimlane', 'Category']]}
NEW_NOTES={APP:'{p}__ signs in with sign_in(username,password). task_searchtasks(project_id,query) reads project-scoped literal task text; Task.description carries policy. task_gettask(task_id) reads known tasks. task_create(title,project_id,...), task_update(id,description,owner_id), task_moveposition(project_id,task_id,column_id,position,swimlane_id), task_movetoproject(task_id,project_id,...) execute actual scalar/FK writes. task_close/open(task_id) transition is_active. comment_create(task_id,user_id,content), comment_update(id,content), comment_remove(comment_id), task_remove(task_id) modify records. subtask_togglestatus(subtask_id) cycles status0/1/2. No notification/automation/recurrence execution, complete reorder side effects or comprehensive project ACL certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='kanboard';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('task_searchtasks', {'project_id': 1, 'query': 'task'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Task',[{'id':201,'project_id':1,'column_id':1,'swimlane_id':1,'owner_id':1,'creator_id':1,'title':'Review policy task','description':'Policy: set task202 description Reviewed and approved.; move task202 to column2 position1; add Review recorded. comment on task202 as User1. Keep reference task203 description unchanged.','is_active':1},{'id':202,'project_id':1,'column_id':1,'swimlane_id':1,'owner_id':1,'creator_id':1,'title':'Review task','description':'Pending review.','is_active':1},{'id':203,'project_id':1,'column_id':1,'swimlane_id':1,'owner_id':2,'creator_id':1,'title':'Reference task','description':'Retain reference task description.','is_active':1}])
    steps=[(APP,'task_update',{'id':202,'description':'Reviewed and approved.'}),(APP,'task_moveposition',{'project_id':1,'task_id':202,'column_id':2,'position':1,'swimlane_id':1}),(APP,'comment_create',{'task_id':202,'user_id':1,'content':'Review recorded.'})]
    preds=[('description','Task description updated.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False),('move','Task moved to target column.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',202),F('column_id','eq',2)))),False),('comment','Comment persisted.',CNT(SEL(NS(APP,'Comment'),AND(F('task_id','eq',202),F('comment','eq','Review recorded.')))),False),('reference','Reference task unchanged.',CNT(SEL(NS(APP,'Task'),AND(F('id','eq',203),F('description','eq','Retain reference task description.')))),True)]
    return steps,preds
