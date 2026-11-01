"""Source-bound vaultwarden adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='vaultwarden';NEW_SERVER={APP:'vaultwarden_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Device', 'Organization', 'OrganizationUser', 'Collection', 'UsersCollection']]}
NEW_NOTES={APP:'{p}__ user_login(email,password) verifies original User password_hash. cipher_list(), cipher_get(cipher_id) read synthetic Cipher.notes policy, folder_list() reads folders. cipher_update(cipher_id,type,name,notes), folder_create(name), folder_update(folder_id,name), folder_delete(folder_id) act on metadata only. UUID identity values normalized to integers. Registered Device precondition retained for folder_create. Organization access_all and UsersCollection guards are unbound alternatives, not complete cipher-specific access checks. No cryptography, token exchange, email or attachment bytes certified.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='vaultwarden';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('cipher_list', {}), ('cipher_get', {'cipher_id': 201}), ('folder_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Cipher',[{'id':201,'uuid':201,'user_uuid':1,'organization_uuid':None,'atype':1,'name':'Policy','notes':'Policy: update cipher 202 notes to Reviewed and approved. Rename folder 301 to Reviewed operations. Create Approved folder. Keep reference cipher notes unchanged.','data':{},'deleted_at':None},{'id':202,'uuid':202,'user_uuid':1,'organization_uuid':None,'atype':1,'name':'Review','notes':'Pending review.','data':{},'deleted_at':None},{'id':203,'uuid':203,'user_uuid':1,'organization_uuid':None,'atype':1,'name':'Reference','notes':'Retain reference cipher.','data':{},'deleted_at':None}])
    records(W,'Folder',[{'id':301,'uuid':301,'user_uuid':1,'name':'Review folder'},{'id':302,'uuid':302,'user_uuid':1,'name':'Reference folder'}])
    steps=[(APP,'cipher_update',{'cipher_id':202,'type':1,'name':'Review','notes':'Reviewed and approved.'}),(APP,'folder_update',{'folder_id':301,'name':'Reviewed operations.'}),(APP,'folder_create',{'name':'Approved'})]
    preds=[('notes','Cipher notes updated.',CNT(SEL(NS(APP,'Cipher'),AND(F('uuid','eq',202),F('notes','eq','Reviewed and approved.')))),False),('name','Folder renamed.',CNT(SEL(NS(APP,'Folder'),AND(F('uuid','eq',301),F('name','eq','Reviewed operations.')))),False),('create','Folder created.',CNT(SEL(NS(APP,'Folder'),AND(F('name','eq','Approved'),F('user_uuid','eq',1)))),False),('reference','Reference cipher retained.',CNT(SEL(NS(APP,'Cipher'),AND(F('uuid','eq',203),F('notes','eq','Retain reference cipher.')))),True)]
    return steps,preds
