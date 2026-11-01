"""Source-bound hemmelig_app adapter; no new tool implementation."""
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='hemmelig_app';NEW_SERVER={APP:'hemmelig_app_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(email,password) original source User credential fixture. secretrequest_get(id=201) reads genuine plaintext request description, separate from encrypted Secrets.secret. secretrequest_create(title,description,expiresIn,validFor,token) inserts local request metadata; secretrequest_cancel(id) changes own pending request status to cancelled. No secret decryption/submission or share-link service executed.'}
LOGIN={APP:('sign_in','email')};SERVER.update(NEW_SERVER);PFX[APP]='hemmelig_app';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'email':self.persona,'password':self.password}).get('ok')
    for t,args in [('secretrequest_get', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    records(W,'SecretRequest',[{'id': 201, 'user_id': 1, 'title': 'Policy', 'description': 'Policy: cancel pending request202. Create Approved request with Approved notes. Keep Reference unchanged.', 'status': 'pending', 'token': 'policy-token'}, {'id': 202, 'user_id': 1, 'title': 'Pending', 'description': 'Pending review.', 'status': 'pending', 'token': 'review-token'}, {'id': 203, 'user_id': 1, 'title': 'Reference', 'description': 'Retain reference request.', 'status': 'pending', 'token': 'reference-token'}])
    steps=[('__APP__', 'secretrequest_cancel', {'id': 202}), ('__APP__', 'secretrequest_create', {'title': 'Approved', 'description': 'Approved notes.', 'expiresIn': 3600, 'validFor': 3600, 'token': 'approved-token'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'SecretRequest'),AND(F('id','eq',202),F('status','eq','cancelled')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'SecretRequest'),AND(F('title','eq','Approved'),F('description','eq','Approved notes.')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'SecretRequest'),AND(F('title','eq','Approved'),F('status','eq','pending'),F('user_id','eq',1)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'SecretRequest'),AND(F('id','eq',203),F('description','eq','Retain reference request.')))),True))
    return steps,preds
