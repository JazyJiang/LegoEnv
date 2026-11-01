"""Source-bound bitwarden_server adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='bitwarden_server';NEW_SERVER={APP:'vault_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Organization', 'OrganizationUser']]}
NEW_NOTES={APP:'{p}__ signs in with sign_in(username=<email>,password). secret_list(organizationId) and secret_get(id) read synthetic Secret.Note policy; no cryptographic decryption is simulated. folder_create(Name), folder_rename(id,Name), folder_delete(id) operate metadata; no Folder read/list. project_create(organizationId,Name), project_update(id,Name), project_delete(Ids=<one integer>) operate records. secret_create(organizationId,Key,Value,Note) inserts a string record; secret_delete_soft(Ids=<one integer>) and secret_restore_hard(organizationId,Ids) set deletion metadata. Source secret_update only attempts malformed SecretVersion insertion, not current-secret update. No bulk execution, secure storage/crypto, key rotation or full ACL certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='bitwarden_server';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('secret_list', {'organizationId': 1})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Secret',[{'id':301,'Id':301,'OrganizationId':1,'Key':'policy','Value':'synthetic-context','Note':'Policy: create folder Reviewed operations, project Approved project in organization1, and secret Approved key / synthetic-value / Review recorded. Keep reference secret303 Note unchanged.'},{'id':302,'Id':302,'OrganizationId':1,'Key':'review','Value':'synthetic-review','Note':'Review context.'},{'id':303,'Id':303,'OrganizationId':1,'Key':'reference','Value':'synthetic-reference','Note':'Retain this reference note.'}])
    steps=[(APP,'folder_create',{'Name':'Reviewed operations'}),(APP,'project_create',{'organizationId':1,'Name':'Approved project'}),(APP,'secret_create',{'organizationId':1,'Key':'Approved key','Value':'synthetic-value','Note':'Review recorded.'})]
    preds=[('folder','Owned folder metadata created.',CNT(SEL(NS(APP,'Folder'),AND(F('Name','eq','Reviewed operations'),F('UserId','eq',1)))),False),('project','Project metadata created.',CNT(SEL(NS(APP,'Project'),AND(F('Name','eq','Approved project'),F('OrganizationId','eq',1)))),False),('secret','Secret string record created.',CNT(SEL(NS(APP,'Secret'),AND(F('Key','eq','Approved key'),F('Note','eq','Review recorded.')))),False),('reference','Reference note unchanged.',CNT(SEL(NS(APP,'Secret'),AND(F('Id','eq',303),F('Note','eq','Retain this reference note.')))),True)]
    return steps,preds
