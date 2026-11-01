"""Source-bound local_deep_research adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='local_deep_research';NEW_SERVER={APP:'research_library_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ uses user_login(username,password). library_get_documents(search) and library_get_document_text(document_id) read Document.text_content policy. note_create(title,content) creates Document plus initial NoteVersion; note_update is not a current-document update and is not certified. rag_create_collection(name,description,type), rag_update_collection(collection_id,description), delete_delete_collection(collection_id) operate metadata; library_toggle_favorite(document_id,favorite), delete_delete_document(document_id) modify records. No real research, indexing/embedding/model calls, download/network, note-version restoration or app benchmark operations are exercised.'}
LOGIN={APP:('user_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='local_deep_research';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('library_get_documents', {}), ('rag_get_collections', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Document',[{'id':201,'title':'Review policy','text_content':'Policy: mark document202 favorite=true; create collection Reviewed operations and note Approved note with Reviewed and approved. body. Keep reference document203 text unchanged.','favorite':False},{'id':202,'title':'Review document','text_content':'Review context.','favorite':False},{'id':203,'title':'Reference document','text_content':'Retain reference document text.','favorite':False}])
    steps=[(APP,'library_toggle_favorite',{'document_id':202,'favorite':True}),(APP,'rag_create_collection',{'name':'Reviewed operations','description':'Reviewed collection','type':'user_collection'}),(APP,'note_create',{'title':'Approved note','content':'Reviewed and approved.'})]
    preds=[('favorite','Document favorite updated.',CNT(SEL(NS(APP,'Document'),AND(F('id','eq',202),F('favorite','eq',True)))),False),('collection','Collection record created.',CNT(SEL(NS(APP,'Collection'),F('name','eq','Reviewed operations'))),False),('note','Note document created.',CNT(SEL(NS(APP,'Document'),AND(F('title','eq','Approved note'),F('text_content','eq','Reviewed and approved.')))),False),('reference','Reference text unchanged.',CNT(SEL(NS(APP,'Document'),AND(F('id','eq',203),F('text_content','eq','Retain reference document text.')))),True)]
    return steps,preds
