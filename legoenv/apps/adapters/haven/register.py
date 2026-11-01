"""Source-bound haven adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='haven';NEW_SERVER={APP:'haven_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) uses original User admin/publisher/member flags. show_post(id) reads genuine Post.content policy. create_post(content,datetime), update_post(id,content,datetime), delete_post(id) mutate native post rows with source publisher/admin or author checks. Dates are stored metadata only. No web publication, scheduling, Markdown execution, feed fetch or email.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='haven';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('show_post', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Post',[{'id': 201, 'content': 'Policy: update post202 content to Reviewed and approved. and datetime 2026-10-20T00:00:00. Create Approved post. Keep Reference unchanged.', 'datetime': '2026-01-01T00:00:00', 'author_id': 1}, {'id': 202, 'content': 'Pending review.', 'datetime': '2026-01-01T00:00:00', 'author_id': 1}, {'id': 203, 'content': 'Retain reference post.', 'datetime': '2026-01-01T00:00:00', 'author_id': 1}])
    steps=[('__APP__', 'update_post', {'id': 202, 'content': 'Reviewed and approved.', 'datetime': '2026-10-20T00:00:00'}), ('__APP__', 'create_post', {'content': 'Approved post.', 'datetime': '2026-10-20T00:00:00'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('id','eq',202),F('content','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('id','eq',202),F('datetime','eq','2026-10-20T00:00:00')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('content','eq','Approved post.'),F('author_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('id','eq',203),F('content','eq','Retain reference post.')))),True))
    return steps,preds
