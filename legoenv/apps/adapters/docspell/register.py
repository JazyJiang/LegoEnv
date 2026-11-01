"""Source-bound docspell adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='docspell';NEW_SERVER={APP:'document_coordination'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Collective']]}
NEW_NOTES={APP:'{p}__ signs in with sign_in(login,password). item_search(q) and item_get(id) read collective-scoped Item.notes policy. item_setnotes(id,notes), item_setname(id,name), item_setduedate(id,date) write document scalars. item_setstates(id,state) transitions from created/confirmed; item_setdeletedstate(id) trashes; item_restore(id) restores deleted to created. tag_create(name,category), tag_update(id,name), tag_delete(id), folder_create(name), folder_changename(id,name), folder_delete(id) operate metadata. Folder rename checks owner. No binary upload, OCR/extracted text pipeline, job execution, SMTP/IMAP delivery, or complete folder authorization certified.'}
LOGIN={APP:('sign_in','login')};SERVER.update(NEW_SERVER);PFX[APP]='docspell';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'login':self.persona,'password':self.password}).get('ok')
    for t,args in [('item_search', {'q': 'document'}), ('item_search', {'q': 'Retain'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Item',[{'id':201,'itemid':201,'coll_id':1,'name':'Policy document','state':'confirmed','notes':'Policy: set document202 notes Reviewed and approved.; confirm document202; create tag Reviewed operations. Keep reference document203 notes unchanged.'},{'id':202,'itemid':202,'coll_id':1,'name':'Review document','state':'created','notes':'Pending review.'},{'id':203,'itemid':203,'coll_id':1,'name':'Reference document','state':'confirmed','notes':'Retain reference notes.'}])
    steps=[(APP,'item_setnotes',{'id':202,'notes':'Reviewed and approved.'}),(APP,'item_setstates',{'id':202,'state':'confirmed'}),(APP,'tag_create',{'name':'Reviewed operations','category':'review'})]
    preds=[('notes','Document notes updated.',CNT(SEL(NS(APP,'Item'),AND(F('itemid','eq',202),F('notes','eq','Reviewed and approved.')))),False),('state','Document confirmed.',CNT(SEL(NS(APP,'Item'),AND(F('itemid','eq',202),F('state','eq','confirmed')))),False),('tag','Collective tag created.',CNT(SEL(NS(APP,'Tag'),AND(F('name','eq','Reviewed operations'),F('coll_id','eq',1)))),False),('reference','Reference notes unchanged.',CNT(SEL(NS(APP,'Item'),AND(F('itemid','eq',203),F('notes','eq','Retain reference notes.')))),True)]
    return steps,preds
