'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound ollama adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='ollama';NEW_SERVER={APP:'local_model_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Settings', 'ServerConfig']]}
NEW_NOTES={APP:'{p}__ exposes local metadata with NO source authentication. No fake login exists. modelregistry_listmodels/showmodel(model) read manifest metadata; app_listchats/getchat(id) read chat headers without Message join; app_getsettings and app_getcloudsetting read scalar configuration. app_createchat(id,prompt,model) ONLY inserts a user Message, without inference/assistant reply. app_renamechat(id,title), app_updatesettings(context_length,...), app_setcloudenabled(disable_ollama_cloud) change metadata; no real runtime configuration enforcement is certified. modelregistry_copymodel(source,destination,config,layers), modelregistry_createblob(digest,size), modelregistry_deletemodel(model), app_deletechat(id) operate local synthetic rows. Complete admission blocked by missing source auth and no readable Message/policy body interface. No actual model/registry/network calls.'}
LOGIN={};SERVER.update(NEW_SERVER);PFX[APP]='ollama';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES)
# Deliberately no packlib.LOGIN entry: source authentication does not exist.
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world)
    for t,args in [('modelregistry_listmodels', {}), ('app_listchats', {}), ('app_getsettings', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    raise RuntimeError('No source-readable business policy text carrier; do not fabricate a read tool or repurpose metadata as instructions. Complete admission blocked.')
def metadata_smoke_seed(W):
    records(W,'Chat',[{'id':201,'title':'Review context'},{'id':202,'title':'Pending review'},{'id':203,'title':'Reference chat retained'}]);records(W,'ModelManifest',[{'id':301,'name':'review/base','schema_version':2,'config':{'model_family':'synthetic'},'layers':[]}])
    steps=[(APP,'app_renamechat',{'id':202,'title':'Reviewed operations'}),(APP,'app_updatesettings',{'context_length':4096}),(APP,'modelregistry_createblob',{'digest':'sha256:synthetic-review-blob','size':10,'media_type':'application/octet-stream'})]
    preds=[('chat','Chat title metadata updated.',CNT(SEL(NS(APP,'Chat'),AND(F('id','eq',202),F('title','eq','Reviewed operations')))),False),('settings','Settings context length metadata updated.',CNT(SEL(NS(APP,'Settings'),AND(F('id','eq',1),F('context_length','eq',4096)))),False),('blob','Blob metadata created.',CNT(SEL(NS(APP,'Blob'),AND(F('digest','eq','sha256:synthetic-review-blob'),F('size','eq',10)))),False),('reference','Reference chat title unchanged.',CNT(SEL(NS(APP,'Chat'),AND(F('id','eq',203),F('title','eq','Reference chat retained')))),True)]
    return steps,preds

# Explicit capability declaration: no login interface is available.
packlib.LOGIN[APP] = None

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
