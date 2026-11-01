"""Source-bound idno adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='idno';NEW_SERVER={APP:'social_content'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ uses sign_in(handle,password). homepage_stream(q) reads published visible Entry bodies; entity_view(id) fetches a known Entry. Entry.body carries policy. entry_edit/status_edit/event_edit(id,body,...) insert on missing numeric id. On existing records source upsert only changes publication/owner metadata and does not replace body. annotation_post(object,type,body) sets one Entry.annotations scalar via uuid, not an append-only structured thread. entry_delete/status_delete/event_delete(id) delete known records. No federation/network delivery, complete scheduling or comprehensive read ACL is certified.'}
LOGIN={APP:('sign_in','handle')};SERVER.update(NEW_SERVER);PFX[APP]='idno';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'handle':self.persona,'password':self.password}).get('ok')
    for t,args in [('homepage_stream', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Entry',[{'id':201,'_id':201,'uuid':'policy-entry','owner':1,'access':'PUBLIC','publish_status':'published','title':'Policy','body':'Policy: create Entry401 with Approved record.; publish Entry202 using entry_edit; set Entry202 annotations to Review recorded. Keep reference Entry203 body unchanged.'},{'id':202,'_id':202,'uuid':'review-entry','owner':1,'access':'PUBLIC','publish_status':'draft','title':'Review','body':'Original review body.'},{'id':203,'_id':203,'uuid':'reference-entry','owner':2,'access':'PUBLIC','publish_status':'published','title':'Reference','body':'Retain reference body.'}])
    steps=[(APP,'entry_edit',{'id':401,'body':'Approved record.','title':'Approved','access':'PUBLIC','publish_status':'published'}),(APP,'entry_edit',{'id':202,'body':'Ignored replacement body.'}),(APP,'annotation_post',{'object':'review-entry','type':'reply','body':'Review recorded.'})]
    preds=[('create','Entry body inserted.',CNT(SEL(NS(APP,'Entry'),AND(F('_id','eq',401),F('body','eq','Approved record.')))),False),('publish','Existing entry metadata published.',CNT(SEL(NS(APP,'Entry'),AND(F('_id','eq',202),F('publish_status','eq','published')))),False),('annotation','Scalar annotation persisted.',CNT(SEL(NS(APP,'Entry'),AND(F('_id','eq',202),F('annotations','eq','Review recorded.')))),False),('reference','Reference body unchanged.',CNT(SEL(NS(APP,'Entry'),AND(F('_id','eq',203),F('body','eq','Retain reference body.')))),True)]
    return steps,preds
