"""Source-bound memos adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='memos';NEW_SERVER={APP:'memo_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Space', 'SpaceMember']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password) verifies original password_hash and NORMAL user guard. get_memo(name=<uid>) or list_memos() reads genuine Memo.content policy. create_memo(memo_id,content,visibility), update_memo(name,update_mask,content,pinned), delete_memo(name) operate own memo records. UID/name is the literal business uid, not a resource path. update_mask is required but source ignores it; create payload remains literal placeholder. No attachments/location/email/OAuth/AI or external effects certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='memos';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('get_memo', {'name': 'policy'}), ('list_memos', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Memo',[{'id':201,'uid':'policy','creator_id':1,'row_status':'NORMAL','content':'Policy: update review memo content to Reviewed and approved. and pin it. Create approved memo with Approved content. Keep Reference unchanged.','visibility':'PRIVATE','pinned':0,'payload':{}},{'id':202,'uid':'review','creator_id':1,'row_status':'NORMAL','content':'Pending review.','visibility':'PRIVATE','pinned':0,'payload':{}},{'id':203,'uid':'reference','creator_id':1,'row_status':'NORMAL','content':'Retain reference memo.','visibility':'PRIVATE','pinned':0,'payload':{}}])
    steps=[(APP,'update_memo',{'name':'review','update_mask':['content'],'content':'Reviewed and approved.'}),(APP,'update_memo',{'name':'review','update_mask':['pinned'],'pinned':True}),(APP,'create_memo',{'memo_id':'approved','content':'Approved content.','visibility':'PRIVATE'})]
    preds=[('content','Memo body updated.',CNT(SEL(NS(APP,'Memo'),AND(F('uid','eq','review'),F('content','eq','Reviewed and approved.')))),False),('pin','Memo pinned.',CNT(SEL(NS(APP,'Memo'),AND(F('uid','eq','review'),F('pinned','eq',1)))),False),('create','Memo created.',CNT(SEL(NS(APP,'Memo'),AND(F('uid','eq','approved'),F('content','eq','Approved content.'),F('creator_id','eq',1)))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'Memo'),AND(F('uid','eq','reference'),F('content','eq','Retain reference memo.')))),True)]
    return steps,preds
