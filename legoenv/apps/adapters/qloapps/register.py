'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound qloapps adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='qloapps';NEW_SERVER={APP:'qloapps_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Customer', 'Employee', 'Country', 'State', 'Gender', 'Language', 'Shop', 'ShopGroup', 'Currency', 'Zone', 'Group', 'CustomerGroup']]}
NEW_NOTES={APP:'{p}__ customer_login(email,passwd) uses real Customer. Source has no readable narrative body interface: order_downloadinvoice only fetches Order metadata without note/content joins, and no Order is seeded. Independent address_create/alias/city update/soft-delete modify Address rows. No read/body/auth interface invented, no room booking/payment or actual guest operation.'}
LOGIN={APP:('customer_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='qloapps';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);auth=env.call(NS(APP,'customer_login'),{'email':self.persona,'passwd':self.password});assert auth.get('ok');rep[APP+' customer_login authentication-only']=len(json.dumps(auth,ensure_ascii=False,default=str))
    for t,args in []:
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
    records(W,'Address',[{'id': 201, 'id_address': 201, 'id_customer': 1, 'id_country': 1, 'alias': 'Operations', 'firstname': 'Operations', 'lastname': 'Example', 'address1': '1 Test Street', 'city': 'Paris', 'deleted': False}, {'id': 202, 'id_address': 202, 'id_customer': 1, 'id_country': 1, 'alias': 'Pending', 'firstname': 'Operations', 'lastname': 'Example', 'address1': '2 Test Street', 'city': 'Paris', 'deleted': False}, {'id': 203, 'id_address': 203, 'id_customer': 1, 'id_country': 1, 'alias': 'Reference', 'firstname': 'Operations', 'lastname': 'Example', 'address1': '3 Test Street', 'city': 'Paris', 'deleted': False}])
    steps=[('__APP__', 'address_update', {'id_address': 202, 'alias': 'Reviewed', 'city': 'Lyon'}), ('__APP__', 'address_create', {'alias': 'Approved', 'firstname': 'Test', 'lastname': 'Example', 'address1': '1 Test Street', 'city': 'Paris', 'id_country': 1})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Address'),AND(F('id_address','eq',202),F('alias','eq','Reviewed')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Address'),AND(F('id_address','eq',202),F('city','eq','Lyon')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Address'),AND(F('alias','eq','Approved'),F('id_customer','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Address'),AND(F('id_address','eq',203),F('alias','eq','Reference'),F('city','eq','Paris')))),True))
    steps=[lambda e:e.call(NS(APP,'customer_login'),{'email':W.persona,'passwd':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
