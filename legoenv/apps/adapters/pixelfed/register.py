"""Source-bound pixelfed adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='pixelfed';NEW_SERVER={APP:'social_profile_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ uses user_login(email,password); regular User1 links to Profile1. federation_webfinger(resource) returns Profile metadata including bio policy, but source ignores resource and does not implement real WebFinger/visibility isolation. user_updateprofile(name,bio) updates your profile; customfilter_create(title,context,filter_action), customfilter_update(id,title,filter_action), customfilter_delete(id) operate owned filter metadata. directmessage_create(to_id,message,type) only inserts direct Status.caption; it does not create a DirectMessage row, so thread/read/delete are not a complete send workflow. No federation/network delivery, media processing or filter execution certified.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='pixelfed';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('federation_webfinger', {'resource': 'ada'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Profile',[{'id':1,'user_id':1,'username':'ada','name':'Pending review','bio':'Policy: set own display name Reviewed operations; create direct Status caption Review recorded. to profile2; create filter Approved filter. Keep profile3 bio unchanged.'},{'id':2,'user_id':2,'username':'grace','name':'Colleague','bio':'Review context.'},{'id':3,'user_id':3,'username':'alan','name':'Reference','bio':'Retain reference profile bio.'},{'id':4,'user_id':4,'username':'linus','name':'Administrator','bio':'Administrative context.'}])
    steps=[(APP,'user_updateprofile',{'name':'Reviewed operations'}),(APP,'directmessage_create',{'to_id':2,'message':'Review recorded.','type':'text'}),(APP,'customfilter_create',{'title':'Approved filter','context':['home'],'filter_action':'warn'})]
    preds=[('profile','Own display name updated.',CNT(SEL(NS(APP,'Profile'),AND(F('id','eq',1),F('name','eq','Reviewed operations')))),False),('status','Direct Status record created.',CNT(SEL(NS(APP,'Status'),AND(F('profile_id','eq',1),F('caption','eq','Review recorded.'),F('scope','eq','direct')))),False),('filter','Own filter record created.',CNT(SEL(NS(APP,'CustomFilter'),AND(F('profile_id','eq',1),F('phrase','eq','Approved filter')))),False),('reference','Reference bio unchanged.',CNT(SEL(NS(APP,'Profile'),AND(F('id','eq',3),F('bio','eq','Retain reference profile bio.')))),True)]
    return steps,preds
