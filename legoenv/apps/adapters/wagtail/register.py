"""Wagtail source page flags, scalar revisions and collection records."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='wagtail';NEW_SERVER={APP:'cms'}
CONFIG={'User','UserProfile','Group','ContentType','Locale','Permission','Site','Collection'}
NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in CONFIG]}
NEW_NOTES={APP:('{p}__ is Wagtail. Sign in with {p}__sign_in(username,password), as User 1. '
    'page_search(q) lists owned Page metadata with optional title/search_description/seo_title substring filtering. Page.search_description carries policy. '
    'page_edit_get(page_id) lists Revisions with the numeric object_id representation produced by source draft insertion. '
    'page_edit_save_draft(page_id,title,content) inserts a Revision; it does not update Page title or revision pointers. '
    'page_lock/page_unlock(page_id) toggle locked; page_unpublish(page_id) sets a live non-root page live=false; page_bulk_publish(id=<single scalar id>) sets live=true only. '
    'collection_index(q), collection_create(parent,name), collection_edit(pk,name), collection_delete(pk) operate on scalar collection records; parent/tree changes are not implemented. '
    'page_delete(page_id) removes a non-root scalar page. Full tree creation/movement/descendant batching, publish pointers, lock enforcement, general ACLs, comments and binary media transfer are not certified.')}
LOGIN={APP:('sign_in','username')}
SERVER.update(NEW_SERVER);PFX[APP]='wagtail';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    reads=[('page_search',{}),('collection_index',{})]+[('page_edit_get',{'page_id':r['id']}) for r in env.state.get(NS(APP,'Page'),[])]
    for tool,args in reads:
        result=env.call(NS(APP,tool),args);assert result.get('ok'),result
        rep[APP+' '+tool+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(result,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def _append(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) and not isinstance(r['id'],bool) for r in rows)
    W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def pages(W,rows,src=None):return _append(W,'Page',[{'owner_id':1,'content_type_id':1,'locale_id':1,'depth':2,'path':f"0001{r['id']:04}",'url_path':f"/page-{r['id']}/",'slug':f"page-{r['id']}",'draft_title':r['title'],'live':True,'locked':False,'has_unpublished_changes':False,'numchild':0,**r} for r in rows],src)
def revisions(W,rows,src=None):return _append(W,'Revision',[{'content_type':1,'base_content_type':1,'created_at':W.now,'user_id':1,**r} for r in rows],src)
def collections(W,rows,src=None):return _append(W,'Collection',rows,src)
def smoke_seed(W):
    pages(W,[{'id':1,'title':'Home','depth':1,'path':'0001','search_description':'CMS root context.'},
        {'id':101,'title':'Review policy','search_description':'Policy: unpublish page102, create an approved revision, and lock it. Keep page103 reference search description unchanged.'},
        {'id':102,'title':'Review page','search_description':'Review pending.'},{'id':103,'title':'Reference page','search_description':'Retain this reference wording.'}])
    revisions(W,[{'id':201,'object_id':102,'object_str':'Review page','content':{'body':'Review pending.'}}])
    collections(W,[{'id':30,'name':'Review collection','numchild':0,'depth':2,'path':'00010003'}])
    steps=[(APP,'page_unpublish',{'page_id':102}),(APP,'page_edit_save_draft',{'page_id':102,'title':'Approved review draft','content':{'body':'Reviewed and approved.'}}),(APP,'page_lock',{'page_id':102})]
    preds=[('unpublished','Review page is not live.',CNT(SEL(NS(APP,'Page'),AND(F('id','eq',102),F('live','eq',False)))),False),
        ('revision','Approved revision exists.',CNT(SEL(NS(APP,'Revision'),AND(F('object_id','eq',102),F('content.body','eq','Reviewed and approved.')))),False),
        ('locked','Review page is locked.',CNT(SEL(NS(APP,'Page'),AND(F('id','eq',102),F('locked','eq',True)))),False),
        ('reference','Reference description unchanged.',CNT(SEL(NS(APP,'Page'),AND(F('id','eq',103),F('search_description','eq','Retain this reference wording.')))),True)]
    return steps,preds
__all__=['NEW_SERVER','pages','revisions','collections','smoke_seed']
