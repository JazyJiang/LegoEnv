"""Source-bound photoprism adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='photoprism';NEW_SERVER={APP:'photoprism_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Password', 'User', 'UserSettings']]}
NEW_NOTES={APP:'{p}__ session_create(uid,hash) uses original Password credential. album_get(uid) returns Album.album_description policy. album_create(title) inserts metadata with source fixed UID timestamp; only one create succeeds before collision. album_like(uid) sets favorite flag; album_delete(uid) sets deleted_at. album_update aliases ignore title/description, so edits are not certified. No images, ML vision, downloads or real storage.'}
LOGIN={APP:('session_create','uid')};SERVER.update(NEW_SERVER);PFX[APP]='photoprism';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'session_create'),{'uid':self.persona,'hash':self.password}).get('ok')
    for t,args in [('album_get', {'uid': 'policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Album',[{'id': 201, 'album_uid': 'policy', 'album_title': 'Policy', 'album_description': 'Policy: create Approved album. Favorite and soft-delete review album. Keep Reference unchanged.', 'created_by': 'ops@photoprism.example', 'album_type': 'album', 'album_favorite': False}, {'id': 202, 'album_uid': 'review', 'album_title': 'Review', 'album_description': 'Pending review.', 'created_by': 'ops@photoprism.example', 'album_type': 'album', 'album_favorite': False}, {'id': 203, 'album_uid': 'reference', 'album_title': 'Reference', 'album_description': 'Retain reference album.', 'created_by': 'ops@photoprism.example', 'album_type': 'album', 'album_favorite': False}])
    steps=[('__APP__', 'album_create', {'title': 'Approved'}), ('__APP__', 'album_like', {'uid': 'review'}), ('__APP__', 'album_delete', {'uid': 'review'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Album'),AND(F('album_title','eq','Approved'),F('created_by','eq','ops@photoprism.example')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Album'),AND(F('album_uid','eq','review'),F('album_favorite','eq',True)))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Album'),AND(F('album_uid','eq','review'),F('deleted_at','eq','2026-01-01T00:00:00Z')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Album'),AND(F('album_uid','eq','reference'),F('album_description','eq','Retain reference album.')))),True))
    steps=[lambda e:e.call(NS(APP,'session_create'),{'uid':W.persona,'hash':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds
