"""Source-bound artalk adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='artalk';NEW_SERVER={APP:'artalk_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Site', 'Page']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) uses original admin flag. comment_get(id) reads genuine Comment.content policy publicly. comment_create(name,email,content,page_key,site_name) trusts existing name/email; comment_update(id,site_name,is_pending,content,is_pinned) and comment_delete(id) require source admin. No email-code verification, Markdown rendering or actual hosted comments delivery.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='artalk';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('comment_get', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Comment',[{'id': 201, 'content': 'Policy: update comment202 content to Reviewed and approved. and pin it. Create Approved comment on /blog/hello at example site. Keep Reference unchanged.', 'user_id': 1, 'page_key': '/blog/hello', 'site_name': 'example', 'is_pending': False, 'is_pinned': False}, {'id': 202, 'content': 'Pending review.', 'user_id': 1, 'page_key': '/blog/hello', 'site_name': 'example', 'is_pending': True, 'is_pinned': False}, {'id': 203, 'content': 'Retain reference comment.', 'user_id': 1, 'page_key': '/blog/hello', 'site_name': 'example', 'is_pending': False, 'is_pinned': False}])
    steps=[('__APP__', 'comment_update', {'id': 202, 'site_name': 'example', 'is_pending': False, 'content': 'Reviewed and approved.', 'is_pinned': True}), ('__APP__', 'comment_create', {'name': 'admin', 'email': 'ops@artalk.example', 'content': 'Approved comment.', 'page_key': '/blog/hello', 'site_name': 'example'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',202),F('content','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',202),F('is_pinned','eq',True)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('content','eq','Approved comment.'),F('user_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',203),F('content','eq','Retain reference comment.')))),True))
    return steps,preds
