'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound btcpayserver adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='btcpayserver';NEW_SERVER={APP:'btcpayserver_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['Account', 'StoreUser', 'StoreRole']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password). Complete admission blocked: source reads have no genuine readable policy body; opaque settings/payment blobs are not instructions. store_update(id,storeName,storeWebsite) and store_toggle_archive(id,archived) independently prove metadata writes. Native guards permit any existing Account, including unapproved account, to update arbitrary store.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='btcpayserver';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('invoice_search', {'storeId': 201})]:
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
    records(W,'Store',[{'id': 201, 'Id': 201, 'StoreName': 'Policy', 'StoreWebsite': 'https://policy.invalid', 'Archived': False}, {'id': 202, 'Id': 202, 'StoreName': 'Pending', 'StoreWebsite': 'https://pending.invalid', 'Archived': False}, {'id': 203, 'Id': 203, 'StoreName': 'Reference', 'StoreWebsite': 'https://reference.invalid', 'Archived': False}])
    steps=[('__APP__', 'store_update', {'id': 202, 'storeName': 'Reviewed', 'storeWebsite': 'https://approved.invalid'}), ('__APP__', 'store_toggle_archive', {'id': 202, 'archived': True})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Store'),AND(F('Id','eq',202),F('StoreName','eq','Reviewed')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Store'),AND(F('Id','eq',202),F('StoreWebsite','eq','https://approved.invalid')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Store'),AND(F('Id','eq',202),F('Archived','eq',True)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Store'),AND(F('Id','eq',203),F('StoreName','eq','Reference')))),True))
    return steps,preds

# No policy carrier is declared; retain the existing verified business fixture.
def smoke_seed(W):
    return metadata_smoke_seed(W)
