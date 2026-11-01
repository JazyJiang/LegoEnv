"""Source-bound peertube adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='peertube';NEW_SERVER={APP:'peertube_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Account', 'Actor', 'VideoChannel']]}
NEW_NOTES={APP:'{p}__ auth_login(username,password). videoplaylist_read(playlistId=201) reads description. videoplaylist_create(displayName,description,privacy) creates metadata; videoplaylist_update(playlistId,description,privacy) edits it but sets name null, ignoring displayName; videoplaylist_delete(playlistId) deletes. Native guards check User existence only, not playlist owner.'}
LOGIN={APP:('auth_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='peertube';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'auth_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('videoplaylist_read', {'playlistId': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'VideoPlaylist',[{'id': 201, 'name': 'Policy', 'description': 'Policy: update playlist202 description to Reviewed and approved. and privacy3. Create Approved playlist. Keep Reference unchanged.', 'privacy': 1, 'ownerAccountId': 1, 'videoChannelId': 1}, {'id': 202, 'name': 'Pending', 'description': 'Pending review.', 'privacy': 1, 'ownerAccountId': 1, 'videoChannelId': 1}, {'id': 203, 'name': 'Reference', 'description': 'Retain reference playlist.', 'privacy': 1, 'ownerAccountId': 1, 'videoChannelId': 1}])
    steps=[('__APP__', 'videoplaylist_update', {'playlistId': 202, 'description': 'Reviewed and approved.', 'privacy': 3}), ('__APP__', 'videoplaylist_create', {'displayName': 'Approved', 'description': 'Approved playlist.', 'privacy': 1})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'VideoPlaylist'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'VideoPlaylist'),AND(F('id','eq',202),F('privacy','eq',3)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'VideoPlaylist'),AND(F('name','eq','Approved'),F('description','eq','Approved playlist.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'VideoPlaylist'),AND(F('id','eq',203),F('description','eq','Retain reference playlist.')))),True))
    return steps,preds
