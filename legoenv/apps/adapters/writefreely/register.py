"""Source-bound writefreely adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='writefreely';NEW_SERVER={APP:'writefreely_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Collection']]}
NEW_NOTES={APP:'{p}__ user_login(username,password). post_view(post) reads genuine Post.content policy publicly. post_create(title,content,slug) inserts native row; original runtime injects owner_id from session, collection alias remains unmapped. post_update(post,title,content) edits owned rows. post_delete(post) accepts any signed-in user regardless target owner. No real blog publishing, ActivityPub or email.'}
LOGIN={APP:('user_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='writefreely';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('post_view', {'post': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Post',[{'id': 201, 'title': 'Policy', 'slug': 'policy', 'content': 'Policy: update post202 body to Reviewed and approved. and title Reviewed. Create Approved post. Keep Reference unchanged.', 'owner_id': 1, 'collection_id': 1, 'privacy': 0, 'view_count': 0, 'text_appearance': 'norm'}, {'id': 202, 'title': 'Pending', 'slug': 'review', 'content': 'Pending review.', 'owner_id': 1, 'collection_id': 1, 'privacy': 0, 'view_count': 0, 'text_appearance': 'norm'}, {'id': 203, 'title': 'Reference', 'slug': 'reference', 'content': 'Retain reference post.', 'owner_id': 1, 'collection_id': 1, 'privacy': 0, 'view_count': 0, 'text_appearance': 'norm'}])
    steps=[('__APP__', 'post_update', {'post': 202, 'content': 'Reviewed and approved.', 'title': 'Reviewed'}), ('__APP__', 'post_create', {'title': 'Approved', 'content': 'Approved post.', 'slug': 'approved'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('id','eq',202),F('content','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('id','eq',202),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('title','eq','Approved'),F('content','eq','Approved post.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('id','eq',203),F('content','eq','Retain reference post.')))),True))
    return steps,preds
