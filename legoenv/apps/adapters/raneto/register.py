"""Source-bound raneto adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='raneto';NEW_SERVER={APP:'wiki_page_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Account', 'Category']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). page_render(slug) reads genuine Page.body; it fetches a row and does not render HTML. page_list() is public. page_edit(file=review.md,content) locates exact filepath, not extensionless slug, and updates Markdown body. page_delete(file) sets deleted_at; source page_list does not hide deleted rows. category_create(category) creates a slug record, not a filesystem directory. page_create lacks filepath binding and is not certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='raneto';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('page_render', {'slug': 'policy'}), ('page_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Page',[{'id':201,'filepath':'policy.md','slug':'policy','title':'Policy','body':'Policy: edit review.md body to Reviewed and approved. and other.md body to Approved other. Create category approved. Keep Reference unchanged.','category':'tutorials'},{'id':202,'filepath':'review.md','slug':'review','title':'Review','body':'Pending review.','category':'tutorials'},{'id':203,'filepath':'reference.md','slug':'reference','title':'Reference','body':'Retain reference page.','category':'tutorials'},{'id':204,'filepath':'other.md','slug':'other','title':'Other','body':'Pending other.','category':'tutorials'}])
    steps=[(APP,'page_edit',{'file':'review.md','content':'Reviewed and approved.'}),(APP,'page_edit',{'file':'other.md','content':'Approved other.'}),(APP,'category_create',{'category':'approved'})]
    preds=[('review','Review body updated.',CNT(SEL(NS(APP,'Page'),AND(F('filepath','eq','review.md'),F('body','eq','Reviewed and approved.')))),False),('other','Other body updated.',CNT(SEL(NS(APP,'Page'),AND(F('filepath','eq','other.md'),F('body','eq','Approved other.')))),False),('create','Category record created.',CNT(SEL(NS(APP,'Category'),F('slug','eq','approved'))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'Page'),AND(F('filepath','eq','reference.md'),F('body','eq','Retain reference page.')))),True)]
    return steps,preds
