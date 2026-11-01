"""Source-bound remark42 adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='remark42';NEW_SERVER={APP:'remark42_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) uses original source synthetic password mirror; no emailed login link validation. comment_by_id(id,site,url) reads text, source lookup actually keys only id. comment_create(site,url,text), comment_edit(id,site,url,text), comment_delete(id,site,url) edit local comments; delete is admin soft-delete that blanks body.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='remark42';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('comment_by_id', {'id': 201, 'site': 'demo', 'url': 'https://page.invalid'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Comment',[{'id': 201, 'user_id': 1, 'site_id': 'demo', 'url': 'https://page.invalid', 'text': 'Policy: edit comment202 to Reviewed and approved. Append Approved comment and Approved second comment. Keep Reference unchanged.', 'deleted': False}, {'id': 202, 'user_id': 1, 'site_id': 'demo', 'url': 'https://page.invalid', 'text': 'Pending review.', 'deleted': False}, {'id': 203, 'user_id': 1, 'site_id': 'demo', 'url': 'https://page.invalid', 'text': 'Retain reference comment.', 'deleted': False}])
    steps=[('__APP__', 'comment_edit', {'id': 202, 'site': 'demo', 'url': 'https://page.invalid', 'text': 'Reviewed and approved.'}), ('__APP__', 'comment_create', {'site': 'demo', 'url': 'https://page.invalid', 'text': 'Approved comment.'}), ('__APP__', 'comment_create', {'site': 'demo', 'url': 'https://page.invalid', 'text': 'Approved second comment.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',202),F('text','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Comment'),F('text','eq','Approved comment.'))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Comment'),F('text','eq','Approved second comment.'))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',203),F('text','eq','Retain reference comment.')))),True))
    return steps,preds
