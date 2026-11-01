"""Source-bound wallos adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='wallos';NEW_SERVER={APP:'wallos_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User', 'Currency', 'Cycle', 'Frequency', 'PaymentMethod', 'Household', 'Category', 'Admin', 'OauthSettings']]}
NEW_NOTES={APP:'{p}__ user_login(username,password). subscription_read(id=201) reads notes. subscription_add(name,price,currency_id,cycle,frequency,notes,...) inserts tracking metadata only; subscription_renew(id,next_payment) sets explicit date subject to own/non-auto/non-one-time guard; subscription_delete(id) deletes metadata. No actual subscription renewal, charge, payment or notification executed.'}
LOGIN={APP:('user_login','username')};SERVER.update(NEW_SERVER);PFX[APP]='wallos';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'user_login'),{'username':self.persona,'password':self.password}).get('ok')
    for t,args in [('subscription_read', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'Subscription',[{'id': 201, 'user_id': 1, 'name': 'Policy', 'notes': 'Policy: set subscription202 next_payment to 2026-12-01T00:00:00. Create Approved subscription with Approved notes. Keep Reference unchanged.', 'auto_renew': 0, 'cycle': 3, 'frequency': 1, 'currency_id': 1, 'next_payment': '2026-11-01T00:00:00'}, {'id': 202, 'user_id': 1, 'name': 'Pending', 'notes': 'Pending review.', 'auto_renew': 0, 'cycle': 3, 'frequency': 1, 'currency_id': 1, 'next_payment': '2026-11-01T00:00:00'}, {'id': 203, 'user_id': 1, 'name': 'Reference', 'notes': 'Retain reference subscription.', 'auto_renew': 0, 'cycle': 3, 'frequency': 1, 'currency_id': 1, 'next_payment': '2026-11-01T00:00:00'}])
    steps=[('__APP__', 'subscription_renew', {'id': 202, 'next_payment': '2026-12-01T00:00:00'}), ('__APP__', 'subscription_add', {'name': 'Approved', 'notes': 'Approved notes.', 'price': 1.0, 'currency_id': 1, 'cycle': 3, 'frequency': 1, 'payment_method_id': 32, 'payer_user_id': 1, 'category_id': 1, 'auto_renew': False, 'next_payment': '2026-11-01T00:00:00'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Subscription'),AND(F('id','eq',202),F('next_payment','eq','2026-12-01T00:00:00')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Subscription'),AND(F('name','eq','Approved'),F('notes','eq','Approved notes.')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Subscription'),AND(F('name','eq','Approved'),F('user_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Subscription'),AND(F('id','eq',203),F('notes','eq','Retain reference subscription.')))),True))
    return steps,preds
