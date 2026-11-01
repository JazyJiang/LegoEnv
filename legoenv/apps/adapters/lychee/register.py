"""Source-bound lychee adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='lychee';NEW_SERVER={APP:'lychee_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ auth_login(username,password). catalog_getalbumcatalog() reads real BaseAlbum.description. album_create(title) inserts BaseAlbum metadata with original runtime owner injection; album_update(album_id,title,description) updates; album_delete(album_ids=[id]) uses original multi executor. Source public catalog has no visibility guard.'}
LOGIN={APP:('auth_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='lychee';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'auth_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('catalog_getalbumcatalog', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'BaseAlbum',[{'id': 201, 'owner_id': 1, 'title': 'Policy', 'description': 'Policy: update album202 description to Reviewed and approved. and title Reviewed. Create Approved album. Keep Reference unchanged.'}, {'id': 202, 'owner_id': 1, 'title': 'Pending', 'description': 'Pending review.'}, {'id': 203, 'owner_id': 1, 'title': 'Reference', 'description': 'Retain reference album.'}])
    steps=[('__APP__', 'album_update', {'album_id': 202, 'title': 'Reviewed', 'description': 'Reviewed and approved.'}), ('__APP__', 'album_create', {'title': 'Approved'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'BaseAlbum'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'BaseAlbum'),AND(F('id','eq',202),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'BaseAlbum'),AND(F('title','eq','Approved'),F('owner_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'BaseAlbum'),AND(F('id','eq',203),F('description','eq','Retain reference album.')))),True))
    return steps,preds
