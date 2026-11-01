"""Source-bound owncloud_core adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='owncloud_core';NEW_SERVER={APP:'cloud_comment_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ uses sign_in(uid,password); text uid remains business identity and session.account_name. comment_list(objectType,objectId) reads Comment.message policy; comment_create(objectType,objectId,message), comment_update(commentId,message), comment_delete(commentId) operate authored comments. privatedata_set(app,key,value), privatedata_get(app,key), privatedata_delete(app,key) operate your text-uid data. No source file-content read/write interface, full DAV calendar/addressbook lifecycle, permission sharing, token transport or network effects certified.'}
LOGIN={APP:('sign_in','uid')};SERVER.update(NEW_SERVER);PFX[APP]='owncloud_core';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'uid':self.persona,'password':self.password}).get('ok')
    for t,args in [('comment_list', {'objectType': 'files', 'objectId': 'review'}), ('privatedata_get', {'app': 'review'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Comment',[{'id':101,'actor_type':'users','actor_id':W.persona,'object_type':'files','object_id':'review','message':'Policy: update comment102 to Reviewed and approved.; create Review recorded. comment on files/review; set private app review key approval value approved. Keep comment103 message unchanged.'},{'id':102,'actor_type':'users','actor_id':W.persona,'object_type':'files','object_id':'review','message':'Pending review.'},{'id':103,'actor_type':'users','actor_id':W.persona,'object_type':'files','object_id':'review','message':'Retain reference comment.'}])
    steps=[(APP,'comment_update',{'commentId':102,'message':'Reviewed and approved.'}),(APP,'comment_create',{'objectType':'files','objectId':'review','message':'Review recorded.'}),(APP,'privatedata_set',{'app':'review','key':'approval','value':'approved'})]
    preds=[('edit','Comment updated.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',102),F('message','eq','Reviewed and approved.')))),False),('create','Comment created.',CNT(SEL(NS(APP,'Comment'),AND(F('object_id','eq','review'),F('message','eq','Review recorded.')))),False),('private','Own private data persisted.',CNT(SEL(NS(APP,'PrivateData'),AND(F('user','eq',W.persona),F('app','eq','review'),F('key','eq','approval'),F('value','eq','approved')))),False),('reference','Reference comment unchanged.',CNT(SEL(NS(APP,'Comment'),AND(F('id','eq',103),F('message','eq','Retain reference comment.')))),True)]
    return steps,preds
