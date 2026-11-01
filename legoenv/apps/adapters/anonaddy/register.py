'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound anonaddy adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='anonaddy';NEW_SERVER={APP:'anonaddy_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['User']]}
NEW_NOTES={APP:'{p}__ sign_in(username=1,password) is genuine numeric account login. Native source explicitly verifies username against User.id; The capability card declares numeric User.id=1 rather than an unsupported handle lookup. alias_show(id) reads description; alias_update(id,description,from_name) and alias_pin(id) are genuine local writes.'}
LOGIN={APP:('sign_in','username')};SERVER.update(NEW_SERVER);PFX[APP]='anonaddy';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'username':1,'password':self.password}).get('ok')
    for t,args in [('alias_show', {'id': 201})]:
        r=env.call(NS(APP,t),args);assert r.get('ok'),r;rep[APP+' '+t+' '+json.dumps(args,sort_keys=True)]=len(json.dumps(r,ensure_ascii=False,default=str))
    return rep,{k:v for k,v in rep.items() if v>OBS_CAP}
World.obs_report=_obs
def records(W,entity,rows,src=None):
    rows=[dict(r) for r in rows];assert all(isinstance(r['id'],int) for r in rows);W.spec[APP]['seed_state'].setdefault(entity,[]).extend(rows)
    if src:W.bindings[NS(APP,entity)]={'dataset':src,'rows':len(rows)}
    return rows
def smoke_seed(W):
    return metadata_smoke_seed(W)
def metadata_smoke_seed(W):
    W.spec[APP]['seed_state']['User'][0]['id']=1
    records(W,'Alias',[{'id': 201, 'user_id': 1, 'email': 'policy@example.invalid', 'local_part': 'policy', 'domain': 'example.invalid', 'active': True, 'pinned': False, 'description': 'Policy: review alias202 description to Reviewed and approved. and from_name Reviewed. Pin alias202. Keep Reference unchanged.'}, {'id': 202, 'user_id': 1, 'email': 'review@example.invalid', 'local_part': 'review', 'domain': 'example.invalid', 'active': True, 'pinned': False, 'description': 'Pending review.', 'from_name': 'Pending'}, {'id': 203, 'user_id': 1, 'email': 'reference@example.invalid', 'local_part': 'reference', 'domain': 'example.invalid', 'active': True, 'pinned': False, 'description': 'Retain reference alias.'}])
    steps=[('__APP__', 'alias_update', {'id': 202, 'description': 'Reviewed and approved.', 'from_name': 'Reviewed'}), ('__APP__', 'alias_pin', {'id': 202})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('id','eq',202),F('from_name','eq','Reviewed')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('id','eq',202),F('pinned','eq',True)))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Alias'),AND(F('id','eq',203),F('description','eq','Retain reference alias.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'username':1,'password':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds

# Parameters are the card-declared native login interface, not a fabricated username.
packlib.LOGIN_ARGUMENTS[APP] = {'username': 1, 'password': '$password'}
