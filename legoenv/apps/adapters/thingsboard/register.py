"""ThingsBoard original system-tenant and notification metadata."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='thingsboard';NEW_SERVER={APP:'iot_system_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User','UserCredentials']]}
NEW_NOTES={APP:('{p}__ uses auth_login(email,password). User1 retains source SYS_ADMIN authority. notification_search(pageSize,page,textSearch) reads your notifications; Notification.body carries policy. tenant_search(pageSize,page,textSearch), tenant_read(tenantId) read tenant metadata. tenantprofile_save(name,description), tenant_save(title,tenant_profile_id), tenant_update(id,title) and tenant_delete(tenantId) are system-admin scalar writes. tenantprofile_setdefault(tenantProfileId) sets one flag without clearing others. notification_markasread(id) sets READ and notification_delete(id) removes metadata. No telemetry transport, device provisioning, alarm/notification delivery or general tenant ACL is certified.')}
LOGIN={APP:('auth_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='thingsboard';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'auth_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t in ['tenant_search','notification_search']:
        r=env.call(NS(APP,t),{'pageSize':100,'page':0});assert r.get('ok'),r;rep[APP+' '+t]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'TenantProfile',[{'id':101,'name':'Operations profile','description':'Operations profile','is_default':False}]);records(W,'Tenant',[{'id':201,'title':'Review tenant','tenant_profile_id':101}])
    records(W,'Notification',[{'id':301,'recipient_id':1,'subject':'Review policy','body':'Policy: create Approved tenant using profile101, update tenant201 title to Reviewed tenant, mark notification302 READ. Keep reference notification303 body unchanged.','status':'UNREAD'},{'id':302,'recipient_id':1,'subject':'Review task','body':'Review context.','status':'UNREAD'},{'id':303,'recipient_id':1,'subject':'Reference','body':'Retain this reference notification.','status':'UNREAD'}])
    steps=[(APP,'tenant_save',{'title':'Approved tenant','tenant_profile_id':101}),(APP,'tenant_update',{'id':201,'title':'Reviewed tenant'}),(APP,'notification_markasread',{'id':302})]
    preds=[('create','Approved tenant metadata created.',CNT(SEL(NS(APP,'Tenant'),F('title','eq','Approved tenant'))),False),('update','Existing tenant title updated.',CNT(SEL(NS(APP,'Tenant'),AND(F('id','eq',201),F('title','eq','Reviewed tenant')))),False),('read','Notification marked READ.',CNT(SEL(NS(APP,'Notification'),AND(F('id','eq',302),F('status','eq','READ')))),False),('reference','Reference notification unchanged.',CNT(SEL(NS(APP,'Notification'),AND(F('id','eq',303),F('body','eq','Retain this reference notification.')))),True)]
    return steps,preds
