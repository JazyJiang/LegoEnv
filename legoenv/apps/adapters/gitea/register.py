"""Gitea project/issue/release scalar operations; no invented tool interface."""
import json
import runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP, SEL, F, AND, CNT

APP = 'gitea'
NEW_SERVER = {APP:'development'}
# Clear every per-world business entity while retaining the persona's local
# identity configuration. This list derives solely from this app's patched base.
NEW_CONTENT = {APP:[e['name'] for e in packlib.base(APP)['entities']
                   if e['name'] not in ('User','EmailAddress','Source')]}
NEW_NOTES = {APP:(
    '{p}__ is the Gitea development tracker. Sign in using '
    '{p}__user_sign_in(username=<your email>,password); you are active admin User 1. '
    'Repository owner names in this world match the supplied persona email. '
    'project_search(owner,repo,q) lists repository projects and can filter their title/description; '
    'project_read(id,owner,repo) reads a policy from Project.description. '
    'project_create(title,description,owner,repo) creates a project; '
    'project_update(id,title,description) changes scalar metadata. '
    'column_create(id=<project id>,title,color) requires an open project; '
    'column_update(column_id,title,color,sorting) updates a column. '
    'issue_create(repo_id,title,body,closed) creates one issue using the seed-reserved next index; '
    'this executor does not advance IssueIndex, so repeated creations cannot rely on unique indices. '
    'issue_close(owner,repo,index) and issue_reopen(owner,repo,index) change real Issue.is_closed; '
    'issue_comment_create(owner,repo,index,body) records a comment. '
    'projectissue_add(column_id,issue_id) adds a real ProjectIssue membership, but projectissue_move '
    'and projectissue_remove only append comments and do not move/remove membership. '
    'release_createrelease(owner,repo,TagName,Title,Note,Target) creates a scalar release; '
    'release_updaterelease(id,Title,Note) updates it; release_deletereleasebyid(id) deletes it. '
    'issue_delete(owner,repo,index) and column_delete(id=<open project id>,column_id) delete their rows. '
    'Issue deletion is refused while linked comments remain; it does not cascade them. '
    'The panel has no Repository/Issue/Comment/Column/Release read/list tools; task-provided ids '
    'and repository names are required for those operations. Ordinary issue_edit targets Comment '
    'and lacks its target-id argument; comment_edit targets IssueContentHistory. Neither is a '
    'reliable edit of its named main row. project_delete does not delete Project. '
    'Repository transfers, team membership, file operations, workflow execution and Git commits '
    'are not fully represented. Use the supported project reader and scalar writes above.'
)}
LOGIN = {APP:('user_sign_in','username')}
SERVER.update(NEW_SERVER)
PFX[APP] = 'gitea'
CONTENT.update(NEW_CONTENT)
NOTES.update(NEW_NOTES)
packlib.LOGIN.update(LOGIN)

OBS_READS = ['project_search','project_read']
_original_obs = World.obs_report

def _obs_report(self):
    rep,bad = _original_obs(self)
    if APP not in self.apps:
        return rep,bad
    env = runtime.Env(self.world)
    result = env.call(NS(APP,'user_sign_in'),{'username':self.persona,'password':self.password})
    if not result.get('ok'):
        raise RuntimeError(f'Gitea observation login failed: {result}')
    repos = env.state.get(NS(APP,'Repository'),[])
    reads = [('project_search',{'owner':r['owner_name'],'repo':r['lower_name']}) for r in repos]
    for project in env.state.get(NS(APP,'Project'),[]):
        repo = next(r for r in repos if r['id']==project['repo_id'])
        reads.append(('project_read',{'id':project['id'],'owner':repo['owner_name'],'repo':repo['lower_name']}))
    for tool,args in reads:
        result = env.call(NS(APP,tool),args)
        if not result.get('ok'):
            raise RuntimeError(f'Gitea observation {tool} failed: {result}')
        key = f"{APP} {tool} {args['owner']}/{args['repo']}" + (f" {args['id']}" if 'id' in args else '')
        rep[key] = len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{key:size for key,size in rep.items() if size>OBS_CAP}

World.obs_report = _obs_report

def _append(W,entity,rows,src=None):
    rows = [dict(row) for row in rows]
    for row in rows:
        if 'id' in row and (not isinstance(row['id'],int) or isinstance(row['id'],bool)):
            raise ValueError(f'{entity} seed ids must be integers')
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:
        W.bindings[NS(APP,entity)] = {'dataset':src,'rows':len(rows)}
    return rows

def repositories(W,rows,src=None):
    return _append(W,'Repository',[{'owner_id':1,'owner_name':W.persona,
        'lower_name':r['name'].lower(),'is_private':False,'is_archived':False,
        'default_branch':'main',**r} for r in rows],src)

def projects(W,rows,src=None):
    return _append(W,'Project',[{'owner_id':1,'creator_id':1,'is_closed':False,**r} for r in rows],src)

def columns(W,rows,src=None):
    return _append(W,'Column',[{'creator_id':1,'default':False,'sorting':i,**r} for i,r in enumerate(rows)],src)

def issues(W,rows,src=None):
    result = _append(W,'Issue',[{'poster_id':1,'is_closed':False,'is_pull':False,
        'is_locked':False,'priority':0,**r} for r in rows],src)
    ss = W.spec[APP]['seed_state']
    # One reserved next-index value per repository. The raw write does not
    # increment it; this limitation is exposed rather than hidden by helpers.
    ss['IssueIndex'] = [{'group_id':repo,'max_index':max(r['index'] for r in ss['Issue'] if r['repo_id']==repo)+1}
                        for repo in sorted({r['repo_id'] for r in ss['Issue']})]
    return result

def releases(W,rows,src=None):
    return _append(W,'Release',[{'publisher_id':1,'is_draft':False,'is_prerelease':False,**r} for r in rows],src)

def smoke_seed(W):
    repositories(W,[{'id':101,'name':'handbook','description':'Operations handbook repository'}])
    _append(W,'Access',[{'id':1,'user_id':1,'repo_id':101,'mode':3}])
    projects(W,[
        {'id':201,'repo_id':101,'title':'Review queue','description':'Policy review pending.'},
        {'id':202,'repo_id':101,'title':'Handling policy','description':
            'Policy: add a review comment before closing the access-policy issue. '
            'Keep the reserved reference issue open, and add the reviewed issue to the Done column.'},
    ])
    columns(W,[{'id':401,'project_id':201,'title':'Done'}])
    issues(W,[
        {'id':301,'repo_id':101,'index':1,'name':'Review access policy','content':'Confirm access-policy review.'},
        {'id':302,'repo_id':101,'index':2,'name':'Archive older policy','content':'Archive after review.'},
        {'id':303,'repo_id':101,'index':3,'name':'Reserved reference issue','content':'Reference only; leave open.'},
    ])
    path = {'owner':W.persona,'repo':'handbook','index':1}
    steps = [
        (APP,'issue_comment_create',{**path,'body':'Access policy reviewed; closure approved.'}),
        (APP,'issue_close',path),
        (APP,'project_update',{'id':201,'description':'Access-policy review completed.'}),
        (APP,'projectissue_add',{'column_id':401,'issue_id':301}),
    ]
    predicates = [
        ('commented','The target issue has the review comment.',
         CNT(SEL(NS(APP,'Comment'),AND(F('issue_id','eq',301),F('content','eq','Access policy reviewed; closure approved.')))),False),
        ('closed','The reviewed issue is closed.',
         CNT(SEL(NS(APP,'Issue'),AND(F('id','eq',301),F('is_closed','eq',True)))),False),
        ('project_updated','The review project records completion.',
         CNT(SEL(NS(APP,'Project'),AND(F('id','eq',201),F('description','eq','Access-policy review completed.')))),False),
        ('on_board','The reviewed issue belongs to the Done column.',
         CNT(SEL(NS(APP,'ProjectIssue'),AND(F('issue_id','eq',301),F('project_board_id','eq',401)))),False),
        ('reserved_unchanged','The reserved reference issue remains open.',
         CNT(SEL(NS(APP,'Issue'),AND(F('id','eq',303),F('is_closed','eq',False)))),True),
    ]
    return steps,predicates

__all__ = ['NEW_SERVER','repositories','projects','columns','issues','releases','smoke_seed']
