"""Source-bound seaweedfs adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='seaweedfs';NEW_SERVER={APP:'iam_group_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Credential', 'Policy', 'UserInlinePolicy', 'GroupInlinePolicy']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). serviceaccount_get(ServiceAccountId=201) returns ServiceAccount.content, whose existing description text carries the policy. group_list() reads group metadata. group_create(GroupName), group_update(GroupName,NewGroupName,disabled), group_delete(GroupName) operate group metadata under preserved s3:Admin action. Text username/group names remain business keys, service account opaque id normalized integer. No IAM policy evaluation, S3 object bytes, service credentials or real storage/ACL effects certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='seaweedfs';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('serviceaccount_get', {'ServiceAccountId': 201}), ('group_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Group',packlib.base(APP)['seed_state']['Group'])
    records(W,'Group',[{'id':301,'name':'Review','members':[],'policy_names':[],'disabled':False},{'id':302,'name':'Reference','members':[],'policy_names':[],'disabled':False}])
    records(W,'ServiceAccount',[{'id':201,'content':{'description':'Policy: rename Review group to Reviewed operations. and disable it. Create Approved group. Keep Reference group unchanged.'},'disabled':False}])
    steps=[(APP,'group_update',{'GroupName':'Review','NewGroupName':'Reviewed operations.'}),(APP,'group_update',{'GroupName':'Reviewed operations.','disabled':True}),(APP,'group_create',{'GroupName':'Approved'})]
    preds=[('name','Group renamed.',CNT(SEL(NS(APP,'Group'),F('name','eq','Reviewed operations.'))),False),('disabled','Group disabled.',CNT(SEL(NS(APP,'Group'),AND(F('name','eq','Reviewed operations.'),F('disabled','eq',True)))),False),('create','Group created.',CNT(SEL(NS(APP,'Group'),F('name','eq','Approved'))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'Group'),AND(F('name','eq','Reference'),F('disabled','eq',False)))),True)]
    return steps,preds
