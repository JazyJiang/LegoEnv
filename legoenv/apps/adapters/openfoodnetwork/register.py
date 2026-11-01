"""Source-bound openfoodnetwork adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='openfoodnetwork';NEW_SERVER={APP:'openfoodnetwork_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ user_login(email,password) authenticates confirmed real User. enterprise_check_permalink(permalink) reads Enterprise.description policy through original full-row availability fetch. enterprise_create(name,permalink,description), enterprise_update(id,name,description), enterprise_delete(id) edit scalar rows with original owner/admin checks. No ordering/payment/stock/delivery effects.'}
LOGIN={APP:('user_login','email')};SERVER.update(NEW_SERVER);PFX[APP]='openfoodnetwork';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('enterprise_check_permalink', {'permalink': 'policy'})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Enterprise',[{'id': 201, 'name': 'Policy', 'permalink': 'policy', 'description': 'Policy: update Enterprise202 description to Reviewed and approved. and name to Reviewed. Create Approved enterprise. Keep Reference unchanged.', 'owner_id': 1, 'sells': 'none', 'visible': 'only_through_links'}, {'id': 202, 'name': 'Pending', 'permalink': 'review', 'description': 'Pending review.', 'owner_id': 1, 'sells': 'none', 'visible': 'only_through_links'}, {'id': 203, 'name': 'Reference', 'permalink': 'reference', 'description': 'Retain reference enterprise.', 'owner_id': 1, 'sells': 'none', 'visible': 'only_through_links'}])
    steps=[('__APP__', 'enterprise_update', {'id': 202, 'description': 'Reviewed and approved.'}), ('__APP__', 'enterprise_update', {'id': 202, 'name': 'Reviewed'}), ('__APP__', 'enterprise_create', {'name': 'Approved', 'permalink': 'approved', 'description': 'Approved enterprise.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Enterprise'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Enterprise'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Enterprise'),AND(F('name','eq','Approved'),F('owner_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Enterprise'),AND(F('id','eq',203),F('description','eq','Retain reference enterprise.')))),True))
    return steps,preds
