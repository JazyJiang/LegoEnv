"""Source-bound tiddlywiki5 adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='tiddlywiki5';NEW_SERVER={APP:'wiki_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Credential']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). tiddler_read(title) reads Tiddler.text policy; tiddler_search() lists records. tiddler_save(title,text,tags,type) inserts or updates native fields and tiddler_delete(title) deletes. Both configured credentials have source auth-only edit rights. Source filter argument is not a full TiddlyWiki expression evaluator; tiddler_render fetches a row and does not render HTML. No filesystem write or real wiki rendering certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='tiddlywiki5';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('tiddler_search', {}), ('tiddler_read', {'title': 'Policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Tiddler',[{'id':201,'title':'Policy','text':'Policy: update Review body to Reviewed and approved. and tags to Approved. Save new Approved tiddler. Keep Reference body unchanged.','tags':['Policy'],'type':'text/vnd.tiddlywiki'},{'id':202,'title':'Review','text':'Pending review.','tags':['Pending'],'type':'text/vnd.tiddlywiki'},{'id':203,'title':'Reference','text':'Retain reference tiddler.','tags':['Reference'],'type':'text/vnd.tiddlywiki'}])
    steps=[(APP,'tiddler_save',{'title':'Review','text':'Reviewed and approved.'}),(APP,'tiddler_save',{'title':'Review','tags':['Approved']}),(APP,'tiddler_save',{'title':'Approved','text':'Approved tiddler.','tags':['Approved']})]
    preds=[('body','Tiddler body updated.',CNT(SEL(NS(APP,'Tiddler'),AND(F('title','eq','Review'),F('text','eq','Reviewed and approved.')))),False),('tags','Tiddler tags updated.',CNT(SEL(NS(APP,'Tiddler'),AND(F('title','eq','Review'),F('tags','eq',{'const':['Approved']})))),False),('create','Tiddler created.',CNT(SEL(NS(APP,'Tiddler'),F('title','eq','Approved'))),False),('reference','Reference body retained.',CNT(SEL(NS(APP,'Tiddler'),AND(F('title','eq','Reference'),F('text','eq','Retain reference tiddler.')))),True)]
    return steps,preds
