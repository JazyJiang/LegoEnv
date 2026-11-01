"""Source-bound podfetch adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='podfetch';NEW_SERVER={APP:'podcast_tag_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['users']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). list_tags() reads own tags.description policy. create_tag(name,description,color), update_tag(tag_id,name,description,color), delete_tag(tag_id) operate own tags. Source schema requires color/description despite optional prose, so provide all fields. Admin/uploader/user roles unchanged; tag operations use owner identity. No feed/network/audio/download/playback/transcription/casting/models or Audiobookshelf effect certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='podfetch';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('list_tags', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'tags',[{'id':201,'user_id':1,'name':'Policy','description':'Policy: update tag 202 description to Reviewed and approved. and color to #008800. Create Approved tag. Keep Reference unchanged.','color':'#000000'},{'id':202,'user_id':1,'name':'Review','description':'Pending review.','color':'#000000'},{'id':203,'user_id':1,'name':'Reference','description':'Retain reference tag.','color':'#000000'}])
    steps=[(APP,'update_tag',{'tag_id':202,'name':'Review','description':'Reviewed and approved.','color':'#000000'}),(APP,'update_tag',{'tag_id':202,'name':'Review','description':'Reviewed and approved.','color':'#008800'}),(APP,'create_tag',{'name':'Approved','description':'Approved tag.','color':'#008800'})]
    preds=[('description','Tag description updated.',CNT(SEL(NS(APP,'tags'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False),('color','Tag color updated.',CNT(SEL(NS(APP,'tags'),AND(F('id','eq',202),F('color','eq','#008800')))),False),('create','Tag created.',CNT(SEL(NS(APP,'tags'),AND(F('name','eq','Approved'),F('user_id','eq',1)))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'tags'),AND(F('id','eq',203),F('description','eq','Retain reference tag.')))),True)]
    return steps,preds
