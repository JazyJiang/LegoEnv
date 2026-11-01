"""Source-bound mautic adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='mautic';NEW_SERVER={APP:'marketing_metadata'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Role', 'Permission']]}
NEW_NOTES={APP:'{p}__ uses user_login(username,password). report_execute(id) reads Report definition metadata including description policy; it does not run analytics. lead_edit(objectId,firstname,email,phone), company_create(companyname,...), company_edit(objectId,companyname), leadnote_create(leadId,text,type), lead_delete(objectId), report_create(name,source,columns,filters) operate scalar records. Original Role/Permission rows remain and permission checks are global, not fully tied to actor role. No actual campaign execution, send_email, SMS, push delivery, dynamic contact fields, report aggregation or comprehensive authorization certified.'}
LOGIN={APP:('user_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='mautic';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('report_execute', {'id': 101}), ('report_execute', {'id': 103})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Report',[{'id':101,'name':'Review policy','source':'leads','description':'Policy: set lead201 firstname Reviewed, company301 companyname Approved company, and append note Reviewed and approved. to lead201. Keep report103 description unchanged.'},{'id':102,'name':'Review context','source':'leads','description':'Review context.'},{'id':103,'name':'Reference report','source':'leads','description':'Retain reference report description.'}]);records(W,'Lead',[{'id':201,'firstname':'Pending','email':'synthetic@example.invalid','created_by':1}]);records(W,'Company',[{'id':301,'companyname':'Pending company','created_by':1}])
    steps=[(APP,'lead_edit',{'objectId':201,'firstname':'Reviewed'}),(APP,'company_edit',{'objectId':301,'companyname':'Approved company'}),(APP,'leadnote_create',{'leadId':201,'text':'Reviewed and approved.','type':'general'})]
    preds=[('lead','Lead scalar updated.',CNT(SEL(NS(APP,'Lead'),AND(F('id','eq',201),F('firstname','eq','Reviewed')))),False),('company','Company scalar updated.',CNT(SEL(NS(APP,'Company'),AND(F('id','eq',301),F('companyname','eq','Approved company')))),False),('note','Lead note persisted.',CNT(SEL(NS(APP,'LeadNote'),AND(F('lead_id','eq',201),F('text','eq','Reviewed and approved.')))),False),('reference','Reference report unchanged.',CNT(SEL(NS(APP,'Report'),AND(F('id','eq',103),F('description','eq','Retain reference report description.')))),True)]
    return steps,preds
