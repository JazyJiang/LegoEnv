"""Source-bound alf_io adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='alf_io';NEW_SERVER={APP:'organization_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Authority']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). organization_list() reads Organization.description policy. organization_create(name,description,email,slug) needs source ROLE_ADMIN. organization_update(id,name,email) updates metadata and preserves description when omitted; organization_delete(organizationId) removes metadata. Update/delete only require authentication in source; owner/public roles are not prevented. No payments, check-in, email delivery, extension execution or resource bytes certified.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='alf_io';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('organization_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Organization',[{'id':201,'name':'Policy','description':'Policy: update Review organization name to Reviewed operations. and email to approved@alf.example. Create Approved organization. Keep Reference description unchanged.','email':'policy@alf.example'},{'id':202,'name':'Review','description':'Pending review.','email':'pending@alf.example'},{'id':203,'name':'Reference','description':'Retain reference organization.','email':'reference@alf.example'}])
    steps=[(APP,'organization_update',{'id':202,'name':'Reviewed operations.','email':'pending@alf.example'}),(APP,'organization_update',{'id':202,'name':'Reviewed operations.','email':'approved@alf.example'}),(APP,'organization_create',{'name':'Approved','description':'Approved organization.','email':'new@alf.example'})]
    preds=[('name','Organization renamed.',CNT(SEL(NS(APP,'Organization'),AND(F('id','eq',202),F('name','eq','Reviewed operations.')))),False),('email','Organization email updated.',CNT(SEL(NS(APP,'Organization'),AND(F('id','eq',202),F('email','eq','approved@alf.example')))),False),('create','Organization created.',CNT(SEL(NS(APP,'Organization'),F('name','eq','Approved'))),False),('reference','Reference description retained.',CNT(SEL(NS(APP,'Organization'),AND(F('id','eq',203),F('description','eq','Retain reference organization.')))),True)]
    return steps,preds
