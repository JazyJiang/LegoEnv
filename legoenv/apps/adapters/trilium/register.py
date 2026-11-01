"""Source-bound trilium adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='trilium';NEW_SERVER={APP:'note_revision_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Option', 'Note', 'Blob', 'Branch']]}
NEW_NOTES={APP:'{p}__ sign_in(name,password) uses original admin Option credential; instance/locale settings retained. revision_get(revisionId), revision_list(noteId) read Revision.description policy. revision_updatedescription(revisionId,description), revision_delete(revisionId), attribute_create(noteId,type,name,value,isInheritable) act on annotations and attribute records. Internal opaque *Id values normalized to integers. Source login compares any Option name/value, so config values can also authenticate; no user isolation claimed. No rendering, note-body encryption, embeddings or bytes effect certified.'}
LOGIN={APP:('sign_in','name')};SERVER.update(NEW_SERVER);PFX[APP]='trilium';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'name':self.persona,'password':self.password}).get('ok')
    for t,args in [('revision_get', {'revisionId': 201}), ('revision_list', {'noteId': 1})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Revision',[{'id':201,'revisionId':201,'noteId':1,'title':'Policy snapshot','description':'Policy: annotate revision 202 as Reviewed and approved. Add approval label value yes to notes 1 and 2. Keep reference revision unchanged.','source':'user','type':'text','mime':'text/html','isProtected':False,'blobId':1,'utcDateCreated':'2026-01-01T00:00:00Z'},{'id':202,'revisionId':202,'noteId':1,'title':'Review snapshot','description':'Pending review.','source':'user','type':'text','mime':'text/html','isProtected':False,'blobId':1,'utcDateCreated':'2026-01-02T00:00:00Z'},{'id':203,'revisionId':203,'noteId':1,'title':'Reference snapshot','description':'Retain reference revision.','source':'user','type':'text','mime':'text/html','isProtected':False,'blobId':1,'utcDateCreated':'2026-01-03T00:00:00Z'}])
    steps=[(APP,'revision_updatedescription',{'revisionId':202,'description':'Reviewed and approved.'}),(APP,'attribute_create',{'noteId':1,'type':'label','name':'approval','value':'yes','isInheritable':False}),(APP,'attribute_create',{'noteId':2,'type':'label','name':'approval','value':'yes','isInheritable':False})]
    preds=[('description','Revision annotation updated.',CNT(SEL(NS(APP,'Revision'),AND(F('revisionId','eq',202),F('description','eq','Reviewed and approved.')))),False),('first','First note label created.',CNT(SEL(NS(APP,'Attribute'),AND(F('noteId','eq',1),F('name','eq','approval'),F('value','eq','yes')))),False),('second','Second note label created.',CNT(SEL(NS(APP,'Attribute'),AND(F('noteId','eq',2),F('name','eq','approval'),F('value','eq','yes')))),False),('reference','Reference annotation retained.',CNT(SEL(NS(APP,'Revision'),AND(F('revisionId','eq',203),F('description','eq','Retain reference revision.')))),True)]
    return steps,preds
