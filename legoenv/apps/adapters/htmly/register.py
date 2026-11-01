"""Source-bound htmly adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='htmly';NEW_SERVER={APP:'htmly_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ auth_login(username,password) uses original admin/editor User identity via explicit username session. staticpage_read(static=<slug>) reads StaticPage.body policy. staticpage_create(title,url,content), staticpage_update(slug,title,content,status), staticpage_delete(slug) edit local content metadata. Both existing admin and editor can edit any page. No filesystem Markdown publication, MFA, feeds, comments or URL rename effects certified.'}
LOGIN={APP:('auth_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='htmly';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'auth_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('staticpage_read', {'static': 'policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'StaticPage',[{'id': 201, 'slug': 'policy', 'title': 'Policy', 'body': 'Policy: update review page body to Reviewed and approved. and title to Reviewed. Create approved page. Keep Reference unchanged.', 'status': 'published'}, {'id': 202, 'slug': 'review', 'title': 'Pending', 'body': 'Pending review.', 'status': 'published'}, {'id': 203, 'slug': 'reference', 'title': 'Reference', 'body': 'Retain reference page.', 'status': 'published'}])
    steps=[('__APP__', 'staticpage_update', {'slug': 'review', 'title': 'Reviewed', 'content': 'Reviewed and approved.'}), ('__APP__', 'staticpage_create', {'title': 'Approved', 'url': 'approved', 'content': 'Approved page.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'StaticPage'),AND(F('slug','eq','review'),F('body','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'StaticPage'),AND(F('slug','eq','review'),F('title','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'StaticPage'),AND(F('slug','eq','approved'),F('body','eq','Approved page.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'StaticPage'),AND(F('slug','eq','reference'),F('body','eq','Retain reference page.')))),True))
    return steps,preds
