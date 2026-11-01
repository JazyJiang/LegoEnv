'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound snappymail adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='snappymail';NEW_SERVER={APP:'webmail_script_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['RainloopUser', 'RainloopSystem', 'DomainConfig', 'SystemConfig']]}
NEW_NOTES={APP:'{p}__ sign_in(rl_email,password) verifies original pw column. actions_docontacts() reads account-owned contact display metadata. Complete policy-carrier admission blocked: SieveScript.body exists but no native Sieve/email body read tool; contact names and config are not repurposed. Independent actions_dofiltersscriptsave(name,body), actions_dofiltersscriptactivate(name), actions_dofiltersscriptdelete(name) store script records/active flags only. Email ownership uses explicit account_email binding. No IMAP/SMTP/mail delivery/real Sieve execution/crypto effects certified.'}
LOGIN={APP:('sign_in','rl_email')};SERVER.update(NEW_SERVER);PFX[APP]='snappymail';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'rl_email':self.persona,'password':self.password}).get('ok')
    for t,args in [('actions_docontacts', {})]:
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
    records(W,'AbContact',[{'id':201,'id_contact':201,'id_user':W.persona,'display':'Alice','changed':0,'deleted':0},{'id':202,'id_contact':202,'id_user':W.persona,'display':'Bob','changed':0,'deleted':0},{'id':203,'id_contact':203,'id_user':W.persona,'display':'Reference','changed':0,'deleted':0}])
    records(W,'SieveScript',[{'id':301,'account':W.persona,'name':'review','body':'keep;','active':False},{'id':302,'account':W.persona,'name':'reference','body':'# reference\nkeep;','active':False}])
    steps=[(APP,'actions_dofiltersscriptsave',{'name':'review','body':'# reviewed\nkeep;'}),(APP,'actions_dofiltersscriptactivate',{'name':'review'}),(APP,'actions_dofiltersscriptsave',{'name':'approved','body':'keep;'})]
    preds=[('body','Stored script body updated.',CNT(SEL(NS(APP,'SieveScript'),AND(F('account','eq',W.persona),F('name','eq','review'),F('body','eq','# reviewed\nkeep;')))),False),('active','Script active flag set.',CNT(SEL(NS(APP,'SieveScript'),AND(F('account','eq',W.persona),F('name','eq','review'),F('active','eq',True)))),False),('create','Script record created.',CNT(SEL(NS(APP,'SieveScript'),AND(F('account','eq',W.persona),F('name','eq','approved')))),False),('reference','Reference script retained.',CNT(SEL(NS(APP,'SieveScript'),AND(F('account','eq',W.persona),F('name','eq','reference'),F('body','eq','# reference\nkeep;')))),True)]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
