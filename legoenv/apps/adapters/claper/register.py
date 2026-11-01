"""Source-bound claper adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='claper';NEW_SERVER={APP:'claper_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Role', 'Event', 'ActivityLeader']]}
NEW_NOTES={APP:'{p}__ user_log_in(email,password) uses original User. post_list(event_id) reads real Post.body policy. post_create(body,name) inserts local row but has no event link input. post_toggle_pin(id=<uuid>) only sets true, never unpins. post_delete(id=<uuid>) checks actual row owner. Native pin guard accepts owner of any event, so cross-event pin is possible. No live presentation/chat/broadcast effects.'}
LOGIN={APP:('user_log_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='claper';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_log_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('post_list', {'event_id': 1})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Post',[{'id': 201, 'uuid': 'policy-post', 'body': 'Policy: pin review-post. Add Approved review. and Review complete. posts. Keep Reference unchanged.', 'event_id': 1, 'user_id': 1, 'pinned': False}, {'id': 202, 'uuid': 'review-post', 'body': 'Pending review.', 'event_id': 1, 'user_id': 1, 'pinned': False}, {'id': 203, 'uuid': 'reference-post', 'body': 'Retain reference post.', 'event_id': 1, 'user_id': 1, 'pinned': False}])
    steps=[('__APP__', 'post_toggle_pin', {'id': 'review-post'}), ('__APP__', 'post_create', {'body': 'Approved review.', 'name': 'Approved'}), ('__APP__', 'post_create', {'body': 'Review complete.', 'name': 'Complete'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('uuid','eq','review-post'),F('pinned','eq',True)))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('body','eq','Approved review.'),F('user_id','eq',1)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('body','eq','Review complete.'),F('user_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('uuid','eq','reference-post'),F('body','eq','Retain reference post.')))),True))
    return steps,preds
