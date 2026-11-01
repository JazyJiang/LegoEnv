"""Source-bound audiobookshelf adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='audiobookshelf';NEW_SERVER={APP:'audio_playlist_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Library', 'LibraryFolder']]}
NEW_NOTES={APP:'{p}__ uses sign_in(username,password). User1 retains source root role. list_my_playlists() and get_playlist(id) read Playlist.description policy. create_playlist(name,libraryId,description), update_playlist(id,name,description), delete_playlist(id) operate scalar records with source admin/root plus owner rules. items input does not create full PlaylistItem membership. No audio/file streaming, playback synchronization, metadata fetching, podcast download, library scan or backup application certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='audiobookshelf';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('list_my_playlists', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Playlist',[{'id':201,'libraryId':1,'userId':1,'name':'Review policy','description':'Policy: update playlist202 description Reviewed and approved. and name Reviewed operations; create Approved playlist in library1. Keep playlist203 description unchanged.'},{'id':202,'libraryId':1,'userId':1,'name':'Pending review','description':'Pending review.'},{'id':203,'libraryId':1,'userId':1,'name':'Reference playlist','description':'Retain reference playlist description.'}])
    steps=[(APP,'update_playlist',{'id':202,'description':'Reviewed and approved.'}),(APP,'update_playlist',{'id':202,'name':'Reviewed operations'}),(APP,'create_playlist',{'name':'Approved playlist','libraryId':1,'description':'Approved playlist metadata'})]
    preds=[('description','Playlist description updated.',CNT(SEL(NS(APP,'Playlist'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False),('name','Playlist name updated.',CNT(SEL(NS(APP,'Playlist'),AND(F('id','eq',202),F('name','eq','Reviewed operations')))),False),('create','Owned playlist created.',CNT(SEL(NS(APP,'Playlist'),AND(F('name','eq','Approved playlist'),F('userId','eq',1)))),False),('reference','Reference playlist unchanged.',CNT(SEL(NS(APP,'Playlist'),AND(F('id','eq',203),F('description','eq','Retain reference playlist description.')))),True)]
    return steps,preds
