"""Source-bound monica adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='monica';NEW_SERVER={APP:'journal_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Account', 'Vault', 'UserVault', 'Contact']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password). list_journals(query,limit) reads Journal.description policy. journal_create(vault_id,name,description), journal_update(vault_id,journal_id,name,description), journal_delete(vault_id,journal_id) act on Journal metadata. Source UserVault permission <=200 grants both existing members editing. list_journals is auth-only and not vault-scoped; update/delete lookup by journal_id does not bind target vault. No email delivery, sync or file bytes certified.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='monica';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('list_journals', {}), ('list_journals', {'query': 'Policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Journal',[{'id':201,'vault_id':1,'name':'Policy','description':'Policy: update Review journal description to Reviewed and approved. and name to Reviewed operations. Create Approved journal. Keep Reference unchanged.'},{'id':202,'vault_id':1,'name':'Review','description':'Pending review.'},{'id':203,'vault_id':1,'name':'Reference','description':'Retain reference journal.'}])
    steps=[(APP,'journal_update',{'vault_id':1,'journal_id':202,'name':'Review','description':'Reviewed and approved.'}),(APP,'journal_update',{'vault_id':1,'journal_id':202,'name':'Reviewed operations.'}),(APP,'journal_create',{'vault_id':1,'name':'Approved','description':'Approved journal.'})]
    preds=[('description','Journal description updated.',CNT(SEL(NS(APP,'Journal'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False),('name','Journal renamed.',CNT(SEL(NS(APP,'Journal'),AND(F('id','eq',202),F('name','eq','Reviewed operations.')))),False),('create','Journal created.',CNT(SEL(NS(APP,'Journal'),AND(F('name','eq','Approved'),F('vault_id','eq',1)))),False),('reference','Reference journal retained.',CNT(SEL(NS(APP,'Journal'),AND(F('id','eq',203),F('description','eq','Retain reference journal.')))),True)]
    return steps,preds
