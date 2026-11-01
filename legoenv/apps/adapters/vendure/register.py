"""Source-bound vendure adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='vendure';NEW_SERVER={APP:'vendure_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['NativeAuthenticationMethod', 'User', 'Administrator', 'Role']]}
NEW_NOTES={APP:'{p}__ auth_login(username,password). stocklocation_findone(id=201) reads description. stocklocation_create(input={{}},name,description,customFields={{}}), stocklocation_update(input={{}},id,name,description), stocklocation_delete(id) edit local metadata. Required input wrapper remains; native stock tools do not enforce admin Role despite prose.'}
LOGIN={APP:('auth_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='vendure';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'auth_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('stocklocation_findone', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'StockLocation',[{'id': 201, 'name': 'Policy', 'description': 'Policy: update warehouse202 description to Reviewed and approved. and name Reviewed. Create Approved warehouse. Keep Reference unchanged.', 'customFields': {}}, {'id': 202, 'name': 'Pending', 'description': 'Pending review.', 'customFields': {}}, {'id': 203, 'name': 'Reference', 'description': 'Retain reference warehouse.', 'customFields': {}}])
    steps=[('__APP__', 'stocklocation_update', {'input': {}, 'id': 202, 'name': 'Reviewed', 'description': 'Reviewed and approved.'}), ('__APP__', 'stocklocation_create', {'input': {}, 'name': 'Approved', 'description': 'Approved warehouse.', 'customFields': {}})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'StockLocation'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'StockLocation'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'StockLocation'),AND(F('name','eq','Approved'),F('description','eq','Approved warehouse.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'StockLocation'),AND(F('id','eq',203),F('description','eq','Retain reference warehouse.')))),True))
    return steps,preds
