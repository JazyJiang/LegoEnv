"""Source-bound gitbucket adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='gitbucket';NEW_SERVER={APP:'repository_issue_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Account', 'Repository', 'Collaborator', 'GroupMember']]}
NEW_NOTES={APP:'{p}__ account_login(userName,password); business usernames stay text and map to session.user_name. issue_listapi(owner=<your login>,repository=notes) reads Issue.content policy; source owner scope uses login username but owner/repository args do not filter results. milestone_create(owner,repository,title,description), milestone_update(owner,repository,userName,repositoryName,milestoneId,title,description), milestone_delete(owner,repository,userName,repositoryName,milestoneId) operate metadata. Both locator aliases must be supplied. Source any-existing-account OR collaborator guard is permissive; no repository access guarantee. No Git merge/file/wiki/asset bytes or webhook effects certified.'}
LOGIN={APP:('account_login','userName')};SERVER.update(NEW_SERVER);PFX[APP]='gitbucket';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'account_login'),{'userName':self.persona,'password':self.password}).get('ok')
    for t,args in [('issue_listapi', {'owner': {'$session': 'user_name'}, 'repository': 'notes'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Issue',[{'id':201,'issueId':201,'userName':W.persona,'repositoryName':'notes','openedUserName':W.persona,'title':'Policy','content':'Policy: update milestone 301 description to Reviewed and approved. and title to Reviewed operations. Create Approved milestone. Keep Reference unchanged.','closed':False,'isPullRequest':False}])
    records(W,'Milestone',[{'id':301,'milestoneId':301,'userName':W.persona,'repositoryName':'notes','title':'Review','description':'Pending review.'},{'id':302,'milestoneId':302,'userName':W.persona,'repositoryName':'notes','title':'Reference','description':'Retain reference milestone.'}])
    common={'owner':W.persona,'repository':'notes','userName':W.persona,'repositoryName':'notes','milestoneId':301}
    steps=[(APP,'milestone_update',{**common,'title':'Review','description':'Reviewed and approved.'}),(APP,'milestone_update',{**common,'title':'Reviewed operations.'}),(APP,'milestone_create',{'owner':W.persona,'repository':'notes','title':'Approved','description':'Approved milestone.'})]
    preds=[('description','Milestone description updated.',CNT(SEL(NS(APP,'Milestone'),AND(F('milestoneId','eq',301),F('description','eq','Reviewed and approved.')))),False),('title','Milestone renamed.',CNT(SEL(NS(APP,'Milestone'),AND(F('milestoneId','eq',301),F('title','eq','Reviewed operations.')))),False),('create','Milestone created.',CNT(SEL(NS(APP,'Milestone'),F('title','eq','Approved'))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'Milestone'),AND(F('milestoneId','eq',302),F('description','eq','Retain reference milestone.')))),True)]
    return steps,preds
