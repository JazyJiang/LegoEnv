"""Source-bound pigallery2 adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='pigallery2';NEW_SERVER={APP:'gallery_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(name,password). gallery_get_media(mediaPath=policy.jpg) reads Media.metadataCaption policy; source lookup matches Media.name only. person_list(), album_list() read metadata. person_update(name,isFavourite) toggles a matching existing person; it cannot rename through separate new-name arg. album_create_saved_search(name,searchQuery), album_delete(id) operate saved-search records. Source admin OR unlocked delete allows admin to delete locked albums. No media bytes/upload/job/extension execution or real share expiry certified.'}
LOGIN={APP:('sign_in','name')};SERVER.update(NEW_SERVER);PFX[APP]='pigallery2';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'name':self.persona,'password':self.password}).get('ok')
    for t,args in [('gallery_get_media', {'mediaPath': 'policy.jpg'}), ('person_list', {}), ('album_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Directory',[{'id':210,'name':'Operations','path':'/operations','lastModified':0,'lastScanned':0,'parent_id':None}])
    records(W,'Media',[{'id':101,'name':'policy.jpg','type':'photo','directory_id':210,'metadataCaption':'Policy: mark Alice and Bob as favourites. Create Approved saved-search album. Keep Reference person unchanged.','metadataPersonsLength':0}])
    records(W,'Person',[{'id':301,'name':'Alice','isFavourite':False},{'id':302,'name':'Bob','isFavourite':False},{'id':303,'name':'Reference','isFavourite':False}])
    records(W,'Album',[{'id':501,'name':'Reference album','type':'savedSearch','locked':True,'searchQuery':{'type':'text','text':'reference'}}])
    steps=[(APP,'person_update',{'name':'Alice','isFavourite':True}),(APP,'person_update',{'name':'Bob','isFavourite':True}),(APP,'album_create_saved_search',{'name':'Approved','searchQuery':{'type':'text','text':'approved'}})]
    preds=[('alice','Alice marked favourite.',CNT(SEL(NS(APP,'Person'),AND(F('id','eq',301),F('isFavourite','eq',True)))),False),('bob','Bob marked favourite.',CNT(SEL(NS(APP,'Person'),AND(F('id','eq',302),F('isFavourite','eq',True)))),False),('create','Saved-search album created.',CNT(SEL(NS(APP,'Album'),F('name','eq','Approved'))),False),('reference','Reference person retained.',CNT(SEL(NS(APP,'Person'),AND(F('id','eq',303),F('isFavourite','eq',False)))),True)]
    return steps,preds
