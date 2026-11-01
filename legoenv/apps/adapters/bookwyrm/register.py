"""Source-bound bookwyrm adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='bookwyrm';NEW_SERVER={APP:'reading_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Work', 'Author']]}
NEW_NOTES={APP:'{p}__ uses user_login(username,password). book_search(q) reads Book rows including description policy; book_create/title and book_edit(book_id,description) target distinct Edition rows, with no inherited Book join. shelf_create(name,description,privacy), shelf_delete(shelf_id) write own shelf records. status_create(status_type,content,privacy) inserts generic Status only; status_edit(status_id,content), status_delete(status_id) change records. readthrough_create(book,start_date,progress) inserts reading metadata, readthrough_delete(id) removes it. No shelf/status/readthrough read/list, real subtype review/rating/comment creation, federation or comprehensive ownership/trusted-editor ACL certified.'}
LOGIN={APP:('user_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='bookwyrm';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('book_search', {'q': 'Review'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Book',[{'id':201,'title':'Review policy','description':'Policy: update Edition301 description to Reviewed catalog description.; create a status Reviewed and approved.; create shelf Reviewed operations. Keep Book203 description unchanged.'},{'id':202,'title':'Review context','description':'Review context book.'},{'id':203,'title':'Reference book','description':'Retain reference description.'}]);records(W,'Edition',[{'id':301,'title':'Review edition','description':'Pending catalog description.','parent_work_id':1,'last_edited_by_id':1}])
    steps=[(APP,'book_edit',{'book_id':301,'description':'Reviewed catalog description.'}),(APP,'status_create',{'status_type':'comment','content':'Reviewed and approved.','privacy':'public'}),(APP,'shelf_create',{'name':'Reviewed operations','description':'Reviewed shelf','privacy':'public'})]
    preds=[('edition','Edition scalar description updated.',CNT(SEL(NS(APP,'Edition'),AND(F('id','eq',301),F('description','eq','Reviewed catalog description.')))),False),('status','Status text record created.',CNT(SEL(NS(APP,'Status'),AND(F('content','eq','Reviewed and approved.'),F('user_id','eq',1)))),False),('shelf','Owned shelf created.',CNT(SEL(NS(APP,'Shelf'),AND(F('name','eq','Reviewed operations'),F('user_id','eq',1)))),False),('reference','Reference Book description unchanged.',CNT(SEL(NS(APP,'Book'),AND(F('id','eq',203),F('description','eq','Retain reference description.')))),True)]
    return steps,preds
