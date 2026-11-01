"""Source-bound mediacms adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='mediacms';NEW_SERVER={APP:'media_playlist_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ uses loginview_login(username,password). playlistlist_search() reads Playlist.description policy globally; mediadetail_read(friendly_token) reads known Media metadata. playlistlist_create(title,description) inserts metadata but omits friendly_token generation; playlistdetail_update(friendly_token,title,description) changes known records; playlistdetail_delete(friendly_token) deletes under source editor/manager guards. mediadetail_update(friendly_token,title,description) edits existing metadata. No binary upload, video transcode/trim, subtitle processing, actual publication or streaming delivery certified. Playlist update/read source ACL is incomplete.'}
LOGIN={APP:('loginview_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='mediacms';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'loginview_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('playlistlist_search', {}), ('mediadetail_read', {'friendly_token': 'review-media'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Playlist',[{'id':101,'friendly_token':'policy-list','user_id':1,'title':'Policy','description':'Policy: update review-list description Reviewed playlist.; update media review-media title Reviewed media.; create Approved playlist. Keep reference-list description unchanged.'},{'id':102,'friendly_token':'review-list','user_id':1,'title':'Review playlist','description':'Pending review.'},{'id':103,'friendly_token':'reference-list','user_id':1,'title':'Reference','description':'Retain reference playlist description.'}]);records(W,'Media',[{'id':201,'friendly_token':'review-media','user_id':1,'title':'Pending media','description':'Review media context.','listable':True}])
    steps=[(APP,'playlistdetail_update',{'friendly_token':'review-list','description':'Reviewed playlist.'}),(APP,'mediadetail_update',{'friendly_token':'review-media','title':'Reviewed media.'}),(APP,'playlistlist_create',{'title':'Approved playlist','description':'Approved playlist metadata.'})]
    preds=[('playlist','Playlist description updated.',CNT(SEL(NS(APP,'Playlist'),AND(F('friendly_token','eq','review-list'),F('description','eq','Reviewed playlist.')))),False),('media','Media title updated.',CNT(SEL(NS(APP,'Media'),AND(F('friendly_token','eq','review-media'),F('title','eq','Reviewed media.')))),False),('create','Owned playlist created.',CNT(SEL(NS(APP,'Playlist'),AND(F('title','eq','Approved playlist'),F('user_id','eq',1)))),False),('reference','Reference playlist unchanged.',CNT(SEL(NS(APP,'Playlist'),AND(F('friendly_token','eq','reference-list'),F('description','eq','Retain reference playlist description.')))),True)]
    return steps,preds
