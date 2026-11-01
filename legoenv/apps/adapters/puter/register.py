"""Source-bound puter adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='puter';NEW_SERVER={APP:'desktop_app_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ uses sign_in(username,password). app_listownapps() reads your App.description policy; app_getbyname(name) reads known metadata. app_create(uid,name,title,index_url,description), app_update(uid,description,title), app_delete(uid) operate App records. App.uid remains text business identity. No application hosting/deployment or filesystem bytes are certified; fsentry_write fileContent is ignored by source executor. Source app_update checks owner; app_delete has a permissive existence alternative and must not be treated as complete ownership enforcement.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='puter';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('app_listownapps', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'App',[{'id':101,'uid':'policy-app','owner_user_id':1,'name':'policy','title':'Review policy','description':'Policy: update review-app description to Reviewed and approved. and title to Reviewed operations.; create approved-app named approved. Keep reference-app description unchanged.','protected':False},{'id':102,'uid':'review-app','owner_user_id':1,'name':'review','title':'Pending review','description':'Pending review.','protected':False},{'id':103,'uid':'reference-app','owner_user_id':1,'name':'reference','title':'Reference','description':'Retain reference app description.','protected':False}])
    steps=[(APP,'app_update',{'uid':'review-app','description':'Reviewed and approved.'}),(APP,'app_update',{'uid':'review-app','title':'Reviewed operations.'}),(APP,'app_create',{'uid':'approved-app','name':'approved','title':'Approved app','index_url':'https://approved.invalid','description':'Approved app metadata.'})]
    preds=[('description','Owned app description updated.',CNT(SEL(NS(APP,'App'),AND(F('uid','eq','review-app'),F('description','eq','Reviewed and approved.')))),False),('title','Owned app title updated.',CNT(SEL(NS(APP,'App'),AND(F('uid','eq','review-app'),F('title','eq','Reviewed operations.')))),False),('create','Owned app created.',CNT(SEL(NS(APP,'App'),AND(F('uid','eq','approved-app'),F('owner_user_id','eq',1)))),False),('reference','Reference description unchanged.',CNT(SEL(NS(APP,'App'),AND(F('uid','eq','reference-app'),F('description','eq','Retain reference app description.')))),True)]
    return steps,preds
