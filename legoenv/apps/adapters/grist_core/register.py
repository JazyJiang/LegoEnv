"""Source-bound grist_core adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='grist_core';NEW_SERVER={APP:'grist_core_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) uses original login-type User. serviceaccount_get(said) or serviceaccount_list() reads genuine ServiceAccount.description policy. serviceaccount_create(label,description,expiresAt), serviceaccount_update(said,label,description), serviceaccount_delete(said) edit local metadata with actual owner guards. Create uses caller as serviceUserId; no distinct service credential or API execution exists. Direct fetch is public because source ignores owner scope.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='grist_core';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('serviceaccount_get', {'said': 201}), ('serviceaccount_list', {})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'ServiceAccount',[{'id': 201, 'ownerId': 1, 'serviceUserId': 1, 'label': 'Policy', 'description': 'Policy: update service account202 description to Reviewed and approved. and label Reviewed. Create Approved account expiring 2027-01-01. Keep Reference unchanged.', 'expiresAt': '2027-01-01T00:00:00'}, {'id': 202, 'ownerId': 1, 'serviceUserId': 1, 'label': 'Pending', 'description': 'Pending review.', 'expiresAt': '2027-01-01T00:00:00'}, {'id': 203, 'ownerId': 1, 'serviceUserId': 1, 'label': 'Reference', 'description': 'Retain reference service account.', 'expiresAt': '2027-01-01T00:00:00'}])
    steps=[('__APP__', 'serviceaccount_update', {'said': 202, 'description': 'Reviewed and approved.'}), ('__APP__', 'serviceaccount_update', {'said': 202, 'label': 'Reviewed'}), ('__APP__', 'serviceaccount_create', {'label': 'Approved', 'description': 'Approved account.', 'expiresAt': '2027-01-01T00:00:00'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'ServiceAccount'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'ServiceAccount'),AND(F('id','eq',202),F('label','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'ServiceAccount'),AND(F('label','eq','Approved'),F('ownerId','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'ServiceAccount'),AND(F('id','eq',203),F('description','eq','Retain reference service account.')))),True))
    return steps,preds
