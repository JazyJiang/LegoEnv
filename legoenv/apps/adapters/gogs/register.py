"""Source-faithful Gogs repository metadata and known-ID issue writes."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='gogs';NEW_SERVER={APP:'code_hosting'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ('User','LoginSource')]}
NEW_NOTES={APP:('{p}__ is Gogs. Sign in with {p}__sign_in(username,password), as User 1. '
    'list_my_repositories lists your repository metadata; search_repositories(q) uses a real substring filter; get_repository(repo_id) reads metadata. '
    'Repository.description carries policy and may name the known issue IDs to operate on. The source has no Issue/Comment read/list tool. '
    'create_issue(repo_id,title,body), edit_issue(issue_id,title,body), close_issue(issue_id), reopen_issue(issue_id) write issue scalars. '
    'create_issue_comment(issue_id,body) adds a comment; edit_comment(comment_id,body) and delete_comment(comment_id) require the author. '
    'create_label(repo_id,name,color) adds a label; edit_repository(repo_id,description,website) updates metadata with source Access guard. '
    'create_issue omits numbering/default fields; create_repository/edit_repository have lower(...) placeholders. '
    'Full Git operations, repository ownership transfer, missing issue/comment reads, general ACL isolation and binary transfer are not implemented or certified.')}
LOGIN={APP:('sign_in','username')}
SERVER.update(NEW_SERVER);PFX[APP]='gogs';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    reads=[('list_my_repositories',{}),('search_repositories',{'q':'Review'})]+[('get_repository',{'repo_id':r['id']}) for r in env.state.get(NS(APP,'Repository'),[]) if r.get('owner_id')==1]
    for tool,args in reads:
        result=env.call(NS(APP,tool),args);assert result.get('ok'),result
        rep[APP+' '+tool+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def repositories(W,rows,src=None):
    rows=_append(W,'Repository',[{'owner_id':1,'lower_name':r['name'].lower(),'is_private':False,'enable_issues':True,'enable_external_tracker':False,'enable_pulls':True,**r} for r in rows],src)
    for r in rows:_append(W,'Access',[{'id':r['id'],'repo_id':r['id'],'user_id':r['owner_id'],'mode':4}],src)
    return rows
def issues(W,rows,src=None):return _append(W,'Issue',[{'repo_id':101,'poster_id':1,'index':r['id'],'is_closed':False,'is_pull':False,**r} for r in rows],src)
def comments(W,rows,src=None):return _append(W,'Comment',[{'poster_id':1,'type':0,**r} for r in rows],src)
def smoke_seed(W):
    repositories(W,[{'id':101,'name':'Review repository','description':'Policy: issue202 is the review ticket; change its body to Reviewed and approved., add a review comment and close it. Keep issue203 reference content unchanged.'},
        {'id':102,'name':'Reference repository','description':'Reference repository metadata.'},{'id':103,'name':'Support context','description':'Review context metadata.'}])
    issues(W,[{'id':201,'name':'Policy context','content':'Review context.'},{'id':202,'name':'Review issue','content':'Review pending.'},{'id':203,'name':'Reference issue','content':'Retain this reference wording.'}])
    comments(W,[{'id':301,'issue_id':201,'content':'Existing policy comment.'}])
    steps=[(APP,'edit_issue',{'issue_id':202,'body':'Reviewed and approved.'}),(APP,'create_issue_comment',{'issue_id':202,'body':'Review complete; approval recorded.'}),(APP,'close_issue',{'issue_id':202})]
    preds=[('body','Reviewed issue body updated.',CNT(SEL(NS(APP,'Issue'),AND(F('id','eq',202),F('content','eq','Reviewed and approved.')))),False),
        ('comment','Review comment recorded.',CNT(SEL(NS(APP,'Comment'),AND(F('issue_id','eq',202),F('content','eq','Review complete; approval recorded.')))),False),
        ('closed','Reviewed issue closed.',CNT(SEL(NS(APP,'Issue'),AND(F('id','eq',202),F('is_closed','eq',True)))),False),
        ('reference','Reference issue content unchanged.',CNT(SEL(NS(APP,'Issue'),AND(F('id','eq',203),F('content','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','repositories','issues','comments','smoke_seed']
