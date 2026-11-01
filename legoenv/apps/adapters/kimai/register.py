"""Source-bound kimai adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='kimai';NEW_SERVER={APP:'kimai_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ user_login(username,password). customer_read(id=201) reads comment. customer_create(name,number,country,language,currency) inserts local metadata; customer_update(id,name,comment) edits; customer_delete(id) deletes. Native enabled-user guard lacks role/team binding; source timezone is overwritten with literal date string, not repaired.'}
LOGIN={APP:('user_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='kimai';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('customer_read', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Customer',[{'id': 201, 'name': 'Policy', 'number': 'POL', 'comment': 'Policy: update customer202 comment to Reviewed and approved. and name Reviewed. Create Approved customer. Keep Reference unchanged.', 'country': 'US', 'timezone': 'UTC'}, {'id': 202, 'name': 'Pending', 'number': 'REV', 'comment': 'Pending review.', 'country': 'US', 'timezone': 'UTC'}, {'id': 203, 'name': 'Reference', 'number': 'REF', 'comment': 'Retain reference customer.', 'country': 'US', 'timezone': 'UTC'}])
    steps=[('__APP__', 'customer_update', {'id': 202, 'name': 'Reviewed', 'comment': 'Reviewed and approved.'}), ('__APP__', 'customer_create', {'name': 'Approved', 'number': 'APPROVED', 'country': 'US', 'language': 'en', 'currency': 'EUR'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Customer'),AND(F('id','eq',202),F('comment','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Customer'),AND(F('id','eq',202),F('name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Customer'),AND(F('name','eq','Approved'),F('number','eq','APPROVED')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Customer'),AND(F('id','eq',203),F('comment','eq','Retain reference customer.')))),True))
    return steps,preds
