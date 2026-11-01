'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nChyrp Lite source writes; no readable body carrier exists.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='chyrp_lite';NEW_SERVER={APP:'blog_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User','Group','Permission']]}
NEW_NOTES={APP:('{p}__ is blog metadata. user_login(login,password) verifies original Admin User1. post_manage(search,status,feather) reads own Post metadata (clean/url/status), not PostAttribute title/body. No Page, Comment or PostAttribute body read/list exists, so complete admission is blocked. page_add(title,body,slug), page_update(id,title,body,slug), page_delete(id,destroy), category_add(name,clean), category_update(id,name,clean), category_delete(id,destroy) write scalar records. post_update(id,body,status) persists status but ignores the body input; no actual article-content edit/publication/notification effects certified. Permission semantic codes are preserved in code with integer internal ids.')}
LOGIN={APP:('user_login','login')};SERVER.update(NEW_SERVER);PFX[APP]='chyrp_lite';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'login':self.persona,'password':self.password}).get('ok')
    r=env.call(NS(APP,'post_manage'),{});assert r.get('ok'),r;rep[APP+' post_manage']=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    raise RuntimeError('No readable business policy body interface: post_manage returns Post metadata only; Page.body, Comment.body and PostAttribute.value have no source read/list. Complete admission blocked.')
def metadata_smoke_seed(W):
    records(W,'Page',[{'id':101,'title':'Context','body':'Context text','user_id':1,'url':'context'},{'id':102,'title':'Review','body':'Pending review.','user_id':1,'url':'review'},{'id':103,'title':'Reference','body':'Retain this reference body.','user_id':1,'url':'reference'}]);records(W,'Post',[{'id':201,'user_id':1,'feather':'markdown','url':'review-post','clean':'review-post','status':'draft'}]);records(W,'PostAttribute',[{'id':301,'post_id':201,'name':'body','value':'Original post body.'}])
    steps=[(APP,'page_update',{'id':102,'title':'Reviewed page','body':'Reviewed and approved.','slug':'review'}),(APP,'page_add',{'title':'Approved page','body':'Approved page body.','slug':'approved-page'}),(APP,'category_add',{'name':'Approved category','clean':'approved-category'})]
    preds=[('update','Page raw body updated.',CNT(SEL(NS(APP,'Page'),AND(F('id','eq',102),F('body','eq','Reviewed and approved.')))),False),('create','Page created.',CNT(SEL(NS(APP,'Page'),F('url','eq','approved-page'))),False),('category','Category metadata created.',CNT(SEL(NS(APP,'Category'),F('clean','eq','approved-category'))),False),('reference','Reference page body unchanged.',CNT(SEL(NS(APP,'Page'),AND(F('id','eq',103),F('body','eq','Retain this reference body.')))),True)]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
