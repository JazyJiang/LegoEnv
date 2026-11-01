"""Source-bound piga adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='piga';NEW_SERVER={APP:'task_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'DocumentEntity', 'DocumentPermissionAndPlacement']]}
NEW_NOTES={APP:'{p}__ sign_in(loginName,password). get_tasks_by_document(documentId) or find_tasks_by_content(documentId,query) reads TaskEntity.contentHtml policy. add_task(documentId,contentHtml,tags) inserts supplied task content. share_document(documentId,loginName,userId) inserts access placement. update_user(id,name) changes display name under source admin-or-self check. No task update/delete tool exists; no ordering, subtree operation, Markdown conversion or modification-log effect certified. get_tasks_by_document is unauthenticated in source.'}
LOGIN={APP:('sign_in','loginName')};SERVER.update(NEW_SERVER);PFX[APP]='piga';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'loginName':self.persona,'password':self.password}).get('ok')
    for t,args in [('get_tasks_by_document', {'documentId': 1}), ('find_tasks_by_content', {'documentId': 1, 'query': 'Policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'TaskEntity',[{'id':201,'documentId':1,'contentHtml':'Policy: rename colleague user 2 to Reviewed colleague. Add Approved task to document 1. Share document 2 with robot user 3. Keep Reference task unchanged.','orderToken':'a','indentation':0,'collapsed':False,'checked':False,'tags':['#policy'],'lastContentModifierUserId':1},{'id':202,'documentId':1,'contentHtml':'Review task.','orderToken':'b','indentation':0,'collapsed':False,'checked':False,'tags':['#review'],'lastContentModifierUserId':1},{'id':203,'documentId':1,'contentHtml':'Retain reference task.','orderToken':'c','indentation':0,'collapsed':False,'checked':False,'tags':['#reference'],'lastContentModifierUserId':1}])
    steps=[(APP,'update_user',{'id':2,'name':'Reviewed colleague.'}),(APP,'add_task',{'documentId':1,'contentHtml':'Approved task.','tags':['#approved']}),(APP,'share_document',{'documentId':2,'loginName':'robot@piga.example','userId':3})]
    preds=[('name','Colleague display name updated.',CNT(SEL(NS(APP,'User'),AND(F('id','eq',2),F('name','eq','Reviewed colleague.')))),False),('task','Task created.',CNT(SEL(NS(APP,'TaskEntity'),AND(F('documentId','eq',1),F('contentHtml','eq','Approved task.')))),False),('share','Document access placement created.',CNT(SEL(NS(APP,'DocumentPermissionAndPlacement'),AND(F('documentId','eq',2),F('userId','eq',3)))),False),('reference','Reference task retained.',CNT(SEL(NS(APP,'TaskEntity'),AND(F('id','eq',203),F('contentHtml','eq','Retain reference task.')))),True)]
    return steps,preds
