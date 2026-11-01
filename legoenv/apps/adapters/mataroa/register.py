"""Source-bound mataroa adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='mataroa';NEW_SERVER={APP:'mataroa_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password) uses real User and its existing api_key. api_get_page(slug) reads Page.body policy; api_list_pages() lists own pages. create_page(title,slug,body), update_page(slug,title,body,is_hidden), delete_page(slug) use original owner-scoped keys. No email/newsletter/image bytes/billing or site publishing effects certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='mataroa';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('api_get_page', {'slug': 'policy'}), ('api_list_pages', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Page',[{'id': 201, 'title': 'Policy', 'slug': 'policy', 'body': 'Policy: update review page body to Reviewed and approved. and title to Reviewed. Create approved page. Keep Reference unchanged.', 'owner': 1, 'is_hidden': False}, {'id': 202, 'title': 'Pending', 'slug': 'review', 'body': 'Pending review.', 'owner': 1, 'is_hidden': False}, {'id': 203, 'title': 'Reference', 'slug': 'reference', 'body': 'Retain reference page.', 'owner': 1, 'is_hidden': False}])
    steps=[('__APP__', 'update_page', {'slug': 'review', 'body': 'Reviewed and approved.'}), ('__APP__', 'update_page', {'slug': 'review', 'title': 'Reviewed'}), ('__APP__', 'create_page', {'title': 'Approved', 'slug': 'approved', 'body': 'Approved page.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('slug','eq','review'),F('body','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('slug','eq','review'),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('slug','eq','approved'),F('owner','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Page'),AND(F('slug','eq','reference'),F('body','eq','Retain reference page.')))),True))
    return steps,preds
