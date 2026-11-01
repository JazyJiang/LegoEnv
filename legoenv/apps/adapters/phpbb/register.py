"""Source-bound phpbb adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='phpbb';NEW_SERVER={APP:'phpbb_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Group', 'UserGroup', 'Forum', 'Topic']]}
NEW_NOTES={APP:'{p}__ sign_in(username,user_password) uses original User. post_quote_load(p) returns full Post.post_text policy. post_create(f,t,subject,message) appends local reply; topic_lock(topic_id,status) changes lock flag; post_delete(p,f,t) deletes row. Source post_update ignores subject/message aliases, so body editing is not certified. Source topic locking/deletion only checks any signed-in user, no moderator permission.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='phpbb';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'user_password':self.password}).get('ok')
    for t,args in [('post_quote_load', {'p': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Post',[{'id': 201, 'post_id': 201, 'topic_id': 10, 'forum_id': 1, 'poster_id': 1, 'post_subject': 'Policy', 'post_text': 'Policy: post Approved review. and Review complete. replies in forum1 topic10; lock topic10 state1. Keep Reference unchanged.', 'post_approved': True}, {'id': 202, 'post_id': 202, 'topic_id': 10, 'forum_id': 1, 'poster_id': 1, 'post_subject': 'Review', 'post_text': 'Pending review.', 'post_approved': True}, {'id': 203, 'post_id': 203, 'topic_id': 10, 'forum_id': 1, 'poster_id': 1, 'post_subject': 'Reference', 'post_text': 'Retain reference post.', 'post_approved': True}])
    steps=[('__APP__', 'post_create', {'f': 1, 't': 10, 'subject': 'Approved', 'message': 'Approved review.'}), ('__APP__', 'post_create', {'f': 1, 't': 10, 'subject': 'Complete', 'message': 'Review complete.'}), ('__APP__', 'topic_lock', {'topic_id': 10, 'status': 1})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('post_subject','eq','Approved'),F('post_text','eq','Approved review.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('post_subject','eq','Complete'),F('post_text','eq','Review complete.')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Topic'),AND(F('topic_id','eq',10),F('topic_status','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Post'),AND(F('post_id','eq',203),F('post_text','eq','Retain reference post.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'username':W.persona,'user_password':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
