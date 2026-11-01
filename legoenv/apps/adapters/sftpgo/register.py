"""Source-bound sftpgo adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='sftpgo';NEW_SERVER={APP:'file_share_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Admin']]}
NEW_NOTES={APP:'{p}__ uses sign_in(username,password) as regular User1. share_search() and share_getbyid(share_id) read your Share.description policy. share_add(name,scope,paths) creates metadata without generating public share_id. share_update(share_id,name,scope,max_tokens,expires_at), share_delete(share_id) operate existing known public identities and enforce owner. No actual filesystem transfer, share-password hashing/enforcement, visitor token/expiry handling, file permissions or SFTP/network behavior certified. Admin operations require separate original admin realm and are not claimed.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='sftpgo';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('share_search', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Share',[{'id':101,'share_id':'policy-share','user_id':1,'name':'Policy share','description':'Policy: update review-share name to Reviewed operations, scope3 and max_tokens10. Keep reference-share description unchanged.','scope':1,'paths':['/synthetic/review']},{'id':102,'share_id':'review-share','user_id':1,'name':'Pending review','description':'Review context.','scope':1,'max_tokens':2,'paths':['/synthetic/review']},{'id':103,'share_id':'reference-share','user_id':1,'name':'Reference share','description':'Retain reference share description.','scope':1,'paths':['/synthetic/reference']}])
    steps=[(APP,'share_update',{'share_id':'review-share','name':'Reviewed operations'}),(APP,'share_update',{'share_id':'review-share','scope':3}),(APP,'share_update',{'share_id':'review-share','max_tokens':10})]
    preds=[('name','Share name updated.',CNT(SEL(NS(APP,'Share'),AND(F('share_id','eq','review-share'),F('name','eq','Reviewed operations')))),False),('scope','Scope scalar updated.',CNT(SEL(NS(APP,'Share'),AND(F('share_id','eq','review-share'),F('scope','eq',3)))),False),('limit','Token-limit metadata updated.',CNT(SEL(NS(APP,'Share'),AND(F('share_id','eq','review-share'),F('max_tokens','eq',10)))),False),('reference','Reference description unchanged.',CNT(SEL(NS(APP,'Share'),AND(F('share_id','eq','reference-share'),F('description','eq','Retain reference share description.')))),True)]
    return steps,preds
