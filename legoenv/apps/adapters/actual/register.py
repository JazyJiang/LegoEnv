'Current admission note (2026-10-24): explicit optional login/carrier declarations are supported; old blocking notes are historical. Functional source limits below remain current.\n\nSource-bound actual adapter; no new tool implementation.'
import json
import runtime,packlib
from packlib import World,NS,SERVER,PFX,CONTENT,NOTES,OBS_CAP,SEL,F,AND,CNT
APP='actual';NEW_SERVER={APP:'actual_records'};NEW_CONTENT={APP:[e['name'] for e in packlib.base(APP)['entities'] if e['name'] not in ['AuthMethod']]}
NEW_NOTES={APP:'{p}__ sign_in(method=password,extra_data=<server secret>) is genuine server-level authentication, not employee login. The capability card declares the fixed server selector and real extra_data password field. tag_read_all() reads Tag.description policy; tag_create/tag_update/tag_delete edit metadata and tombstone flag publicly. No budget sync/financial execution or fake persona authentication.'}
LOGIN={APP:('sign_in','method')};SERVER.update(NEW_SERVER);PFX[APP]='actual';CONTENT.update(NEW_CONTENT);NOTES.update(NEW_NOTES);packlib.LOGIN.update(LOGIN)
_old=World.obs_report
def _obs(self):
    rep,bad=_old(self)
    if APP not in self.apps:return rep,bad
    env=runtime.Env(self.world);assert env.call(NS(APP,'sign_in'),{'method':'password','extra_data':self.password}).get('ok')
    for t,args in [('tag_read_all', {})]:
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
    W.spec[APP]['seed_state']['AuthMethod'][0]['method']='password'
    records(W,'Tag',[{'id': 201, 'tag': 'policy', 'description': 'Policy: update tag202 description to Reviewed and approved. and color blue. Create approved tag. Keep Reference unchanged.', 'color': 'gray', 'hidden': False, 'tombstone': False}, {'id': 202, 'tag': 'review', 'description': 'Pending review.', 'color': 'gray', 'hidden': False, 'tombstone': False}, {'id': 203, 'tag': 'reference', 'description': 'Retain reference tag.', 'color': 'gray', 'hidden': False, 'tombstone': False}])
    steps=[('__APP__', 'tag_update', {'id': 202, 'description': 'Reviewed and approved.'}), ('__APP__', 'tag_update', {'id': 202, 'color': 'blue'}), ('__APP__', 'tag_create', {'tag': 'approved', 'description': 'Approved tag.'})]
    steps=[(APP,t,a) for app,t,a in steps]
    preds=[]
    preds.append(('0','Native state predicate.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',202),F('description','eq','Reviewed and approved.')))),False))
    preds.append(('1','Native state predicate.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',202),F('color','eq','blue')))),False))
    preds.append(('2','Native state predicate.',CNT(SEL(NS(APP,'Tag'),AND(F('tag','eq','approved'),F('description','eq','Approved tag.')))),False))
    preds.append(('3','Native state predicate.',CNT(SEL(NS(APP,'Tag'),AND(F('id','eq',203),F('description','eq','Retain reference tag.')))),True))
    steps=[lambda e:e.call(NS(APP,'sign_in'),{'method':'password','extra_data':W.password})]+[(lambda e,t=t,a=a:e.call(NS(APP,t),a)) for _,t,a in steps]
    return steps,preds

# Parameters are the card-declared native login interface, not a fabricated username.
packlib.LOGIN_ARGUMENTS[APP] = {'method': 'password', 'extra_data': '$password'}
