"""Source-bound wordpress adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='wordpress';NEW_SERVER={APP:'wordpress_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Usermeta', 'Post']]}
NEW_NOTES={APP:'{p}__ sign_in(user_login,user_pass) uses original User and serialized Usermeta administrator capability. get_comment(id) reads Comment.comment_content policy. create_comment(post,content), update_comment(id,content,status), delete_comment(id,force) edit metadata; native deletion removes row even force=false. No Post read tool or public site publication invented.'}
LOGIN={APP:('sign_in','user_login')};SERVER.update(NEW_SERVER);PFX[APP]='wordpress';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'user_login':self.persona,'user_pass':self.password}).get('ok')
    for t,args in [('get_comment', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Comment',[{'id': 201, 'comment_ID': 201, 'comment_post_ID': 1, 'comment_content': 'Policy: update comment202 body to Reviewed and approved. and approval status1. Add Approved comment on post1. Keep Reference unchanged.', 'user_id': 1, 'comment_approved': '1', 'comment_parent': 0}, {'id': 202, 'comment_ID': 202, 'comment_post_ID': 1, 'comment_content': 'Pending review.', 'user_id': 1, 'comment_approved': '0', 'comment_parent': 0}, {'id': 203, 'comment_ID': 203, 'comment_post_ID': 1, 'comment_content': 'Retain reference comment.', 'user_id': 1, 'comment_approved': '1', 'comment_parent': 0}])
    steps=[('__APP__', 'update_comment', {'id': 202, 'content': 'Reviewed and approved.', 'status': '1'}), ('__APP__', 'create_comment', {'post': 1, 'content': 'Approved comment.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('comment_ID','eq',202),F('comment_content','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('comment_ID','eq',202),F('comment_approved','eq','1')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('comment_content','eq','Approved comment.'),F('comment_post_ID','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('comment_ID','eq',203),F('comment_content','eq','Retain reference comment.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'user_login':W.persona,'user_pass':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
