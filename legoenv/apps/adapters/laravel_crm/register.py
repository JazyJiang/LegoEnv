"""Source-bound laravel_crm adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='laravel_crm';NEW_SERVER={APP:'laravel_crm_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Role', 'Group', 'UserGroup']]}
NEW_NOTES={APP:'{p}__ auth_login(email,password). warehouse_view(id=201) reads description. warehouse_create requires name plus contact_name/contact_emails/contact_numbers/contact_address. warehouse_update(id,name,description) edits metadata; warehouse_destroy(id) deletes. Native User-existence guard permits custom Sales role global writes.'}
LOGIN={APP:('auth_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='laravel_crm';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'auth_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('warehouse_view', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Warehouse',[{'id': 201, 'name': 'Policy', 'description': 'Policy: update warehouse202 description to Reviewed and approved. and name Reviewed. Create Approved warehouse. Keep Reference unchanged.'}, {'id': 202, 'name': 'Pending', 'description': 'Pending review.'}, {'id': 203, 'name': 'Reference', 'description': 'Retain reference warehouse.'}])
    steps=[('__APP__', 'warehouse_update', {'id': 202, 'description': 'Reviewed and approved.', 'name': 'Reviewed'}), ('__APP__', 'warehouse_create', {'name': 'Approved', 'description': 'Approved warehouse.', 'contact_name': 'Operator', 'contact_emails': [], 'contact_numbers': [], 'contact_address': {}})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Warehouse'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Warehouse'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Warehouse'),AND(F('name','eq','Approved'),F('description','eq','Approved warehouse.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Warehouse'),AND(F('id','eq',203),F('description','eq','Retain reference warehouse.')))),True))
    return steps,preds
