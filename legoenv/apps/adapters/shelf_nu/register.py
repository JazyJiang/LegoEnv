"""Source-bound shelf_nu adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='shelf_nu';NEW_SERVER={APP:'asset_kit_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Organization', 'UserOrganization', 'TeamMember', 'Tier', 'Role']]}
NEW_NOTES={APP:'{p}__ user_login(email,password) uses original User and active organization. kit_read(id) and kit_search() expose Kit.description policy. kit_create(name,description), kit_update(id,name,description), kit_delete(id) operate native kit metadata. Source OR permissions and fetch scope limits remain; no real custody, asset relocation, barcode or checkout effects certified.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='shelf_nu';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('kit_read', {'id': 201}), ('kit_search', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Kit',[{'id':201,'name':'Policy','description':'Policy: update kit 202 description to Reviewed and approved. and name to Reviewed. Create Approved kit. Keep Reference unchanged.','status':'AVAILABLE','organizationId':1,'createdById':1},{'id':202,'name':'Pending','description':'Pending review.','status':'AVAILABLE','organizationId':1,'createdById':1},{'id':203,'name':'Reference','description':'Retain reference kit.','status':'AVAILABLE','organizationId':1,'createdById':1}])
    steps=[(APP,'kit_update',{'id':202,'description':'Reviewed and approved.'}),(APP,'kit_update',{'id':202,'name':'Reviewed'}),(APP,'kit_create',{'name':'Approved','description':'Approved kit.'})]
    preds=[('description','Kit description updated.',CNT(SEL(NS(APP,'Kit'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False),('name','Kit name updated.',CNT(SEL(NS(APP,'Kit'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False),('create','Kit created.',CNT(SEL(NS(APP,'Kit'),AND(F('name','eq','Approved'),F('organizationId','eq',1)))),False),('reference','Reference retained.',CNT(SEL(NS(APP,'Kit'),AND(F('id','eq',203),F('description','eq','Retain reference kit.')))),True)]
    return steps,preds
