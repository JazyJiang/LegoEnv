"""Source-bound fusionpbx adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='fusionpbx';NEW_SERVER={APP:'fusionpbx_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Users', 'Contacts', 'Domains', 'Groups', 'UserGroups']]}
NEW_NOTES={APP:'{p}__ sign_in(username,password). emailtemplates_list() reads template_body under existing domain session binding. emailtemplates_update(id,template_subject,template_body,template_enabled) and emailtemplates_delete(uuid) edit existing local template metadata. Source create cannot satisfy required domain_uuid through its panel and is not certified. Writes only check Users existence; gaps preserved. No mail or call action executed.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='fusionpbx';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('emailtemplates_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'EmailTemplates',[{'id': 201, 'email_template_uuid': 201, 'domain_uuid': 1, 'template_subject': 'Policy', 'template_body': 'Policy: update template202 body to Reviewed and approved. and subject Reviewed. Enable template202. Keep Reference unchanged.'}, {'id': 202, 'email_template_uuid': 202, 'domain_uuid': 1, 'template_subject': 'Pending', 'template_body': 'Pending review.', 'template_enabled': False}, {'id': 203, 'email_template_uuid': 203, 'domain_uuid': 1, 'template_subject': 'Reference', 'template_body': 'Retain reference template.'}])
    steps=[('__APP__','emailtemplates_update',{'id':202,'template_subject':'Reviewed','template_body':'Reviewed and approved.','template_enabled':True})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'EmailTemplates'),AND(F('email_template_uuid','eq',202),F('template_body','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'EmailTemplates'),AND(F('email_template_uuid','eq',202),F('template_subject','eq','Reviewed')))),False))
    preds.append(('2','Native template enabled flag.',CNT(SEL(NS(APP,'EmailTemplates'),AND(F('email_template_uuid','eq',202),F('template_enabled','eq',True)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'EmailTemplates'),AND(F('email_template_uuid','eq',203),F('template_body','eq','Retain reference template.')))),True))
    return steps,preds
