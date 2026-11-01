"""Source-bound chibisafe adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='chibisafe';NEW_SERVER={APP:'album_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Users', 'Roles', 'UsersRoles']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). albums_list() or albums_getone(uuid) reads Albums.description policy. albums_create(name), albums_update(uuid,name,description), albums_delete(uuid) operate album metadata. Native deterministic UUID auto-generation is preserved, without crypto guarantee. Source enabled-user OR owner guards allow any enabled user to read/update/delete another album; disabled new-name create may also pass the no-duplicate alternative. No file upload/ZIP/download/sharing or external effects certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='chibisafe';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('albums_list', {}), ('albums_getone', {'uuid': 'policy-album'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Albums',[{'id':201,'uuid':'policy-album','userId':1,'name':'Policy','description':'Policy: update review-album description to Reviewed and approved. and name to Reviewed operations. Create Approved album. Keep Reference unchanged.','nsfw':False},{'id':202,'uuid':'review-album','userId':1,'name':'Review','description':'Pending review.','nsfw':False},{'id':203,'uuid':'reference-album','userId':1,'name':'Reference','description':'Retain reference album.','nsfw':False}])
    steps=[(APP,'albums_update',{'uuid':'review-album','description':'Reviewed and approved.'}),(APP,'albums_update',{'uuid':'review-album','name':'Reviewed operations.'}),(APP,'albums_create',{'name':'Approved'})]
    preds=[('description','Album description updated.',CNT(SEL(NS(APP,'Albums'),AND(F('uuid','eq','review-album'),F('description','eq','Reviewed and approved.')))),False),('name','Album renamed.',CNT(SEL(NS(APP,'Albums'),AND(F('uuid','eq','review-album'),F('name','eq','Reviewed operations.')))),False),('create','Album record created.',CNT(SEL(NS(APP,'Albums'),AND(F('name','eq','Approved'),F('userId','eq',1)))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'Albums'),AND(F('uuid','eq','reference-album'),F('description','eq','Retain reference album.')))),True)]
    return steps,preds
