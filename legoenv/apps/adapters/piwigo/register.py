"""Source-bound piwigo adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='piwigo';NEW_SERVER={APP:'piwigo_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'UserInfos']]}
NEW_NOTES={APP:'{p}__ session_login(username,password). category_getlist() reads genuine comment. category_add(name,comment,status,visible), category_setinfo(category_id,name,comment), category_delete(category_id,pwg_token) edit local album metadata. Native pwg_token guard checks presence only and source tools lack admin-status predicate; guest write behavior is preserved.'}
LOGIN={APP:('session_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='piwigo';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'session_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('category_getlist', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Category',[{'id': 201, 'name': 'Policy', 'comment': 'Policy: update album202 comment to Reviewed and approved. and name Reviewed. Create Approved album. Keep Reference unchanged.', 'status': 'public', 'visible': True}, {'id': 202, 'name': 'Pending', 'comment': 'Pending review.', 'status': 'public', 'visible': True}, {'id': 203, 'name': 'Reference', 'comment': 'Retain reference album.', 'status': 'public', 'visible': True}])
    steps=[('__APP__', 'category_setinfo', {'category_id': 202, 'name': 'Reviewed', 'comment': 'Reviewed and approved.'}), ('__APP__', 'category_add', {'name': 'Approved', 'comment': 'Approved album.', 'status': 'public', 'visible': True})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Category'),AND(F('id','eq',202),F('comment','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Category'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Category'),AND(F('name','eq','Approved'),F('comment','eq','Approved album.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Category'),AND(F('id','eq',203),F('comment','eq','Retain reference album.')))),True))
    return steps,preds
