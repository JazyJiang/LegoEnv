'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound postal adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='postal';NEW_SERVER={APP:'mail_server_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Organization', 'OrganizationUser', 'Server', 'Credential']]}
NEW_NOTES={APP:'{p}__ sign_in(email_address,password). Independent metadata uses message_information(id,api_key) and ippool_create(name,default), ippool_update(id,name,default), ippool_destroy(id). Complete policy-carrier admission blocked: original Message read does not expose RawMessage.data/body; subject and machine delivery diagnostics are not repurposed as instructions. Real credential key is a text string, not numeric id. No mail delivery, DNS, HTTP/SMTP or cryptography effect certified.'}
LOGIN={APP:('sign_in','email_address')};SERVER.update(NEW_SERVER);PFX[APP]='postal';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email_address':self.persona,'password':self.password}).get('ok')
    for t,args in [('message_information', {'id': 201, 'api_key': 'api-key-1'})]:
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
    records(W,'IPPool',packlib.base(APP)['seed_state']['IPPool'])
    records(W,'IPPool',[{'id':101,'name':'Review','default':False},{'id':102,'name':'Reference','default':False},{'id':103,'name':'Other','default':False}])
    records(W,'Message',[{'id':201,'token':'synthetic-message-token','scope':'sent','rcpt_to':'operator@postal.example','mail_from':'ops@postal.example','subject':'Operations metadata','credential_id':2,'status':'Sent','held':False,'size':0,'raw_body_id':1,'raw_headers_id':1}])
    steps=[(APP,'ippool_update',{'id':101,'name':'Reviewed'}),(APP,'ippool_update',{'id':101,'default':True}),(APP,'ippool_create',{'name':'Approved','default':False})]
    preds=[('name','Pool renamed.',CNT(SEL(NS(APP,'IPPool'),AND(F('id','eq',101),F('name','eq','Reviewed')))),False),('default','Pool default flag set.',CNT(SEL(NS(APP,'IPPool'),AND(F('id','eq',101),F('default','eq',True)))),False),('create','Pool record created.',CNT(SEL(NS(APP,'IPPool'),F('name','eq','Approved'))),False),('reference','Reference pool retained.',CNT(SEL(NS(APP,'IPPool'),AND(F('id','eq',102),F('name','eq','Reference')))),True)]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
