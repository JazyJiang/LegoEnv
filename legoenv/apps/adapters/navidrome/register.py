"""Source-bound navidrome adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='navidrome';NEW_SERVER={APP:'navidrome_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ user_login(user_name,password). playlist_getwithtracks(id=201) returns genuine Playlist.comment metadata, not media bytes or joined tracks. playlist_create(name), playlist_update(playlistId,name,comment), playlist_delete(id) certify native local records. Nonowner update/delete denied; native fetch ignores private owner scope.'}
LOGIN={APP:('user_login','user_name')};SERVER.update(NEW_SERVER);PFX[APP]='navidrome';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'user_name':self.persona,'password':self.password}).get('ok')
    for t,args in [('playlist_getwithtracks', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Playlist',[{'id': 201, 'owner_id': 1, 'name': 'Policy', 'comment': 'Policy: update playlist202 comment to Reviewed and approved. and name Reviewed. Create Approved playlist metadata. Keep Reference unchanged.', 'public': False}, {'id': 202, 'owner_id': 1, 'name': 'Pending', 'comment': 'Pending review.', 'public': False}, {'id': 203, 'owner_id': 1, 'name': 'Reference', 'comment': 'Retain reference playlist.', 'public': False}])
    steps=[('__APP__', 'playlist_update', {'playlistId': 202, 'name': 'Reviewed', 'comment': 'Reviewed and approved.'}), ('__APP__', 'playlist_create', {'name': 'Approved'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Playlist'),AND(F('id','eq',202),F('comment','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Playlist'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Playlist'),AND(F('name','eq','Approved'),F('owner_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Playlist'),AND(F('id','eq',203),F('comment','eq','Retain reference playlist.')))),True))
    return steps,preds
