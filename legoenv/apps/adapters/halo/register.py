"""Halo source snapshot edits and comment moderation, with explicit lifecycle limits."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='halo';NEW_SERVER={APP:'blog'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ('User','Role','RoleBinding')]}
NEW_NOTES={APP:('{p}__ is Halo. Sign in with {p}__sign_in(name,password); spec_password is also accepted. User 1 is your account. '
    'Resource name fields are string metadata keys, separate from internal integer ids. post_list(page=1,keyword,publishPhase) lists Post metadata; '
    'snapshot_listbypost(name=<Post name>) reads Snapshot bodies whose subject reference contains that name; overlapping names may match multiple subjects. Snapshot.spec_raw_patch carries policy. '
    'post_updatecontent(name,snapshotName,raw,content,rawType) edits an existing Snapshot; use a known matching post/snapshot pair. '
    'post_publish/post_unpublish(name) change status_phase only, not spec_publish or release pointers. '
    'comment_create(name,subjectRef=<Post name>,raw,content) creates a linked comment; comment_list(q) lists it. '
    'comment_update(name,spec_approved,spec_hidden,spec_top,spec_priority), comment_approve/unapprove(name), comment_delete(name) moderate scalar state; deletion marks a timestamp. '
    'group_create(name,displayName), group_update(name,displayName), group_delete(name) manage attachment group rows. post_recycle(name) marks spec_deleted. '
    'post_draft drops raw/content and post_update does not advance the Post head; no complete publication pipeline or RBAC is claimed. No binary attachment transfer is implemented.')}
LOGIN={APP:('sign_in','name')}
SERVER.update(NEW_SERVER);PFX[APP]='halo';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'name':self.persona,'password':self.password}).get('ok')
    reads=[('post_list',{'page':1}),('comment_list',{})]
    reads.extend(('snapshot_listbypost',{'name':r['name']}) for r in env.state.get(NS(APP,'Post'),[]))
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
def posts(W,rows,src=None):return _append(W,'Post',[{'spec_owner':W.persona,'spec_publish':False,'spec_deleted':False,'status_phase':'DRAFT',**r} for r in rows],src)
def snapshots(W,rows,src=None):return _append(W,'Snapshot',[{'spec_owner':W.persona,'spec_raw_type':'markdown',**r} for r in rows],src)
def comments(W,rows,src=None):return _append(W,'Comment',[{'spec_approved':False,'spec_hidden':False,'spec_owner_name':W.persona,**r} for r in rows],src)
def groups(W,rows,src=None):return _append(W,'Group',rows,src)
def smoke_seed(W):
    posts(W,[{'id':101,'name':'post-review','spec_title':'Safety review'},{'id':102,'name':'post-reference','spec_title':'Reference announcement'},{'id':103,'name':'post-context','spec_title':'Review context'}])
    snapshots(W,[{'id':201,'name':'snap-policy','spec_subject_ref':{'name':'post-context'},'spec_raw_patch':'Policy: update the reviewed snapshot wording, mark its Post phase published, and approve the review comment. Keep the reference snapshot unchanged.'},
        {'id':202,'name':'snap-review','spec_subject_ref':{'name':'post-review'},'spec_raw_patch':'Checklist awaiting review.','spec_content_patch':'<p>Checklist awaiting review.</p>'},
        {'id':203,'name':'snap-reference','spec_subject_ref':{'name':'post-reference'},'spec_raw_patch':'Retain this reference wording.'}])
    comments(W,[{'id':301,'name':'comment-review','spec_subject_ref':'post-review','spec_raw':'Review complete.','spec_content':'Review complete.'}])
    groups(W,[{'id':401,'name':'review-group','spec_display_name':'Review attachments'}])
    steps=[(APP,'post_updatecontent',{'name':'post-review','snapshotName':'snap-review','raw':'Checklist reviewed and approved.','content':'<p>Checklist reviewed and approved.</p>','rawType':'markdown'}),
        (APP,'post_publish',{'name':'post-review'}),(APP,'comment_approve',{'name':'comment-review'})]
    preds=[('body','Snapshot has approved text.',CNT(SEL(NS(APP,'Snapshot'),AND(F('name','eq','snap-review'),F('spec_raw_patch','eq','Checklist reviewed and approved.')))),False),
        ('phase','Post phase is published.',CNT(SEL(NS(APP,'Post'),AND(F('name','eq','post-review'),F('status_phase','eq','PUBLISHED')))),False),
        ('approved','Review comment is approved.',CNT(SEL(NS(APP,'Comment'),AND(F('name','eq','comment-review'),F('spec_approved','eq',True)))),False),
        ('reference','Reference snapshot stays unchanged.',CNT(SEL(NS(APP,'Snapshot'),AND(F('name','eq','snap-reference'),F('spec_raw_patch','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','posts','snapshots','comments','groups','smoke_seed']
